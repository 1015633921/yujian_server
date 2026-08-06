<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import PageErrorState from '@/components/ui/PageErrorState.vue'
import { getOrder, refreshOrderLogistics, shipOrder } from '@/features/orders/api'
import { formatCurrency, formatOrderDate, orderStatusLabel, orderStatusTone, paymentStatusLabel, receiverAddress } from '@/features/orders/presentation'
import type { AdminOrder } from '@/features/orders/types'

const route = useRoute()
const order = ref<AdminOrder | null>(null)
const loading = ref(true)
const error = ref('')
const shipping = ref(false)
const refreshingLogistics = ref(false)
const actionMessage = ref('')
const carrierCode = ref('shunfeng')
const carrier = ref('顺丰速运')
const trackingNo = ref('')
const phoneTail = ref('')
let controller: AbortController | null = null
let version = 0

const orderId = computed(() => String(route.params.orderId || ''))
const returnLocation = computed(() => ({ name: 'orders', query: { keyword: route.query.keyword, status: route.query.status, page: route.query.page } }))
const canShip = computed(() => order.value?.status === 'pending_ship')
const logistics = computed(() => order.value?.logistics || {})

function syncCarrier(event: Event): void {
  const [name, code] = (event.target as HTMLSelectElement).value.split('|')
  carrier.value = name || '顺丰速运'
  carrierCode.value = code || 'shunfeng'
}

async function loadOrder(): Promise<void> {
  const current = ++version
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  actionMessage.value = ''
  try {
    const result = await getOrder(orderId.value, controller.signal)
    if (current !== version) return
    order.value = result
    carrier.value = result.logistics?.carrier || '顺丰速运'
    carrierCode.value = result.logistics?.carrier_code || 'shunfeng'
    trackingNo.value = result.logistics?.tracking_no || ''
    phoneTail.value = result.logistics?.phone_tail || String(result.receiver?.phone || '').slice(-4)
  } catch (cause) {
    if (current !== version || (cause instanceof DOMException && cause.name === 'AbortError')) return
    error.value = cause instanceof Error ? cause.message : '订单详情加载失败'
  } finally {
    if (current === version) loading.value = false
  }
}

async function submitShipment(): Promise<void> {
  if (!order.value || shipping.value) return
  if (trackingNo.value.trim().length < 6) {
    actionMessage.value = '请填写至少 6 位的快递单号。'
    return
  }
  if (!window.confirm(`确认将 ${order.value.order_id} 标记为已发货？`)) return
  shipping.value = true
  actionMessage.value = ''
  try {
    order.value = await shipOrder(order.value.order_id, { carrier: carrier.value, carrier_code: carrierCode.value, tracking_no: trackingNo.value.trim(), phone_tail: phoneTail.value.trim() })
    actionMessage.value = '发货信息已提交，物流订阅将由服务端继续处理。'
  } catch (cause) {
    actionMessage.value = cause instanceof Error ? cause.message : '发货提交失败'
  } finally {
    shipping.value = false
  }
}

async function refreshLogisticsNow(): Promise<void> {
  if (!order.value || refreshingLogistics.value) return
  refreshingLogistics.value = true
  actionMessage.value = ''
  try {
    order.value = await refreshOrderLogistics(order.value.order_id)
    actionMessage.value = '已刷新最新物流状态。'
  } catch (cause) {
    actionMessage.value = cause instanceof Error ? cause.message : '物流刷新失败'
  } finally {
    refreshingLogistics.value = false
  }
}

async function copyReceiver(): Promise<void> {
  if (!order.value) return
  const receiver = order.value.receiver || {}
  const content = `${receiver.name || ''} ${receiver.phone || ''}\n${receiverAddress(receiver)}`.trim()
  try {
    await navigator.clipboard.writeText(content)
    actionMessage.value = '收件信息已复制。'
  } catch {
    actionMessage.value = '当前浏览器未授予剪贴板权限，请手动复制收件信息。'
  }
}

