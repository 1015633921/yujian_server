import { apiRequest } from '@/api/client'
import type { AfterSaleCase, AfterSaleListPage } from './types'

interface Payload { items?: AfterSaleCase[]; total?: number; limit?: number; offset?: number; has_more?: boolean }
export async function listAfterSales(query: { keyword: string; status: string; caseType: string; limit: number; offset: number }, signal?: AbortSignal): Promise<AfterSaleListPage> {
  const params = new URLSearchParams({ keyword: query.keyword, status: query.status, case_type: query.caseType, limit: String(query.limit), offset: String(query.offset), include_meta: 'true' })
  const result = await apiRequest<Payload | AfterSaleCase[]>(`/api/v1/admin/after-sales?${params}`, { signal })
  if (Array.isArray(result)) return { items: result, total: query.offset + result.length, limit: query.limit, offset: query.offset, has_more: result.length === query.limit }
  const items = Array.isArray(result.items) ? result.items : []
  const offset = Number(result.offset) || 0
  return { items, total: Number.isFinite(Number(result.total)) ? Number(result.total) : offset + items.length, limit: Number(result.limit) || query.limit, offset, has_more: result.has_more ?? false }
}
export function getAfterSale(caseId: string, signal?: AbortSignal): Promise<AfterSaleCase> { return apiRequest<AfterSaleCase>(`/api/v1/admin/after-sales/${encodeURIComponent(caseId)}`, { signal }) }
export function reviewAfterSale(caseId: string, action: string, note: string): Promise<AfterSaleCase> { return apiRequest<AfterSaleCase>(`/api/v1/admin/after-sales/${encodeURIComponent(caseId)}/review`, { method: 'POST', body: JSON.stringify({ action, note }) }) }
export function submitAfterSaleRefund(caseId: string, note: string): Promise<AfterSaleCase> { return apiRequest<AfterSaleCase>(`/api/v1/admin/after-sales/${encodeURIComponent(caseId)}/refund`, { method: 'POST', body: JSON.stringify({ note }) }) }
export function syncAfterSaleRefund(caseId: string): Promise<AfterSaleCase> { return apiRequest<AfterSaleCase>(`/api/v1/admin/after-sales/${encodeURIComponent(caseId)}/refund/sync`, { method: 'POST' }) }
export function retryAfterSaleRefund(caseId: string, note: string): Promise<AfterSaleCase> { return apiRequest<AfterSaleCase>(`/api/v1/admin/after-sales/${encodeURIComponent(caseId)}/refund/retry`, { method: 'POST', body: JSON.stringify({ note }) }) }
