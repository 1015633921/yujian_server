import type { AfterSaleCase } from './types'

export const AFTER_SALE_STATUS_OPTIONS = [
  { value: '', label: '全部状态' }, { value: 'requested', label: '待审核' }, { value: 'awaiting_return', label: '等待寄回' },
  { value: 'returning', label: '寄回中' }, { value: 'service_processing', label: '处理中' }, { value: 'refund_pending', label: '待确认退款' },
  { value: 'refund_submitting', label: '退款提交中' }, { value: 'refunding', label: '退款处理中' }, { value: 'resolved', label: '已完成' },
  { value: 'rejected', label: '已拒绝' }, { value: 'canceled', label: '已取消' },
] as const

export const AFTER_SALE_TYPE_OPTIONS = [
  { value: '', label: '全部诉求' }, { value: 'return_refund', label: '退货退款' }, { value: 'resize', label: '修改手围' },
  { value: 'repair', label: '重新穿制／维修' }, { value: 'resend', label: '缺件／补发' }, { value: 'other', label: '其他问题' },
] as const

const statusLabels = Object.fromEntries(AFTER_SALE_STATUS_OPTIONS.filter((item) => item.value).map((item) => [item.value, item.label]))
export function afterSaleStatusLabel(status?: string): string { return statusLabels[status || ''] || '状态更新' }
const eventLabels: Record<string, string> = {
  submitted: '用户提交售后申请', reject: '已拒绝售后申请', approve_service: '已接受服务处理', request_return: '已要求寄回商品',
  return_shipped: '用户已提交退回物流', canceled: '用户已取消售后申请', prepare_direct_refund: '已批准免退退款',
  confirm_return: '已确认收到退回商品', complete: '服务处理已完成', refund_submitting: '退款指令已登记',
  refund_submitted: '已提交原路退款', refund_failed: '退款未生效，等待核对', refund_success: '原路退款已成功',
}
export function afterSaleEventLabel(eventType?: string): string { return eventLabels[eventType || ''] || '已记录处理动作' }
export function afterSaleEventStatusText(fromStatus?: string, toStatus?: string): string {
  if (!fromStatus && !toStatus) return '已记录本次处理'
  if (!fromStatus) return `状态更新为「${afterSaleStatusLabel(toStatus)}」`
  if (!toStatus || fromStatus === toStatus) return `状态保持为「${afterSaleStatusLabel(fromStatus)}」`
  return `状态：${afterSaleStatusLabel(fromStatus)} → ${afterSaleStatusLabel(toStatus)}`
}
export function afterSaleStatusTone(status?: string): string {
  if (status === 'requested' || status?.startsWith('refund_')) return 'attention'
  if (status === 'awaiting_return' || status === 'returning') return 'waiting'
  if (status === 'service_processing' || status === 'refunding') return 'active'
  if (status === 'resolved') return 'success'
  return 'muted'
}
export function afterSaleNextStep(item: AfterSaleCase): string {
  if (item.status === 'requested') return item.type === 'return_refund' ? '审核退货或免退退款' : '审核是否接受服务'
  if (['awaiting_return', 'returning'].includes(item.status)) return '等待商品寄回并确认收货'
  if (item.status === 'service_processing') return '完成维修、改手围或补发服务'
  if (item.status === 'refund_pending') return '核对后发起微信原路退款'
  if (item.status === 'refund_submitting') return '同步微信确认退款结果'
  if (item.status === 'refunding') return '等待微信退款结果'
  return item.status === 'resolved' ? '工单已闭环' : '-'
}
export function formatAfterSaleDate(value?: string): string {
  if (!value || Number.isNaN(new Date(value).getTime())) return '-'
  return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(value))
}
export function actionConfig(item: AfterSaleCase): { action: string; label: string; danger?: boolean } | null {
  if (item.status === 'requested') return item.type === 'return_refund' ? { action: 'request_return', label: '同意并要求寄回' } : { action: 'approve_service', label: '接受并开始处理' }
  if (['awaiting_return', 'returning'].includes(item.status)) return { action: 'confirm_return', label: '确认收到退回商品' }
  if (item.status === 'service_processing') return { action: 'complete', label: '标记服务已完成' }
  return null
}
