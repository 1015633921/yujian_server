<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import MaterialOptionChecks from '@/components/materials/MaterialOptionChecks.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import {
  getMaterialSeries,
  listMaterialOptions,
  updateMaterialSeries,
  type MaterialOption,
  type MaterialOptionsPayload,
  type MaterialSeries,
  type MaterialSeriesInput,
} from '@/features/materials/api'
import { useAuthStore } from '@/stores/auth'

interface SeriesDraft {
  name: string
  materialCode: string
  color: string
  shine: string
  sortOrder: number
  enabled: boolean
  imageUrl: string
  imageUrls: string[]
  primaryElement: string
  secondaryElements: string[]
  chakras: string[]
  effects: string[]
  wishPools: string[]
  colorFamily: string
  moodTags: string[]
  visualTags: string[]
  story: string
  allowedRoles: string[]
  matchRules: string[]
  careTags: string[]
  beadShape: string
  placementMode: string
  visualAxis: string
  surfaceFinish: string
  transparencyLevel: string
  textureFeatures: string[]
  batchVariation: string
}

type MaterialOptionKey = Exclude<keyof MaterialOptionsPayload, 'option_items'>
type DisplayOption = MaterialOption & { unavailable?: boolean }

const route = useRoute()
const auth = useAuthStore()
const profile = ref<MaterialSeries | null>(null)
const draft = ref<SeriesDraft | null>(null)
const materialOptions = ref<MaterialOptionsPayload | null>(null)
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const notice = ref('')
let controller: AbortController | null = null

const seriesId = computed(() => String(route.params.seriesId || '').trim())
const canManage = computed(() => auth.admin?.role !== 'viewer')

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? [...new Set(value.map(String).map(item => item.trim()).filter(Boolean))] : []
}

function optionsFor(optionType: MaterialOptionKey, selected: string[] = []): DisplayOption[] {
  const active = materialOptions.value?.[optionType]
  const base = Array.isArray(active) ? active : []
  const activeKeys = new Set(base.map(item => item.key))
  const itemLabels = new Map(
    (materialOptions.value?.option_items || [])
      .filter(item => item.option_type === optionType)
      .map(item => [item.key, item.label]),
  )
  const historical = selected
    .filter(key => key && !activeKeys.has(key))
    .map(key => ({ key, label: itemLabels.get(key) || `历史值：${key}`, unavailable: true }))
  return [...base, ...historical]
}

function unavailableValues(optionType: MaterialOptionKey, selected: string[]): string[] {
  const activeKeys = new Set(optionsFor(optionType).map(item => item.key))
  return selected.filter(value => value && !activeKeys.has(value))
}

function secondaryElementOptions(selected: string[], primary: string): DisplayOption[] {
  return optionsFor('elements', selected).filter(option => option.key !== primary)
}

function makeDraft(item: MaterialSeries): SeriesDraft {
  const energy = item.energy || {}
  const rules = item.rules || {}
  const params = item.material_params || {}
  return {
    name: item.name || '',
    materialCode: item.material_code || '',
    color: item.color || '#dfe3e5',
    shine: item.shine || '#ffffff',
    sortOrder: Number(item.sort_order || 0),
    enabled: item.enabled,
    imageUrl: item.image_url || '',
    imageUrls: [...(item.image_urls || [])],
    primaryElement: String(energy.primary_element || ''),
    secondaryElements: stringList(energy.secondary_elements),
    chakras: stringList(energy.chakras),
    effects: stringList(energy.effects),
    wishPools: stringList(energy.wish_pools),
    colorFamily: energy.color_family || '',
    moodTags: stringList(energy.mood_tags),
    visualTags: stringList(energy.visual_tags),
    story: energy.story || '',
    allowedRoles: stringList(rules.allowed_roles),
    matchRules: stringList(rules.match_rules),
    careTags: stringList(rules.care_tags),
    beadShape: String(params.bead_shape || 'round'),
    placementMode: String(params.placement_mode || 'threaded'),
    visualAxis: String(params.visual_axis || 'radial'),
    surfaceFinish: String(params.surface_finish || ''),
    transparencyLevel: String(params.transparency_level || ''),
    textureFeatures: stringList(params.texture_features),
    batchVariation: String(params.batch_variation || ''),
  }
}

