<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageEmptyState from '@/components/ui/PageEmptyState.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import { listAfterSales } from '@/features/after-sales/api'
import { AFTER_SALE_STATUS_OPTIONS, AFTER_SALE_TYPE_OPTIONS, afterSaleNextStep, afterSaleStatusLabel, afterSaleStatusTone, formatAfterSaleDate } from '@/features/after-sales/presentation'
import type { AfterSaleCase } from '@/features/after-sales/types'
import { legacyAdminPath } from '@/runtime/environment'

const PAGE_SIZE = 30
const route = useRoute(); const router = useRouter()
const items = ref<AfterSaleCase[]>([]); const total = ref(0); const hasMore = ref(false); const loading = ref(true); const refreshing = ref(false); const error = ref(''); const warning = ref('')
let controller: AbortController | null = null; let version = 0
const keyword = computed(() => typeof route.query.keyword === 'string' ? route.query.keyword : '')
const status = computed(() => typeof route.query.status === 'string' ? route.query.status : '')
const caseType = computed(() => typeof route.query.type === 'string' ? route.query.type : '')
const page = computed(() => { const value = Number(route.query.page); return Number.isInteger(value) && value > 0 ? value : 1 })
const offset = computed(() => (page.value - 1) * PAGE_SIZE)
const legacyUrl = computed(() => `${legacyAdminPath()}?page=afterSales`)
function query(updates: Record<string, string | undefined>): void { const next = { ...route.query }; for (const [key, value] of Object.entries(updates)) { if (value) next[key] = value; else delete next[key] }; void router.replace({ query: next }) }
function search(event: Event): void { const value = new FormData(event.target as HTMLFormElement).get('keyword'); query({ keyword: typeof value === 'string' ? value.trim() || undefined : undefined, page: undefined }) }
function select(event: Event, key: 'status' | 'type'): void { query({ [key]: (event.target as HTMLSelectElement).value || undefined, page: undefined }) }
function clear(): void { query({ keyword: undefined, status: undefined, type: undefined, page: undefined }) }
function changePage(next: number): void { if (next < 1 || (next > page.value && !hasMore.value)) return; query({ page: next > 1 ? String(next) : undefined }) }
async function load(silent = false): Promise<void> { const current = ++version; controller?.abort(); controller = new AbortController(); if (silent && items.value.length) refreshing.value = true; else loading.value = true; error.value = ''; warning.value = ''; try { const result = await listAfterSales({ keyword: keyword.value, status: status.value, caseType: caseType.value, limit: PAGE_SIZE, offset: offset.value }, controller.signal); if (current !== version) return; items.value = result.items; total.value = result.total; hasMore.value = result.has_more; if (!items.value.length && page.value > 1) changePage(Math.max(1, Math.ceil(total.value / PAGE_SIZE))) } catch (cause) { if (current !== version || (cause instanceof DOMException && cause.name === 'AbortError')) return; const message = cause instanceof Error ? cause.message : '售后工单加载失败'; if (silent && items.value.length) warning.value = message; else { items.value = []; total.value = 0; hasMore.value = false; error.value = message } } finally { if (current === version) { loading.value = false; refreshing.value = false } } }
watch(() => [keyword.value, status.value, caseType.value, page.value], () => void load(), { immediate: true }); onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <section class="workspace-page after-sales-page">
    <PageHeading
      eyebrow="AFTER-SALE SERVICE"
      title="售后服务"
      description="按工单当前状态处理；退款操作必须在工单详情内二次确认。"
    >
      <template #actions>
        <a
          class="heading-link"
          :href="legacyUrl"
        >打开当前后台售后页 ↗</a><button
          type="button"
          :disabled="loading || refreshing"
          @click="load(true)"
        >
          {{ refreshing ? '刷新中' : '刷新工单' }}
        </button>
      </template>
    </PageHeading>
    <div class="order-queue-summary">
      <div><span>当前结果</span><strong>{{ total }}</strong><small>张工单</small></div><p><b>{{ items.filter((item) => item.status === 'requested').length }}</b> 张待审核，请先确认用户诉求、凭证和关联订单。</p>
    </div>
    <div class="after-sales-toolbar">
      <form @submit.prevent="search">
        <label><span>工单搜索</span><input
          name="keyword"
          :value="keyword"
          :disabled="loading"
          placeholder="工单、订单、用户或问题说明"
        ></label><button
          type="submit"
          :disabled="loading"
        >
          查询
        </button>
      </form>
      <label><span>处理状态</span><select
        :value="status"
        :disabled="loading"
        @change="select($event, 'status')"
      ><option
        v-for="item in AFTER_SALE_STATUS_OPTIONS"
        :key="item.value || 'all'"
        :value="item.value"
      >{{ item.label }}</option></select></label>
      <label><span>用户诉求</span><select
        :value="caseType"
        :disabled="loading"
        @change="select($event, 'type')"
      ><option
        v-for="item in AFTER_SALE_TYPE_OPTIONS"
        :key="item.value || 'all'"
        :value="item.value"
      >{{ item.label }}</option></select></label>
    </div>
    <p
      v-if="warning"
      class="inline-warning"
    >
      本次刷新失败，已保留上次结果：{{ warning }}
    </p>
    <div
      v-if="loading"
      class="order-list-skeleton"
    >
      <i /><i /><i />
    </div>
    <PageErrorState
      v-else-if="error"
      eyebrow="CASES UNAVAILABLE"
      title="售后工单暂时无法读取"
      :message="error"
      @retry="load"
    />
    <PageEmptyState
      v-else-if="!items.length"
      :title="keyword || status || caseType ? '没有符合条件的售后工单' : '暂无售后工单'"
      :message="keyword || status || caseType ? '清除筛选后可查看全部工单。' : '用户提交售后申请后，工单会显示在这里。'"
      @clear="clear"
    >
      <template
        v-if="keyword || status || caseType"
        #action
      >
        清除筛选
      </template>
    </PageEmptyState>
    <template v-else>
      <div
        class="after-sale-grid"
        role="table"
        :aria-busy="refreshing"
      >
        <div
          class="after-sale-grid__head"
          role="row"
        >
          <span>售后工单</span><span>用户诉求</span><span>问题说明</span><span>订单 / 收货人</span><span>状态与下一步</span><span>申请时间</span><span>操作</span>
        </div>
        <article
          v-for="item in items"
          :key="item.case_id"
          class="after-sale-row"
          role="row"
        >
          <div
            class="after-sale-cell after-sale-cell--identity"
            data-label="售后工单"
          >
            <strong>{{ item.case_id }}</strong><span>订单 {{ item.order_id }}</span>
          </div><div
            class="after-sale-cell"
            data-label="用户诉求"
          >
            <strong>{{ item.type_text || item.type }}</strong><span>{{ item.reason_text || item.reason_code || '-' }}</span>
          </div><div
            class="after-sale-cell"
            data-label="问题说明"
          >
            <strong class="line-clamp">{{ item.reason || '-' }}</strong><span v-if="item.evidence_urls?.length">{{ item.evidence_urls.length }} 张用户凭证</span>
          </div><div
            class="after-sale-cell"
            data-label="订单 / 收货人"
          >
            <strong>{{ item.order?.receiver?.name || '-' }} · {{ item.order?.receiver?.phone || item.user_id || '-' }}</strong><span>{{ item.type === 'return_refund' ? `申请退款 ¥${item.requested_refund_amount || '0.00'}` : '服务类售后' }}</span>
          </div><div
            class="after-sale-cell"
            data-label="状态与下一步"
          >
            <b
              class="status-label"
              :data-tone="afterSaleStatusTone(item.status)"
            >{{ item.status_text || afterSaleStatusLabel(item.status) }}</b><span>{{ afterSaleNextStep(item) }}</span>
          </div><div
            class="after-sale-cell"
            data-label="申请时间"
          >
            <strong>{{ formatAfterSaleDate(item.created_at) }}</strong><span>更新 {{ formatAfterSaleDate(item.updated_at) }}</span>
          </div><div
            class="after-sale-cell after-sale-cell--action"
            data-label="操作"
          >
            <RouterLink
              :class="{ 'is-primary': item.status === 'requested' }"
              :to="{ name: 'after-sale-detail', params: { caseId: item.case_id }, query: { keyword: keyword || undefined, status: status || undefined, type: caseType || undefined, page: page > 1 ? String(page) : undefined } }"
            >
              {{ item.status === 'requested' ? '立即审核' : '查看工单' }} <span>→</span>
            </RouterLink>
          </div>
        </article>
      </div>
      <nav
        class="design-pagination"
        aria-label="售后工单分页"
      >
        <button
          type="button"
          :disabled="page === 1 || loading || refreshing"
          @click="changePage(page - 1)"
        >
          ← 上一页
        </button><span>第 {{ page }} 页</span><button
          type="button"
          :disabled="!hasMore || loading || refreshing"
          @click="changePage(page + 1)"
        >
          下一页 →
        </button>
      </nav>
    </template>
  </section>
</template>
