<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import PageEmptyState from '@/components/ui/PageEmptyState.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import {
  deleteEmptyMaterialCategory,
  deleteEmptyMaterialSeries,
  deleteEmptyMaterialType,
  disableMaterialTaxonomyItem,
  disableMaterialType,
  listMaterialOptions,
  listMaterialTaxonomyPage,
  listMaterialTypes,
  saveMaterialCategory,
  saveMaterialSeries,
  saveMaterialType,
  updateMaterialSeries,
  type MaterialDirectoryCategoryOption,
  type MaterialOptionsPayload,
  type MaterialSeries,
  type MaterialType,
} from '@/features/materials/api'
import { useAuthStore } from '@/stores/auth'

type EditorKind = 'type' | 'category' | 'series'

interface DirectoryEditor {
  kind: EditorKind
  id: string
  parentId: string
  code: string
  name: string
  description: string
  sortOrder: number
  color: string
  shine: string
  enabled: boolean
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const types = ref<MaterialType[]>([])
const seriesRows = ref<MaterialSeries[]>([])
const categoryOptions = ref<MaterialDirectoryCategoryOption[]>([])
const materialOptions = ref<MaterialOptionsPayload | null>(null)
const loading = ref(true)
const error = ref('')
const notice = ref('')
const saving = ref(false)
const total = ref(0)
const hasNext = ref(false)
const wasEnabled = ref(true)
const editor = reactive<DirectoryEditor>({
  kind: 'category',
  id: '',
  parentId: '',
  code: '',
  name: '',
  description: '',
  sortOrder: 0,
  color: '#dfe3e5',
  shine: '#ffffff',
  enabled: true,
})
let typesController: AbortController | null = null
let directoryController: AbortController | null = null
let directoryRequest = 0

const canManage = computed(() => auth.admin?.role !== 'viewer')
const selectedTop = computed(() => (typeof route.query.top === 'string' ? route.query.top : ''))
const selectedType = computed(() => types.value.find((item) => item.code === selectedTop.value) || null)
const keyword = computed(() => (typeof route.query.keyword === 'string' ? route.query.keyword : ''))
const categoryId = computed(() => (typeof route.query.category_id === 'string' ? route.query.category_id : ''))
const status = computed(() => (typeof route.query.status === 'string' ? route.query.status : ''))
const element = computed(() => (typeof route.query.element === 'string' ? route.query.element : ''))
const chakra = computed(() => (typeof route.query.chakra === 'string' ? route.query.chakra : ''))
const colorFamily = computed(() => (typeof route.query.color_family === 'string' ? route.query.color_family : ''))
const assetState = computed(() => (typeof route.query.asset_state === 'string' ? route.query.asset_state : ''))
const page = computed(() => Math.max(1, Number(route.query.page) || 1))
const visibleCategoryCount = computed(() => new Set(seriesRows.value.map((item) => item.parent_id)).size)
const selectedCategory = computed(() => categoryOptions.value.find((item) => item.id === categoryId.value) || null)

function updateQuery(updates: Record<string, string | undefined>): void {
  const query = { ...route.query }
  Object.entries(updates).forEach(([key, value]) => {
    if (value) query[key] = value
    else delete query[key]
  })
  void router.replace({ query })
}

function elementLabel(value?: string): string {
  return ({ metal: '金', wood: '木', water: '水', fire: '火', earth: '土', 金: '金', 木: '木', 水: '水', 火: '火', 土: '土' } as Record<string, string>)[value || ''] || '待补五行'
}

function optionLabel(type: keyof MaterialOptionsPayload, value?: string): string {
  if (!value) return '待补'
  return materialOptions.value?.[type]?.find((item) => item.key === value)?.label || value
}

function optionLabels(type: keyof MaterialOptionsPayload, values?: string[]): string {
  const labels = (values || []).map((value) => optionLabel(type, value)).filter(Boolean)
  return labels.length ? labels.join('、') : '待补'
}

function setTop(top: string): void {
  updateQuery({ top: top || undefined, category_id: undefined, page: undefined })
}

function resetEditor(kind: EditorKind, parentId = ''): void {
  Object.assign(editor, {
    kind,
    id: '',
    parentId,
    code: '',
    name: '',
    description: '',
    sortOrder: 0,
    color: '#dfe3e5',
    shine: '#ffffff',
    enabled: true,
  })
  wasEnabled.value = true
  notice.value = ''
}

function editType(item: MaterialType): void {
  Object.assign(editor, {
    kind: 'type',
    id: item.id,
    parentId: '',
    code: item.code,
    name: item.name,
    description: item.description,
    sortOrder: item.sort_order,
    color: '#dfe3e5',
    shine: '#ffffff',
    enabled: item.enabled,
  })
  wasEnabled.value = item.enabled
}

function editCategory(item: Pick<MaterialDirectoryCategoryOption, 'id' | 'name' | 'sort_order' | 'enabled'>): void {
  Object.assign(editor, {
    kind: 'category',
    id: item.id,
    parentId: '',
    code: '',
    name: item.name,
    description: '',
    sortOrder: item.sort_order,
    color: '#dfe3e5',
    shine: '#ffffff',
    enabled: item.enabled,
  })
  wasEnabled.value = item.enabled
}

function categorySortLabel(item: Pick<MaterialDirectoryCategoryOption, 'sort_order'>): string {
  const value = Number(item.sort_order || 0)
  return value > 0 ? String(value) : '未设置'
}

function editSeries(item: MaterialSeries): void {
  Object.assign(editor, {
    kind: 'series',
    id: item.id,
    parentId: item.parent_id,
    code: item.material_code || '',
    name: item.name,
    description: '',
    sortOrder: item.sort_order,
    color: item.color || '#dfe3e5',
    shine: item.shine || '#ffffff',
    enabled: item.enabled,
  })
  wasEnabled.value = item.enabled
}

function selectedCategoryName(): string {
  return categoryOptions.value.find((item) => item.id === editor.parentId)?.name || '未选择分类'
}

async function requestWithTimeout<T>(
  request: (signal: AbortSignal) => Promise<T>,
  controller: AbortController,
  timeoutMessage: string,
): Promise<T> {
  const timeout = window.setTimeout(() => controller.abort('timeout'), 10_000)
  try {
    return await request(controller.signal)
  } catch (cause) {
    if (controller.signal.reason === 'timeout') throw new Error(`${timeoutMessage}，请重试。`)
    throw cause
  } finally {
    window.clearTimeout(timeout)
  }
}

async function loadTypes(): Promise<void> {
  typesController?.abort()
  typesController = new AbortController()
  loading.value = true
  error.value = ''
  try {
    const nextTypes = await requestWithTimeout(
      (signal) => listMaterialTypes(true, signal),
      typesController,
      '材料类型加载超时',
    )
    types.value = nextTypes
    const firstType = nextTypes.at(0)
    if (!selectedTop.value && firstType) setTop(firstType.code)
    else if (selectedTop.value) await loadDirectory()
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') return
    error.value = cause instanceof Error ? cause.message : '材料三级目录加载失败'
  } finally {
    loading.value = false
  }
}

async function loadDirectory(): Promise<void> {
  directoryController?.abort()
  const currentController = new AbortController()
  directoryController = currentController
  const requestId = ++directoryRequest
  if (!selectedTop.value) {
    seriesRows.value = []
    categoryOptions.value = []
    loading.value = false
    return
  }
  loading.value = true
  error.value = ''
  try {
    const [result, options] = await requestWithTimeout(
      (signal) => Promise.all([
        listMaterialTaxonomyPage({
          keyword: keyword.value,
          top: selectedTop.value,
          categoryId: categoryId.value,
          status: status.value,
          element: element.value,
          chakra: chakra.value,
          colorFamily: colorFamily.value,
          assetState: assetState.value,
          page: page.value,
          pageSize: 20,
        }, signal),
        materialOptions.value ? Promise.resolve(materialOptions.value) : listMaterialOptions(signal),
      ]),
      currentController,
      '目录分页加载超时',
    )
    if (requestId !== directoryRequest) return
    seriesRows.value = result.items
    categoryOptions.value = result.categories
    total.value = result.pagination.total
    hasNext.value = result.pagination.has_next
    materialOptions.value = options
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') return
    if (requestId === directoryRequest) error.value = cause instanceof Error ? cause.message : '材料目录加载失败'
  } finally {
    if (requestId === directoryRequest) loading.value = false
  }
}

async function load(): Promise<void> {
  await loadTypes()
}

async function save(): Promise<void> {
  if (!canManage.value || saving.value) return
  const name = editor.name.trim()
  if (!name) {
    notice.value = '请先填写名称。'
    return
  }
  if (editor.kind !== 'type' && !selectedTop.value) {
    notice.value = '请先选择一个材料类型。'
    return
  }
  if (editor.kind === 'series' && !editor.parentId) {
    notice.value = '请先选择所属分类。'
    return
  }
  if (wasEnabled.value && !editor.enabled) {
    const scope = editor.kind === 'type' ? '该类型下的分类、品种和 SKU' : editor.kind === 'category' ? '该分类下的品种和 SKU' : '该品种下的 SKU'
    if (!window.confirm(`停用后，${scope} 会同步停用，且不会自动恢复。确定继续吗？`)) {
      editor.enabled = true
      return
    }
  }
  saving.value = true
  notice.value = ''
  const creatingSeries = editor.kind === 'series' && !editor.id
  let createdSeries: MaterialSeries | null = null
  try {
    if (editor.kind === 'type') {
      const result = await saveMaterialType({
        ...(editor.id ? { id: editor.id } : { code: editor.code.trim() }),
        name,
        description: editor.description.trim(),
        sort_order: Number(editor.sortOrder) || 0,
        enabled: editor.enabled,
      })
      if (!selectedTop.value) setTop(result.code)
    } else if (editor.kind === 'category') {
      await saveMaterialCategory({
        ...(editor.id ? { id: editor.id } : {}),
        top: selectedTop.value,
        name,
        sort_order: Number(editor.sortOrder) || 0,
        enabled: editor.enabled,
      })
    } else {
      const payload = {
        category_id: editor.parentId,
        name,
        ...(editor.code.trim() ? { material_code: editor.code.trim() } : {}),
        color: editor.color,
        shine: editor.shine,
        sort_order: Number(editor.sortOrder) || 0,
        enabled: editor.enabled,
      }
      if (editor.id) await updateMaterialSeries(editor.id, payload)
      else createdSeries = await saveMaterialSeries(payload)
    }
    notice.value = '目录已保存，相关 SKU 将继续引用此层级。'
    wasEnabled.value = editor.enabled
    if (creatingSeries && createdSeries) {
      await router.push({ name: 'material-series-profile', params: { seriesId: createdSeries.id } })
      return
    }
    await load()
  } catch (cause) {
    notice.value = cause instanceof Error ? cause.message : '保存失败，请稍后重试。'
  } finally {
    saving.value = false
  }
}

async function disable(kind: EditorKind, id: string, name: string): Promise<void> {
  if (!canManage.value || saving.value) return
  const scope = kind === 'type' ? '该类型下的分类、品种和 SKU' : kind === 'category' ? '该分类下的品种和 SKU' : '该品种下的 SKU'
  if (!window.confirm(`停用「${name}」后，${scope} 会同步停用，且不会自动恢复。确定继续吗？`)) return
  saving.value = true
  notice.value = ''
  try {
    if (kind === 'type') await disableMaterialType(id)
    else await disableMaterialTaxonomyItem(id)
    notice.value = `已停用「${name}」，关联销售材料已同步不可用。`
    resetEditor('category')
    await load()
  } catch (cause) {
    notice.value = cause instanceof Error ? cause.message : '停用失败，请刷新后重试。'
  } finally {
    saving.value = false
  }
}

async function remove(kind: EditorKind, id: string, name: string): Promise<void> {
  if (!canManage.value || saving.value) return
  if (!window.confirm(`仅当「${name}」为空时才能删除。删除后无法恢复，确定继续吗？`)) return
  saving.value = true
  notice.value = ''
  try {
    if (kind === 'type') await deleteEmptyMaterialType(id)
    else if (kind === 'category') await deleteEmptyMaterialCategory(id)
    else await deleteEmptyMaterialSeries(id)
    notice.value = `已删除空${kind === 'type' ? '材料类型' : kind === 'category' ? '分类' : '品种'}「${name}」。`
    resetEditor('category')
    await load()
  } catch (cause) {
    notice.value = cause instanceof Error ? cause.message : '删除失败，请刷新后重试。'
  } finally {
    saving.value = false
  }
}

watch(selectedTop, (top, previousTop) => {
  if (editor.kind !== 'type') resetEditor('category')
  if (top && top !== previousTop) void loadDirectory()
})

watch([keyword, categoryId, status, element, chakra, colorFamily, assetState, page], () => {
  if (selectedTop.value) void loadDirectory()
})

void loadTypes()
onBeforeUnmount(() => {
  typesController?.abort()
  directoryController?.abort()
})
</script>

<template>
  <section class="workspace-page material-directory-page">
    <PageHeading
      eyebrow="MATERIAL DIRECTORY"
      title="材料三级目录"
      description="先维护类型、分类与品种，再为品种建立可销售的 SKU。目录状态会约束工作台和销售可用性。"
    >
      <template #actions>
        <RouterLink
          class="heading-link"
          :to="{ name: 'materials', query: selectedTop ? { top: selectedTop } : {} }"
        >
          查看 {{ selectedType?.name || '材料' }} SKU ↗
        </RouterLink>
      </template>
    </PageHeading>

