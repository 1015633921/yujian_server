<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import PageEmptyState from '@/components/ui/PageEmptyState.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import ActionConfirmDialog from '@/components/ui/ActionConfirmDialog.vue'
import {
  applyAiMaterialTag,
  listAiMaterialTags,
  reviewAiMaterialTag,
  type AiTagPayload,
  type AiTagRecord,
  type AiTagStatus,
} from '@/features/ai-tags/api'
import { useAuthStore } from '@/stores/auth'

const statuses: Array<{ value: AiTagStatus | ''; label: string }> = [
  { value: '', label: '全部记录' }, { value: 'pending_review', label: '待审核' }, { value: 'approved', label: '已通过' },
  { value: 'applied', label: '已应用' }, { value: 'rejected', label: '已驳回' }, { value: 'failed', label: '标注失败' },
]
const statusLabel: Record<AiTagStatus, string> = { pending_review: '待审核', approved: '已通过', applied: '已应用', rejected: '已驳回', failed: '标注失败' }

const auth = useAuthStore()
const items = ref<AiTagRecord[]>([])
const filter = ref<AiTagStatus | ''>('pending_review')
const keyword = ref('')
const categoryFilter = ref('')
const confidenceFilter = ref<'all' | 'high' | 'medium' | 'low'>('all')
const sortOrder = ref<'oldest' | 'newest'>('oldest')
const selectedId = ref('')
const imageIndex = ref(0)
const notes = ref('')
const loading = ref(true)
const error = ref('')
const busy = ref(false)
const notice = ref('')
const confirmAction = ref<'rejected' | 'apply' | ''>('')
let controller: AbortController | null = null

const canManage = computed(() => auth.admin?.role !== 'viewer')
const visibleItems = computed(() => {
  const query = keyword.value.trim().toLowerCase()
  const next = items.value.filter((item) => {
    const confidence = Number((item.reviewer_final?.confidence ?? item.parsed_response?.confidence) || 0)
    const confidenceMatches = confidenceFilter.value === 'all'
      || (confidenceFilter.value === 'high' && confidence >= 0.8)
      || (confidenceFilter.value === 'medium' && confidence >= 0.6 && confidence < 0.8)
      || (confidenceFilter.value === 'low' && confidence < 0.6)
    return (!filter.value || item.status === filter.value)
      && (!categoryFilter.value || item.category === categoryFilter.value)
      && confidenceMatches
      && (!query || [item.series, item.category, item.material_code, item.top].some((value) => value.toLowerCase().includes(query)))
  })
  return [...next].sort((left, right) => {
    const delta = new Date(left.created_at || 0).getTime() - new Date(right.created_at || 0).getTime()
    return sortOrder.value === 'oldest' ? delta : -delta
  })
})
const selected = computed(() => visibleItems.value.find((item) => item.annotation_id === selectedId.value) || null)
const payload = computed<AiTagPayload>(() => selected.value?.reviewer_final && Object.keys(selected.value.reviewer_final).length ? selected.value.reviewer_final : selected.value?.parsed_response || {})
const image = computed(() => selected.value?.image_urls[Math.min(imageIndex.value, Math.max(0, (selected.value?.image_urls.length || 1) - 1))] || '')
const counts = computed(() => Object.fromEntries(statuses.slice(1).map(({ value }) => [value, items.value.filter((item) => item.status === value).length])))
const categories = computed(() => [...new Set(items.value.map((item) => item.category).filter(Boolean))].sort((left, right) => left.localeCompare(right, 'zh-CN')))
const applicationRows = computed(() => {
  const fields = selected.value?.application?.fields || {}
  const params = (fields.material_params || {}) as Record<string, unknown>
  const rows = [
    ['材料角色', fields.allowed_roles],
    ['搭配规则', fields.match_rules],
    ['视觉标签', fields.visual_tags],
    ['情绪标签', fields.mood_tags],
    ['主色系', fields.color_family],
    ['通透度', params.transparency_level],
    ['纹理特征', params.texture_features],
  ] as Array<[string, unknown]>
  return rows.filter(([, value]) => Array.isArray(value) ? value.length : Boolean(value)).map(([labelText, value]) => ({ label: labelText, value: applicationValue(value) }))
})
const confirmTitle = computed(() => confirmAction.value === 'apply' ? '应用 AI 审核结果' : '驳回 AI 打标结果')
const confirmDescription = computed(() => {
  const name = selected.value?.series || '当前材料'
  return confirmAction.value === 'apply'
    ? `将「${name}」已审核的视觉标签写入材料资料。名称、分类、图片、价格、库存、尺寸、五行、功效和养护资料不会被修改。`
    : `将「${name}」的打标结果标记为驳回；审核备注会保留，方便后续重新生成和复核。`
})

