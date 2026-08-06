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
  listMaterialTaxonomy,
  listMaterialTypes,
  saveMaterialCategory,
  saveMaterialSeries,
  saveMaterialType,
  updateMaterialSeries,
  type MaterialCategory,
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
const categories = ref<MaterialCategory[]>([])
const loading = ref(true)
const error = ref('')
const notice = ref('')
const saving = ref(false)
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
let categoriesController: AbortController | null = null
let categoryRequest = 0

const canManage = computed(() => auth.admin?.role !== 'viewer')
const selectedTop = computed(() => (typeof route.query.top === 'string' ? route.query.top : ''))
const selectedType = computed(() => types.value.find((item) => item.code === selectedTop.value) || null)
const selectedCategories = computed(() => categories.value.filter((item) => item.top === selectedTop.value))
const selectedSeriesCount = computed(() => selectedCategories.value.reduce((total, item) => total + item.series.length, 0))
const activeCategories = computed(() => selectedCategories.value.filter((item) => item.enabled).length)

function elementLabel(value?: string): string {
  return ({ metal: '金', wood: '木', water: '水', fire: '火', earth: '土', 金: '金', 木: '木', 水: '水', 火: '火', 土: '土' } as Record<string, string>)[value || ''] || '待补五行'
}

function setTop(top: string): void {
  void router.replace({ query: top ? { top } : {} })
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

function editCategory(item: MaterialCategory): void {
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
  return selectedCategories.value.find((item) => item.id === editor.parentId)?.name || '未选择分类'
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
    else if (selectedTop.value) await loadCategories(selectedTop.value)
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') return
    error.value = cause instanceof Error ? cause.message : '材料三级目录加载失败'
  } finally {
    loading.value = false
  }
}

async function loadCategories(top: string): Promise<void> {
  categoriesController?.abort()
  const currentController = new AbortController()
  categoriesController = currentController
  const requestId = ++categoryRequest
  if (!top) {
    categories.value = []
    loading.value = false
    return
  }
  loading.value = true
  error.value = ''
  try {
    const nextCategories = await requestWithTimeout(
      (signal) => listMaterialTaxonomy(top, true, signal),
      currentController,
      '该类型的三级目录加载超时',
    )
    if (requestId !== categoryRequest) return
    categories.value = nextCategories
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') return
    if (requestId === categoryRequest) error.value = cause instanceof Error ? cause.message : '材料三级目录加载失败'
  } finally {
    if (requestId === categoryRequest) loading.value = false
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
      else await saveMaterialSeries(payload)
    }
    notice.value = '目录已保存，相关 SKU 将继续引用此层级。'
    wasEnabled.value = editor.enabled
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
  if (top && top !== previousTop) void loadCategories(top)
})

void loadTypes()
onBeforeUnmount(() => {
  typesController?.abort()
  categoriesController?.abort()
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
            <span>第二层 / 第三层</span>
            <h2>{{ selectedType?.name || '选择材料类型' }}</h2>
          </div>
          <p v-if="selectedType">
            {{ activeCategories }} 个启用分类 · {{ selectedSeriesCount }} 个品种 · {{ selectedType.sku_count }} 个 SKU
          </p>
        </div>

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
          v-else-if="!selectedCategories.length"
          title="此类型还没有分类"
          :message="`先为「${selectedType.name}」建立分类，SKU 才能选择到可用品种。`"
          @clear="resetEditor('category')"
        >
          <template
            v-if="canManage"
            #action
          >
            新建分类
          </template>
        </PageEmptyState>
        <div
          v-else
          class="directory-categories"
        >
          <section
            v-for="category in selectedCategories"
            :key="category.id"
            class="directory-category"
            :class="{ 'is-disabled': !category.enabled }"
          >
            <header>
              <div>
                <span>分类</span>
                <h3>{{ category.name }}</h3>
                <small>{{ category.series.length }} 个品种</small>
              </div>
              <div class="directory-row-actions">
                <button
                  v-if="canManage"
                  type="button"
                  @click="editCategory(category)"
                >
                  编辑
                </button>
                <button
                  v-if="canManage"
                  type="button"
                  @click="resetEditor('series', category.id)"
                >
                  新增品种
                </button>
                <button
                  v-if="canManage && category.enabled"
                  class="danger-text"
                  type="button"
                  @click="disable('category', category.id, category.name)"
                >
                  停用
                </button>
                <button
                  v-if="canManage"
                  class="danger-text"
                  type="button"
                  @click="remove('category', category.id, category.name)"
                >
                  删除空分类
                </button>
              </div>
            </header>
            <div
              v-if="category.series.length"
              class="directory-series-list"
            >
              <article
                v-for="series in category.series"
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
                  <small>主五行：{{ elementLabel(series.energy?.primary_element) }} · {{ series.image_url ? '已设主图' : '缺主图' }}</small>
                </div>
                <span>{{ series.enabled ? '已启用' : '已停用' }}</span>
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
            <p
              v-else
              class="directory-category__empty"
            >
              暂未建立品种。
            </p>
          </section>
        </div>
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
          <label v-if="editor.kind === 'series'">
            <span>材料编码</span>
            <input
              v-model.trim="editor.code"
              :disabled="!canManage"
              maxlength="160"
              placeholder="留空时按目录自动生成"
            >
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
            <span>排序值</span>
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
            {{ saving ? '正在保存…' : '保存目录' }}
          </button>
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
