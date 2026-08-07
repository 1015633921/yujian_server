<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'

import ActionConfirmDialog from '@/components/ui/ActionConfirmDialog.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import {
  getCustomDesignCandidates,
  getCustomDesignWorkbench,
  listCustomDesignMaterials,
  publishCustomDesignProposal,
  saveCustomDesignDraft,
} from '@/features/custom-design/api'
import type {
  CustomDesignAdminMaterial,
  CustomDesignCandidateItem,
  CustomDesignCandidateResult,
  CustomDesignWorkbenchBootstrap,
  CustomDesignWorkbenchLayoutItem,
  CustomDesignWorkbenchPayload,
} from '@/features/custom-design/types'

interface LayoutItem {
  instanceId: string
  material: CustomDesignWorkbenchLayoutItem
  selectedImageUrl: string
}

const PAGE_SIZE = 24
const EDITABLE_STATUSES = new Set(['submitted', 'designing', 'revision_requested'])
const route = useRoute()
const router = useRouter()
const bootstrap = ref<CustomDesignWorkbenchBootstrap | null>(null)
const loading = ref(true)
const error = ref('')
const layout = ref<LayoutItem[]>([])
const wristSize = ref(16)
const beadSize = ref(8)
const notes = ref('')
const title = ref('专属手串方案')
const description = ref('')
const referenceImageUrl = ref('')
const keyword = ref('')
const materialTop = ref('')
const materialPage = ref(1)
const materials = ref<CustomDesignAdminMaterial[]>([])
const materialsTotal = ref(0)
const materialsHasNext = ref(false)
const materialsLoading = ref(false)
const materialsError = ref('')
const librarySelection = ref<CustomDesignAdminMaterial[]>([])
const candidates = ref<CustomDesignCandidateResult | null>(null)
const candidatesLoading = ref(false)
const candidatesError = ref('')
const saving = ref(false)
const publishing = ref(false)
const publishConfirmOpen = ref(false)
const notice = ref('')
const dirty = ref(false)
let bootstrapController: AbortController | null = null
let materialController: AbortController | null = null
let keywordTimer: ReturnType<typeof setTimeout> | null = null
let candidateVersion = 0
let materialVersion = 0
let instanceSequence = 0

const requestId = computed(() => String(route.params.requestId || '').trim())
const overview = computed(() => bootstrap.value?.overview)
const brief = computed(() => overview.value?.design_brief || {})
const editable = computed(() => EDITABLE_STATUSES.has(overview.value?.status || ''))
const sourceLabel = computed(() => ({ draft: '已恢复设计草稿', proposal: '已载入最近方案', empty: '从空白结构开始' }[bootstrap.value?.source_kind || 'empty'] || '已载入工作台'))
const totalFee = computed(() => layout.value.reduce((sum, item) => sum + materialPrice(item.material), 0))
const totalText = computed(() => `¥${totalFee.value.toFixed(2)}`)
const candidateGroups = computed(() => candidates.value?.candidate_groups || [])
const materialPageText = computed(() => materialsTotal.value ? `${materialsTotal.value} 件可设计材料` : '未找到匹配材料')
const selectedLibraryIds = computed(() => new Set(librarySelection.value.map((item) => materialId(item))))

function number(value: unknown, fallback = 0): number {
  const result = Number(value)
  return Number.isFinite(result) ? result : fallback
}

function text(value: unknown, fallback = ''): string {
  if (typeof value === 'string' || typeof value === 'number') return String(value).trim() || fallback
  return fallback
}

