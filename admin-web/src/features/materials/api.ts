import { apiRequest } from '@/api/client'

export interface Material {
  id: string
  name?: string
  top?: string
  category?: string
  series?: string
  grade?: string
  size?: number
  weight?: number
  sort_order?: number
  physical_specs?: Record<string, unknown>
  image_url?: string
  image_urls?: string[]
  sku?: {
    sku_id?: string
    price_per_bead?: number
    cost_price?: number
    stock?: number
    safety_stock?: number
    enabled?: boolean
    size_mm?: number
  }
  quality?: { score?: number; level?: string }
}

export interface MaterialPage {
  items: Material[]
  pagination: {
    page: number
    page_size: number
    total: number
    total_pages: number
    has_next: boolean
  }
}

export interface MaterialType {
  id: string
  code: string
  name: string
  description: string
  sort_order: number
  enabled: boolean
  category_count: number
  variety_count: number
  sku_count: number
}

export interface MaterialSeries {
  id: string
  parent_id: string
  kind: 'series'
  top: string
  name: string
  material_code?: string
  color?: string
  shine?: string
  image_url?: string
  image_urls?: string[]
  sort_order: number
  enabled: boolean
  energy?: {
    primary_element?: string
    effects?: string[]
    color_family?: string
    visual_tags?: string[]
  }
}

export interface MaterialCategory {
  id: string
  parent_id: string
  kind: 'category'
  top: string
  name: string
  sort_order: number
  enabled: boolean
  series: MaterialSeries[]
}

export interface MaterialTypeInput {
  id?: string
  code?: string
  name: string
  description: string
  sort_order: number
  enabled: boolean
}

export interface MaterialCategoryInput {
  id?: string
  top: string
  name: string
  sort_order: number
  enabled: boolean
}

export interface MaterialSeriesInput {
  id?: string
  category_id: string
  name: string
  material_code?: string
  color?: string
  shine?: string
  sort_order: number
  enabled: boolean
}

export interface MaterialAssetUploadResult {
  image_url: string
  url: string
  key: string
  inspection: {
    width: number
    height: number
    has_alpha: boolean
    animated: boolean
    bytes: number
    codec: string
  }
}

export interface MaterialAssetBindResult {
  id: string
  category_id: string
  top: string
  name: string
  image_url: string
  image_urls: string[]
  bound_count: number
  image_source: 'series'
}

export function listMaterials(
  query: { keyword: string; top: string; status: string; page: number; pageSize: number },
  signal?: AbortSignal,
): Promise<MaterialPage> {
  const params = new URLSearchParams({
    keyword: query.keyword,
    top: query.top,
    status: query.status,
    sort_by: 'sort_order',
    sort_order: 'asc',
    page: String(query.page),
    page_size: String(query.pageSize),
  })
  return apiRequest<MaterialPage>(`/api/v1/admin/materials?${params}`, { signal })
}

export function listMaterialTypes(includeDisabled = false, signal?: AbortSignal): Promise<MaterialType[]> {
  return apiRequest(`/api/v1/admin/material-types?include_disabled=${includeDisabled}`, { signal })
}

export function listMaterialTaxonomy(top: string, includeDisabled = true, signal?: AbortSignal): Promise<MaterialCategory[]> {
  const params = new URLSearchParams({ top, include_disabled: String(includeDisabled) })
  return apiRequest(`/api/v1/admin/material-taxonomy?${params}`, { signal })
}

export function getMaterial(materialId: string, signal?: AbortSignal): Promise<Material> {
  return apiRequest(`/api/v1/admin/materials/${encodeURIComponent(materialId)}`, { signal })
}

export function updateMaterial(materialId: string, payload: Record<string, unknown>): Promise<Material> {
  return apiRequest(`/api/v1/admin/materials/${encodeURIComponent(materialId)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function saveMaterialType(input: MaterialTypeInput): Promise<MaterialType> {
  return apiRequest('/api/v1/admin/material-types', { method: 'POST', body: JSON.stringify(input) })
}

export function saveMaterialCategory(input: MaterialCategoryInput): Promise<MaterialCategory> {
  return apiRequest('/api/v1/admin/material-taxonomy/categories', { method: 'POST', body: JSON.stringify(input) })
}

export function saveMaterialSeries(input: MaterialSeriesInput): Promise<MaterialSeries> {
  return apiRequest('/api/v1/admin/material-taxonomy/series', { method: 'POST', body: JSON.stringify(input) })
}

export function disableMaterialType(typeCode: string): Promise<void> {
  return apiRequest(`/api/v1/admin/material-types/${encodeURIComponent(typeCode)}`, { method: 'DELETE' })
}

export function disableMaterialTaxonomyItem(itemId: string): Promise<void> {
  return apiRequest(`/api/v1/admin/material-taxonomy/${encodeURIComponent(itemId)}`, { method: 'DELETE' })
}

export function deleteEmptyMaterialType(typeCode: string): Promise<void> {
  return apiRequest('/api/v1/admin/material-types/batch-delete', { method: 'POST', body: JSON.stringify({ ids: [typeCode] }) })
}

export function deleteEmptyMaterialCategory(categoryId: string): Promise<void> {
  return apiRequest('/api/v1/admin/material-taxonomy/categories/batch-delete', { method: 'POST', body: JSON.stringify({ ids: [categoryId] }) })
}

export function deleteEmptyMaterialSeries(seriesId: string): Promise<void> {
  return apiRequest('/api/v1/admin/material-taxonomy/series/batch-delete', { method: 'POST', body: JSON.stringify({ ids: [seriesId] }) })
}

export function uploadMaterialAsset(file: Blob, filename: string): Promise<MaterialAssetUploadResult> {
  const form = new FormData()
  form.append('file', file, filename)
  return apiRequest('/api/v1/admin/material-assets/upload', { method: 'POST', body: form })
}

export function bindMaterialAssets(seriesId: string, assetKeys: string[], mode: 'replace' | 'append'): Promise<MaterialAssetBindResult> {
  return apiRequest('/api/v1/admin/material-assets/bind', {
    method: 'POST',
    body: JSON.stringify({ series_id: seriesId, asset_keys: assetKeys, mode }),
  })
}
