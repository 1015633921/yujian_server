import { apiRequest } from '@/api/client'

import type { AdminOrder, OrderListPage, OrderListQuery } from './types'

interface OrderListPayload {
  items?: AdminOrder[]
  total?: number
  limit?: number
  offset?: number
  has_more?: boolean
}

export async function listOrders(query: OrderListQuery, signal?: AbortSignal): Promise<OrderListPage> {
  const params = new URLSearchParams({
    keyword: query.keyword || '',
    status: query.status || '',
    limit: String(query.limit),
    offset: String(query.offset),
    include_meta: 'true',
  })
  const payload = await apiRequest<OrderListPayload | AdminOrder[]>(`/api/v1/admin/orders?${params.toString()}`, { signal })
  if (Array.isArray(payload)) {
    return { items: payload, total: query.offset + payload.length, limit: query.limit, offset: query.offset, has_more: payload.length === query.limit }
  }
  const items = Array.isArray(payload.items) ? payload.items : []
  const offset = Number(payload.offset) || 0
  const limit = Number(payload.limit) || query.limit
  const total = Number.isFinite(Number(payload.total)) ? Number(payload.total) : offset + items.length
  return { items, total, limit, offset, has_more: payload.has_more ?? offset + items.length < total }
}

export function getOrder(orderId: string, signal?: AbortSignal): Promise<AdminOrder> {
  return apiRequest<AdminOrder>(`/api/v1/admin/orders/${encodeURIComponent(orderId)}`, { signal })
}

export function shipOrder(orderId: string, payload: { carrier: string; carrier_code: string; tracking_no: string; phone_tail: string }): Promise<AdminOrder> {
  return apiRequest<AdminOrder>(`/api/v1/admin/orders/${encodeURIComponent(orderId)}/ship`, { method: 'POST', body: JSON.stringify(payload) })
}

export function refreshOrderLogistics(orderId: string): Promise<AdminOrder> {
  return apiRequest<AdminOrder>(`/api/v1/admin/orders/${encodeURIComponent(orderId)}/logistics/refresh`, { method: 'POST' })
}