function date(value?: string): string { return value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value)) : '-' }
function tags(value?: string[]): string { return value?.filter(Boolean).join(' · ') || '—' }
function metric(value: unknown): string { return typeof value === 'number' ? `${Math.round(value)}%` : '—' }
function label(status: AiTagStatus): string { return statusLabel[status] || status }
function applicationValue(value: unknown): string {
  const labels: Record<string, string> = {
    primary: '主石', support: '辅石', accent: '点缀', spacer: '隔珠 / 隔片', pendant: '吊坠 / 花托',
    no_limit: '不限搭配', best_as_primary: '适合作主石', best_as_support: '适合作辅石', accent_only: '建议少量点缀',
    spacer_only: '仅作隔珠 / 隔片', pair_symmetry: '建议成对对称', avoid_dense: '避免高密度使用', balance_color: '需搭配平衡色',
    transparent: '透明感', icy: '冰透', sparkling: '闪光', soft_color: '低饱和', texture: '纹理感', dark: '深色', warm: '暖调',
    calm: '舒缓', calming: '舒缓', confident: '自信', confidence: '自信', clear: '清晰', clarity: '清晰', focused: '专注', focus: '专注', energetic: '活力', vitality: '活力', gentle: '柔和', softness: '柔和', boundary: '边界', companion: '陪伴', companionship: '陪伴',
    white: '白色', clear_color: '清透', pink: '粉色', blue: '蓝色', green: '绿色', purple: '紫色', gold: '金色', red: '红色', brown: '棕色', black: '黑色',
    semi_transparent: '半透', translucent: '微透', opaque: '不透', clean: '净体', cloud: '棉絮', crack: '冰裂', rutile: '发丝', phantom: '幽灵', cat_eye: '猫眼', color_band: '色带', mineral_inclusion: '矿物内含',
  }
  const values = Array.isArray(value) ? value : [value]
  return values.map((item) => labels[String(item)] || String(item)).join(' · ')
}

function attemptLabel(item: AiTagRecord): string {
  const attempts = items.value.filter((candidate) => candidate.target_id === item.target_id || (candidate.series === item.series && candidate.category === item.category)).length
  return attempts > 1 ? `${attempts} 次记录` : '首次记录'
}

function select(item: AiTagRecord): void { selectedId.value = item.annotation_id; imageIndex.value = 0; notes.value = item.review_notes || '' }

async function load(): Promise<void> {
  controller?.abort(); controller = new AbortController(); loading.value = true; error.value = ''
  try {
    items.value = await listAiMaterialTags('', controller.signal)
    if (!visibleItems.value.some((item) => item.annotation_id === selectedId.value)) select(visibleItems.value[0] || { annotation_id: '', review_notes: '' } as AiTagRecord)
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') return
    error.value = cause instanceof Error ? cause.message : 'AI 打标记录加载失败'
  } finally { loading.value = false }
}

