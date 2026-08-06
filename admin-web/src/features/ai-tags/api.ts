import { apiRequest } from '@/api/client'

export type AiTagStatus = 'pending_review' | 'approved' | 'applied' | 'rejected' | 'failed'

export interface AiTagRecord {
  annotation_id: string
  target_id: string
  material_code: string
  top: string
  category: string
  series: string
  status: AiTagStatus
  model_id?: string
  image_urls: string[]
  known_facts?: { available_sizes_mm?: number[]; catalog_names?: string[]; type?: string }
  parsed_response?: AiTagPayload
  reviewer_final?: AiTagPayload
  application?: { can_apply?: boolean; applied?: boolean; fields?: Record<string, unknown> }
  review_notes?: string
  reviewer_name?: string
  reviewed_at?: string
  created_at?: string
  updated_at?: string
  error_code?: string
  error_message?: string
}

export interface AiTagPayload {
  confidence?: number
  visual?: Record<string, number | string[]>
  design?: {
    roles?: string[]
    style_tags?: string[]
    shape_language?: string[]
    recommended_metal_palettes?: string[]
    recommended_usage?: { count_min?: number; count_max?: number; symmetry?: string; focus_strength?: string }
  }
  uncertain_fields?: string[]
  [key: string]: unknown
}

export function listAiMaterialTags(status = '', signal?: AbortSignal): Promise<AiTagRecord[]> {
  const params = new URLSearchParams({ status, limit: '500' })
  return apiRequest(`/api/v1/admin/material-ai-tags?${params}`, { signal })
}

export function reviewAiMaterialTag(annotationId: string, action: 'approved' | 'rejected', notes: string, finalPayload?: AiTagPayload): Promise<AiTagRecord> {
  return apiRequest(`/api/v1/admin/material-ai-tags/${encodeURIComponent(annotationId)}/review`, {
    method: 'POST',
    body: JSON.stringify({ action, notes, ...(action === 'approved' ? { final_payload: finalPayload } : {}) }),
  })
}

export function applyAiMaterialTag(annotationId: string): Promise<AiTagRecord> {
  return apiRequest(`/api/v1/admin/material-ai-tags/${encodeURIComponent(annotationId)}/apply`, { method: 'POST' })
}
