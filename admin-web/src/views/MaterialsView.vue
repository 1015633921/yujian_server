<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageEmptyState from '@/components/ui/PageEmptyState.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import {
  batchUpdateMaterialSkus,
  createMaterialSku,
  listMaterialSpus,
  listMaterialTypes,
  patchMaterialSku,
  type Material,
  type MaterialSpu,
  type MaterialType,
} from '@/features/materials/api'

type Draft = { grade: string; size: number; price: number; costPrice: number; stock: number; safetyStock: number }
type NewDraft = Draft & { id: string }
const route = useRoute()
const router = useRouter()
const groups = ref<MaterialSpu[]>([])
const types = ref<MaterialType[]>([])
const facets = ref<Record<string, Array<{ value: string; count: number }>>>({})
const loading = ref(true)
const error = ref('')
const total = ref(0)
const hasNext = ref(false)
const expanded = ref<string[]>([])
const selected = ref<Record<string, Material>>({})
const drafts = ref<Record<string, Draft>>({})
const addDrafts = ref<Record<string, NewDraft>>({})
const saving = ref<Record<string, boolean>>({})
const batchAction = ref<'enable' | 'disable' | 'price' | 'stock' | 'safety_stock' | 'delete'>('enable')
const batchValue = ref<number | undefined>()
const applyingBatch = ref(false)
let controller: AbortController | null = null

const queryValue = (name: string) => computed(() => typeof route.query[name] === 'string' ? route.query[name] : '')
const keyword = queryValue('keyword')
const top = queryValue('top')
const category = queryValue('category')
const status = queryValue('status')
const stockState = queryValue('stock_state')
const assetState = queryValue('asset_state')
const specState = queryValue('spec_state')
const profileState = queryValue('profile_state')
const page = computed(() => Math.max(1, Number(route.query.page) || 1))
const categories = computed(() => facets.value.category || [])
const selectedItems = computed(() => Object.values(selected.value))
const needsBatchValue = computed(() => ['price', 'stock', 'safety_stock'].includes(batchAction.value))