async function review(action: 'approved' | 'rejected'): Promise<void> {
  if (!selected.value || !canManage.value || busy.value) return
  if (action === 'rejected' && !notes.value.trim()) { notice.value = '驳回前请填写原因，方便后续重新判断。'; return }
  busy.value = true; notice.value = ''
  try {
    const next = await reviewAiMaterialTag(selected.value.annotation_id, action, notes.value.trim(), payload.value)
    items.value = items.value.map((item) => item.annotation_id === next.annotation_id ? next : item)
    select(next); notice.value = action === 'approved' ? '已通过人工审核，可确认后应用到材料资料。' : '已驳回该打标结果。'
  } catch (cause) { notice.value = cause instanceof Error ? cause.message : '审核保存失败。' } finally { busy.value = false }
}

function requestReject(): void {
  if (!selected.value || !canManage.value || busy.value) return
  if (!notes.value.trim()) { notice.value = '驳回前请填写原因，方便后续重新判断。'; return }
  confirmAction.value = 'rejected'
}

async function apply(): Promise<void> {
  if (!selected.value || !canManage.value || busy.value || selected.value.status !== 'approved') return
  busy.value = true; notice.value = ''
  try {
    const next = await applyAiMaterialTag(selected.value.annotation_id)
    items.value = items.value.map((item) => item.annotation_id === next.annotation_id ? next : item)
    select(next); notice.value = 'AI 标签已应用到材料资料。'
  } catch (cause) { notice.value = cause instanceof Error ? cause.message : '应用到材料资料失败。' } finally { busy.value = false }
}

function requestApply(): void {
  if (!selected.value || !canManage.value || busy.value || selected.value.status !== 'approved') return
  confirmAction.value = 'apply'
}

async function resolveConfirm(): Promise<void> {
  const action = confirmAction.value
  if (action === 'rejected') await review('rejected')
  if (action === 'apply') await apply()
  if (!busy.value) confirmAction.value = ''
}

watch(visibleItems, (next) => { if (!next.some((item) => item.annotation_id === selectedId.value)) select(next[0] || { annotation_id: '', review_notes: '' } as AiTagRecord) })
onBeforeUnmount(() => controller?.abort())
void load()
</script>

