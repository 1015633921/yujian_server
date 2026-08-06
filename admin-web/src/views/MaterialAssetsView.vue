<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import PageEmptyState from '@/components/ui/PageEmptyState.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import {
  bindMaterialAssets,
  listMaterialTaxonomy,
  listMaterialTypes,
  uploadMaterialAsset,
  type MaterialCategory,
  type MaterialType,
} from '@/features/materials/api'
import {
  MATERIAL_ASSET_MAX_COUNT,
  processMaterialAssetFile,
  type AssetMetrics,
} from '@/features/materials/assets'
import { useAuthStore } from '@/stores/auth'

type AssetStatus = 'processing' | 'ready' | 'uploading' | 'uploaded' | 'error' | 'upload_error'

interface AssetQueueItem {
  id: string
  name: string
  status: AssetStatus
  blob?: Blob
  previewUrl?: string
  sourceWidth?: number
  sourceHeight?: number
  metrics?: AssetMetrics
  key?: string
  error?: string
}

const auth = useAuthStore()
const route = useRoute()
const types = ref<MaterialType[]>([])
const categories = ref<MaterialCategory[]>([])
const top = ref('')
const categoryId = ref('')
const seriesId = ref('')
const mode = ref<'replace' | 'append'>('replace')
const queue = ref<AssetQueueItem[]>([])
const loading = ref(true)
const error = ref('')
const notice = ref('')
const busy = ref(false)
let typesController: AbortController | null = null
let categoriesController: AbortController | null = null
let categoryRequest = 0

const canManage = computed(() => auth.admin?.role !== 'viewer')
const currentCategories = computed(() => categories.value.filter((item) => item.top === top.value))
const currentCategory = computed(() => currentCategories.value.find((item) => item.id === categoryId.value) || null)
const currentSeries = computed(() => currentCategory.value?.series.find((item) => item.id === seriesId.value) || null)
const uploaded = computed(() => queue.value.filter((item) => item.status === 'uploaded').length)
const ready = computed(() => queue.value.filter((item) => item.status === 'ready').length)
const failed = computed(() => queue.value.filter((item) => item.status === 'error' || item.status === 'upload_error').length)
const bindable = computed(() => Boolean(currentSeries.value) && queue.value.length > 0 && queue.value.every((item) => item.status === 'uploaded' && item.key))

function statusLabel(status: AssetStatus): string {
  return {
    processing: '处理中',
    ready: '待上传',
    uploading: '上传中',
    uploaded: '已上传',
    error: '处理失败',
    upload_error: '上传失败',
  }[status]
}

function byteLabel(bytes = 0): string {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`
}

function createId(): string {
  return `asset_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
}

function resetCategory(): void {
  categoryId.value = ''
  seriesId.value = ''
}

function resetSeries(): void {
  seriesId.value = ''
}

function revoke(item: AssetQueueItem): void {
  if (item.previewUrl) URL.revokeObjectURL(item.previewUrl)
}

function remove(item: AssetQueueItem): void {
  if (busy.value) return
  revoke(item)
  queue.value = queue.value.filter((candidate) => candidate.id !== item.id)
}

function move(index: number, direction: -1 | 1): void {
  const target = index + direction
  if (busy.value || target < 0 || target >= queue.value.length) return
  const next = [...queue.value]
  const current = next[index]
  const swapped = next[target]
  if (!current || !swapped) return
  next[index] = swapped
  next[target] = current
  queue.value = next
}

function download(item: AssetQueueItem): void {
  if (!item.blob || !item.previewUrl) return
  const link = document.createElement('a')
  link.href = item.previewUrl
  link.download = `${item.name.replace(/\.[^.]+$/, '') || 'material'}.webp`
  link.click()
}

async function load(): Promise<void> {
  typesController?.abort()
  typesController = new AbortController()
  loading.value = true
  error.value = ''
  try {
    const nextTypes = await listMaterialTypes(false, typesController.signal)
    types.value = nextTypes
    const requestedTop = typeof route.query.top === 'string' ? route.query.top : ''
    if (requestedTop && nextTypes.some((item) => item.code === requestedTop)) top.value = requestedTop
    else if (!nextTypes.some((item) => item.code === top.value)) top.value = nextTypes.at(0)?.code || ''
    else await loadCategories(top.value)
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') return
    error.value = cause instanceof Error ? cause.message : '素材目录加载失败'
  } finally {
    loading.value = false
  }
}

