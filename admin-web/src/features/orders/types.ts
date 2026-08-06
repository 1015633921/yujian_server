export const ORDER_STATUSES = [
  'pending_payment',
  'pending_ship',
  'shipped',
  'completed',
  'refund_requested',
  'refunded',
  'closed',
] as const

export type OrderStatus = (typeof ORDER_STATUSES)[number]

export interface OrderReceiver {
  name?: string
  phone?: string
  region?: string[]
  detailAddress?: string
  address?: string
}

export interface OrderLogisticsTrace {
  desc?: string
  location?: string
  time?: string
}

export interface OrderLogistics {
  carrier?: string
  carrier_code?: string
  tracking_no?: string
  phone_tail?: string
  status?: string
  status_text?: string
  traces?: OrderLogisticsTrace[]
}

export interface OrderSequenceItem {
  id?: string
  name?: string
  sku?: string
  series?: string
  grade?: string
  size?: number | string
  image_url?: string
  price?: number | string
  index?: number
}

export interface OrderBomItem {
  name?: string
  sku?: string
  qty?: number
}

export interface OrderDesign {
  wristSize?: number | string
  wearStyle?: string
  summary?: { count?: number; length?: number | string; weight?: number | string; price?: number | string }
}

export interface AdminOrder {
  order_id: string
  out_trade_no?: string
  user_id?: string
  design_id?: string
  status: string
  status_text?: string
  payment_status?: string
  total_amount?: string
  total_fee?: number
  currency?: string
  receiver?: OrderReceiver
  logistics?: OrderLogistics
  sequence?: OrderSequenceItem[]
  bom?: OrderBomItem[]
  design?: OrderDesign
  remark?: string
  created_at?: string
  updated_at?: string
  paid_at?: string
  status_history?: Array<{ status?: string; label?: string; time?: string }>
}

export interface OrderListPage {
  items: AdminOrder[]
  total: number
  limit: number
  offset: number
  has_more: boolean
}

export interface OrderListQuery {
  keyword?: string
  status?: string
  limit: number
  offset: number
}
