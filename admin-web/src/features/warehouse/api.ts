import { apiRequest } from '@/api/client'

export interface WarehouseOption { key?: string; label?: string; enabled?: boolean; [key: string]: unknown }
export interface WarehouseItem {
  item_id: string
  item_code: string
  display_name: string
  material_name: string
  item_type: string
  category?: string
  size_mm?: number
  grade?: string
  unit?: string
  unit_label?: string
  image_urls?: string[]
  actual_stock: number
  batch_count: number
  avg_cost: number
  stock_cost_value: number
  enabled: boolean
}
export interface WarehouseMovement { movement_id: string; movement_no?: string; item_id: string; item_name?: string; item_code?: string; movement_type: string; quantity: number; before_quantity?: number; after_quantity?: number; occurred_at?: string; channel_name?: string; batch_no?: string; external_order_no?: string; reason?: string; [key: string]: unknown }
export interface WarehouseOverview { stats: { item_count: number; total_stock: number; stock_value: number; zero_stock_items: number; batch_count: number }; low_stock_items: WarehouseItem[]; recent_movements: WarehouseMovement[] }
export interface WarehouseSupplier { supplier_id: string; supplier_code: string; name: string; contact_name: string; phone: string; address: string; remark: string; enabled: boolean }
export interface WarehouseLocation { location_id: string; location_code: string; name: string; area: string; shelf: string; box_no: string; remark: string; enabled: boolean }
export interface WarehouseChannel { channel_id: string; channel_code: string; name: string; channel_type: string; remark: string; enabled: boolean }
export interface WarehouseOptions { suppliers: WarehouseSupplier[]; locations: WarehouseLocation[]; channels: WarehouseChannel[]; movement_types: WarehouseOption[]; item_types: WarehouseOption[]; grade_options: WarehouseOption[]; unit_options: WarehouseOption[] }
export interface WarehouseBatch { batch_id: string; batch_no: string; item_id: string; item_code?: string; item_name?: string; material_name?: string; remaining_quantity: number; inbound_quantity: number; unit_cost: number; total_cost?: number; status: string; supplier_name?: string; location_name?: string; inbound_at?: string; purchase_date?: string; quality_note?: string; remark?: string }
export interface WarehouseInboundInput { item_id: string; supplier_id?: string; location_id?: string; quantity: number; unit_cost: number; purchase_date?: string; inbound_at?: string; quality_note?: string; remark?: string }
export interface WarehouseOutboundInput { item_id: string; batch_id?: string; movement_type: string; channel_id?: string; quantity: number; external_order_no?: string; external_platform?: string; reason?: string; remark?: string; occurred_at?: string }
export interface WarehouseSupplierInput { supplier_id?: string; supplier_code?: string; name: string; contact_name?: string; phone?: string; address?: string; remark?: string; enabled: boolean }
export interface WarehouseLocationInput { location_id?: string; location_code?: string; name: string; area?: string; shelf?: string; box_no?: string; remark?: string; enabled: boolean }
export interface WarehouseChannelInput { channel_id?: string; channel_code?: string; name: string; channel_type: string; remark?: string; enabled: boolean }

export function warehouseOverview(signal?: AbortSignal): Promise<WarehouseOverview> { return apiRequest('/api/v1/admin/warehouse/overview', { signal }) }
export function warehouseOptions(signal?: AbortSignal): Promise<WarehouseOptions> { return apiRequest('/api/v1/admin/warehouse/options', { signal }) }
export function listWarehouseItems(query: { keyword: string; category: string; itemType: string; enabled: string }, signal?: AbortSignal): Promise<WarehouseItem[]> {
  const params = new URLSearchParams({ keyword: query.keyword, category: query.category, item_type: query.itemType, enabled: query.enabled, limit: '500' })
  return apiRequest(`/api/v1/admin/warehouse/items?${params}`, { signal })
}
export function listWarehouseMovements(query: { keyword: string; itemId: string; movementType: string; channelId: string; startDate: string; endDate: string }, signal?: AbortSignal): Promise<WarehouseMovement[]> {
  const params = new URLSearchParams({ keyword: query.keyword, item_id: query.itemId, movement_type: query.movementType, channel_id: query.channelId, start_date: query.startDate, end_date: query.endDate, limit: '300' })
  return apiRequest(`/api/v1/admin/warehouse/movements?${params}`, { signal })
}
export function listWarehouseBatches(query: { keyword?: string; itemId?: string; status?: string } = {}, signal?: AbortSignal): Promise<WarehouseBatch[]> {
  const params = new URLSearchParams({ item_id: query.itemId || '', status: query.status || '', keyword: query.keyword || '', limit: '300' })
  return apiRequest(`/api/v1/admin/warehouse/batches?${params}`, { signal })
}
export function createWarehouseInbound(input: WarehouseInboundInput): Promise<WarehouseBatch> { return apiRequest('/api/v1/admin/warehouse/inbound', { method: 'POST', body: JSON.stringify(input) }) }
export function createWarehouseOutbound(input: WarehouseOutboundInput): Promise<{ item_id: string; quantity: number; entries: Array<{ movement_id: string; batch_id: string; quantity: number }> }> { return apiRequest('/api/v1/admin/warehouse/outbound', { method: 'POST', body: JSON.stringify(input) }) }
export function saveWarehouseSupplier(input: WarehouseSupplierInput): Promise<WarehouseSupplier> { return apiRequest('/api/v1/admin/warehouse/suppliers', { method: 'POST', body: JSON.stringify(input) }) }
export function saveWarehouseLocation(input: WarehouseLocationInput): Promise<WarehouseLocation> { return apiRequest('/api/v1/admin/warehouse/locations', { method: 'POST', body: JSON.stringify(input) }) }
export function saveWarehouseChannel(input: WarehouseChannelInput): Promise<WarehouseChannel> { return apiRequest('/api/v1/admin/warehouse/channels', { method: 'POST', body: JSON.stringify(input) }) }