async function loadCategories(nextTop: string): Promise<void> {
  categoriesController?.abort()
  const currentController = new AbortController()
  categoriesController = currentController
  const requestId = ++categoryRequest
  if (!nextTop) {
    categories.value = []
    resetCategory()
    loading.value = false
    return
  }
  loading.value = true
  error.value = ''
  const timeout = window.setTimeout(() => currentController.abort('timeout'), 10_000)
  try {
    // 素材处理只需要当前类型的三级目录；避免一次加载全量图库目标。
    const nextCategories = await listMaterialTaxonomy(nextTop, false, currentController.signal)
    if (requestId !== categoryRequest) return
    categories.value = nextCategories
    const requestedSeriesId = typeof route.query.series_id === 'string' ? route.query.series_id : ''
    const requestedCategory = requestedSeriesId
      ? currentCategories.value.find((item) => item.series.some((series) => series.id === requestedSeriesId))
      : undefined
    if (requestedCategory) {
      categoryId.value = requestedCategory.id
      seriesId.value = requestedSeriesId
    } else {
      if (!currentCategories.value.some((item) => item.id === categoryId.value)) resetCategory()
      if (!currentCategory.value?.series.some((item) => item.id === seriesId.value)) resetSeries()
    }
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') {
      if (currentController.signal.reason === 'timeout') error.value = '该类型的素材目录加载超时，请重试。'
      return
    }
    if (requestId === categoryRequest) error.value = cause instanceof Error ? cause.message : '素材目录加载失败'
  } finally {
    window.clearTimeout(timeout)
    if (requestId === categoryRequest) loading.value = false
  }
}

async function addFiles(files: FileList | File[]): Promise<void> {
  if (busy.value || !canManage.value) return
  const available = MATERIAL_ASSET_MAX_COUNT - queue.value.length
  const sorted = [...files].sort((left, right) => left.name.localeCompare(right.name, 'zh-CN', { numeric: true, sensitivity: 'base' })).slice(0, Math.max(0, available))
  if (!sorted.length) {
    notice.value = `一次最多处理 ${MATERIAL_ASSET_MAX_COUNT} 张图片。`
    return
  }
  if (files.length > sorted.length) notice.value = `本次仅加入前 ${sorted.length} 张，单次最多 ${MATERIAL_ASSET_MAX_COUNT} 张。`
  busy.value = true
  try {
    for (const file of sorted) {
      const item: AssetQueueItem = { id: createId(), name: file.name, status: 'processing' }
      queue.value = [...queue.value, item]
      try {
        const processed = await processMaterialAssetFile(file)
        Object.assign(item, processed, { status: 'ready' satisfies AssetStatus })
      } catch (cause) {
        item.status = 'error'
        item.error = cause instanceof Error ? cause.message : '图片处理失败'
      }
      queue.value = [...queue.value]
    }
  } finally {
    busy.value = false
  }
}

function chooseFiles(event: Event): void {
  const input = event.target as HTMLInputElement
  if (input.files) void addFiles(input.files)
  input.value = ''
}

function dropFiles(event: DragEvent): void {
  event.preventDefault()
  if (event.dataTransfer?.files) void addFiles(event.dataTransfer.files)
}

async function upload(): Promise<void> {
  if (!canManage.value || busy.value) return
  const targets = queue.value.filter((item) => ['ready', 'upload_error'].includes(item.status) && item.blob)
  if (!targets.length) return
  busy.value = true
  notice.value = ''
  try {
    for (const item of targets) {
      if (!item.blob) continue
      item.status = 'uploading'
      queue.value = [...queue.value]
      try {
        const result = await uploadMaterialAsset(item.blob, `${item.name.replace(/\.[^.]+$/, '') || 'material'}.webp`)
        item.status = 'uploaded'
        item.key = result.key
        item.error = ''
      } catch (cause) {
        item.status = 'upload_error'
        item.error = cause instanceof Error ? cause.message : '素材上传失败'
      }
      queue.value = [...queue.value]
    }
    notice.value = failed.value ? '部分素材未上传成功，可移除后重试。' : '全部素材已上传，确认目标品种后即可绑定。'
  } finally {
    busy.value = false
  }
}

