export interface AfterSaleOrderSnapshot {
  status?: string
  status_text?: string
  payment_status?: string
  total_amount?: string
  receiver?: { name?: string; phone?: string; region?: string[]; detailAddress?: string }
  refund_status?: string
  refund?: { status?: string; out_refund_no?: string }
}

export interface AfterSaleEvent {
  event_type?: string
  from_status?: string
  to_status?: string
  operator_type?: string
  operator_id?: string
  note?: string
  created_at?: string
}

export interface AfterSaleCase {
  case_id: string
  order_id: string
  user_id?: string
  type: string
  type_text?: string
  reason_code?: string
  reason_text?: string
  reason?: string
  evidence_urls?: string[]
  order_snapshot?: AfterSaleOrderSnapshot
  order?: AfterSaleOrderSnapshot
  status: string
  status_text?: string
  requested_refund_fee?: number
  requested_refund_amount?: string
  approved_refund_fee?: number
  approved_refund_amount?: string
  resolution_type?: string
  review_note?: string
  reviewed_by?: string
  return_carrier?: string
  return_tracking_no?: string
  created_at?: string
  updated_at?: string
  events?: AfterSaleEvent[]
}

export interface AfterSaleListPage {
  items: AfterSaleCase[]
  total: number
  limit: number
  offset: number
  has_more: boolean
}
