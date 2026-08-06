import type {
  CustomDesignListItem,
  CustomDesignProposalSummary,
  CustomDesignStatus,
} from './types'
import { CUSTOM_DESIGN_STATUSES } from './types'

export const CUSTOM_DESIGN_STATUS_OPTIONS: ReadonlyArray<{
  value: '' | CustomDesignStatus
  label: string
}> = [
  { value: '', label: '全部状态' },
  { value: 'deposit_pending', label: '待付保证金' },
  { value: 'submitted', label: '待设计' },
  { value: 'designing', label: '设计中' },
  { value: 'revision_requested', label: '待调整' },
  { value: 'proposed', label: '待用户确认' },
  { value: 'completed', label: '设计已完成' },
  { value: 'confirmed', label: '已确认（历史）' },
  { value: 'closed', label: '已结束' },
]

const STATUS_LABELS: Record<string, string> = Object.fromEntries(
  CUSTOM_DESIGN_STATUS_OPTIONS.filter((item) => item.value).map((item) => [item.value, item.label]),
)

const DEPOSIT_STATUS_LABELS: Record<string, string> = {
  unpaid: '待支付',
  prepay_ready: '待支付',
  processing: '支付中',
  paid: '已支付',
  refund_submitting: '退款提交中',
  refunding: '退款中',
  refunded: '已退回',
  refund_failed: '退款待重试',
}

export function normalizeCustomDesignStatus(value: unknown): '' | CustomDesignStatus {
  const status = typeof value === 'string' ? value : ''
  return CUSTOM_DESIGN_STATUSES.includes(status as CustomDesignStatus)
    ? (status as CustomDesignStatus)
    : ''
}

export function customDesignStatusLabel(status: string): string {
  if (!status) return '-'
  return STATUS_LABELS[status] || '状态更新'
}

export function depositStatusLabel(status?: string): string {
  return (status && DEPOSIT_STATUS_LABELS[status]) || '-'
}

export function customDesignStatusTone(status: string): string {
  if (status === 'submitted' || status === 'revision_requested') return 'attention'
  if (status === 'designing') return 'active'
  if (status === 'proposed' || status === 'deposit_pending') return 'waiting'
  if (status === 'completed' || status === 'confirmed') return 'success'
  return 'muted'
}

export function customDesignActionLabel(status: string): string {
  return ['submitted', 'designing', 'revision_requested'].includes(status)
    ? '开始设计'
    : '查看工单'
}

export function proposalCount(item: CustomDesignListItem): number {
  if (Number.isFinite(Number(item.proposal_count))) return Math.max(0, Number(item.proposal_count))
  return Array.isArray(item.proposals) ? item.proposals.length : 0
}

export function latestProposal(item: CustomDesignListItem): CustomDesignProposalSummary | null {
  if (item.latest_proposal) return item.latest_proposal
  const proposal = Array.isArray(item.proposals) ? item.proposals[0] : undefined
  if (proposal) return proposal
  if (item.latest_proposal_title) return { title: item.latest_proposal_title }
  return null
}

export function formatAdminDate(value?: string | null): string {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}

export function preferenceMeasurement(value: number | string | undefined, unit: string): string {
  if (value === undefined || value === null || String(value).trim() === '') return '-'
  return `${String(value).trim()}${unit}`
}
