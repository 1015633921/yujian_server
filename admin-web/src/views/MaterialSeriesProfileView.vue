<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import {
  getMaterialSeries,
  updateMaterialSeries,
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
  secondaryElements: string
  chakras: string
  effects: string
  wishPools: string
  colorFamily: string
  moodTags: string
  visualTags: string
  story: string
  allowedRoles: string
  conflictCodes: string
  matchRules: string
  careTags: string
  beadShape: string
  placementMode: string
  visualAxis: string
  textureFeatures: string
}

const route = useRoute()
const auth = useAuthStore()
const profile = ref<MaterialSeries | null>(null)
const draft = ref<SeriesDraft | null>(null)
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const notice = ref('')
let controller: AbortController | null = null

const seriesId = computed(() => String(route.params.seriesId || '').trim())
const canManage = computed(() => auth.admin?.role !== 'viewer')
const elementOptions = [
  { value: '', label: '暂未设置' },
  { value: 'metal', label: '金' },
  { value: 'wood', label: '木' },
  { value: 'water', label: '水' },
  { value: 'fire', label: '火' },
  { value: 'earth', label: '土' },
]

const operatorLabels: Record<string, string> = {
  metal: '金', wood: '木', water: '水', fire: '火', earth: '土',
  calm: '平静安定', focus: '专注', vitality: '活力', clarity: '清晰',
  communication: '沟通表达', clear: '清透', transparent: '通透',
  primary: '主石', support: '辅助石', accent: '点缀石',
  no_limit: '无特殊限制', avoid_sun: '避免暴晒', avoid_sunlight: '避免暴晒',
  not_together: '不建议搭配', threaded: '穿线', round: '圆珠', nugget: '随形',
  horizontal: '横向', vertical: '纵向', radial: '环绕',
}
const operatorCodes = Object.fromEntries(Object.entries(operatorLabels).map(([code, label]) => [label, code]))

function listText(value: unknown): string {
  return Array.isArray(value) ? value.filter(Boolean).map((item) => operatorLabels[String(item)] || String(item)).join('、') : ''
}

function splitList(value: string): string[] {
  return [...new Set(value.split(/[,，、\n\r]+/).map((item) => item.trim()).filter(Boolean).map((item) => operatorCodes[item] || item))]
}

function elementKey(value: string | undefined): string {
  const map: Record<string, string> = { 金: 'metal', 木: 'wood', 水: 'water', 火: 'fire', 土: 'earth' }
  return map[value || ''] || value || ''
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
    primaryElement: elementKey(energy.primary_element),
    secondaryElements: listText(energy.secondary_elements),
    chakras: listText(energy.chakras),
    effects: listText(energy.effects),
    wishPools: listText(energy.wish_pools),
    colorFamily: energy.color_family || '',
    moodTags: listText(energy.mood_tags),
    visualTags: listText(energy.visual_tags),
    story: energy.story || '',
    allowedRoles: listText(rules.allowed_roles),
    conflictCodes: listText(rules.conflict_codes),
    matchRules: listText(rules.match_rules),
    careTags: listText(rules.care_tags),
    beadShape: String(params.bead_shape || 'round'),
    placementMode: String(params.placement_mode || 'threaded'),
    visualAxis: String(params.visual_axis || 'radial'),
    textureFeatures: listText(params.texture_features),
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
    const item = await getMaterialSeries(seriesId.value, controller.signal)
    profile.value = item
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
  saving.value = true
  notice.value = ''
  const previousParams = profile.value.material_params || {}
  const materialParams = {
    ...previousParams,
    bead_shape: current.beadShape.trim(),
    placement_mode: current.placementMode.trim(),
    visual_axis: current.visualAxis.trim(),
    texture_features: splitList(current.textureFeatures),
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
    secondary_elements: splitList(current.secondaryElements).map(elementKey),
    chakras: splitList(current.chakras),
    chakra_weights: profile.value.energy?.chakra_weights || {},
    effects: splitList(current.effects),
    wish_pools: splitList(current.wishPools),
    color_family: current.colorFamily.trim(),
    mood_tags: splitList(current.moodTags),
    visual_tags: splitList(current.visualTags),
    story: current.story.trim(),
    allowed_roles: splitList(current.allowedRoles),
    conflict_codes: splitList(current.conflictCodes),
    match_rules: splitList(current.matchRules),
    care_tags: splitList(current.careTags),
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
            ><option
              v-for="option in elementOptions"
              :key="option.value"
              :value="option.value"
            >{{ option.label }}</option></select></label>
            <label><span>副五行</span><input
              v-model="draft.secondaryElements"
              :disabled="!canManage || saving"
              placeholder="例如 金、土"
            ></label>
            <label><span>脉轮</span><input
              v-model="draft.chakras"
              :disabled="!canManage || saving"
              placeholder="用顿号或逗号分隔"
            ></label>
            <label><span>核心功效</span><input
              v-model="draft.effects"
              :disabled="!canManage || saving"
              placeholder="例如 专注、平静"
            ></label>
            <label><span>愿望池</span><input
              v-model="draft.wishPools"
              :disabled="!canManage || saving"
              placeholder="例如 学业、关系"
            ></label>
            <label><span>色系</span><input
              v-model="draft.colorFamily"
              :disabled="!canManage || saving"
              placeholder="例如 透明白"
            ></label>
            <label><span>情绪标签</span><input
              v-model="draft.moodTags"
              :disabled="!canManage || saving"
              placeholder="用顿号或逗号分隔"
            ></label>
            <label><span>视觉标签</span><input
              v-model="draft.visualTags"
              :disabled="!canManage || saving"
              placeholder="例如 通透、清冷"
            ></label>
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
            ><option value="round">圆珠</option><option value="nugget">随形</option><option value="faceted">切面珠</option><option value="flat">扁珠</option></select></label>
            <label><span>安装方式</span><select
              v-model="draft.placementMode"
              :disabled="!canManage || saving"
            ><option value="threaded">穿线</option><option value="strung">串接</option><option value="pendant">吊挂</option><option value="spacer">隔珠</option></select></label>
            <label><span>视觉轴向</span><select
              v-model="draft.visualAxis"
              :disabled="!canManage || saving"
            ><option value="radial">环绕</option><option value="horizontal">横向</option><option value="vertical">纵向</option><option value="none">无固定方向</option></select></label>
            <label><span>纹理 / 内含特征</span><input
              v-model="draft.textureFeatures"
              :disabled="!canManage || saving"
              placeholder="用顿号或逗号分隔"
            ></label>
          </div>
        </section>

        <section>
          <header><span>05 / 搭配与养护</span><h2>使用规则</h2><p>这些信息只影响推荐和运营说明，不会替代库存或价格规则。</p></header>
          <div class="material-profile__fields material-profile__fields--two">
            <label><span>适配角色</span><input
              v-model="draft.allowedRoles"
              :disabled="!canManage || saving"
              placeholder="用顿号或逗号分隔"
            ></label>
            <label><span>冲突品种编码</span><input
              v-model="draft.conflictCodes"
              :disabled="!canManage || saving"
              placeholder="仅维护确有冲突的品种"
            ></label>
            <label class="material-profile__full"><span>搭配规则</span><textarea
              v-model="draft.matchRules"
              :disabled="!canManage || saving"
              placeholder="一条规则用顿号、逗号或换行分隔"
            /></label>
            <label class="material-profile__full"><span>养护标签</span><input
              v-model="draft.careTags"
              :disabled="!canManage || saving"
              placeholder="例如 避免暴晒、单独收纳"
            ></label>
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
