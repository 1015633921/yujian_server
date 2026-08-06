import type { OrderReceiver } from './types'

export const ORDER_STATUS_OPTIONS = [
  { value: '', label: '全部履约状态' },
  { value: 'pending_payment', label: '待付款' },
  { value: 'pending_ship', label: '待发货' },
  { value: 'shipped', label: '待收货' },
  { value: 'completed', label: '已完成' },
  { value: 'refund_requested', label: '退款中' },
  { value: 'refunded', label: '已退款' },
  { value: 'closed', label: '已关闭' },
] as const

const labels = Object.fromEntries(ORDER_STATUS_OPTIONS.filter((option) => option.value).map((option) => [option.value, option.label]))

export function orderStatusLabel(status?: string): string {
  return labels[status || ''] || '状态更新'
}

export function orderStatusTone(status?: string): string {
  if (status === 'pending_ship') return 'attention'
  if (status === 'shipped') return 'active'
  if (status === 'completed') return 'success'
  if (status === 'pending_payment' || status === 'refund_requested') return 'waiting'
  return 'muted'
}

export function paymentStatusLabel(status?: string): string {
  return ({ unpaid: '未支付', prepay_ready: '待支付', processing: '支付中', paid: '已支付', closed: '已关闭', refunded: '已退款' })[status || ''] || status || '-'
}

export function formatOrderDate(value?: string | null): string {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(date)
}

export function formatCurrency(value?: string | number | null): string {
  const amount = Number(value)
  return Number.isFinite(amount) ? `¥${amount.toFixed(2)}` : '¥0.00'
}

export function receiverAddress(receiver?: OrderReceiver): string {
  if (!receiver) return '-'
  return [[...(receiver.region || [])].join(' '), receiver.detailAddress || receiver.address || ''].filter(Boolean).join(' ') || '-'
}
