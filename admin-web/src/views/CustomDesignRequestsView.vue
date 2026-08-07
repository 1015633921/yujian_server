<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import PageEmptyState from '@/components/ui/PageEmptyState.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import DesignRequestListSkeleton from '@/features/custom-design/DesignRequestListSkeleton.vue'
import { listCustomDesignRequests } from '@/features/custom-design/api'
import {
  CUSTOM_DESIGN_STATUS_OPTIONS,
  customDesignActionLabel,
  customDesignStatusLabel,
  customDesignStatusTone,
  depositStatusLabel,
  formatAdminDate,
  latestProposal,
  normalizeCustomDesignStatus,
  preferenceMeasurement,
  proposalCount,
} from '@/features/custom-design/presentation'
import type { CustomDesignListItem } from '@/features/custom-design/types'
import { legacyAdminPath } from '@/runtime/environment'

const PAGE_SIZE = 30
const MAX_PAGE = Math.floor(100_000 / PAGE_SIZE) + 1
const route = useRoute()
const router = useRouter()
const items = ref<CustomDesignListItem[]>([])
const total = ref(0)
const hasMore = ref(false)
const loading = ref(true)
const refreshing = ref(false)
const error = ref('')
const refreshWarning = ref('')
const refreshedAt = ref('')
let requestSequence = 0
let requestController: AbortController | null = null

const selectedStatus = computed(() => normalizeCustomDesignStatus(route.query.status))
const currentPage = computed(() => {
  const page = Number(route.query.page)
  return Number.isInteger(page) && page > 0 && page <= MAX_PAGE ? page : 1
})
const offset = computed(() => (currentPage.value - 1) * PAGE_SIZE)
const firstResult = computed(() => (items.value.length ? offset.value + 1 : 0))
const lastResult = computed(() => offset.value + items.value.length)
const legacyUrl = legacyAdminPath()
const sortedItems = computed(() => [...items.value].sort((left, right) => queuePriority(left) - queuePriority(right)))

function dueMinutes(value?: string | null): number | null {
  if (!value) return null
  const time = new Date(value).getTime()
  return Number.isFinite(time) ? Math.round((time - Date.now()) / 60_000) : null
}

function queuePriority(item: CustomDesignListItem): number {
  const minutes = dueMinutes(item.first_draft_due_at)
  if (minutes !== null && minutes <= 0) return 0
  if (minutes !== null && minutes <= 24 * 60) return 1
  if (['submitted', 'revision_requested'].includes(item.status)) return 2
  if (item.status === 'designing') return 3
  return 4
}

function dueLabel(value?: string | null): string {
  const minutes = dueMinutes(value)
  if (minutes === null) return '尚未设首稿时限'
  if (minutes <= 0) return `已超时 ${Math.max(1, Math.ceil(Math.abs(minutes) / 60))} 小时`
  if (minutes < 60) return `剩余 ${minutes} 分钟`
  if (minutes < 24 * 60) return `剩余 ${Math.ceil(minutes / 60)} 小时`
  return `首稿 ${formatAdminDate(value)}`
}

function setStatus(event: Event): void {
  const status = normalizeCustomDesignStatus((event.target as HTMLSelectElement).value)
  const query = { ...route.query }
  if (status) query.status = status
  else delete query.status
  delete query.page
  void router.replace({ query })
}

function clearStatus(): void {
  const query = { ...route.query }
  delete query.status
  delete query.page
  void router.replace({ query })
}

function changePage(page: number): void {
  if (page < 1 || (page > currentPage.value && !hasMore.value)) return
  const query = { ...route.query }
  if (page === 1) delete query.page
  else query.page = String(page)
  void router.replace({ query })
}

