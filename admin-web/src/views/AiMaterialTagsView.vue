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
const filter = ref<AiTagStatus | ''>('')
const keyword = ref('')
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
  return items.value.filter((item) => !query || [item.series, item.category, item.material_code, item.top].some((value) => value.toLowerCase().includes(query)))
})
const selected = computed(() => visibleItems.value.find((item) => item.annotation_id === selectedId.value) || null)
const payload = computed<AiTagPayload>(() => selected.value?.reviewer_final && Object.keys(selected.value.reviewer_final).length ? selected.value.reviewer_final : selected.value?.parsed_response || {})
const image = computed(() => selected.value?.image_urls[Math.min(imageIndex.value, Math.max(0, (selected.value?.image_urls.length || 1) - 1))] || '')
const counts = computed(() => Object.fromEntries(statuses.slice(1).map(({ value }) => [value, items.value.filter((item) => item.status === value).length])))
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

function select(item: AiTagRecord): void { selectedId.value = item.annotation_id; imageIndex.value = 0; notes.value = item.review_notes || '' }

async function load(): Promise<void> {
  controller?.abort(); controller = new AbortController(); loading.value = true; error.value = ''
  try {
    items.value = await listAiMaterialTags(filter.value, controller.signal)
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

watch(filter, () => void load())
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
            v-for="item in statuses.slice(1)"
            :key="item.value"
            type="button"
            :class="{ 'is-current': filter === item.value }"
            @click="filter = item.value"
          >
            {{ item.label }} <b>{{ counts[item.value] || 0 }}</b>
          </button>
        </div>
        <input
          v-model="keyword"
          placeholder="搜索材料名称、编码或分类"
        >
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
            <span><strong>{{ item.series || '未命名品种' }}</strong><small>{{ item.category || '未分类' }} · 已提交视觉审核</small><em>{{ date(item.created_at) }}</em></span><b :class="`status-${item.status}`">{{ label(item.status) }}</b>
          </button>
        </aside>
        <main
          v-if="selected"
          class="ai-tags__inspector"
        >
          <header><div><span>{{ selected.top === 'accessory' ? '配饰视觉审核' : '珠材视觉审核' }}</span><h2>{{ selected.series || '未命名品种' }}</h2><p>{{ selected.category || '未分类' }} · 系统已记录审核模型与材料关联</p></div><b :class="`status-${selected.status}`">{{ label(selected.status) }}</b></header>
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
                <h3>将应用到材料资料</h3><p>只会写入材料角色、搭配规则、视觉/情绪标签、色彩倾向、通透度与纹理特征；名称、分类、图片、价格、库存、尺寸、五行、功效和养护资料受保护。</p>
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
                确认通过
              </button><button
                v-else-if="selected.status === 'approved'"
                class="primary-action"
                type="button"
                :disabled="!canManage || busy"
                @click="requestApply"
              >
                应用到材料资料
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