async function bind(): Promise<void> {
  if (!canManage.value || busy.value || !currentSeries.value || !bindable.value) return
  const action = mode.value === 'append' ? '追加到' : '替换'
  if (!window.confirm(`确认将 ${queue.value.length} 张图片${action}「${currentSeries.value.name}」的图库吗？主图不会被修改。`)) return
  busy.value = true
  notice.value = ''
  try {
    const result = await bindMaterialAssets(
      currentSeries.value.id,
      queue.value.map((item) => item.key || ''),
      mode.value,
      {
        expectedVersion: currentSeries.value.asset_version,
        idempotencyKey: `asset_${currentSeries.value.id}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      },
    )
    notice.value = `图库已更新，共 ${result.bound_count || queue.value.length} 张；主图未改动，材料缓存已刷新。`
    await load()
  } catch (cause) {
    notice.value = cause instanceof Error ? cause.message : '图库绑定失败，请刷新后重试。'
  } finally {
    busy.value = false
  }
}

function clear(): void {
  if (busy.value || !queue.value.length) return
  if (queue.value.some((item) => item.key) && !window.confirm('已上传的 COS 文件不会被删除，仍要清空当前队列吗？')) return
  queue.value.forEach(revoke)
  queue.value = []
  notice.value = ''
}

watch(top, (nextTop, previousTop) => {
  if (nextTop && nextTop !== previousTop) {
    resetCategory()
    void loadCategories(nextTop)
  }
})

onBeforeUnmount(() => {
  typesController?.abort()
  categoriesController?.abort()
  queue.value.forEach(revoke)
})

void load()
</script>

<template>
  <section class="workspace-page material-assets-page">
    <PageHeading
      eyebrow="MATERIAL ASSET LAB"
      title="透明材料图标准化"
      description="仅接收已抠图的 PNG / WebP，统一输出 512 × 512 透明 WebP，并写入品种共享图库。"
    >
      <template #actions>
        <RouterLink
          v-if="currentSeries"
          class="heading-link"
          :to="{ name: 'material-series-profile', params: { seriesId: currentSeries.id } }"
        >
          返回「{{ currentSeries.name }}」资料 ↗
        </RouterLink>
        <RouterLink
          class="heading-link"
          :to="{ name: 'material-directory', query: top ? { top } : {} }"
        >
          返回材料目录 ↗
        </RouterLink>
      </template>
    </PageHeading>

    <PageErrorState
      v-if="error && !loading"
      title="素材目录暂时无法读取"
      :message="error"
      eyebrow="ASSET LAB UNAVAILABLE"
      @retry="load"
    />

    <div
      v-else
      class="material-assets"
      :aria-busy="loading || busy"
    >
      <aside class="material-assets__target">
        <span>绑定位置</span>
        <h2>共享图库</h2>
        <p>图片绑定到品种后，全部 SKU 会引用图库；回到品种资料页可选择主图并调整图库顺序。</p>
        <label>
          <span>材料类型</span>
          <select
            v-model="top"
            :disabled="busy"
            @change="resetCategory"
          >
            <option
              v-for="item in types"
              :key="item.code"
              :value="item.code"
            >{{ item.name }}</option>
          </select>
        </label>
        <label>
          <span>材料分类</span>
          <select
            v-model="categoryId"
            :disabled="busy || !top"
            @change="resetSeries"
          >
            <option value="">请选择材料分类</option>
            <option
              v-for="item in currentCategories"
              :key="item.id"
              :value="item.id"
            >{{ item.name }}</option>
          </select>
        </label>
        <label>
          <span>品种 / 款式</span>
          <select
            v-model="seriesId"
            :disabled="busy || !currentCategory"
          >
            <option value="">{{ currentCategory ? '请选择品种 / 款式' : '请先选择材料分类' }}</option>
            <option
              v-for="item in currentCategory?.series || []"
              :key="item.id"
              :value="item.id"
            >{{ item.name }}</option>
          </select>
        </label>
        <label>
          <span>写入方式</span>
          <select
            v-model="mode"
            :disabled="busy"
          >
            <option value="replace">替换品种图库</option>
            <option value="append">追加到品种图库</option>
          </select>
        </label>
        <div class="material-assets__summary">
          <strong v-if="currentSeries">{{ currentSeries.name }}</strong>
          <strong v-else>尚未选择品种</strong>
          <small v-if="currentSeries">当前图库 {{ currentSeries.image_urls?.length || 0 }} 张 · {{ mode === 'append' ? '追加图片' : '替换图库' }}</small>
          <small v-else>完成三级选择后才可绑定素材</small>
        </div>
      </aside>

      <main class="material-assets__main">
        <header class="material-assets__toolbar">
          <div>
            <span>处理队列</span>
            <h2>{{ queue.length ? `${queue.length} 张素材` : '待处理素材' }}</h2>
          </div>
          <p>
            待上传 {{ ready }} · 已上传 {{ uploaded }}<template v-if="failed">
              · 异常 {{ failed }}
            </template>
          </p>
        </header>

        <label
          class="asset-dropzone"
          :class="{ 'is-disabled': !canManage || busy }"
          @dragover.prevent
          @drop="dropFiles"
        >
          <input
            type="file"
            accept="image/png,image/webp,.png,.webp"
            multiple
            :disabled="!canManage || busy"
            @change="chooseFiles"
          >
          <b>选择已抠图图片</b>
          <span>支持批量 PNG / WebP，单次最多 {{ MATERIAL_ASSET_MAX_COUNT }} 张</span>
          <small>将校验透明背景、主体居中与输出文件大小。</small>
        </label>

        <div
          v-if="loading"
          class="asset-queue-skeleton"
        >
          <i
            v-for="item in 4"
            :key="item"
          />
        </div>
        <PageEmptyState
          v-else-if="!queue.length"
          title="暂无待处理素材"
          message="选择已完成抠图的材料图片；处理结果会同时显示在浅色与深色背景中。"
        />
        <div
          v-else
          class="asset-queue"
        >
          <article
            v-for="(item, index) in queue"
            :key="item.id"
            class="asset-row"
            :class="`is-${item.status}`"
          >
            <span class="asset-row__order">{{ index + 1 }}</span>
            <div class="asset-row__preview">
              <div>
                <img
                  v-if="item.previewUrl"
                  :src="item.previewUrl"
                  :alt="item.name"
                ><small>浅底</small>
              </div>
              <div>
                <img
                  v-if="item.previewUrl"
                  :src="item.previewUrl"
                  :alt="item.name"
                ><small>深底</small>
              </div>
            </div>
            <div class="asset-row__copy">
              <strong>{{ item.name }}</strong>
              <p
                v-if="item.error"
                class="is-error"
              >
                {{ item.error }}
              </p>
              <p v-else-if="item.blob">
                {{ item.sourceWidth }} × {{ item.sourceHeight }} · {{ byteLabel(item.blob.size) }} · 占比 {{ ((item.metrics?.fillRatio || 0) * 100).toFixed(1) }}%
              </p>
              <p v-else>
                正在读取透明通道与主体边界
              </p>
            </div>
            <span class="asset-row__state">{{ statusLabel(item.status) }}</span>
            <div class="asset-row__actions">
              <button
                type="button"
                :disabled="busy || index === 0"
                @click="move(index, -1)"
              >
                上移
              </button>
              <button
                type="button"
                :disabled="busy || index === queue.length - 1"
                @click="move(index, 1)"
              >
                下移
              </button>
              <button
                type="button"
                :disabled="!item.blob"
                @click="download(item)"
              >
                下载
              </button>
              <button
                class="danger-text"
                type="button"
                :disabled="busy"
                @click="remove(item)"
              >
                移除
              </button>
            </div>
          </article>
        </div>

        <footer
          v-if="queue.length"
          class="asset-actions"
        >
          <button
            type="button"
            :disabled="busy"
            @click="clear"
          >
            清空队列
          </button>
          <button
            class="primary-action"
            type="button"
            :disabled="!canManage || busy || !ready"
            @click="upload"
          >
            {{ busy ? '处理中…' : '上传处理结果' }}
          </button>
          <button
            class="primary-action"
            type="button"
            :disabled="!canManage || busy || !bindable"
            @click="bind"
          >
            {{ mode === 'append' ? '追加到品种图库' : '替换品种图库' }}
          </button>
        </footer>
        <p
          v-if="notice"
          class="asset-notice"
          :class="{ 'is-error': notice.includes('失败') || notice.includes('最多') }"
        >
          {{ notice }}
        </p>
      </main>
    </div>
  </section>
</template>