async function load(): Promise<void> {
  if (!seriesId.value) {
    error.value = '未找到需要编辑的品种。'
    loading.value = false
    return
  }
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  notice.value = ''
  try {
    const [item, nextOptions] = await Promise.all([
      getMaterialSeries(seriesId.value, controller.signal),
      listMaterialOptions(controller.signal),
    ])
    profile.value = item
    materialOptions.value = nextOptions
    draft.value = makeDraft(item)
  } catch (cause) {
    if (!(cause instanceof DOMException && cause.name === 'AbortError')) {
      error.value = cause instanceof Error ? cause.message : '品种资料读取失败'
    }
  } finally {
    loading.value = false
  }
}

function useAsPrimary(url: string): void {
  if (!draft.value || saving.value || !canManage.value) return
  const previous = draft.value.imageUrl
  draft.value.imageUrl = url
  draft.value.imageUrls = draft.value.imageUrls.filter((item) => item !== url)
  if (previous && previous !== url) draft.value.imageUrls = [previous, ...draft.value.imageUrls]
}

function moveGallery(index: number, direction: -1 | 1): void {
  if (!draft.value || saving.value) return
  const target = index + direction
  if (target < 0 || target >= draft.value.imageUrls.length) return
  const next = [...draft.value.imageUrls]
  const current = next[index]
  const swapped = next[target]
  if (typeof current !== 'string' || typeof swapped !== 'string') return
  next[index] = swapped
  next[target] = current
  draft.value.imageUrls = next
}

function removeGallery(index: number): void {
  if (!draft.value || saving.value || !canManage.value) return
  draft.value.imageUrls = draft.value.imageUrls.filter((_, current) => current !== index)
}

function clearPrimary(): void {
  if (!draft.value || saving.value || !canManage.value || !draft.value.imageUrl) return
  draft.value.imageUrls = [draft.value.imageUrl, ...draft.value.imageUrls]
  draft.value.imageUrl = ''
}

async function save(): Promise<void> {
  if (!profile.value || !draft.value || saving.value || !canManage.value) return
  const current = draft.value
  const name = current.name.trim()
  if (!name) {
    notice.value = '请先填写品种名称。'
    return
  }
  const optionFields: Array<[MaterialOptionKey, string, string[]]> = [
    ['elements', '主五行', [current.primaryElement]],
    ['elements', '副五行', current.secondaryElements],
    ['chakras', '脉轮', current.chakras],
    ['effects', '核心功效', current.effects],
    ['wish_pools', '愿望池', current.wishPools],
    ['color_families', '色系', [current.colorFamily]],
    ['mood_tags', '情绪标签', current.moodTags],
    ['visual_tags', '视觉标签', current.visualTags],
    ['roles', '适配角色', current.allowedRoles],
    ['match_rules', '搭配规则', current.matchRules],
    ['care_tags', '养护标签', current.careTags],
    ['bead_shapes', '珠子形制', [current.beadShape]],
    ['placement_modes', '安装方式', [current.placementMode]],
    ['visual_axes', '视觉轴向', [current.visualAxis]],
    ['surface_finishes', '表面工艺', [current.surfaceFinish]],
    ['transparency_levels', '通透度', [current.transparencyLevel]],
    ['texture_features', '纹理特征', current.textureFeatures],
    ['batch_variation_levels', '批次差异', [current.batchVariation]],
  ]
  const invalid = optionFields
    .map(([type, label, values]) => ({ label, values: unavailableValues(type, values) }))
    .find(item => item.values.length)
  if (invalid) {
    notice.value = `${invalid.label}包含已停用或未维护的历史值，请取消或替换后再保存。`
    return
  }
  saving.value = true
  notice.value = ''
  const previousParams = profile.value.material_params || {}
  const materialParams = {
    ...previousParams,
    bead_shape: current.beadShape,
    placement_mode: current.placementMode,
    visual_axis: current.visualAxis,
    surface_finish: current.surfaceFinish,
    transparency_level: current.transparencyLevel,
    texture_features: current.textureFeatures,
    batch_variation: current.batchVariation,
  }
  const payload: MaterialSeriesInput = {
    category_id: profile.value.parent_id,
    name,
    material_code: current.materialCode.trim(),
    color: current.color,
    shine: current.shine,
    image_url: current.imageUrl,
    image_urls: current.imageUrls,
    primary_element: current.primaryElement,
    secondary_elements: current.secondaryElements,
    chakras: current.chakras,
    chakra_weights: profile.value.energy?.chakra_weights || {},
    effects: current.effects,
    wish_pools: current.wishPools,
    color_family: current.colorFamily,
    mood_tags: current.moodTags,
    visual_tags: current.visualTags,
    story: current.story.trim(),
    allowed_roles: current.allowedRoles,
    match_rules: current.matchRules,
    care_tags: current.careTags,
    material_params: materialParams,
    asset: profile.value.asset || {},
    sort_order: Number(current.sortOrder) || 0,
    enabled: current.enabled,
  }
  try {
    await updateMaterialSeries(profile.value.id, payload)
    await load()
    notice.value = '品种完整资料已保存并重新读取。'
  } catch (cause) {
    notice.value = cause instanceof Error ? cause.message : '品种资料保存失败，请稍后重试。'
  } finally {
    saving.value = false
  }
}

