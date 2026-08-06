<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { apiRequest } from '@/api/client'
import type { DashboardMetrics } from '@/api/types'
import MetricSkeleton from '@/components/ui/MetricSkeleton.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import { legacyAdminPath } from '@/runtime/environment'

const dashboard = ref<DashboardMetrics | null>(null)
const loading = ref(true)
const error = ref('')
const legacyUrl = legacyAdminPath()

const metrics = computed(() => {
  if (!dashboard.value) return []
  return [
    { label: '累计用户', value: dashboard.value.users, suffix: '人' },
    { label: '订单总数', value: dashboard.value.orders, suffix: '单' },
    { label: '已支付营收', value: dashboard.value.revenue.toFixed(2), suffix: '元' },
    { label: '材料 SKU', value: dashboard.value.materials, suffix: '项' },
  ]
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
      description="验证新版工程的鉴权、接口、路由和真实数据链路。"
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

      <section class="migration-note">
        <div>
          <span>运营提示</span>
          <h2>常用功能已连接当前后台</h2>
          <p>在这里查看经营数据、处理订单，并进入各项运营工作。</p>
        </div>
        <a :href="legacyUrl">继续使用当前后台 <span>↗</span></a>
      </section>
    </template>
  </section>
</template>
