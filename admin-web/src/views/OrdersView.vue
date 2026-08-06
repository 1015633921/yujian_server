<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import PageEmptyState from '@/components/ui/PageEmptyState.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import { listOrders } from '@/features/orders/api'
import { formatCurrency, formatOrderDate, orderStatusLabel, orderStatusTone, paymentStatusLabel } from '@/features/orders/presentation'
import { ORDER_STATUS_OPTIONS } from '@/features/orders/presentation'
import type { AdminOrder } from '@/features/orders/types'
import { legacyAdminPath } from '@/runtime/environment'

const PAGE_SIZE = 30
const route = useRoute()
const router = useRouter()
const items = ref<AdminOrder[]>([])
const total = ref(0)
const hasMore = ref(false)
const loading = ref(true)
const refreshing = ref(false)
const error = ref('')
const refreshWarning = ref('')
let controller: AbortController | null = null
let requestVersion = 0

const keyword = computed(() => typeof route.query.keyword === 'string' ? route.query.keyword : '')
const selectedStatus = computed(() => typeof route.query.status === 'string' ? route.query.status : '')
const currentPage = computed(() => {
  const page = Number(route.query.page)
  return Number.isInteger(page) && page > 0 ? page : 1
})
const offset = computed(() => (currentPage.value - 1) * PAGE_SIZE)
const firstResult = computed(() => items.value.length ? offset.value + 1 : 0)
const lastResult = computed(() => offset.value + items.value.length)
const legacyUrl = computed(() => `${legacyAdminPath()}?page=orders`)

function updateQuery(updates: Record<string, string | undefined>): void {
  const query = { ...route.query }
  for (const [key, value] of Object.entries(updates)) {
    if (value) query[key] = value
    else delete query[key]
  }
  void router.replace({ query })
}

function setStatus(event: Event): void {
  updateQuery({ status: (event.target as HTMLSelectElement).value || undefined, page: undefined })
}

function submitSearch(event: Event): void {
  const value = new FormData(event.target as HTMLFormElement).get('keyword')
  updateQuery({ keyword: typeof value === 'string' ? value.trim() || undefined : undefined, page: undefined })
}

function clearFilters(): void {
  updateQuery({ keyword: undefined, status: undefined, page: undefined })
}

function changePage(page: number): void {
  if (page < 1 || (page > currentPage.value && !hasMore.value)) return
  updateQuery({ page: page > 1 ? String(page) : undefined })
}