async function loadRequests(silent = false): Promise<void> {
  const sequence = ++requestSequence
  requestController?.abort()
  requestController = new AbortController()
  if (silent && items.value.length) refreshing.value = true
  else loading.value = true
  error.value = ''
  refreshWarning.value = ''

  try {
    const page = await listCustomDesignRequests(
      {
        status: selectedStatus.value,
        limit: PAGE_SIZE,
        offset: offset.value,
      },
      requestController.signal,
    )
    if (sequence !== requestSequence) return
    items.value = page.items
    total.value = page.total
    hasMore.value = page.has_more
    refreshedAt.value = new Intl.DateTimeFormat('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    }).format(new Date())

    if (!page.items.length && currentPage.value > 1) {
      changePage(Math.max(1, Math.ceil(page.total / PAGE_SIZE)))
    }
  } catch (cause) {
    if (sequence !== requestSequence || (cause instanceof DOMException && cause.name === 'AbortError')) return
    const message = cause instanceof Error ? cause.message : '人工搭配工单加载失败'
    if (silent && items.value.length) {
      refreshWarning.value = message
    } else {
      items.value = []
      total.value = 0
      hasMore.value = false
      refreshedAt.value = ''
      error.value = message
    }
  } finally {
    if (sequence === requestSequence) {
      loading.value = false
      refreshing.value = false
    }
  }
}

watch(
  () => [selectedStatus.value, currentPage.value],
  () => void loadRequests(),
  { immediate: true },
)

onBeforeUnmount(() => requestController?.abort())
</script>

<template>
  <section class="workspace-page design-requests-page">
    <PageHeading
      eyebrow="CUSTOM DESIGN QUEUE"
      title="人工搭配"
      description="按最近更新时间查看真实服务单；列表只加载设计排期所需信息。"
    >
      <template #actions>
        <a
          class="heading-link"
          :href="legacyUrl"
        >设计规范与设置 ↗</a>
        <button
          type="button"
          :disabled="loading || refreshing"
          @click="loadRequests(true)"
        >
          {{ refreshing ? '刷新中' : '刷新工单' }}
        </button>
      </template>
    </PageHeading>

    <div class="design-queue-summary">
      <div>
        <span>当前结果</span>
        <strong>{{ total }}</strong>
        <small>条服务单</small>
      </div>
      <p>
        <span v-if="refreshedAt">最近刷新 {{ refreshedAt }}</span>
        <span v-else>正在同步服务队列</span>
        <b>打开工单后按需读取测算与方案资料</b>
      </p>
    </div>

    <div class="design-list-toolbar">
      <label>
        <span>服务状态</span>
        <select
          :value="selectedStatus"
          aria-label="筛选人工搭配服务状态"
          :disabled="loading"
          @change="setStatus"
        >
          <option
            v-for="option in CUSTOM_DESIGN_STATUS_OPTIONS"
            :key="option.value || 'all'"
            :value="option.value"
          >
            {{ option.label }}
          </option>
        </select>
      </label>
      <span v-if="items.length">
        第 {{ firstResult }}–{{ lastResult }} 条
      </span>
    </div>

    <p
      v-if="refreshWarning"
      class="inline-warning"
      role="alert"
    >
      本次刷新失败，已保留上次结果：{{ refreshWarning }}
    </p>

    <DesignRequestListSkeleton v-if="loading" />

    <PageErrorState
      v-else-if="error"
      eyebrow="QUEUE UNAVAILABLE"
      title="服务队列暂时无法读取"
      :message="error"
      @retry="loadRequests()"
    />

    <PageEmptyState
      v-else-if="!items.length"
      :title="selectedStatus ? '当前状态下暂无工单' : '暂无人工搭配工单'"
      :message="selectedStatus ? '清除状态筛选后可查看全部服务单。' : '用户提交并完成保证金流程后，服务单会出现在这里。'"
      @clear="clearStatus"
    >
      <template
        v-if="selectedStatus"
        #action
      >
        查看全部状态
      </template>
    </PageEmptyState>

    <template v-else>
      <div
        class="design-request-grid"
        role="table"
        aria-label="人工搭配服务单"
        :aria-busy="refreshing"
      >
        <div
          class="design-request-grid__head"
          role="row"
        >
          <span role="columnheader">服务单 / 报告</span>
          <span role="columnheader">佩戴偏好</span>
          <span role="columnheader">进度 / 时限</span>
          <span role="columnheader">保证金 / 方案</span>
          <span role="columnheader">更新时间</span>
          <span role="columnheader">操作</span>
        </div>

        <article
          v-for="item in sortedItems"
          :key="item.request_id"
          class="design-request-row"
          role="row"
        >
          <div
            class="design-request-cell design-request-cell--identity"
            data-label="服务单 / 报告"
            role="cell"
          >
            <strong>{{ item.request_id }}</strong>
            <span>{{ item.report_code || item.report_id }} · 第 {{ item.report_version || 1 }} 版</span>
          </div>

          <div
            class="design-request-cell design-request-cell--preference"
            data-label="佩戴偏好"
            role="cell"
          >
            <strong>{{ item.request?.style_preference || '未指定风格' }}</strong>
            <span>
              {{ preferenceMeasurement(item.request?.wrist_size_cm, 'cm') }} ·
              {{ preferenceMeasurement(item.request?.bead_size_mm, 'mm') }}
            </span>
            <small>{{ item.request?.budget || '预算未填' }}</small>
          </div>

          <div
            class="design-request-cell design-request-cell--status"
            data-label="进度 / 时限"
            role="cell"
          >
            <b
              class="status-label"
              :data-tone="customDesignStatusTone(item.status)"
            >
              {{ customDesignStatusLabel(item.status) }}
            </b>
            <span
              :class="{ 'design-request-cell__overdue': dueMinutes(item.first_draft_due_at) !== null && dueMinutes(item.first_draft_due_at)! <= 0 }"
            >{{ dueLabel(item.first_draft_due_at) }}</span>
          </div>

          <div
            class="design-request-cell design-request-cell--proposal"
            data-label="保证金 / 方案"
            role="cell"
          >
            <strong>¥{{ item.deposit?.amount_text || '0.00' }} · {{ depositStatusLabel(item.deposit?.status) }}</strong>
            <span>{{ proposalCount(item) }} 版方案</span>
            <small>{{ latestProposal(item)?.title || '尚未发布方案' }}</small>
          </div>

          <div
            class="design-request-cell design-request-cell--time"
            data-label="更新时间"
            role="cell"
          >
            <strong>{{ formatAdminDate(item.updated_at || item.created_at) }}</strong>
            <span>提交 {{ formatAdminDate(item.created_at) }}</span>
          </div>

          <div
            class="design-request-cell design-request-cell--action"
            data-label="操作"
            role="cell"
          >
            <RouterLink
              :class="{ 'is-primary': ['submitted', 'designing', 'revision_requested'].includes(item.status) }"
              :to="{
                name: 'design-request-detail',
                params: { requestId: item.request_id },
                query: { queueStatus: selectedStatus, queuePage: currentPage > 1 ? String(currentPage) : undefined },
              }"
            >
              {{ customDesignActionLabel(item.status) }} <span>→</span>
            </RouterLink>
          </div>
        </article>
      </div>

      <nav
        class="design-pagination"
        aria-label="人工搭配工单分页"
      >
        <button
          type="button"
          :disabled="currentPage === 1 || loading || refreshing"
          @click="changePage(currentPage - 1)"
        >
          ← 上一页
        </button>
        <span>第 {{ currentPage }} 页</span>
        <button
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