function updateQuery(updates: Record<string, string | undefined>) {
  const query = { ...route.query }
  Object.entries(updates).forEach(([key, value]) => value ? query[key] = value : delete query[key])
  void router.replace({ query })
}
function keyOf(group: MaterialSpu) { return group.series_id || group.id }
function price(value: unknown) { return Number(value || 0) }
function elementLabel(value?: string) {
  return ({ metal: '金', wood: '木', water: '水', fire: '火', earth: '土', 金: '金', 木: '木', 水: '水', 火: '火', 土: '土' } as Record<string, string>)[value || ''] || '待补'
}
function draftFor(item: Material): Draft {
  const sku = item.sku || {}
  return {
    grade: item.grade || '',
    size: Number(sku.size_mm ?? item.size ?? 0),
    price: price(sku.price_per_bead),
    costPrice: price(sku.cost_price),
    stock: Number(sku.stock || 0),
    safetyStock: Number(sku.safety_stock || 0),
  }
}
function skuDraft(item: Material): Draft {
  return drafts.value[item.id] || (drafts.value[item.id] = draftFor(item))
}
function resetDrafts() {
  drafts.value = Object.fromEntries(groups.value.flatMap(group => group.items.map(item => [item.id, draftFor(item)])))
}
function toggle(group: MaterialSpu) {
  const key = keyOf(group)
  expanded.value = expanded.value.includes(key) ? expanded.value.filter(item => item !== key) : [...expanded.value, key]
}
function isExpanded(group: MaterialSpu) { return expanded.value.includes(keyOf(group)) }
function isSelected(item: Material) { return Boolean(selected.value[item.id]) }
function toggleSelected(item: Material) {
  const next = { ...selected.value }
  if (next[item.id]) delete next[item.id]
  else next[item.id] = item
  selected.value = next
}
function clearSelected() { selected.value = {} }
function setQuickFilter(key: 'stock_state' | 'asset_state' | 'spec_state' | 'profile_state', value: string) {
  updateQuery({ [key]: (route.query[key] === value ? undefined : value), page: undefined })
}
function newSkuId() {
  const uuid = globalThis.crypto?.randomUUID?.().replaceAll('-', '') || `${Date.now()}${Math.random().toString(36).slice(2)}`
  return `mat_${uuid}`
}
function startAdd(group: MaterialSpu) {
  const key = keyOf(group)
  if (addDrafts.value[key]) { delete addDrafts.value[key]; addDrafts.value = { ...addDrafts.value }; return }
  const lastSize = Math.max(0, ...(group.spu.size_values || []))
  addDrafts.value = { ...addDrafts.value, [key]: { id: newSkuId(), grade: '', size: lastSize || 8, price: Number(group.spu.min_price || 0), costPrice: 0, stock: 0, safetyStock: 0 } }
}
function addDraft(group: MaterialSpu): NewDraft | null { return addDrafts.value[keyOf(group)] || null }
async function addSku(group: MaterialSpu) {
  const key = keyOf(group)
  const draft = addDrafts.value[key]
  if (!draft || saving.value[draft.id]) return
  saving.value = { ...saving.value, [draft.id]: true }
  try {
    await createMaterialSku({
      id: draft.id,
      top: group.spu.top || '', category: group.spu.category || '', series: group.spu.series || '', series_id: group.series_id || '', material_code: group.spu.material_code || '',
      name: group.spu.series || '', element: group.energy?.primary_element || '', grade: draft.grade,
      price: draft.price, size: draft.size, weight: 1, cost_price: draft.costPrice, stock: draft.stock, safety_stock: draft.safetyStock, enabled: draft.stock > 0,
    })
    const next = { ...addDrafts.value }; delete next[key]; addDrafts.value = next
    await load()
  } catch (cause) { error.value = cause instanceof Error ? cause.message : '新增规格失败' } finally {
    const next = { ...saving.value }; delete next[draft.id]; saving.value = next
  }
}
async function load() {
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  try {
    const [result, materialTypes] = await Promise.all([
      listMaterialSpus({ keyword: keyword.value, top: top.value, category: category.value, status: status.value, stockState: stockState.value, assetState: assetState.value, specState: specState.value, profileState: profileState.value, page: page.value, pageSize: 20 }, controller.signal),
      types.value.length ? Promise.resolve(types.value) : listMaterialTypes(false, controller.signal),
    ])
    groups.value = result.items
    total.value = result.pagination.total
    hasNext.value = result.pagination.has_next
    facets.value = result.facets || {}
    types.value = materialTypes
    resetDrafts()
    const validIds = new Set(groups.value.flatMap(group => group.items.map(item => item.id)))
    selected.value = Object.fromEntries(Object.entries(selected.value).filter(([id]) => validIds.has(id)))
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') return
    error.value = cause instanceof Error ? cause.message : '珠材目录加载失败'
  } finally { loading.value = false }
}
function search(event: Event) {
  const value = new FormData(event.target as HTMLFormElement).get('keyword')
  updateQuery({ keyword: typeof value === 'string' ? value.trim() || undefined : undefined, page: undefined })
}
async function saveSku(item: Material) {
  const draft = drafts.value[item.id]
  if (!draft || saving.value[item.id]) return
  const current = draftFor(item)
  const payload: Record<string, unknown> = { expected_revision: item.sku?.revision }
  if (draft.grade !== current.grade) payload.grade = draft.grade
  if (draft.size !== current.size) payload.size_mm = draft.size
  if (draft.price !== current.price) payload.price_per_bead = draft.price
  if (draft.costPrice !== current.costPrice) payload.cost_price = draft.costPrice
  if (draft.stock !== current.stock) payload.stock = draft.stock
  if (draft.safetyStock !== current.safetyStock) payload.safety_stock = draft.safetyStock
  if (Object.keys(payload).length === 1) return
  saving.value = { ...saving.value, [item.id]: true }
  try {
    await patchMaterialSku(item.id, payload)
    await load()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'SKU 保存失败'
  } finally {
    const next = { ...saving.value }; delete next[item.id]; saving.value = next
  }
}
async function toggleEnabled(item: Material) {
  if (saving.value[item.id]) return
  saving.value = { ...saving.value, [item.id]: true }
  try {
    await patchMaterialSku(item.id, { enabled: !item.sku?.enabled, expected_revision: item.sku?.revision })
    await load()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '状态更新失败'
  } finally {
    const next = { ...saving.value }; delete next[item.id]; saving.value = next
  }
}
async function applyBatch() {
  if (!selectedItems.value.length || applyingBatch.value) return
  if (needsBatchValue.value && !Number.isFinite(batchValue.value)) { error.value = '请填写批量操作的数值'; return }
  if (batchAction.value === 'delete' && !window.confirm(`确认删除已选 ${selectedItems.value.length} 个 SKU？此操作不能撤销。`)) return
  applyingBatch.value = true
  error.value = ''
  try {
    await batchUpdateMaterialSkus({
      ids: selectedItems.value.map(item => item.id),
      action: batchAction.value,
      ...(needsBatchValue.value ? { value: Number(batchValue.value) } : {}),
      expectedRevisions: Object.fromEntries(selectedItems.value.map(item => [item.id, Number(item.sku?.revision || 1)])),
    })
    clearSelected(); batchValue.value = undefined
    await load()
  } catch (cause) { error.value = cause instanceof Error ? cause.message : '批量操作失败' } finally { applyingBatch.value = false }
}
watch(() => [keyword.value, top.value, category.value, status.value, stockState.value, assetState.value, specState.value, profileState.value, page.value], () => void load(), { immediate: true })
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <section class="workspace-page materials-page">
    <PageHeading
      eyebrow="MATERIAL OPERATIONS"
      title="珠材管理"
      description="按品种查看所有规格、库存和售价；一个品种只出现一次，展开后再管理 SKU。"
    >
      <template #actions>
        <RouterLink
          class="heading-link"
          :to="{ name: 'material-directory' }"
        >
          目录与品种设置 →
        </RouterLink>
        <RouterLink
          class="heading-link"
          :to="{ name: 'material-assets' }"
        >
          图库处理 →
        </RouterLink>
      </template>
    </PageHeading>
    <form
      class="material-query"
      @submit.prevent="search"
    >
      <input
        name="keyword"
        :value="keyword"
        placeholder="搜索品种、规格、SKU 或材料编码"
      ><button>搜索</button>
      <select
        :value="top"
        @change="updateQuery({ top: ($event.target as HTMLSelectElement).value || undefined, page: undefined })"
      >
        <option value="">
          全部类型
        </option><option
          v-for="type in types"
          :key="type.code"
          :value="type.code"
        >
          {{ type.name }}
        </option>
      </select>
      <select
        :value="category"
        @change="updateQuery({ category: ($event.target as HTMLSelectElement).value || undefined, page: undefined })"
      >
        <option value="">
          全部分类
        </option><option
          v-for="item in categories"
          :key="item.value"
          :value="item.value"
        >
          {{ item.value }}（{{ item.count }}）
        </option>
      </select>
      <select
        :value="status"
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
    </form>
    <div class="material-quick-filters">
      <button
        :class="{ active: stockState === 'low' }"
        @click="setQuickFilter('stock_state', 'low')"
      >
        低库存
      </button>
      <button
        :class="{ active: stockState === 'out' }"
        @click="setQuickFilter('stock_state', 'out')"
      >
        缺货
      </button>
      <button
        :class="{ active: assetState === 'missing_primary' }"
        @click="setQuickFilter('asset_state', 'missing_primary')"
      >
        缺主图
      </button>
      <button
        :class="{ active: specState === 'incomplete' }"
        @click="setQuickFilter('spec_state', 'incomplete')"
      >
        规格不全
      </button>
      <button
        :class="{ active: profileState === 'incomplete' }"
        @click="setQuickFilter('profile_state', 'incomplete')"
      >
        资料待补
      </button>
      <span>{{ total }} 个品种</span>
    </div>
    <div
      v-if="selectedItems.length"
      class="material-batch-bar"
    >
      <b>已选择 {{ selectedItems.length }} 个 SKU</b>
      <select v-model="batchAction">
        <option value="enable">
          启用销售
        </option><option value="disable">
          停用销售
        </option><option value="price">
          设定售价
        </option><option value="stock">
          设定库存
        </option><option value="safety_stock">
          设定安全库存
        </option><option value="delete">
          删除 SKU
        </option>
      </select>
      <input
        v-if="needsBatchValue"
        v-model.number="batchValue"
        type="number"
        min="0"
        step="0.01"
        :placeholder="batchAction === 'price' ? '单颗售价' : '数量'"
      >
      <button
        :disabled="applyingBatch"
        @click="applyBatch"
      >
        {{ applyingBatch ? '处理中…' : '执行操作' }}
      </button><button
        class="text-button"
        @click="clearSelected"
      >
        取消选择
      </button>
      <small>提交时会校验每个 SKU 的版本；有其他人先修改则整批不会执行。</small>
    </div>
    <div
      v-if="loading"
      class="order-list-skeleton"
    >
      <i /><i /><i />
    </div>
    <PageErrorState
      v-else-if="error && !groups.length"
      eyebrow="CATALOG UNAVAILABLE"
      title="珠材目录暂时无法读取"
      :message="error"
      @retry="load"
    />
    <PageEmptyState
      v-else-if="!groups.length"
      title="暂无符合条件的品种"
      message="调整筛选条件，或在目录设置中建立新品种。"
      @clear="updateQuery({ keyword: undefined, top: undefined, category: undefined, status: undefined, stock_state: undefined, asset_state: undefined, spec_state: undefined, profile_state: undefined })"
    />
    <template v-else>
      <p
        v-if="error"
        class="material-inline-error"
      >
        {{ error }} <button @click="load">
          重新读取
        </button>
      </p>
      <div class="material-spu-list">
        <article
          v-for="group in groups"
          :key="keyOf(group)"
          class="material-spu"
        >
          <button
            class="material-spu-summary"
            :aria-expanded="isExpanded(group)"
            @click="toggle(group)"
          >
            <span class="material-spu-expand">{{ isExpanded(group) ? '−' : '+' }}</span><img
              v-if="group.spu.image"
              :src="group.spu.image"
              alt=""
            ><i v-else />
            <span class="material-spu-name"><strong>{{ group.spu.series || group.id }}</strong><small>{{ group.spu.category || '未分类' }} · 主五行：{{ elementLabel(group.energy?.primary_element) }}</small></span>
            <span class="material-spu-specs">{{ group.spu.size_values?.join(' / ') || '—' }}<small>规格（mm）</small></span>
            <span>¥{{ Number(group.spu.min_price || 0).toFixed(2) }}<template v-if="group.spu.max_price !== group.spu.min_price"> – ¥{{ Number(group.spu.max_price || 0).toFixed(2) }}</template><small>单颗售价</small></span>
            <span>{{ group.spu.total_stock || 0 }}<small>总库存</small></span>
            <span class="material-spu-badges"><em
              v-if="group.outStockCount"
              class="risk"
            >{{ group.outStockCount }} 缺货</em><em
              v-else-if="group.lowStockCount"
              class="warn"
            >{{ group.lowStockCount }} 低库存</em><em
              v-if="group.assetState !== 'ready'"
              class="muted"
            >图片待补</em><em
              v-if="group.specStatus === 'partial'"
              class="muted"
            >规格待补</em></span>
          </button>
          <div
            v-if="isExpanded(group)"
            class="material-sku-table-wrap"
          >
            <div class="material-sku-table-head">
              <span>{{ group.spu.sku_count }} 个 SKU · {{ group.spu.enabled_count }} 个已启用</span><span><RouterLink :to="{ name: 'material-series-profile', params: { seriesId: group.series_id || group.id } }">完善品种资料 →</RouterLink><button
                class="add-sku"
                @click="startAdd(group)"
              >{{ addDrafts[keyOf(group)] ? '取消新增' : '新增规格' }}</button><RouterLink :to="{ name: 'material-assets', query: { series_id: group.series_id, top: group.spu.top } }">管理品种图库 →</RouterLink></span>
            </div>
            <table class="material-sku-table">
              <thead><tr><th /><th>规格</th><th>等级</th><th>售价</th><th>成本</th><th>库存 / 可售</th><th>安全库存</th><th>销售状态</th><th /></tr></thead><tbody>
                <tr
                  v-for="item in group.items"
                  :key="item.id"
                >
                  <td>
                    <input
                      type="checkbox"
                      :checked="isSelected(item)"
                      @change="toggleSelected(item)"
                    >
                  </td><td>
                    <input
                      v-model.number="skuDraft(item).size"
                      type="number"
                      min="0.1"
                      step="0.1"
                    ><small>mm</small>
                  </td><td>
                    <input
                      v-model="skuDraft(item).grade"
                      placeholder="—"
                    >
                  </td><td>
                    <input
                      v-model.number="skuDraft(item).price"
                      type="number"
                      min="0"
                      step="0.01"
                    >
                  </td><td>
                    <input
                      v-model.number="skuDraft(item).costPrice"
                      type="number"
                      min="0"
                      step="0.01"
                    >
                  </td><td>
                    <input
                      v-model.number="skuDraft(item).stock"
                      type="number"
                      min="0"
                      step="1"
                    ><small>可售 {{ item.sku?.available_stock ?? item.sku?.stock ?? 0 }}</small>
                  </td><td>
                    <input
                      v-model.number="skuDraft(item).safetyStock"
                      type="number"
                      min="0"
                      step="1"
                    >
                  </td><td>
                    <button
                      class="status-switch"
                      :class="{ on: item.sku?.enabled }"
                      :disabled="saving[item.id]"
                      @click="toggleEnabled(item)"
                    >
                      {{ item.sku?.enabled ? '已启用' : '已停用' }}
                    </button>
                  </td><td>
                    <button
                      class="row-save"
                      :disabled="saving[item.id]"
                      @click="saveSku(item)"
                    >
                      {{ saving[item.id] ? '保存中' : '保存' }}
                    </button>
                  </td>
                </tr>
                <tr
                  v-if="addDraft(group)"
                  class="new-sku-row"
                >
                  <td /><td>
                    <input
                      v-model.number="addDraft(group)!.size"
                      type="number"
                      min="0.1"
                      step="0.1"
                    ><small>mm</small>
                  </td><td>
                    <input
                      v-model="addDraft(group)!.grade"
                      placeholder="等级"
                    >
                  </td><td>
                    <input
                      v-model.number="addDraft(group)!.price"
                      type="number"
                      min="0"
                      step="0.01"
                    >
                  </td><td>
                    <input
                      v-model.number="addDraft(group)!.costPrice"
                      type="number"
                      min="0"
                      step="0.01"
                    >
                  </td><td>
                    <input
                      v-model.number="addDraft(group)!.stock"
                      type="number"
                      min="0"
                      step="1"
                    ><small>库存为 0 时默认停用</small>
                  </td><td>
                    <input
                      v-model.number="addDraft(group)!.safetyStock"
                      type="number"
                      min="0"
                      step="1"
                    >
                  </td><td><small>新规格</small></td><td>
                    <button
                      class="row-save"
                      :disabled="saving[addDraft(group)!.id]"
                      @click="addSku(group)"
                    >
                      {{ saving[addDraft(group)!.id] ? '创建中' : '创建' }}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>
      </div>
      <nav class="design-pagination">
        <button
          :disabled="page === 1"
          @click="updateQuery({ page: page > 2 ? String(page - 1) : undefined })"
        >
          ← 上一页
        </button><span>第 {{ page }} 页</span><button
          :disabled="!hasNext"
          @click="updateQuery({ page: String(page + 1) })"
        >
          下一页 →
        </button>
      </nav>
    </template>
  </section>
</template>