async function loadOrders(silent = false): Promise<void> {
  const version = ++requestVersion
  controller?.abort()
  controller = new AbortController()
  if (silent && items.value.length) refreshing.value = true
  else loading.value = true
  error.value = ''
  refreshWarning.value = ''
  try {
    const page = await listOrders({ keyword: keyword.value, status: selectedStatus.value, limit: PAGE_SIZE, offset: offset.value }, controller.signal)
    if (version !== requestVersion) return
    items.value = page.items
    total.value = page.total
    hasMore.value = page.has_more
    if (!items.value.length && currentPage.value > 1) changePage(Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
  } catch (cause) {
    if (version !== requestVersion || (cause instanceof DOMException && cause.name === 'AbortError')) return
    const message = cause instanceof Error ? cause.message : '订单列表加载失败'
    if (silent && items.value.length) refreshWarning.value = message
    else {
      items.value = []
      total.value = 0
      hasMore.value = false
      error.value = message
    }
  } finally {
    if (version === requestVersion) {
      loading.value = false
      refreshing.value = false
    }
  }
}

watch(() => [keyword.value, selectedStatus.value, currentPage.value], () => void loadOrders(), { immediate: true })
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <section class="workspace-page orders-page">
    <PageHeading
      eyebrow="ORDER FULFILLMENT"
      title="订单履约"
      description="从付款、拣货到物流签收；打开订单后处理实际发货信息。"
    >
      <template #actions>
        <a
          class="heading-link"
          :href="legacyUrl"
        >支付补偿与退款处理 ↗</a>
        <button
          type="button"
          :disabled="loading || refreshing"
          @click="loadOrders(true)"
        >
          {{ refreshing ? '刷新中' : '刷新订单' }}
        </button>
      </template>
    </PageHeading>

    <div class="order-queue-summary">
      <div><span>当前结果</span><strong>{{ total }}</strong><small>笔订单</small></div>
      <p><b>{{ items.filter((item) => item.status === 'pending_ship').length }}</b> 笔待发货订单位于当前页，发货前请核对收件信息和配货清单。</p>
    </div>

    <div class="order-list-toolbar">
      <form @submit.prevent="submitSearch">
        <label><span>订单搜索</span><input
          name="keyword"
          :value="keyword"
          placeholder="订单号、用户或收件信息"
          :disabled="loading"
        ></label>
        <button
          type="submit"
          :disabled="loading"
        >
          查询
        </button>
      </form>
      <label><span>履约状态</span><select
        :value="selectedStatus"
        :disabled="loading"
        @change="setStatus"
      >
        <option
          v-for="option in ORDER_STATUS_OPTIONS"
          :key="option.value || 'all'"
          :value="option.value"
        >{{ option.label }}</option>
      </select></label>
      <span v-if="items.length">第 {{ firstResult }}–{{ lastResult }} 条</span>
    </div>

    <p
      v-if="refreshWarning"
      class="inline-warning"
      role="alert"
    >
      本次刷新失败，已保留上次结果：{{ refreshWarning }}
    </p>
    <div
      v-if="loading"
      class="order-list-skeleton"
      aria-label="正在加载订单"
    >
      <i /><i /><i />
    </div>
    <PageErrorState
      v-else-if="error"
      eyebrow="ORDERS UNAVAILABLE"
      title="订单暂时无法读取"
      :message="error"
      @retry="loadOrders"
    />
    <PageEmptyState
      v-else-if="!items.length"
      :title="keyword || selectedStatus ? '没有符合条件的订单' : '暂无订单'"
      :message="keyword || selectedStatus ? '清除搜索或状态筛选后查看全部订单。' : '用户支付后，订单会自动进入待发货队列。'"
      @clear="clearFilters"
    >
      <template
        v-if="keyword || selectedStatus"
        #action
      >
        清除筛选
      </template>
    </PageEmptyState>

    <template v-else>
      <div
        class="order-request-grid"
        role="table"
        aria-label="订单履约列表"
        :aria-busy="refreshing"
      >
        <div
          class="order-request-grid__head"
          role="row"
        >
          <span>订单 / 方案</span><span>收件信息</span><span>履约状态</span><span>订单内容</span><span>金额 / 物流</span><span>下单时间</span><span>操作</span>
        </div>
        <article
          v-for="item in items"
          :key="item.order_id"
          class="order-request-row"
          role="row"
        >
          <div
            class="order-request-cell order-request-cell--identity"
            data-label="订单 / 方案"
          >
            <strong>{{ item.order_id }}</strong><span>{{ item.design_id || '订单材料快照' }}</span>
          </div>
          <div
            class="order-request-cell"
            data-label="收件信息"
          >
            <strong>{{ item.receiver?.name || '-' }} · {{ item.receiver?.phone || '-' }}</strong><span>{{ item.receiver?.region?.join(' ') || item.user_id || '-' }}</span>
          </div>
          <div
            class="order-request-cell"
            data-label="履约状态"
          >
            <b
              class="status-label"
              :data-tone="orderStatusTone(item.status)"
            >{{ item.status_text || orderStatusLabel(item.status) }}</b><span>{{ paymentStatusLabel(item.payment_status) }}</span>
          </div>
          <div
            class="order-request-cell"
            data-label="订单内容"
          >
            <strong>{{ item.sequence?.length || item.design?.summary?.count || 0 }} 颗 · {{ item.design?.wristSize || '-' }}cm</strong><span>{{ item.design?.wearStyle === 'double' ? '双圈' : '单圈' }} · {{ item.bom?.length || 0 }} 种材料</span>
          </div>
          <div
            class="order-request-cell"
            data-label="金额 / 物流"
          >
            <strong>{{ formatCurrency(item.total_amount) }}</strong><span>{{ item.logistics?.tracking_no ? `${item.logistics.carrier || '快递'} · ${item.logistics.tracking_no}` : '尚未发货' }}</span>
          </div>
          <div
            class="order-request-cell"
            data-label="下单时间"
          >
            <strong>{{ formatOrderDate(item.created_at) }}</strong><span>更新 {{ formatOrderDate(item.updated_at) }}</span>
          </div>
          <div
            class="order-request-cell order-request-cell--action"
            data-label="操作"
          >
            <RouterLink
              :class="{ 'is-primary': item.status === 'pending_ship' }"
              :to="{ name: 'order-detail', params: { orderId: item.order_id }, query: { keyword: keyword || undefined, status: selectedStatus || undefined, page: currentPage > 1 ? String(currentPage) : undefined } }"
            >
              {{ item.status === 'pending_ship' ? '去发货' : '履约详情' }} <span>→</span>
            </RouterLink>
          </div>
        </article>
      </div>
      <nav
        class="design-pagination"
        aria-label="订单分页"
      >
        <button
          type="button"
          :disabled="currentPage === 1 || loading || refreshing"
          @click="changePage(currentPage - 1)"
        >
          ← 上一页
        </button><span>第 {{ currentPage }} 页</span><button
          type="button"
          :disabled="!hasMore || loading || refreshing"
          @click="changePage(currentPage + 1)"
        >
          下一页 →
        </button>
      </nav>
    </template>
  </section>
</template>
