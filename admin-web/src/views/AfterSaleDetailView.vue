<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import ActionConfirmDialog from '@/components/ui/ActionConfirmDialog.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import { getAfterSale, retryAfterSaleRefund, reviewAfterSale, submitAfterSaleRefund, syncAfterSaleRefund } from '@/features/after-sales/api'
import { actionConfig, afterSaleEventLabel, afterSaleEventStatusText, afterSaleNextStep, afterSaleStatusLabel, afterSaleStatusTone, formatAfterSaleDate } from '@/features/after-sales/presentation'
import type { AfterSaleCase } from '@/features/after-sales/types'

type Confirmation = { kind: 'review' | 'refund'; action: string; label: string; description: string; tone: 'default' | 'danger' }

const route = useRoute(); const item = ref<AfterSaleCase | null>(null); const loading = ref(true); const error = ref(''); const note = ref(''); const acting = ref(false); const message = ref(''); const confirmation = ref<Confirmation | null>(null)
let controller: AbortController | null = null; let version = 0
const caseId = computed(() => String(route.params.caseId || ''))
const returnLocation = computed(() => ({ name: 'after-sales', query: { keyword: route.query.keyword, status: route.query.status, type: route.query.type, page: route.query.page } }))
const nextAction = computed(() => item.value ? actionConfig(item.value) : null)
const refundState = computed(() => item.value?.order?.refund_status || item.value?.order?.refund?.status || '')
const canRefund = computed(() => item.value?.status === 'refund_pending' && refundState.value === 'approved')
const canSync = computed(() => ['refund_pending', 'refund_submitting', 'refunding'].includes(item.value?.status || ''))
function actionLabel(action: string): string { return ({ request_return: '同意并要求寄回', approve_service: '接受并开始处理', confirm_return: '确认收到退回商品', complete: '标记服务已完成' })[action] || '更新工单' }
function actionHint(action: string): string { return ({ request_return: '本操作不会退款。用户寄回商品并经确认后，才可进入退款环节。', approve_service: '请记录处理方式、寄送安排或预计完成时间。', confirm_return: '确认商品已收到并核验无误后，系统将生成待确认退款记录。', complete: '确认维修、改手围或补发已实际完成后再关闭工单。' })[action] || '' }
async function load(): Promise<void> { const current = ++version; controller?.abort(); controller = new AbortController(); loading.value = true; error.value = ''; message.value = ''; try { const result = await getAfterSale(caseId.value, controller.signal); if (current !== version) return; item.value = result } catch (cause) { if (current !== version || (cause instanceof DOMException && cause.name === 'AbortError')) return; error.value = cause instanceof Error ? cause.message : '售后工单加载失败' } finally { if (current === version) loading.value = false } }
function requestReview(action: string): void { if (!item.value || acting.value) return; if (action === 'reject' && note.value.trim().length < 2) { message.value = '请填写至少 2 个字的拒绝原因。'; return }; confirmation.value = { kind: 'review', action, label: actionLabel(action), description: actionHint(action) || '该操作会更新售后工单状态，请确认处理依据与用户沟通记录。', tone: action === 'reject' ? 'danger' : 'default' } }
async function review(action: string): Promise<void> { if (!item.value || acting.value) return; acting.value = true; message.value = ''; try { item.value = await reviewAfterSale(item.value.case_id, action, note.value.trim()); note.value = ''; confirmation.value = null; message.value = '工单已更新。' } catch (cause) { message.value = cause instanceof Error ? cause.message : '工单更新失败' } finally { acting.value = false } }
function requestRefund(kind: 'submit' | 'sync' | 'retry'): void { if (!item.value || acting.value) return; if (kind !== 'sync' && !note.value.trim()) { message.value = '请填写本次退款核验备注。'; return }; const labels = { submit: '发起微信原路退款', sync: '同步微信退款状态', retry: '核对并恢复退款' }; confirmation.value = { kind: 'refund', action: kind, label: labels[kind], description: kind === 'sync' ? '将向支付渠道读取最新退款状态，不会新建退款。' : '该操作会触发真实支付状态变更，请核对退款金额、退回商品与处理备注。', tone: kind === 'sync' ? 'default' : 'danger' } }
async function refund(kind: 'submit' | 'sync' | 'retry'): Promise<void> { if (!item.value || acting.value) return; acting.value = true; message.value = ''; try { item.value = kind === 'submit' ? await submitAfterSaleRefund(item.value.case_id, note.value.trim()) : kind === 'sync' ? await syncAfterSaleRefund(item.value.case_id) : await retryAfterSaleRefund(item.value.case_id, note.value.trim()); note.value = ''; confirmation.value = null; message.value = kind === 'sync' ? '已同步微信退款状态。' : '退款操作已提交，状态以微信返回为准。' } catch (cause) { message.value = cause instanceof Error ? cause.message : '退款操作失败' } finally { acting.value = false } }
function confirmAction(): void { if (!confirmation.value) return; if (confirmation.value.kind === 'review') void review(confirmation.value.action); else void refund(confirmation.value.action as 'submit' | 'sync' | 'retry') }
watch(caseId, () => void load(), { immediate: true }); onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <section class="workspace-page after-sale-detail-page">
    <RouterLink
      class="detail-back"
      :to="returnLocation"
    >
      ← 返回售后服务
    </RouterLink><div
      v-if="loading"
      class="design-detail-skeleton"
    >
      <i /><i /><i />
    </div><PageErrorState
      v-else-if="error"
      eyebrow="CASE UNAVAILABLE"
      title="售后工单暂时无法读取"
      :message="error"
      @retry="load"
    />
    <template v-else-if="item">
      <header class="detail-heading">
        <div><span>AFTER-SALE CASE · {{ item.case_id }}</span><h1>{{ item.type_text || item.type }}</h1><p>{{ item.reason_text || item.reason_code || '用户售后申请' }} · 关联订单 {{ item.order_id }}</p></div><div class="detail-heading__actions">
          <b
            class="status-label"
            :data-tone="afterSaleStatusTone(item.status)"
          >{{ item.status_text || afterSaleStatusLabel(item.status) }}</b><RouterLink :to="{ name: 'order-detail', params: { orderId: item.order_id } }">
            查看订单 →
          </RouterLink>
        </div>
      </header>
      <p
        v-if="message"
        class="order-action-message"
      >
        {{ message }}
      </p>
      <div class="after-sale-detail-grid">
        <div>
          <section class="order-detail-section">
            <div class="detail-section-head">
              <div><span>APPLICATION</span><h3>用户申请</h3></div><b>{{ formatAfterSaleDate(item.created_at) }}</b>
            </div><dl class="after-sale-definition">
              <div><dt>问题分类</dt><dd>{{ item.reason_text || item.reason_code || '-' }}</dd></div><div><dt>申请说明</dt><dd>{{ item.reason || '-' }}</dd></div><div v-if="item.return_tracking_no">
                <dt>退回物流</dt><dd>{{ item.return_carrier || '-' }} · {{ item.return_tracking_no }}</dd>
              </div>
            </dl><div class="evidence-strip">
              <a
                v-for="(url, index) in item.evidence_urls || []"
                :key="url"
                :href="url"
                target="_blank"
                rel="noreferrer"
              ><img
                :src="url"
                :alt="`用户凭证 ${index + 1}`"
              ><span>凭证 {{ index + 1 }}</span></a><p v-if="!item.evidence_urls?.length">
                用户未上传图片凭证
              </p>
            </div>
          </section>
          <section class="order-detail-section">
            <div class="detail-section-head">
              <div><span>REVIEW CONTROL</span><h3>处理操作</h3></div>
            </div><p class="after-sale-next">
              下一步：{{ afterSaleNextStep(item) }}
            </p><label class="after-sale-note"><span>处理备注{{ item.status === 'requested' ? '（拒绝时必填）' : '' }}</span><textarea
              v-model="note"
              maxlength="500"
              :disabled="acting"
              placeholder="记录处理依据、用户沟通或实际完成情况"
            /></label><div class="after-sale-actions">
              <button
                v-if="item.status === 'requested'"
                type="button"
                class="danger-outline"
                :disabled="acting"
                @click="requestReview('reject')"
              >
                拒绝申请
              </button><button
                v-if="item.status === 'requested' && item.type === 'return_refund'"
                type="button"
                :disabled="acting"
                @click="requestReview('prepare_direct_refund')"
              >
                免退并批准退款
              </button><button
                v-if="nextAction"
                type="button"
                class="primary-action"
                :disabled="acting"
                @click="requestReview(nextAction.action)"
              >
                {{ acting ? '处理中…' : nextAction.label }}
              </button>
            </div><p
              v-if="nextAction"
              class="action-hint"
            >
              {{ actionHint(nextAction.action) }}
            </p>
          </section>
          <section
            v-if="item.type === 'return_refund'"
            class="order-detail-section refund-control"
          >
            <div class="detail-section-head">
              <div><span>REFUND CONTROL</span><h3>退款与支付状态</h3></div>
            </div><dl class="after-sale-definition">
              <div><dt>申请退款</dt><dd>¥{{ item.requested_refund_amount || '0.00' }}</dd></div><div><dt>审核退款</dt><dd>{{ item.approved_refund_fee ? `¥${item.approved_refund_amount}` : '尚未批准' }}</dd></div><div><dt>订单退款状态</dt><dd>{{ refundState || '尚未进入退款' }}</dd></div><div><dt>商户退款单号</dt><dd>{{ item.order?.refund?.out_refund_no || '尚未生成' }}</dd></div>
            </dl><div
              v-if="canSync"
              class="after-sale-actions"
            >
              <button
                v-if="canRefund"
                type="button"
                class="danger-action"
                :disabled="acting"
                @click="requestRefund('submit')"
              >
                确认发起原路退款
              </button><button
                type="button"
                :disabled="acting"
                @click="requestRefund('sync')"
              >
                同步微信退款状态
              </button><button
                v-if="['submitting', 'abnormal', 'closed'].includes(refundState)"
                type="button"
                class="danger-outline"
                :disabled="acting"
                @click="requestRefund('retry')"
              >
                核对并恢复退款
              </button>
            </div><p
              v-if="canRefund"
              class="action-hint action-hint--danger"
            >
              将真实调用微信退款 API。请核对金额、退回商品与用户沟通记录后再继续。
            </p>
          </section>
        </div><aside>
          <section class="order-detail-section">
            <div class="detail-section-head">
              <div><span>ORDER SNAPSHOT</span><h3>订单快照</h3></div>
            </div><dl class="after-sale-definition">
              <div><dt>订单履约状态</dt><dd>{{ item.order?.status_text || item.order?.status || '-' }}</dd></div><div><dt>支付状态</dt><dd>{{ item.order?.payment_status || '-' }}</dd></div><div><dt>订单金额</dt><dd>¥{{ item.order?.total_amount || item.order_snapshot?.total_amount || '0.00' }}</dd></div><div><dt>收货人</dt><dd>{{ item.order?.receiver?.name || '-' }} · {{ item.order?.receiver?.phone || '-' }}</dd></div>
            </dl>
          </section><section class="order-detail-section">
            <div class="detail-section-head">
              <div><span>PROCESS LOG</span><h3>处理记录</h3></div>
            </div><ol class="order-history">
              <li
                v-for="(event, index) in [...(item.events || [])].reverse()"
                :key="`${event.created_at || index}-${event.event_type || ''}`"
              >
                <strong>{{ afterSaleEventLabel(event.event_type) }}</strong><span>{{ afterSaleEventStatusText(event.from_status, event.to_status) }} · {{ formatAfterSaleDate(event.created_at) }}</span><small v-if="event.note">{{ event.note }}</small>
              </li><li
                v-if="!item.events?.length"
                class="empty-line"
              >
                暂无处理记录
              </li>
            </ol>
          </section>
        </aside>
      </div>
      <ActionConfirmDialog
        :open="Boolean(confirmation)"
        :title="confirmation?.label || '确认操作'"
        :description="confirmation?.description"
        :confirm-label="confirmation?.label || '确认提交'"
        :tone="confirmation?.tone || 'default'"
        :busy="acting"
        @close="confirmation = null"
        @confirm="confirmAction"
      >
        <dl>
          <div><dt>售后工单</dt><dd>{{ item.case_id }}</dd></div>
          <div><dt>关联订单</dt><dd>{{ item.order_id }}</dd></div>
          <div><dt>申请金额</dt><dd>¥{{ item.requested_refund_amount || '0.00' }}</dd></div>
          <div><dt>审核金额</dt><dd>{{ item.approved_refund_fee ? `¥${item.approved_refund_amount}` : '尚未批准' }}</dd></div>
          <div><dt>退款状态</dt><dd>{{ refundState || '尚未进入退款' }}</dd></div>
        </dl>
        <p class="action-confirm__note">
          处理备注：{{ note.trim() || '未填写' }}
        </p>
      </ActionConfirmDialog>
    </template>
  </section>
</template>