    <PageErrorState
      v-if="error && !loading"
      title="材料三级目录暂时无法读取"
      :message="error"
      eyebrow="DIRECTORY UNAVAILABLE"
      @retry="load"
    />

    <div
      v-else
      class="material-directory"
      :aria-busy="loading"
    >
      <aside
        class="directory-types"
        aria-label="材料类型"
      >
        <div class="directory-types__head">
          <span>第一层</span>
          <button
            v-if="canManage"
            type="button"
            @click="resetEditor('type')"
          >
            新建类型
          </button>
        </div>
        <button
          v-for="item in types"
          :key="item.code"
          class="directory-type"
          :class="{ 'is-current': item.code === selectedTop, 'is-disabled': !item.enabled }"
          type="button"
          @click="setTop(item.code)"
        >
          <strong>{{ item.name }}</strong>
          <small>{{ item.category_count }} 分类 · {{ item.variety_count }} 品种 · {{ item.sku_count }} SKU</small>
        </button>
      </aside>

      <div class="directory-tree">
        <div class="directory-tree__summary">
          <div>
            <span>品种目录 · 分页查询</span>
            <h2>{{ selectedType?.name || '选择材料类型' }}</h2>
          </div>
          <p v-if="selectedType">
            共 {{ total }} 个品种 · 当前页覆盖 {{ visibleCategoryCount }} 个分类 · {{ selectedType.sku_count }} 个 SKU
          </p>
        </div>

