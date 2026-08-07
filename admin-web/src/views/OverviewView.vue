<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { apiRequest } from '@/api/client'
import type { DashboardMetrics } from '@/api/types'
import MetricSkeleton from '@/components/ui/MetricSkeleton.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'

const dashboard = ref<DashboardMetrics | null>(null)
const loading = ref(true)
const error = ref('')
const metrics = computed(() => {
  if (!dashboard.value) return []
  return [
    { label: '累计用户', value: dashboard.value.users, suffix: '人' },
    { label: '订单总数', value: dashboard.value.orders, suffix: '单' },
    { label: '已支付营收', value: dashboard.value.revenue.toFixed(2), suffix: '元' },
    { label: '材料 SKU', value: dashboard.value.materials, suffix: '项' },
  ]
})

const actionQueue = computed(() => {
  const data = dashboard.value
  if (!data) return []
  return [
    { label: '待发货订单', count: data.pending_ship || 0, hint: '核验收货信息、物流方式与单号后发货。', route: { name: 'orders' }, tone: 'urgent' },
    { label: '售后申请', count: data.after_sale || 0, hint: '优先处理退款、退货和补发请求。', route: { name: 'after-sales' }, tone: 'urgent' },
    { label: '支付补偿', count: data.payment_compensations || 0, hint: '核对支付状态与订单履约状态。', route: { name: 'orders' }, tone: 'normal' },
  ].filter((item) => item.count > 0)
})

async function loadDashboard(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    dashboard.value = await apiRequest<DashboardMetrics>('/api/v1/admin/dashboard')
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '经营数据加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadDashboard)
</script>

<template>
  <section class="workspace-page">
    <PageHeading
      eyebrow="BUSINESS OVERVIEW"
      title="经营概览"
      description="从待处理履约任务开始，查看真实经营数据并进入对应工作区。"
    >
      <template #actions>
        <button
          type="button"
          :disabled="loading"
          @click="loadDashboard"
        >
          {{ loading ? '加载中' : '刷新数据' }}
        </button>
      </template>
    </PageHeading>

    <MetricSkeleton
      v-if="loading"
      label="正在加载经营数据"
    />

    <PageErrorState
      v-else-if="error"
      title="经营数据暂时无法读取"
      :message="error"
      @retry="loadDashboard"
    />

    <template v-else>
      <div
        class="metric-line"
        aria-label="核心经营指标"
      >
        <div
          v-for="metric in metrics"
          :key="metric.label"
        >
          <span>{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
          <small>{{ metric.suffix }}</small>
        </div>
      </div>

      <section class="overview-actions">
        <header>
          <div>
            <span>OPERATION QUEUE</span>
            <h2>现在需要处理</h2>
          </div>
          <RouterLink :to="{ name: 'custom-design-requests' }">
            查看设计服务队列
          </RouterLink>
        </header>
        <div
          v-if="actionQueue.length"
          class="overview-actions__list"
        >
          <RouterLink
            v-for="item in actionQueue"
            :key="item.label"
            :class="`is-${item.tone}`"
            :to="item.route"
          >
            <strong>{{ item.count }}</strong>
            <div><b>{{ item.label }}</b><small>{{ item.hint }}</small></div>
            <span>处理 →</span>
          </RouterLink>
        </div>
        <div
          v-else
          class="overview-actions__clear"
        >
          <strong>当前没有待处理的订单与售后事项</strong>
          <p>设计服务可在专属队列中继续跟进。</p>
        </div>
      </section>
    </template>
  </section>
</template>
