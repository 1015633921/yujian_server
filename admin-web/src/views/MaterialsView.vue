<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import PageEmptyState from '@/components/ui/PageEmptyState.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import { listMaterialSpus, listMaterialTypes, type MaterialSpu, type MaterialType } from '@/features/materials/api'

const PAGE_SIZE = 24
const route = useRoute()
const router = useRouter()
const groups = ref<MaterialSpu[]>([])
const types = ref<MaterialType[]>([])
const categoryFacets = ref<Array<{ value: string; count: number }>>([])
const failedImages = ref(new Set<string>())
const total = ref(0)
const hasNext = ref(false)
const loading = ref(true)
const refreshing = ref(false)
const error = ref('')
let controller: AbortController | null = null
let sequence = 0

const keyword = computed(() => typeof route.query.keyword === 'string' ? route.query.keyword : '')
const top = computed(() => typeof route.query.top === 'string' ? route.query.top : '')
const category = computed(() => typeof route.query.category === 'string' ? route.query.category : '')
const status = computed(() => typeof route.query.status === 'string' ? route.query.status : 'enabled')
const page = computed(() => Math.max(1, Number(route.query.page) || 1))
const firstResult = computed(() => groups.value.length ? (page.value - 1) * PAGE_SIZE + 1 : 0)
const lastResult = computed(() => (page.value - 1) * PAGE_SIZE + groups.value.length)

function updateQuery(updates: Record<string, string | undefined>): void {
  const query = { ...route.query }
  for (const [key, value] of Object.entries(updates)) {
    if (value) query[key] = value
    else delete query[key]
  }
  void router.replace({ query })
}

function submitSearch(event: Event): void {
  const value = new FormData(event.target as HTMLFormElement).get('keyword')
  updateQuery({ keyword: typeof value === 'string' ? value.trim() || undefined : undefined, page: undefined })
}

function clearFilters(): void {
  updateQuery({ keyword: undefined, top: undefined, category: undefined, status: undefined, page: undefined })
}

function selectType(value: string): void {
  updateQuery({ top: value || undefined, category: undefined, page: undefined })
}

function markImageFailed(imageUrl: string): void {
  failedImages.value = new Set(failedImages.value).add(imageUrl)
}

function changePage(nextPage: number): void {
  if (nextPage < 1 || (nextPage > page.value && !hasNext.value)) return
  updateQuery({ page: nextPage > 1 ? String(nextPage) : undefined })
}

function formatPrice(group: MaterialSpu): string {
  const min = Number(group.spu.min_price || 0).toFixed(2)
  const max = Number(group.spu.max_price || 0).toFixed(2)
  return min === max ? `¥${min}` : `¥${min}–${max}`
}

async function load(silent = false): Promise<void> {
  const current = ++sequence
  controller?.abort()
  controller = new AbortController()
  if (silent && groups.value.length) refreshing.value = true
  else loading.value = true
  error.value = ''
  try {
    const [result, materialTypes] = await Promise.all([
      listMaterialSpus({
        keyword: keyword.value,
        top: top.value,
        category: category.value,
        status: status.value,
        page: page.value,
        pageSize: PAGE_SIZE,
      }, controller.signal),
      types.value.length ? Promise.resolve(types.value) : listMaterialTypes(false, controller.signal),
    ])
    if (current !== sequence) return
    groups.value = result.items
    total.value = result.pagination.total || 0
    hasNext.value = Boolean(result.pagination.has_next)
    categoryFacets.value = result.facets?.category || (category.value ? [{ value: category.value, count: result.pagination.total || 0 }] : [])
    types.value = materialTypes
    if (!result.items.length && page.value > 1) changePage(page.value - 1)
  } catch (cause) {
    if (current !== sequence || (cause instanceof DOMException && cause.name === 'AbortError')) return
    error.value = cause instanceof Error ? cause.message : '珠材目录加载失败'
    if (!silent) {
      groups.value = []
      total.value = 0
      hasNext.value = false
    }
  } finally {
    if (current === sequence) {
      loading.value = false
      refreshing.value = false
    }
  }
}