watch(orderId, () => void loadOrder(), { immediate: true })
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <section class="workspace-page order-detail-page">
    <RouterLink
      class="detail-back"
      :to="returnLocation"
    >
      ← 返回订单履约
    </RouterLink>
    <div
      v-if="loading"
      class="design-detail-skeleton"
      aria-label="正在加载订单详情"
    >
      <i /><i /><i />
    </div>
    <PageErrorState
      v-else-if="error"
      eyebrow="ORDER UNAVAILABLE"
      title="订单详情暂时无法读取"
      :message="error"
      @retry="loadOrder"
    />
    <template v-else-if="order">
      <header class="detail-heading">
        <div><span>ORDER FULFILLMENT · {{ order.order_id }}</span><h1>{{ order.status_text || orderStatusLabel(order.status) }}</h1><p>订单金额 {{ formatCurrency(order.total_amount) }} · {{ order.sequence?.length || 0 }} 颗材料快照 · {{ paymentStatusLabel(order.payment_status) }}</p></div>
        <div class="detail-heading__actions">
          <b
            class="status-label"
            :data-tone="orderStatusTone(order.status)"
          >{{ order.status_text || orderStatusLabel(order.status) }}</b><button
            v-if="logistics.tracking_no"
            type="button"
            :disabled="refreshingLogistics"
            @click="refreshLogisticsNow"
          >
            {{ refreshingLogistics ? '刷新中' : '刷新物流' }}
          </button>
        </div>
      </header>

      <p
        v-if="actionMessage"
        class="order-action-message"
        role="status"
      >
        {{ actionMessage }}
      </p>
      <div class="order-detail-metrics">
        <div><span>应付金额</span><strong>{{ formatCurrency(order.total_amount) }}</strong></div><div><span>下单时间</span><strong>{{ formatOrderDate(order.created_at) }}</strong></div><div><span>付款时间</span><strong>{{ formatOrderDate(order.paid_at) }}</strong></div><div><span>材料种类</span><strong>{{ order.bom?.length || 0 }} 种</strong></div>
      </div>

      <div class="order-detail-grid">
        <div>
          <section class="order-detail-section">
            <div class="detail-section-head">
              <div><span>DELIVERY</span><h3>收货与发货</h3></div><button
                type="button"
                @click="copyReceiver"
              >
                复制收件信息
              </button>
            </div>
            <div class="receiver-summary">
              <strong>{{ order.receiver?.name || '-' }} · {{ order.receiver?.phone || '-' }}</strong><p>{{ receiverAddress(order.receiver) }}</p><small>快递：{{ logistics.carrier || '尚未发货' }} · {{ logistics.tracking_no || '-' }}</small>
            </div>
            <form
              v-if="canShip"
              class="shipment-form"
              @submit.prevent="submitShipment"
            >
              <label><span>快递公司</span><select
                :value="`${carrier}|${carrierCode}`"
                :disabled="shipping"
                @change="syncCarrier"
              ><option value="顺丰速运|shunfeng">顺丰速运</option><option value="中通快递|zhongtong">中通快递</option><option value="圆通速递|yuantong">圆通速递</option><option value="申通快递|shentong">申通快递</option><option value="韵达快递|yunda">韵达快递</option><option value="极兔速递|jtexpress">极兔速递</option></select></label>
              <label><span>快递单号</span><input
                v-model="trackingNo"
                :disabled="shipping"
                placeholder="至少 6 位"
              ></label>
              <label><span>手机号后四位</span><input
                v-model="phoneTail"
                :disabled="shipping"
                maxlength="8"
                placeholder="用于物流查询"
              ></label>
              <button
                class="primary-action"
                type="submit"
                :disabled="shipping"
              >
                {{ shipping ? '正在提交…' : '确认发货' }}
              </button>
            </form>
            <ol
              v-else-if="logistics.traces?.length"
              class="logistics-traces"
            >
              <li
                v-for="(trace, index) in [...(logistics.traces || [])].reverse()"
                :key="`${trace.time || index}-${trace.desc || ''}`"
              >
                <strong>{{ trace.desc || logistics.status_text || '物流更新' }}</strong><span>{{ trace.location || '' }} {{ formatOrderDate(trace.time) }}</span>
              </li>
            </ol>
          </section>

          <section class="order-detail-section">
            <div class="detail-section-head">
              <div><span>BEAD SEQUENCE</span><h3>逐颗材料</h3></div><b>{{ order.sequence?.length || 0 }} 颗</b>
            </div>
            <ol class="order-sequence">
              <li
                v-for="(item, index) in order.sequence || []"
                :key="`${item.index || index}-${item.sku || item.id || ''}`"
              >
                <span>{{ String(item.index || index + 1).padStart(2, '0') }}</span><img
                  v-if="item.image_url"
                  :src="item.image_url"
                  alt=""
                ><i v-else /><div><strong>{{ item.name || item.id || '未命名材料' }}</strong><small>{{ [item.series, item.grade, item.size ? `${item.size}mm` : item.sku].filter(Boolean).join(' · ') || '-' }}</small></div><b>{{ formatCurrency(item.price) }}</b>
              </li>
            </ol>
          </section>
        </div>
        <aside>
          <section class="order-detail-section">
            <div class="detail-section-head">
              <div><span>PICKING LIST</span><h3>拣货汇总</h3></div>
            </div><ul class="bom-list">
              <li
                v-for="item in order.bom || []"
                :key="`${item.sku || item.name}`"
              >
                <span>{{ item.name || item.sku || '-' }}<small>{{ item.sku || '-' }}</small></span><b>× {{ item.qty || 0 }}</b>
              </li><li
                v-if="!order.bom?.length"
                class="empty-line"
              >
                暂无拣货资料
              </li>
            </ul>
          </section>
          <section class="order-detail-section">
            <div class="detail-section-head">
              <div><span>DESIGN</span><h3>定制参数</h3></div>
            </div><dl class="order-definition-list">
              <div><dt>DIY 方案</dt><dd>{{ order.design_id || '订单材料快照' }}</dd></div><div><dt>用户手围</dt><dd>{{ order.design?.wristSize || '-' }} cm</dd></div><div><dt>佩戴方式</dt><dd>{{ order.design?.wearStyle === 'double' ? '双圈' : '单圈' }}</dd></div><div><dt>订单备注</dt><dd>{{ order.remark || '-' }}</dd></div>
            </dl>
          </section>
          <section class="order-detail-section">
            <div class="detail-section-head">
              <div><span>HISTORY</span><h3>状态记录</h3></div>
            </div><ol class="order-history">
              <li
                v-for="(entry, index) in [...(order.status_history || [])].reverse()"
                :key="`${entry.time || index}-${entry.status || ''}`"
              >
                <strong>{{ entry.label || orderStatusLabel(entry.status) }}</strong><span>{{ formatOrderDate(entry.time) }}</span>
              </li><li
                v-if="!order.status_history?.length"
                class="empty-line"
              >
                暂无状态记录
              </li>
            </ol>
          </section>
        </aside>
      </div>
    </template>
  </section>
</template>