watch(seriesId, () => void load(), { immediate: true })
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <section class="workspace-page material-profile-page">
    <RouterLink
      class="detail-back"
      :to="{ name: 'material-directory', query: profile?.top ? { top: profile.top } : {} }"
    >
      ← 返回目录设置
    </RouterLink>

    <PageErrorState
      v-if="error && !loading"
      eyebrow="PROFILE UNAVAILABLE"
      title="品种资料暂时无法读取"
      :message="error"
      @retry="load"
    />
    <div
      v-else-if="loading"
      class="material-profile-skeleton"
      aria-label="正在加载品种资料"
    >
      <i /><i /><i />
    </div>
    <template v-else-if="profile && draft">
      <PageHeading
        eyebrow="MATERIAL PROFILE"
        :title="draft.name || '品种资料'"
        description="品种资料会同步给全部 SKU，并影响工作台展示、推荐和养护说明。"
      >
        <template #actions>
          <RouterLink
            class="heading-link"
            :to="{ name: 'material-assets', query: { top: profile.top, series_id: profile.id } }"
          >
            处理新素材 ↗
          </RouterLink>
          <button
            class="primary-action"
            :disabled="!canManage || saving"
            @click="save"
          >
            {{ saving ? '正在保存…' : '保存完整资料' }}
          </button>
        </template>
      </PageHeading>

      <p
        v-if="!canManage"
        class="material-profile-notice"
      >
        当前账号为只读账号，可以查看资料但不能修改。
      </p>
      <p
        v-if="notice"
        class="material-profile-notice"
        :class="{ 'is-error': notice.includes('失败') || notice.includes('请先') }"
      >
        {{ notice }}
      </p>

      <form
        class="material-profile"
        @submit.prevent="save"
      >
        <section class="material-profile__overview">
          <header><span>01 / 基础资料</span><h2>品种识别</h2><p>面向运营显示名称；材料编码仅在技术信息中保留。</p></header>
          <div class="material-profile__fields">
            <label><span>品种名称</span><input
              v-model="draft.name"
              :disabled="!canManage || saving"
              maxlength="160"
            ></label>
            <label><span>所属分类</span><output>{{ profile.category_name || '未分类' }}</output></label>
            <label><span>基础色</span><input
              v-model="draft.color"
              :disabled="!canManage || saving"
              type="color"
            ></label>
            <label><span>高光色</span><input
              v-model="draft.shine"
              :disabled="!canManage || saving"
              type="color"
            ></label>
            <label><span>排序值</span><input
              v-model.number="draft.sortOrder"
              :disabled="!canManage || saving"
              type="number"
              min="0"
              max="99999"
            ></label>
            <label class="material-profile__switch"><input
              v-model="draft.enabled"
              :disabled="!canManage || saving"
              type="checkbox"
            ><span>此品种可用</span></label>
          </div>
        </section>

        <section class="material-profile__visual">
          <header><span>02 / 图片资料</span><h2>主图与共享图库</h2><p>新图片先在素材处理中标准化上传；这里选择主图、排序或移除已有图库。</p></header>
          <div class="material-profile__images">
            <div class="material-primary-image">
              <img
                v-if="draft.imageUrl"
                :src="draft.imageUrl"
                :alt="`${draft.name} 主图`"
              >
              <span v-else>暂未设置主图</span>
              <div>
                <strong>主图</strong><button
                  type="button"
                  :disabled="!canManage || saving || !draft.imageUrl"
                  @click="clearPrimary"
                >
                  移回图库
                </button>
              </div>
            </div>
            <div class="material-gallery">
              <p v-if="!draft.imageUrls.length">
                暂无图库图片。请先前往“处理新素材”上传并绑定到本品种。
              </p>
              <article
                v-for="(url, index) in draft.imageUrls"
                :key="url"
              >
                <img
                  :src="url"
                  :alt="`${draft.name} 图库 ${index + 1}`"
                >
                <div>
                  <span>图库 {{ index + 1 }}</span><button
                    type="button"
                    :disabled="!canManage || saving"
                    @click="useAsPrimary(url)"
                  >
                    设为主图
                  </button><button
                    type="button"
                    :disabled="!canManage || saving || index === 0"
                    @click="moveGallery(index, -1)"
                  >
                    上移
                  </button><button
                    type="button"
                    :disabled="!canManage || saving || index === draft.imageUrls.length - 1"
                    @click="moveGallery(index, 1)"
                  >
                    下移
                  </button><button
                    class="danger-text"
                    type="button"
                    :disabled="!canManage || saving"
                    @click="removeGallery(index)"
                  >
                    移除
                  </button>
                </div>
              </article>
            </div>
          </div>
        </section>

        <section>
          <header><span>03 / 五行与推荐</span><h2>能量资料</h2><p>用于五行方案、推荐逻辑和用户侧材料说明。</p></header>
          <div class="material-profile__fields material-profile__fields--three">
            <label><span>主五行</span><select
              v-model="draft.primaryElement"
              :disabled="!canManage || saving"
            ><option value="">暂未设置</option><option
              v-for="option in optionsFor('elements', [draft.primaryElement])"
              :key="option.key"
              :value="option.key"
            >{{ option.label }}{{ option.unavailable ? '（已停用）' : '' }}</option></select></label>
            <div class="material-profile__field">
              <span>副五行</span><MaterialOptionChecks
                v-model="draft.secondaryElements"
                label="副五行"
                :disabled="!canManage || saving"
                :options="secondaryElementOptions(draft.secondaryElements, draft.primaryElement)"
              />
            </div>
            <div class="material-profile__field">
              <span>对应脉轮</span><MaterialOptionChecks
                v-model="draft.chakras"
                label="对应脉轮"
                :disabled="!canManage || saving"
                :options="optionsFor('chakras', draft.chakras)"
              />
            </div>
            <div class="material-profile__field">
              <span>核心功效</span><MaterialOptionChecks
                v-model="draft.effects"
                label="核心功效"
                :disabled="!canManage || saving"
                :options="optionsFor('effects', draft.effects)"
              />
            </div>
            <div class="material-profile__field">
              <span>适用愿景</span><MaterialOptionChecks
                v-model="draft.wishPools"
                label="适用愿景"
                :disabled="!canManage || saving"
                :options="optionsFor('wish_pools', draft.wishPools)"
              />
            </div>
            <label><span>主色系</span><select
              v-model="draft.colorFamily"
              :disabled="!canManage || saving"
            ><option value="">暂未设置</option><option
              v-for="option in optionsFor('color_families', [draft.colorFamily])"
              :key="option.key"
              :value="option.key"
            >{{ option.label }}{{ option.unavailable ? '（已停用）' : '' }}</option></select></label>
            <div class="material-profile__field">
              <span>情绪标签</span><MaterialOptionChecks
                v-model="draft.moodTags"
                label="情绪标签"
                :disabled="!canManage || saving"
                :options="optionsFor('mood_tags', draft.moodTags)"
              />
            </div>
            <div class="material-profile__field">
              <span>视觉标签</span><MaterialOptionChecks
                v-model="draft.visualTags"
                label="视觉标签"
                :disabled="!canManage || saving"
                :options="optionsFor('visual_tags', draft.visualTags)"
              />
            </div>
            <label class="material-profile__full"><span>材料故事 / 说明</span><textarea
              v-model="draft.story"
              :disabled="!canManage || saving"
              maxlength="2000"
              placeholder="说明材质特性、用户感知和推荐边界"
            /></label>
          </div>
        </section>

        <section>
          <header><span>04 / 工作台表现</span><h2>物理与视觉参数</h2><p>用于 DIY 工作台的材质表现，不同于单个 SKU 的尺寸和库存。</p></header>
          <div class="material-profile__fields material-profile__fields--four">
            <label><span>珠子形制</span><select
              v-model="draft.beadShape"
              :disabled="!canManage || saving"
            ><option
              v-for="option in optionsFor('bead_shapes', [draft.beadShape])"
              :key="option.key"
              :value="option.key"
            >{{ option.label }}{{ option.unavailable ? '（已停用）' : '' }}</option></select></label>
            <label><span>安装方式</span><select
              v-model="draft.placementMode"
              :disabled="!canManage || saving"
            ><option
              v-for="option in optionsFor('placement_modes', [draft.placementMode])"
              :key="option.key"
              :value="option.key"
            >{{ option.label }}{{ option.unavailable ? '（历史值）' : '' }}</option></select></label>
            <label><span>视觉轴向</span><select
              v-model="draft.visualAxis"
              :disabled="!canManage || saving"
            ><option
              v-for="option in optionsFor('visual_axes', [draft.visualAxis])"
              :key="option.key"
              :value="option.key"
            >{{ option.label }}{{ option.unavailable ? '（历史值）' : '' }}</option></select></label>
            <label><span>表面工艺</span><select
              v-model="draft.surfaceFinish"
              :disabled="!canManage || saving"
            ><option value="">暂未设置</option><option
              v-for="option in optionsFor('surface_finishes', [draft.surfaceFinish])"
              :key="option.key"
              :value="option.key"
            >{{ option.label }}{{ option.unavailable ? '（已停用）' : '' }}</option></select></label>
            <label><span>通透度</span><select
              v-model="draft.transparencyLevel"
              :disabled="!canManage || saving"
            ><option value="">暂未设置</option><option
              v-for="option in optionsFor('transparency_levels', [draft.transparencyLevel])"
              :key="option.key"
              :value="option.key"
            >{{ option.label }}{{ option.unavailable ? '（已停用）' : '' }}</option></select></label>
            <label><span>批次差异</span><select
              v-model="draft.batchVariation"
              :disabled="!canManage || saving"
            ><option value="">暂未设置</option><option
              v-for="option in optionsFor('batch_variation_levels', [draft.batchVariation])"
              :key="option.key"
              :value="option.key"
            >{{ option.label }}{{ option.unavailable ? '（已停用）' : '' }}</option></select></label>
            <div class="material-profile__field material-profile__full">
              <span>纹理 / 内含特征</span><MaterialOptionChecks
                v-model="draft.textureFeatures"
                label="纹理和内含特征"
                :disabled="!canManage || saving"
                :options="optionsFor('texture_features', draft.textureFeatures)"
              />
            </div>
          </div>
        </section>

        <section>
          <header><span>05 / 搭配与养护</span><h2>使用规则</h2><p>这些信息只影响推荐和运营说明，不会替代库存或价格规则。</p></header>
          <div class="material-profile__fields material-profile__fields--two">
            <div class="material-profile__field">
              <span>适配角色</span><MaterialOptionChecks
                v-model="draft.allowedRoles"
                label="适配角色"
                :disabled="!canManage || saving"
                :options="optionsFor('roles', draft.allowedRoles)"
              />
            </div>
            <div class="material-profile__field material-profile__full">
              <span>搭配规则</span><MaterialOptionChecks
                v-model="draft.matchRules"
                label="搭配规则"
                :disabled="!canManage || saving"
                :options="optionsFor('match_rules', draft.matchRules)"
              />
            </div>
            <div class="material-profile__field material-profile__full">
              <span>养护标签</span><MaterialOptionChecks
                v-model="draft.careTags"
                label="养护标签"
                :disabled="!canManage || saving"
                :options="optionsFor('care_tags', draft.careTags)"
              />
            </div>
          </div>
        </section>

        <details class="material-profile__technical">
          <summary>技术信息（仅供排查使用）</summary>
          <dl><div><dt>品种 ID</dt><dd>{{ profile.id }}</dd></div><div><dt>材料编码</dt><dd>{{ draft.materialCode || '尚未生成' }}</dd></div><div><dt>素材版本</dt><dd>{{ profile.asset_version || 1 }}</dd></div></dl>
        </details>
        <footer>
          <button
            class="primary-action"
            type="submit"
            :disabled="!canManage || saving"
          >
            {{ saving ? '正在保存…' : '保存完整资料' }}
          </button>
        </footer>
      </form>
    </template>
  </section>
</template>