        <section
          v-if="selectedType && categoryOptions.length"
          class="directory-category-order"
          aria-label="二级分类排序"
        >
          <header>
            <div>
              <span>SECOND LEVEL</span>
              <h3>二级分类排序</h3>
              <p>数值越大越靠前；0 表示未设置，会排在已设置分类之后。</p>
            </div>
            <button
              v-if="canManage"
              class="directory-category-order__create"
              type="button"
              @click="resetEditor('category')"
            >
              新建二级分类
            </button>
          </header>
          <div class="directory-category-order__list">
            <button
              v-for="item in categoryOptions"
              :key="item.id"
              class="directory-category-order__item"
              :class="{
                'is-current': editor.kind === 'category' && editor.id === item.id,
                'is-disabled': !item.enabled,
              }"
              type="button"
              @click="editCategory(item)"
            >
              <span class="directory-category-order__value">{{ categorySortLabel(item) }}</span>
              <span class="directory-category-order__name">
                <strong>{{ item.name }}</strong>
                <small>{{ item.series_count }} 个品种 · {{ item.enabled ? '已启用' : '已停用' }}</small>
              </span>
              <span class="directory-category-order__action">{{ canManage ? '设置排序' : '查看排序' }} →</span>
            </button>
          </div>
        </section>

        <form
          v-if="selectedType"
          class="directory-filters"
          @submit.prevent="updateQuery({ keyword: keyword || undefined, page: undefined })"
        >
          <input
            :value="keyword"
            type="search"
            placeholder="搜索品种、分类或材料编码"
            aria-label="搜索目录"
            @input="updateQuery({ keyword: ($event.target as HTMLInputElement).value.trim() || undefined, page: undefined })"
          >
          <select
            :value="categoryId"
            aria-label="按分类筛选"
            @change="updateQuery({ category_id: ($event.target as HTMLSelectElement).value || undefined, page: undefined })"
          >
            <option value="">
              全部分类
            </option>
            <option
              v-for="item in categoryOptions"
              :key="item.id"
              :value="item.id"
            >
              {{ item.name }}（{{ item.series_count }}）{{ item.enabled ? '' : ' · 已停用' }}
            </option>
          </select>
          <select
            :value="status"
            aria-label="按状态筛选"
            @change="updateQuery({ status: ($event.target as HTMLSelectElement).value || undefined, page: undefined })"
          >
            <option value="">
              全部状态
            </option><option value="enabled">
              已启用
            </option><option value="disabled">
              已停用
            </option>
          </select>
          <select
            :value="element"
            aria-label="按主五行筛选"
            @change="updateQuery({ element: ($event.target as HTMLSelectElement).value || undefined, page: undefined })"
          >
            <option value="">
              全部主五行
            </option>
            <option
              v-for="item in materialOptions?.elements || []"
              :key="item.key"
              :value="item.key"
            >
              {{ item.label }}
            </option>
          </select>
          <select
            :value="chakra"
            aria-label="按脉轮筛选"
            @change="updateQuery({ chakra: ($event.target as HTMLSelectElement).value || undefined, page: undefined })"
          >
            <option value="">
              全部脉轮
            </option>
            <option
              v-for="item in materialOptions?.chakras || []"
              :key="item.key"
              :value="item.key"
            >
              {{ item.label }}
            </option>
          </select>
          <select
            :value="colorFamily"
            aria-label="按色系筛选"
            @change="updateQuery({ color_family: ($event.target as HTMLSelectElement).value || undefined, page: undefined })"
          >
            <option value="">
              全部色系
            </option>
            <option
              v-for="item in materialOptions?.color_families || []"
              :key="item.key"
              :value="item.key"
            >
              {{ item.label }}
            </option>
          </select>
          <select
            :value="assetState"
            aria-label="按图片状态筛选"
            @change="updateQuery({ asset_state: ($event.target as HTMLSelectElement).value || undefined, page: undefined })"
          >
            <option value="">
              全部图片状态
            </option><option value="ready">
              已设主图
            </option><option value="missing">
              缺主图
            </option>
          </select>
          <button
            v-if="keyword || categoryId || status || element || chakra || colorFamily || assetState"
            class="text-action"
            type="button"
            @click="updateQuery({ keyword: undefined, category_id: undefined, status: undefined, element: undefined, chakra: undefined, color_family: undefined, asset_state: undefined, page: undefined })"
          >
            清除筛选
          </button>
          <button
            v-if="canManage"
            class="text-action"
            type="button"
            @click="resetEditor('category')"
          >
            新建分类
          </button>
          <button
            v-if="canManage && categoryOptions.length"
            class="text-action"
            type="button"
            @click="resetEditor('series', categoryId)"
          >
            新建品种
          </button>
          <button
            v-if="canManage && selectedCategory"
            class="text-action"
            type="button"
            @click="editCategory(selectedCategory)"
          >
            编辑当前分类
          </button>
          <button
            v-if="canManage && selectedCategory?.enabled"
            class="text-action danger-text"
            type="button"
            @click="disable('category', selectedCategory.id, selectedCategory.name)"
          >
            停用当前分类
          </button>
          <button
            v-if="canManage && selectedCategory"
            class="text-action danger-text"
            type="button"
            @click="remove('category', selectedCategory.id, selectedCategory.name)"
          >
            删除空分类
          </button>
          <button type="submit">
            查询
          </button>
        </form>

        <div
          v-if="loading"
          class="directory-skeleton"
          aria-label="正在加载目录"
        >
          <i
            v-for="item in 5"
            :key="item"
          />
        </div>
        <PageEmptyState
          v-else-if="!selectedType"
          title="尚未维护材料类型"
          message="先创建第一层材料类型，再建立分类与品种。"
          @clear="resetEditor('type')"
        >
          <template
            v-if="canManage"
            #action
          >
            新建材料类型
          </template>
        </PageEmptyState>
        <PageEmptyState
          v-else-if="!seriesRows.length"
          :title="categoryOptions.length ? '没有符合筛选条件的品种' : '此类型还没有分类'"
          :message="categoryOptions.length ? '调整筛选条件，或新建一个材料品种。' : `先为「${selectedType.name}」建立分类，SKU 才能选择到可用品种。`"
          @clear="categoryOptions.length ? updateQuery({ keyword: undefined, category_id: undefined, status: undefined, element: undefined, chakra: undefined, color_family: undefined, asset_state: undefined, page: undefined }) : resetEditor('category')"
        />
        <div
          v-else
          class="directory-series-list directory-series-list--paged"
        >
          <article
            v-for="series in seriesRows"
            :key="series.id"
            class="directory-series"
            :class="{ 'is-disabled': !series.enabled }"
          >
            <img
              v-if="series.image_url"
              :src="series.image_url"
              :alt="series.name"
            >
            <i
              v-else
              aria-hidden="true"
              :style="{ background: series.color || '#dfe3e5' }"
            />
            <div>
              <strong>{{ series.name }}</strong>
              <small>{{ series.category_name || '未分配分类' }} · 主五行：{{ elementLabel(series.energy?.primary_element) }} · {{ optionLabels('chakras', series.energy?.chakras) }} · {{ optionLabel('color_families', series.energy?.color_family) }}</small>
            </div>
            <span>{{ series.enabled ? '已启用' : '已停用' }} · {{ series.image_url ? '已设主图' : '缺主图' }}</span>
            <div class="directory-row-actions">
              <RouterLink
                class="directory-profile-link"
                :to="{ name: 'material-series-profile', params: { seriesId: series.id } }"
              >
                完善资料
              </RouterLink>
              <button
                v-if="canManage"
                type="button"
                @click="editSeries(series)"
              >
                编辑
              </button>
              <button
                v-if="canManage && series.enabled"
                class="danger-text"
                type="button"
                @click="disable('series', series.id, series.name)"
              >
                停用
              </button>
              <button
                v-if="canManage"
                class="danger-text"
                type="button"
                @click="remove('series', series.id, series.name)"
              >
                删除空品种
              </button>
            </div>
          </article>
        </div>
        <nav
          v-if="selectedType && total"
          class="design-pagination directory-pagination"
        >
          <button
            :disabled="page === 1"
            @click="updateQuery({ page: page > 2 ? String(page - 1) : undefined })"
          >
            ← 上一页
          </button>
          <span>第 {{ page }} 页 · 共 {{ total }} 个品种</span>
          <button
            :disabled="!hasNext"
            @click="updateQuery({ page: String(page + 1) })"
          >
            下一页 →
          </button>
        </nav>
      </div>

      <aside
        class="directory-editor"
        aria-label="目录编辑器"
      >
        <div class="directory-editor__head">
          <span>{{ editor.id ? 'EDIT DIRECTORY' : 'CREATE DIRECTORY' }}</span>
          <h2>{{ editor.kind === 'type' ? '材料类型' : editor.kind === 'category' ? '材料分类' : '材料品种' }}</h2>
          <p v-if="editor.kind === 'series'">
            所属分类：{{ selectedCategoryName() }}
          </p>
          <p v-else-if="editor.kind === 'category'">
            所属类型：{{ selectedType?.name || '请先选择' }}
          </p>
          <p v-else>
            类型编码创建后不可修改。
          </p>
        </div>

        <form
          class="directory-form"
          @submit.prevent="save"
        >
          <label v-if="editor.kind === 'type'">
            <span>类型编码</span>
            <input
              v-model.trim="editor.code"
              :disabled="Boolean(editor.id) || !canManage"
              maxlength="40"
              placeholder="例如 bead"
            >
          </label>
          <label v-if="editor.kind === 'series'">
            <span>所属分类</span>
            <select
              v-model="editor.parentId"
              :disabled="!canManage || Boolean(editor.id)"
            >
              <option value="">请选择分类</option>
              <option
                v-for="item in categoryOptions"
                :key="item.id"
                :value="item.id"
              >{{ item.name }}{{ item.enabled ? '' : '（已停用）' }}</option>
            </select>
          </label>
          <label>
            <span>{{ editor.kind === 'type' ? '类型名称' : editor.kind === 'category' ? '分类名称' : '品种名称' }}</span>
            <input
              v-model="editor.name"
              :disabled="!canManage"
              maxlength="160"
              placeholder="请输入名称"
            >
          </label>
          <label v-if="editor.kind === 'type'">
            <span>说明</span>
            <textarea
              v-model="editor.description"
              :disabled="!canManage"
              maxlength="500"
              placeholder="用于运营识别，不会展示给小程序用户"
            />
          </label>
          <div
            v-if="editor.kind === 'series'"
            class="directory-form__colors"
          >
            <label><span>基础色</span><input
              v-model="editor.color"
              :disabled="!canManage"
              type="color"
            ></label>
            <label><span>高光色</span><input
              v-model="editor.shine"
              :disabled="!canManage"
              type="color"
            ></label>
          </div>
          <label>
            <span>{{ editor.kind === 'category' ? '二级分类排序值（数值越大越靠前）' : '排序值' }}</span>
            <input
              v-model.number="editor.sortOrder"
              :disabled="!canManage"
              type="number"
              min="0"
              max="99999"
            >
          </label>
          <p
            v-if="editor.id && !editor.enabled"
            class="directory-form__warning"
          >
            该目录已停用。重新启用本项不会自动恢复已停用的子项或 SKU。
          </p>
          <label
            v-if="editor.id"
            class="directory-switch"
          >
            <input
              v-model="editor.enabled"
              :disabled="!canManage"
              type="checkbox"
            >
            <span>此目录可用</span>
          </label>
          <button
            class="primary-action"
            type="submit"
            :disabled="!canManage || saving"
          >
            {{ saving ? '正在保存…' : editor.kind === 'series' && !editor.id ? '创建并完善资料' : '保存目录' }}
          </button>
          <small v-if="editor.kind === 'series' && !editor.id">
            创建后将进入完整资料页，继续选择五行、功效、形制和养护等标准选项。
          </small>
          <p
            v-if="notice"
            class="directory-notice"
            :class="{ 'is-error': notice.includes('失败') || notice.includes('请先') || notice.includes('不能为空') }"
          >
            {{ notice }}
          </p>
        </form>

        <div
          v-if="selectedType && editor.kind !== 'type'"
          class="directory-editor__type-actions"
        >
          <span>当前类型</span>
          <strong>{{ selectedType.name }}</strong>
          <div class="directory-row-actions">
            <button
              v-if="canManage"
              type="button"
              @click="editType(selectedType)"
            >
              编辑类型
            </button>
            <button
              v-if="canManage && selectedType.enabled"
              class="danger-text"
              type="button"
              @click="disable('type', selectedType.code, selectedType.name)"
            >
              停用类型
            </button>
            <button
              v-if="canManage"
              class="danger-text"
              type="button"
              @click="remove('type', selectedType.code, selectedType.name)"
            >
              删除空类型
            </button>
          </div>
        </div>
      </aside>
    </div>
  </section>
</template>
