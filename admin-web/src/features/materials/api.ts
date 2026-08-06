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
  asset_version?: number
  sku?: {
    sku_id?: string
    price_per_bead?: number
    cost_price?: number
    stock?: number
    safety_stock?: number
    enabled?: boolean
    size_mm?: number
    revision?: number
    available_stock?: number
    stock_status?: 'normal' | 'low' | 'out'
    margin_rate?: number
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

export interface MaterialSpu {
  id: string
  series_id?: string
  spu: {
    series_id?: string
    top?: string
    category?: string
    series?: string
    material_code?: string
    sku_count?: number
    total_stock?: number
    enabled_count?: number
    min_price?: number
    max_price?: number
    size_values?: number[]
    missing_sizes?: number[]
    spec_status?: string
    asset_state?: string
    profile_state?: string
    image?: string
  }
  items: Material[]
  energy?: { primary_element?: string }
  assetState?: string
  profileState?: string
  specStatus?: string
  lowStockCount?: number
  outStockCount?: number
}

export interface MaterialSpuPage {
  items: MaterialSpu[]
  facets?: Record<string, Array<{ value: string; count: number }>>
  pagination: MaterialPage['pagination']
}

export interface MaterialSpuQuery {
  keyword: string
  top: string
  category: string
  status: string
  stockState: string
  assetState: string
  specState: string
  profileState: string
  page: number
  pageSize: number
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
  category_name?: string
  kind: 'series'
  top: string
  name: string
  material_code?: string
  color?: string
  shine?: string
  image_url?: string
  image_urls?: string[]
  asset_version?: number
  sort_order: number
  enabled: boolean
  energy?: {
    primary_element?: string
    secondary_elements?: string[]
    chakras?: string[]
    chakra_weights?: Record<string, number>
    effects?: string[]
    wish_pools?: string[]
    color_family?: string
    mood_tags?: string[]
    visual_tags?: string[]
    story?: string
  }
  rules?: {
    allowed_roles?: string[]
    conflict_codes?: string[]
    match_rules?: string[]
    care_tags?: string[]
  }
  material_params?: Record<string, unknown>
  asset?: Record<string, unknown>
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

export interface MaterialOption {
  key: string
  label: string
}

export interface MaterialOptionItem extends MaterialOption {
  id: string
  option_type: string
  enabled: boolean
  sort_order: number
}

export interface MaterialOptionsPayload {
  elements: MaterialOption[]
  wish_pools: MaterialOption[]
  chakras: MaterialOption[]
  color_families: MaterialOption[]
  grades: MaterialOption[]
  effects: MaterialOption[]
  mood_tags: MaterialOption[]
  visual_tags: MaterialOption[]
  roles: MaterialOption[]
  match_rules: MaterialOption[]
  care_tags: MaterialOption[]
  bead_shapes: MaterialOption[]
  placement_modes: MaterialOption[]
  visual_axes: MaterialOption[]
  surface_finishes: MaterialOption[]
  transparency_levels: MaterialOption[]
  texture_features: MaterialOption[]
  batch_variation_levels: MaterialOption[]
  option_items?: MaterialOptionItem[]
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
  series_id?: string
  category_id: string
  name: string
  material_code?: string
  color?: string
  shine?: string
  image_path?: string
  image_url?: string
  image_urls?: string[]
  sync_sku_images?: boolean
  primary_element?: string
  secondary_elements?: string[]
  chakras?: string[]
  chakra_weights?: Record<string, number>
  effects?: string[]
  wish_pools?: string[]
  color_family?: string
  mood_tags?: string[]
  visual_tags?: string[]
  story?: string
  allowed_roles?: string[]
  conflict_codes?: string[]
  match_rules?: string[]
  care_tags?: string[]
  material_params?: Record<string, unknown>
  asset?: Record<string, unknown>
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
  asset_version?: number
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

export function listMaterialSpus(query: MaterialSpuQuery, signal?: AbortSignal): Promise<MaterialSpuPage> {
  const params = new URLSearchParams({
    keyword: query.keyword,
    top: query.top,
    category: query.category,
    status: query.status,
    stock_state: query.stockState,
    asset_state: query.assetState,
    spec_state: query.specState,
    profile_state: query.profileState,
    include_facets: 'true',
    sort_by: 'sort_order',
    sort_order: 'asc',
    page: String(query.page),
    page_size: String(query.pageSize),
  })
  return apiRequest<MaterialSpuPage>(`/api/v1/admin/material-spus?${params}`, { signal })
}

export function listMaterialTypes(includeDisabled = false, signal?: AbortSignal): Promise<MaterialType[]> {
  return apiRequest(`/api/v1/admin/material-types?include_disabled=${includeDisabled}`, { signal })
}

export function listMaterialOptions(signal?: AbortSignal): Promise<MaterialOptionsPayload> {
  return apiRequest('/api/v1/admin/material-options', { signal })
}

export function listMaterialTaxonomy(top: string, includeDisabled = true, signal?: AbortSignal): Promise<MaterialCategory[]> {
  const params = new URLSearchParams({ top, include_disabled: String(includeDisabled) })
  return apiRequest(`/api/v1/admin/material-taxonomy?${params}`, { signal })
}

/** Reads the full series-owned profile before editing, so omitted fields cannot be overwritten. */
export function getMaterialSeries(seriesId: string, signal?: AbortSignal): Promise<MaterialSeries> {
  return apiRequest(`/api/v1/admin/material-taxonomy/series/${encodeURIComponent(seriesId)}`, { signal })
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

/** A caller-generated ID makes a timed-out create safe to retry without duplicating a SKU. */
export function createMaterialSku(payload: Record<string, unknown>): Promise<Material> {
  return apiRequest('/api/v1/admin/materials', { method: 'POST', body: JSON.stringify(payload) })
}

/** Updates only commercial / physical SKU fields. Directory ownership stays on the series API. */
export function patchMaterialSku(materialId: string, payload: Record<string, unknown>): Promise<Material> {
  return apiRequest(`/api/v1/admin/materials/${encodeURIComponent(materialId)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function batchUpdateMaterialSkus(input: {
  ids: string[]
  action: 'enable' | 'disable' | 'price' | 'stock' | 'safety_stock' | 'delete'
  value?: number
  expectedRevisions: Record<string, number>
}): Promise<{ action: string; requested: number; affected: number }> {
  return apiRequest('/api/v1/admin/materials/batch', {
    method: 'POST',
    body: JSON.stringify({
      ids: input.ids,
      action: input.action,
      ...(typeof input.value === 'number' ? { value: input.value } : {}),
      expected_revisions: input.expectedRevisions,
    }),
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

/** Uses the immutable series ID so a rename can never be interpreted as a new product. */
export function updateMaterialSeries(seriesId: string, input: MaterialSeriesInput): Promise<MaterialSeries> {
  return apiRequest(`/api/v1/admin/material-taxonomy/series/${encodeURIComponent(seriesId)}`, {
    method: 'PATCH',
    body: JSON.stringify(input),
  })
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

export function bindMaterialAssets(
  seriesId: string,
  assetKeys: string[],
  mode: 'replace' | 'append',
  options: { expectedVersion?: number; idempotencyKey?: string } = {},
): Promise<MaterialAssetBindResult> {
  return apiRequest('/api/v1/admin/material-assets/bind', {
    method: 'POST',
    body: JSON.stringify({
      series_id: seriesId,
      asset_keys: assetKeys,
      mode,
      ...(typeof options.expectedVersion === 'number' ? { expected_version: options.expectedVersion } : {}),
      ...(options.idempotencyKey ? { idempotency_key: options.idempotencyKey } : {}),
    }),
  })
}