function data(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function materialId(material: CustomDesignWorkbenchLayoutItem): string {
  const sku = data(material.sku)
  return text(material.id || material.material_id || material.sku_id || material.skuId || sku.id, '')
}

function materialName(material: CustomDesignWorkbenchLayoutItem): string {
  const sku = data(material.sku)
  return text(material.name || sku.name || material.series || sku.series, materialId(material) || '未命名材料')
}

function materialSize(material: CustomDesignWorkbenchLayoutItem): number {
  const sku = data(material.sku)
  return number(material.size_mm ?? material.size ?? sku.size_mm, 0)
}

function materialPrice(material: CustomDesignWorkbenchLayoutItem): number {
  const sku = data(material.sku)
  return number(material.price ?? sku.price_per_bead, 0)
}

function materialTopValue(material: CustomDesignWorkbenchLayoutItem): string {
  const sku = data(material.sku)
  return text(material.top || sku.top).toLowerCase()
}

function availableStock(material: CustomDesignWorkbenchLayoutItem): number {
  const sku = data(material.sku)
  const ops = data((material as CustomDesignAdminMaterial).ops)
  const available = material.available_stock ?? sku.available_stock ?? ops.available_stock
  if (available !== undefined) return Math.max(0, number(available))
  return Math.max(0, number(material.stock ?? sku.stock) - number(material.reserved_stock ?? sku.reserved_stock))
}

function galleryImages(material: CustomDesignWorkbenchLayoutItem): string[] {
  const visual = data(material.visual)
  const sources = [material.gallery_image_urls, material.image_urls, visual.image_urls]
  const values: string[] = []
  for (const source of sources) {
    if (!Array.isArray(source)) continue
    for (const value of source) {
      const url = text(value)
      if (url && !values.includes(url)) values.push(url)
    }
  }
  return values
}

function supportsWorkbench(material: CustomDesignWorkbenchLayoutItem): boolean {
  const top = materialTopValue(material)
  if (!['bead', 'accessory'].includes(top) || availableStock(material) <= 0 || !galleryImages(material).length) return false
  return top === 'accessory' || Math.abs(materialSize(material) - beadSize.value) < 0.01
}

function nextInstanceId(): string {
  instanceSequence += 1
  return `layout-${Date.now().toString(36)}-${instanceSequence.toString(36)}`
}

function restoredLayout(items: CustomDesignWorkbenchLayoutItem[]): LayoutItem[] {
  return items.map((material) => {
    const choices = galleryImages(material)
    const selected = text(material.selected_image_url || material.image_url)
    return {
      instanceId: nextInstanceId(),
      material,
      selectedImageUrl: choices.includes(selected) ? selected : choices[0] || selected,
    }
  }).filter((item) => Boolean(materialId(item.material) && item.selectedImageUrl))
}

function markDirty(): void {
  dirty.value = true
  notice.value = ''
}

function workbenchPayload(): CustomDesignWorkbenchPayload {
  return {
    wrist_size_cm: wristSize.value,
    bead_size_mm: beadSize.value,
    notes: notes.value.trim(),
    layout: layout.value.map((item) => ({
      id: materialId(item.material),
      material_id: materialId(item.material),
      price: materialPrice(item.material),
      quantity: 1,
      selected_image_url: item.selectedImageUrl,
    })),
  }
}

function ringPosition(index: number): Record<string, string> {
  const count = Math.max(1, layout.value.length)
  const angle = (index / count) * Math.PI * 2 - Math.PI / 2
  const x = 50 + Math.cos(angle) * 39
  const y = 50 + Math.sin(angle) * 39
  return { left: `${x}%`, top: `${y}%` }
}

function validateMetadata(): void {
  wristSize.value = Math.min(25, Math.max(10, Math.round(wristSize.value * 2) / 2))
  beadSize.value = Math.min(16, Math.max(6, Math.round(beadSize.value)))
  markDirty()
  materialPage.value = 1
  void loadMaterials()
  void loadCandidates()
}

async function loadWorkbench(): Promise<void> {
  bootstrapController?.abort()
  bootstrapController = new AbortController()
  loading.value = true
  error.value = ''
  try {
    const result = await getCustomDesignWorkbench(requestId.value, bootstrapController.signal)
    bootstrap.value = result
    const saved = result.workbench || {}
    layout.value = restoredLayout(Array.isArray(saved.layout) ? saved.layout : [])
    wristSize.value = Math.min(25, Math.max(10, number(saved.wrist_size_cm, number(result.overview.request?.wrist_size_cm, 16))))
    beadSize.value = Math.min(16, Math.max(6, number(saved.bead_size_mm, number(result.overview.request?.bead_size_mm, 8))))
    notes.value = text(saved.notes)
    title.value = text(result.proposal?.title, '专属手串方案')
    description.value = text(result.proposal?.description)
    referenceImageUrl.value = Array.isArray(result.proposal?.image_urls) ? text(result.proposal?.image_urls?.[0]) : ''
    dirty.value = false
    notice.value = ''
    await Promise.all([loadMaterials(), loadCandidates()])
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') return
    error.value = cause instanceof Error ? cause.message : '设计工作台加载失败'
  } finally {
    loading.value = false
  }
}

async function loadMaterials(): Promise<void> {
  const version = ++materialVersion
  materialController?.abort()
  materialController = new AbortController()
  materialsLoading.value = true
  materialsError.value = ''
  try {
    const page = await listCustomDesignMaterials({
      keyword: keyword.value,
      top: materialTop.value,
      page: materialPage.value,
      pageSize: PAGE_SIZE,
    }, materialController.signal)
    if (version !== materialVersion) return
    materials.value = (page.items || []).filter(supportsWorkbench)
    materialsTotal.value = number(page.pagination?.total, materials.value.length)
    materialsHasNext.value = Boolean(page.pagination?.has_next)
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') return
    materials.value = []
    materialsTotal.value = 0
    materialsHasNext.value = false
    materialsError.value = cause instanceof Error ? cause.message : '材料库读取失败'
  } finally {
    if (version === materialVersion) materialsLoading.value = false
  }
}

async function loadCandidates(): Promise<void> {
  if (!bootstrap.value || !editable.value) return
  const version = ++candidateVersion
  candidatesLoading.value = true
  candidatesError.value = ''
  try {
    const result = await getCustomDesignCandidates(requestId.value, {
      selected_material_ids: layout.value.map((item) => materialId(item.material)).filter(Boolean),
      wrist_size_cm: wristSize.value,
      bead_size_mm: beadSize.value,
    })
    if (version === candidateVersion) candidates.value = result
  } catch (cause) {
    if (version !== candidateVersion) return
    candidates.value = null
    candidatesError.value = cause instanceof Error ? cause.message : '候选材料暂时无法读取'
  } finally {
    if (version === candidateVersion) candidatesLoading.value = false
  }
}

function addMaterial(material: CustomDesignWorkbenchLayoutItem, selectedImage = '', refreshCandidates = true): void {
  if (!editable.value) return
  const image = selectedImage || galleryImages(material)[0]
  if (!image) return
  layout.value.push({ instanceId: nextInstanceId(), material, selectedImageUrl: image })
  markDirty()
  if (refreshCandidates) void loadCandidates()
}

function toggleLibraryMaterial(material: CustomDesignAdminMaterial): void {
  if (!editable.value) return
  const id = materialId(material)
  if (!id) return
  if (selectedLibraryIds.value.has(id)) {
    librarySelection.value = librarySelection.value.filter((item) => materialId(item) !== id)
  } else {
    librarySelection.value = [...librarySelection.value, material]
  }
}

function addSelectedLibraryMaterials(): void {
  if (!editable.value || !librarySelection.value.length) return
  let added = false
  for (const material of librarySelection.value) {
    if (!supportsWorkbench(material)) continue
    addMaterial(material, '', false)
    added = true
  }
  librarySelection.value = []
  if (added) void loadCandidates()
}

function clearLibrarySelection(): void {
  librarySelection.value = []
}

function addCandidate(candidate: CustomDesignCandidateItem): void {
  addMaterial({
    id: candidate.material_id,
    material_id: candidate.material_id,
    name: candidate.name,
    top: candidate.top,
    price: candidate.price,
    size_mm: candidate.size_mm,
    image_urls: candidate.image_url ? [candidate.image_url] : [],
    gallery_image_urls: candidate.image_url ? [candidate.image_url] : [],
    stock: candidate.available_stock,
  }, candidate.image_url || '')
}

function removeMaterial(instanceId: string): void {
  layout.value = layout.value.filter((item) => item.instanceId !== instanceId)
  markDirty()
  void loadCandidates()
}

function moveMaterial(instanceId: string, direction: -1 | 1): void {
  const index = layout.value.findIndex((item) => item.instanceId === instanceId)
  const target = index + direction
  if (index < 0 || target < 0 || target >= layout.value.length) return
  const next = [...layout.value]
  const current = next[index]
  const replacement = next[target]
  if (!current || !replacement) return
  next[index] = replacement
  next[target] = current
  layout.value = next
  markDirty()
}

function selectImage(instanceId: string, image: string): void {
  const item = layout.value.find((value) => value.instanceId === instanceId)
  if (!item || !image) return
  item.selectedImageUrl = image
  markDirty()
}

async function saveDraft(): Promise<void> {
  if (!layout.value.length || saving.value || publishing.value) return
  saving.value = true
  notice.value = ''
  try {
    const result = await saveCustomDesignDraft(requestId.value, workbenchPayload())
    if (bootstrap.value) bootstrap.value = { ...bootstrap.value, overview: result, source_kind: 'draft' }
    dirty.value = false
    notice.value = '草稿已保存，材料价格与图库已完成复核。'
  } catch (cause) {
    notice.value = cause instanceof Error ? cause.message : '草稿保存失败'
  } finally {
    saving.value = false
  }
}

function requestPublish(): void {
  if (!layout.value.length || !title.value.trim() || saving.value || publishing.value) return
  publishConfirmOpen.value = true
}

async function publishProposal(): Promise<void> {
  if (!layout.value.length || !title.value.trim() || saving.value || publishing.value) return
  publishing.value = true
  notice.value = ''
  try {
    await publishCustomDesignProposal(requestId.value, {
      title: title.value.trim(),
      description: description.value.trim(),
      image_urls: referenceImageUrl.value.trim() ? [referenceImageUrl.value.trim()] : [],
      workbench: workbenchPayload(),
    })
    dirty.value = false
    publishConfirmOpen.value = false
    await router.replace({ name: 'design-request-detail', params: { requestId: requestId.value } })
  } catch (cause) {
    notice.value = cause instanceof Error ? cause.message : '方案发布失败'
  } finally {
    publishing.value = false
  }
}

function changePage(direction: -1 | 1): void {
  const next = materialPage.value + direction
  if (next < 1 || (direction > 0 && !materialsHasNext.value)) return
  materialPage.value = next
  void loadMaterials()
}

watch([keyword, materialTop], () => {
  if (loading.value) return
  if (keywordTimer) clearTimeout(keywordTimer)
  keywordTimer = setTimeout(() => {
    materialPage.value = 1
    void loadMaterials()
  }, 260)
})

watch(requestId, () => void loadWorkbench(), { immediate: true })
onBeforeRouteLeave(() => !dirty.value || window.confirm('当前修改尚未保存，确认离开设计工作台吗？'))
onBeforeUnmount(() => {
  bootstrapController?.abort()
  materialController?.abort()
  if (keywordTimer) clearTimeout(keywordTimer)
})
</script>

<template>
  <section class="workspace-page designer-workbench-page">
    <RouterLink
      class="detail-back"
      :to="{ name: 'design-request-detail', params: { requestId } }"
    >
      ← 返回工单详情
    </RouterLink>

    <div
      v-if="loading"
      class="design-detail-skeleton"
      aria-label="正在加载设计师工作台"
    >
      <i /><i /><i />
    </div>

    <PageErrorState
      v-else-if="error"
      eyebrow="WORKBENCH UNAVAILABLE"
      title="设计师工作台暂时无法读取"
      :message="error"
      @retry="loadWorkbench"
    />

    <template v-else-if="overview">
      <header class="workbench-heading">
        <div>
          <span>DESIGNER WORKBENCH · {{ overview.report_code || overview.report_id }}</span>
          <h1>结构化成串设计</h1>
          <p>{{ sourceLabel }}。保存和发布时，系统会重新校验真实库存、价格与图库图片。</p>
        </div>
        <div>
          <strong>{{ layout.length }}<small>颗</small></strong>
          <span>{{ totalText }}</span>
        </div>
      </header>

      <p
        v-if="notice"
        class="workbench-notice"
        :class="{ 'is-error': notice.includes('失败') || notice.includes('无效') || notice.includes('不能') }"
        role="alert"
      >
        {{ notice }}
      </p>

      <div
        v-if="!editable"
        class="workbench-readonly"
      >
        此服务单当前为「{{ overview.status }}」状态，不能继续编辑；可在详情页查看已发布方案。
      </div>

      <div class="workbench-grid">
        <section class="workbench-stage">
          <div class="workbench-stage__head">
            <div><span>LIVE STRUCTURE</span><strong>{{ brief.design_goal?.title || '按设计 Brief 完成逐颗排布' }}</strong></div>
            <small>预算 {{ overview.request?.budget || '待确认' }}</small>
          </div>

          <div
            class="workbench-ring"
            :class="{ 'is-empty': !layout.length }"
          >
            <div v-if="!layout.length">
              从右侧材料库或候选建议加入材料
            </div>
            <img
              v-for="(item, index) in layout"
              v-else
              :key="item.instanceId"
              :src="item.selectedImageUrl"
              :alt="materialName(item.material)"
              :style="ringPosition(index)"
            >
          </div>

          <div class="workbench-brief">
            <div
              v-for="role in brief.material_roles || []"
              :key="role.key || role.label"
            >
              <span>{{ role.label }}</span><strong>{{ role.element || '审美主导' }}</strong><p>{{ role.reason || role.purpose }}</p>
            </div>
          </div>

          <div class="workbench-fields">
            <label>手围
              <select
                v-model.number="wristSize"
                :disabled="!editable"
                @change="validateMetadata"
              >
                <option
                  v-for="value in [14, 14.5, 15, 15.5, 16, 16.5, 17, 17.5, 18, 18.5, 19, 19.5, 20]"
                  :key="value"
                  :value="value"
                >{{ value }} cm</option>
              </select>
            </label>
            <label>珠径
              <select
                v-model.number="beadSize"
                :disabled="!editable"
                @change="validateMetadata"
              >
                <option
                  v-for="value in [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]"
                  :key="value"
                  :value="value"
                >{{ value }} mm</option>
              </select>
            </label>
            <label class="workbench-fields__wide">设计备注
              <textarea
                v-model="notes"
                :disabled="!editable"
                maxlength="1000"
                placeholder="记录结构、配色与配饰逻辑"
                @input="markDirty"
              />
            </label>
          </div>
        </section>

        <aside class="workbench-candidates">
          <div class="workbench-panel-heading">
            <span>BRIEF CANDIDATES</span><strong>设计候选</strong><small>候选仅供参考，不会自动加入方案。</small>
          </div>
          <p v-if="candidatesLoading">
            正在按本单规格、设计 Brief 与实时库存整理候选…
          </p>
          <p
            v-else-if="candidatesError"
            class="detail-region-error"
          >
            {{ candidatesError }}
          </p>
          <template v-else-if="candidates?.status === 'ready'">
            <p>{{ candidates.message }}</p>
            <div
              v-for="group in candidateGroups"
              :key="group.role || group.label"
              class="candidate-group"
            >
              <span>{{ group.label }}</span>
              <button
                v-for="candidate in group.items || []"
                :key="candidate.material_id"
                type="button"
                :disabled="!editable"
                @click="addCandidate(candidate)"
              >
                <img
                  :src="candidate.image_url"
                  :alt="candidate.name || candidate.material_id"
                >
                <b>{{ candidate.name || candidate.material_id }}</b>
                <small>{{ candidate.top === 'accessory' ? '配饰' : `${candidate.size_mm || '-'} mm` }} · ¥{{ Number(candidate.price || 0).toFixed(2) }}</small>
                <i>＋</i>
              </button>
            </div>
          </template>
          <p v-else>
            候选资料暂不可用；可直接从材料库选择。
          </p>
        </aside>
      </div>

      <section class="workbench-library">
        <div class="workbench-panel-heading">
          <span>LIVE MATERIAL LIBRARY</span><strong>材料库</strong><small>{{ materialPageText }} · 仅展示有图库且有可用库存的匹配材料</small>
        </div>
        <div class="workbench-library__tools">
          <input
            v-model="keyword"
            :disabled="!editable"
            placeholder="搜索品种、分类或材料编码"
          >
          <select
            v-model="materialTop"
            :disabled="!editable"
          >
            <option value="">
              珠子与配饰
            </option><option value="bead">
              珠子
            </option><option value="accessory">
              配饰
            </option>
          </select>
        </div>
        <div
          v-if="librarySelection.length"
          class="workbench-library__selection"
        >
          <div>
            <strong>已选 {{ librarySelection.length }} 种材料</strong>
            <span>{{ librarySelection.map(materialName).join(' · ') }}</span>
          </div>
          <button
            type="button"
            :disabled="!editable"
            @click="clearLibrarySelection"
          >
            清除
          </button>
          <button
            class="primary-action"
            type="button"
            :disabled="!editable"
            @click="addSelectedLibraryMaterials"
          >
            加入逐颗排布
          </button>
        </div>
        <p v-if="materialsLoading">
          正在读取第 {{ materialPage }} 页材料…
        </p>
        <p
          v-else-if="materialsError"
          class="detail-region-error"
        >
          {{ materialsError }}
        </p>
        <div
          v-else-if="materials.length"
          class="workbench-materials"
        >
          <button
            v-for="material in materials"
            :key="material.id"
            type="button"
            :disabled="!editable"
            :class="{ 'is-selected': selectedLibraryIds.has(materialId(material)) }"
            :aria-pressed="selectedLibraryIds.has(materialId(material))"
            @click="toggleLibraryMaterial(material)"
          >
            <img
              :src="galleryImages(material)[0]"
              :alt="materialName(material)"
            >
            <span><b>{{ materialName(material) }}</b><small>{{ materialTopValue(material) === 'accessory' ? '配饰' : `${materialSize(material)} mm` }} · ¥{{ materialPrice(material).toFixed(2) }} · 可用 {{ availableStock(material) }}</small></span><i>{{ selectedLibraryIds.has(materialId(material)) ? '✓' : '＋' }}</i>
          </button>
        </div>
        <div
          v-else
          class="workbench-empty"
        >
          没有匹配的可设计材料。
        </div>
        <nav
          class="workbench-pagination"
          aria-label="材料库分页"
        >
          <button
            type="button"
            :disabled="materialsLoading || materialPage === 1"
            @click="changePage(-1)"
          >
            ← 上一页
          </button><span>第 {{ materialPage }} 页</span><button
            type="button"
            :disabled="materialsLoading || !materialsHasNext"
            @click="changePage(1)"
          >
            下一页 →
          </button>
        </nav>
      </section>

      <section class="workbench-sequence">
        <div class="workbench-panel-heading">
          <span>BEAD-BY-BEAD LAYOUT</span><strong>逐颗排布</strong><small>顺序即用户工作台中的手串顺序。</small>
        </div>
        <div
          v-if="!layout.length"
          class="workbench-empty"
        >
          尚未添加材料。
        </div>
        <div
          v-else
          class="workbench-sequence__list"
        >
          <article
            v-for="(item, index) in layout"
            :key="item.instanceId"
            :data-instance-id="item.instanceId"
          >
            <span>{{ index + 1 }}</span><img
              :src="item.selectedImageUrl"
              :alt="materialName(item.material)"
            >
            <div>
              <strong>{{ materialName(item.material) }}</strong><small>{{ materialTopValue(item.material) === 'accessory' ? '配饰' : `${materialSize(item.material)} mm` }} · ¥{{ materialPrice(item.material).toFixed(2) }}</small><select
                :value="item.selectedImageUrl"
                :disabled="!editable"
                @change="selectImage(item.instanceId, ($event.target as HTMLSelectElement).value)"
              >
                <option
                  v-for="image in galleryImages(item.material)"
                  :key="image"
                  :value="image"
                >
                  图库图 {{ galleryImages(item.material).indexOf(image) + 1 }}
                </option>
              </select>
            </div>
            <div class="sequence-actions">
              <button
                type="button"
                aria-label="上移当前材料"
                :disabled="!editable || index === 0"
                @click="moveMaterial(item.instanceId, -1)"
              >
                ↑
              </button><button
                type="button"
                aria-label="下移当前材料"
                :disabled="!editable || index === layout.length - 1"
                @click="moveMaterial(item.instanceId, 1)"
              >
                ↓
              </button><button
                type="button"
                aria-label="移除当前材料"
                :disabled="!editable"
                @click="removeMaterial(item.instanceId)"
              >
                ×
              </button>
            </div>
          </article>
        </div>
      </section>

      <section class="workbench-publish">
        <div class="workbench-panel-heading">
          <span>USER-FACING PROPOSAL</span><strong>发布给用户</strong><small>发布会建立一版新方案，并将服务单转为待用户确认。</small>
        </div>
        <div class="workbench-publish__form">
          <label>方案名称<input
            v-model="title"
            :disabled="!editable"
            maxlength="160"
            @input="markDirty"
          ></label>
          <label>方案参考图（可选）<input
            v-model="referenceImageUrl"
            :disabled="!editable"
            type="url"
            placeholder="https://"
            @input="markDirty"
          ></label>
          <label>给用户的设计说明<textarea
            v-model="description"
            :disabled="!editable"
            maxlength="2000"
            placeholder="说明主材、配色、结构与佩戴感"
            @input="markDirty"
          /></label>
        </div>
        <div class="workbench-actions">
          <button
            type="button"
            :disabled="!editable || !layout.length || saving || publishing"
            @click="saveDraft"
          >
            {{ saving ? '保存中…' : '保存草稿' }}
          </button><button
            type="button"
            :disabled="!editable || !layout.length || !title.trim() || saving || publishing"
            @click="requestPublish"
          >
            {{ publishing ? '发布中…' : '发布给用户 →' }}
          </button>
        </div>
      </section>
      <ActionConfirmDialog
        :open="publishConfirmOpen"
        title="确认发布方案给用户"
        description="发布会创建新的方案版本，并将服务单转为待用户确认。材料价格、库存和图库会在提交时再次校验。"
        confirm-label="确认发布"
        :busy="publishing"
        @close="publishConfirmOpen = false"
        @confirm="publishProposal"
      >
        <dl>
          <div><dt>方案名称</dt><dd>{{ title }}</dd></div>
          <div><dt>材料数量</dt><dd>{{ layout.length }} 颗</dd></div>
          <div><dt>预计价格</dt><dd>{{ totalText }}</dd></div>
          <div><dt>佩戴参数</dt><dd>{{ wristSize }} cm · {{ beadSize }} mm</dd></div>
        </dl>
        <p class="action-confirm__note">
          发布后会保留当前材料、价格和图片快照；后续修改将建立新版本，不会覆盖本次方案。
        </p>
      </ActionConfirmDialog>
    </template>
  </section>
</template>