<template>
  <section class="workspace-page ai-tags-page">
    <PageHeading
      eyebrow="AI MATERIAL REVIEW"
      title="AI 打标审核"
      description="AI 仅给出图库的视觉和设计辅助信息；必须人工审核后，才能将可控字段写入材料资料。"
    />
    <PageErrorState
      v-if="error && !loading"
      title="AI 打标记录暂时无法读取"
      :message="error"
      eyebrow="AI REVIEW UNAVAILABLE"
      @retry="load"
    />
    <div
      v-else
      class="ai-tags"
      :aria-busy="loading || busy"
    >
      <header class="ai-tags__toolbar">
        <div class="ai-tags__counts">
          <button
            type="button"
            :class="{ 'is-current': filter === '' }"
            @click="filter = ''"
          >
            全部记录 <b>{{ items.length }}</b>
          </button>
          <button
            v-for="item in statuses.slice(1)"
            :key="item.value"
            type="button"
            :class="{ 'is-current': filter === item.value }"
            @click="filter = item.value"
          >
            {{ item.label }} <b>{{ counts[item.value] || 0 }}</b>
          </button>
        </div>
        <div class="ai-tags__filters">
          <select
            v-model="categoryFilter"
            aria-label="按类目筛选 AI 记录"
          >
            <option value="">
              全部类目
            </option>
            <option
              v-for="category in categories"
              :key="category"
              :value="category"
            >
              {{ category }}
            </option>
          </select>
          <select
            v-model="confidenceFilter"
            aria-label="按置信度筛选 AI 记录"
          >
            <option value="all">
              全部置信度
            </option>
            <option value="high">
              高置信度 ≥ 80%
            </option>
            <option value="medium">
              中置信度 60%–79%
            </option>
            <option value="low">
              低置信度 &lt; 60%
            </option>
          </select>
          <select
            v-model="sortOrder"
            aria-label="AI 记录排序"
          >
            <option value="oldest">
              最早提交优先
            </option>
            <option value="newest">
              最新提交优先
            </option>
          </select>
          <input
            v-model="keyword"
            type="search"
            placeholder="搜索名称、编码或类目"
          >
        </div>
      </header>
      <div class="ai-tags__workspace">
        <aside class="ai-tags__queue">
          <div class="ai-tags__queue-head">
            <span>{{ statuses.find((item) => item.value === filter)?.label }}</span><b>{{ visibleItems.length }} 条</b>
          </div>
          <div
            v-if="loading"
            class="ai-tags__skeleton"
          >
            <i
              v-for="item in 5"
              :key="item"
            />
          </div>
          <PageEmptyState
            v-else-if="!visibleItems.length"
            title="没有符合条件的记录"
            message="尝试清除搜索词或切换审核状态。"
          />
          <button
            v-for="item in visibleItems"
            v-else
            :key="item.annotation_id"
            class="ai-tags__item"
            :class="{ 'is-current': selectedId === item.annotation_id }"
            type="button"
            @click="select(item)"
          >
            <img
              v-if="item.image_urls[0]"
              :src="item.image_urls[0]"
              :alt="item.series"
            ><i v-else />
            <span><strong>{{ item.series || '未命名品种' }}</strong><small>{{ item.category || '未分类' }} · {{ attemptLabel(item) }}</small><em>{{ date(item.created_at) }}</em></span><b :class="`status-${item.status}`">{{ label(item.status) }}</b>
          </button>
        </aside>
        <main
          v-if="selected"
          class="ai-tags__inspector"
        >
          <header><div><span>{{ selected.top === 'accessory' ? '配饰视觉审核' : '珠材视觉审核' }}</span><h2>{{ selected.series || '未命名品种' }}</h2><p>{{ selected.category || '未分类' }} · 系统已记录审核模型与材料关联</p></div><b :class="`status-${selected.status}`">{{ label(selected.status) }}</b></header>
          <ol
            class="ai-tags__stages"
            aria-label="AI 打标审核流程"
          >
            <li class="is-complete">
              <b>1</b><span>检查建议<small>核对图片与视觉判断</small></span>
            </li>
            <li :class="{ 'is-complete': ['approved', 'applied'].includes(selected.status), 'is-current': selected.status === 'pending_review' || selected.status === 'rejected' }">
              <b>2</b><span>人工通过<small>通过不会立即修改资料</small></span>
            </li>
            <li :class="{ 'is-complete': selected.status === 'applied', 'is-current': selected.status === 'approved' }">
              <b>3</b><span>确认应用<small>再次确认后才写入</small></span>
            </li>
          </ol>
          <div class="ai-tags__detail">
            <section class="ai-tags__gallery">
              <div class="ai-tags__hero">
                <img
                  v-if="image"
                  :src="image"
                  :alt="selected.series"
                ><span v-else>没有可展示的图库图片</span>
              </div><div
                v-if="selected.image_urls.length > 1"
                class="ai-tags__thumbs"
              >
                <button
                  v-for="(url, index) in selected.image_urls"
                  :key="url"
                  type="button"
                  :class="{ 'is-current': index === imageIndex }"
                  @click="imageIndex = index"
                >
                  <img
                    :src="url"
                    :alt="`图库图片 ${index + 1}`"
                  >
                </button>
              </div>
            </section>
            <div class="ai-tags__analysis">
              <section
                v-if="selected.status === 'failed'"
                class="ai-tags__failure"
              >
                <span>标注未完成</span><h3>{{ selected.error_code || 'AI_TAGGING_FAILED' }}</h3><p>{{ selected.error_message || '模型请求或结果校验失败' }}</p>
              </section>
              <template v-else>
                <section>
                  <h3>视觉特征 <small>{{ Math.round((payload.confidence || 0) * 100) }}% 置信度</small></h3><div class="ai-tags__metrics">
                    <span>明度<b>{{ metric(payload.visual?.brightness) }}</b></span><span>饱和度<b>{{ metric(payload.visual?.saturation) }}</b></span><span>通透度<b>{{ metric(payload.visual?.transparency) }}</b></span><span>闪耀度<b>{{ metric(payload.visual?.sparkle) }}</b></span>
                  </div><p>{{ tags(payload.visual?.dominant_colors as string[]) }}</p>
                </section><section><h3>设计与搭配</h3><dl><div><dt>材料角色</dt><dd>{{ tags(payload.design?.roles) }}</dd></div><div><dt>风格标签</dt><dd>{{ tags(payload.design?.style_tags) }}</dd></div><div><dt>形态语言</dt><dd>{{ tags(payload.design?.shape_language) }}</dd></div><div><dt>推荐金属色</dt><dd>{{ tags(payload.design?.recommended_metal_palettes) }}</dd></div></dl></section><section><h3>需要人工确认</h3><p>{{ tags(payload.uncertain_fields) }}</p></section>
              </template>
              <section><h3>系统已知资料</h3><p>规格 {{ selected.known_facts?.available_sizes_mm?.join(' / ') || '—' }} mm · {{ selected.known_facts?.catalog_names?.join(' / ') || selected.series }}</p></section>
              <section
                v-if="selected.status !== 'failed'"
                class="ai-tags__guard"
              >
                <h3>字段级写入预览 <small>{{ applicationRows.length }} 项</small></h3>
                <dl
                  v-if="applicationRows.length"
                  class="ai-tags__application-preview"
                >
                  <div
                    v-for="row in applicationRows"
                    :key="row.label"
                  >
                    <dt>{{ row.label }}</dt><dd>{{ row.value }}</dd>
                  </div>
                </dl>
                <p v-else>
                  本次结果没有可写入字段，请驳回并重新生成。
                </p>
                <p>名称、分类、图片、价格、库存、尺寸、五行、功效和养护资料始终受保护。</p>
              </section>
            </div>
          </div>
          <footer class="ai-tags__actions">
            <label>审核备注<textarea
              v-model="notes"
              :disabled="selected.status === 'applied'"
              :placeholder="selected.status === 'rejected' ? '请填写驳回原因' : '可填写判断依据或后续核查事项'"
            /></label><p
              v-if="notice"
              :class="{ 'is-error': notice.includes('失败') || notice.includes('请') }"
            >
              {{ notice }}
            </p><div>
              <button
                v-if="selected.status !== 'applied' && selected.status !== 'failed'"
                class="danger-outline"
                type="button"
                :disabled="!canManage || busy"
                @click="requestReject"
              >
                驳回
              </button><button
                v-if="selected.status === 'pending_review' || selected.status === 'rejected'"
                class="primary-action"
                type="button"
                :disabled="!canManage || busy"
                @click="review('approved')"
              >
                通过审核（暂不写入）
              </button><button
                v-else-if="selected.status === 'approved'"
                class="primary-action"
                type="button"
                :disabled="!canManage || busy"
                @click="requestApply"
              >
                第 2 步：应用到材料资料
              </button><button
                v-else
                disabled
                type="button"
              >
                {{ selected.status === 'applied' ? '已应用到材料资料' : '请重新生成标注' }}
              </button>
            </div>
          </footer>
        </main>
        <PageEmptyState
          v-else
          title="选择一条打标记录"
          message="在左侧队列中查看材料图片、视觉评分和搭配建议。"
        />
      </div>
      <ActionConfirmDialog
        :open="Boolean(confirmAction)"
        :title="confirmTitle"
        :description="confirmDescription"
        :confirm-label="confirmAction === 'apply' ? '确认应用' : '确认驳回'"
        :tone="confirmAction === 'apply' ? 'default' : 'danger'"
        :busy="busy"
        @close="confirmAction = ''"
        @confirm="resolveConfirm"
      />
    </div>
  </section>
</template>