watch(() => [keyword.value, top.value, category.value, status.value, page.value], () => void load(), { immediate: true })
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <section class="workspace-page materials-page materials-page--lookup">
    <PageHeading
      eyebrow="MATERIAL CATALOG"
      title="珠材管理"
    >
      <template #actions>
        <RouterLink
          class="heading-link"
          :to="{ name: 'material-directory' }"
        >
          管理材料目录 →
        </RouterLink>
        <RouterLink
          class="heading-link"
          :to="{ name: 'material-assets' }"
        >
          管理素材 →
        </RouterLink>
        <button
          type="button"
          :disabled="loading || refreshing"
          @click="load(true)"
        >
          {{ refreshing ? '刷新中' : '刷新列表' }}
        </button>
      </template>
    </PageHeading>

    <form
      class="material-lookup-toolbar"
      @submit.prevent="submitSearch"
    >
      <label>
        <span>搜索材料</span>
        <input
          name="keyword"
          :value="keyword"
          placeholder="名称、分类、品种或材料编码"
          :disabled="loading"
        >
      </label>
      <label>
        <span>材料类型</span>
        <select
          :value="top"
          aria-label="按材料类型筛选"
          :disabled="loading"
          @change="selectType(($event.target as HTMLSelectElement).value)"
        >
          <option value="">
            全部类型
          </option>
          <option
            v-for="type in types"
            :key="type.code"
            :value="type.code"
          >
            {{ type.name }}
          </option>
        </select>
      </label>
      <label>
        <span>一级类目</span>
        <select
          :value="category"
          aria-label="按一级类目筛选"
          :disabled="loading"
          @change="updateQuery({ category: ($event.target as HTMLSelectElement).value || undefined, page: undefined })"
        >
          <option value="">全部类目</option>
          <option
            v-for="item in categoryFacets"
            :key="item.value"
            :value="item.value"
          >
            {{ item.value }}（{{ item.count }}）
          </option>
        </select>
      </label>
      <label>
        <span>启用状态</span>
        <select
          :value="status"
          aria-label="按启用状态筛选"
          :disabled="loading"
          @change="updateQuery({ status: ($event.target as HTMLSelectElement).value === 'enabled' ? undefined : ($event.target as HTMLSelectElement).value, page: undefined })"
        >
          <option value="enabled">已启用</option>
          <option value="disabled">已停用</option>
          <option value="all">全部状态</option>
        </select>
      </label>
      <button
        type="submit"
        :disabled="loading"
      >
        查询
      </button>
      <span v-if="groups.length">
        {{ total }} 个品种 · 第 {{ firstResult }}–{{ lastResult }} 条
      </span>
    </form>

    <div
      v-if="loading"
      class="order-list-skeleton"
      aria-label="正在加载珠材目录"
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
      :title="keyword || top ? '没有符合条件的材料' : '暂无可展示的材料'"
      message="调整搜索条件，或前往材料目录建立品种。"
      @clear="clearFilters"
    >
      <template #action>
        清除筛选
      </template>
    </PageEmptyState>
    <template v-else>
      <p
        v-if="error"
        class="material-inline-error"
        role="alert"
      >
        本次刷新失败，已保留当前列表：{{ error }}
      </p>
      <div
        class="material-lookup-list"
        role="table"
        aria-label="珠材品种列表"
        :aria-busy="refreshing"
      >
        <div
          class="material-lookup-list__head"
          role="row"
        >
          <span>品种</span><span>一级类目</span><span>可售 SKU</span><span>售价</span><span>操作</span>
        </div>
        <article
          v-for="group in groups"
          :key="group.id"
          class="material-lookup-row"
          role="row"
        >
          <div
            class="material-lookup-row__identity"
            data-label="品种"
            role="cell"
          >
            <img
              v-if="group.spu.image && !failedImages.has(group.spu.image)"
              :src="group.spu.image"
              alt=""
              @error="markImageFailed(group.spu.image)"
            >
            <i v-else />
            <span>
              <strong>{{ group.spu.series || group.id }}</strong>
              <small>{{ group.spu.sku_count || 0 }} 个规格</small>
            </span>
          </div>
          <span
            data-label="分类"
            role="cell"
          >{{ group.spu.category || '未分类' }}</span>
          <span
            class="material-lookup-row__specs"
            data-label="可售 SKU"
            role="cell"
          ><RouterLink
            v-for="option in group.spu.sku_options || []"
            :key="option.id"
            :to="{ name: 'material-detail', params: { materialId: option.id } }"
            :title="`编辑 ${option.size_mm ? `${option.size_mm}mm` : '该'} SKU 的规格、价格和库存`"
          ><b>{{ option.size_mm ? `${option.size_mm} mm` : '未填尺寸' }}</b><small>{{ option.grade || '常规' }} · 编辑 SKU</small></RouterLink><span v-if="!group.spu.sku_options?.length">尚未建立 SKU</span></span>
          <strong
            data-label="售价"
            role="cell"
          >{{ formatPrice(group) }}</strong>
          <span
            class="material-lookup-row__action"
            data-label="操作"
            role="cell"
          >
            <RouterLink
              v-if="group.series_id"
              :to="{ name: 'material-series-profile', params: { seriesId: group.series_id } }"
            >
              品种资料 →
            </RouterLink>
            <RouterLink
              v-else
              :to="{ name: 'material-directory' }"
            >
              前往目录 →
            </RouterLink>
          </span>
        </article>
      </div>
      <nav
        class="design-pagination"
        aria-label="珠材目录分页"
      >
        <button
          type="button"
          :disabled="page === 1 || loading || refreshing"
          @click="changePage(page - 1)"
        >
          ← 上一页
        </button>
        <span>第 {{ page }} 页</span>
        <button
          type="button"
          :disabled="!hasNext || loading || refreshing"
          @click="changePage(page + 1)"
        >
          下一页 →
        </button>
      </nav>
    </template>
  </section>
</template>
