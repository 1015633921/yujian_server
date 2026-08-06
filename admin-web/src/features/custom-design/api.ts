import { apiRequest } from '@/api/client'

import type {
  CustomDesignAssessmentEvidence,
  CustomDesignComposition,
  CustomDesignEvent,
  CustomDesignListItem,
  CustomDesignListPage,
  CustomDesignListQuery,
  CustomDesignMaterialPreview,
  CustomDesignMaterialPage,
  CustomDesignOverview,
  CustomDesignProposal,
  CustomDesignCandidateResult,
  CustomDesignWorkbenchBootstrap,
  CustomDesignWorkbenchPayload,
} from './types'

interface CustomDesignPagePayload {
  items?: CustomDesignListItem[]
  total?: number
  limit?: number
  offset?: number
  has_more?: boolean
}

export async function listCustomDesignRequests(
  query: CustomDesignListQuery,
  signal?: AbortSignal,
): Promise<CustomDesignListPage> {
  const params = new URLSearchParams({
    status: query.status || '',
    limit: String(query.limit),
    offset: String(query.offset),
    include_meta: 'true',
  })

  const payload = await apiRequest<CustomDesignPagePayload | CustomDesignListItem[]>(
    `/api/v1/admin/custom-design-requests?${params.toString()}`,
    { signal },
  )

  if (Array.isArray(payload)) {
    const hasMore = payload.length === query.limit
    return {
      items: payload,
      total: query.offset + payload.length + (hasMore ? 1 : 0),
      limit: query.limit,
      offset: query.offset,
      has_more: hasMore,
    }
  }

  const items = Array.isArray(payload.items) ? payload.items : []
  const limit = Number.isFinite(Number(payload.limit)) ? Number(payload.limit) : query.limit
  const offset = Number.isFinite(Number(payload.offset)) ? Number(payload.offset) : query.offset
  const total = Number.isFinite(Number(payload.total)) ? Number(payload.total) : offset + items.length
  return {
    items,
    total,
    limit,
    offset,
    has_more: payload.has_more ?? offset + items.length < total,
  }
}

export function getCustomDesignOverview(requestId: string, signal?: AbortSignal): Promise<CustomDesignOverview> {
  return apiRequest<CustomDesignOverview>(
    `/api/v1/admin/custom-design-requests/${encodeURIComponent(requestId)}/overview`,
    { signal },
  )
}

export function getCustomDesignWorkbench(
  requestId: string,
  signal?: AbortSignal,
): Promise<CustomDesignWorkbenchBootstrap> {
  return apiRequest<CustomDesignWorkbenchBootstrap>(
    `/api/v1/admin/custom-design-requests/${encodeURIComponent(requestId)}/workbench`,
    { signal },
  )
}

export function listCustomDesignMaterials(
  query: { keyword?: string; top?: string; page: number; pageSize: number },
  signal?: AbortSignal,
): Promise<CustomDesignMaterialPage> {
  const params = new URLSearchParams({
    keyword: query.keyword || '',
    top: query.top || '',
    status: 'enabled',
    sort_by: 'sort_order',
    sort_order: 'asc',
    page: String(query.page),
    page_size: String(query.pageSize),
  })
  return apiRequest<CustomDesignMaterialPage>(`/api/v1/admin/materials?${params.toString()}`, { signal })
}

export function getCustomDesignCandidates(
  requestId: string,
  payload: { selected_material_ids: string[]; wrist_size_cm: number; bead_size_mm: number },
  signal?: AbortSignal,
): Promise<CustomDesignCandidateResult> {
  return apiRequest<CustomDesignCandidateResult>(
    `/api/v1/admin/custom-design-requests/${encodeURIComponent(requestId)}/material-candidates`,
    { method: 'POST', body: JSON.stringify(payload), signal },
  )
}

export function saveCustomDesignDraft(
  requestId: string,
  payload: CustomDesignWorkbenchPayload,
): Promise<CustomDesignOverview> {
  return apiRequest<CustomDesignOverview>(
    `/api/v1/admin/custom-design-requests/${encodeURIComponent(requestId)}/draft`,
    { method: 'PUT', body: JSON.stringify(payload) },
  )
}

export function publishCustomDesignProposal(
  requestId: string,
  payload: { title: string; description: string; image_urls: string[]; workbench: CustomDesignWorkbenchPayload },
): Promise<CustomDesignOverview> {
  return apiRequest<CustomDesignOverview>(
    `/api/v1/admin/custom-design-requests/${encodeURIComponent(requestId)}/proposal`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}

export function getCustomDesignAssessmentEvidence(
  requestId: string,
  signal?: AbortSignal,
): Promise<CustomDesignAssessmentEvidence> {
  return apiRequest<CustomDesignAssessmentEvidence>(
    `/api/v1/admin/custom-design-requests/${encodeURIComponent(requestId)}/assessment-evidence`,
    { signal },
  )
}

export function listCustomDesignProposals(requestId: string, signal?: AbortSignal): Promise<CustomDesignProposal[]> {
  return apiRequest<CustomDesignProposal[]>(
    `/api/v1/admin/custom-design-requests/${encodeURIComponent(requestId)}/proposals`,
    { signal },
  )
}

export function getCustomDesignProposalComposition(
  requestId: string,
  proposalId: string,
  signal?: AbortSignal,
): Promise<CustomDesignComposition> {
  return apiRequest<CustomDesignComposition>(
    `/api/v1/admin/custom-design-requests/${encodeURIComponent(requestId)}/proposals/${encodeURIComponent(proposalId)}/composition`,
    { signal },
  )
}

export function listCustomDesignEvents(requestId: string, signal?: AbortSignal): Promise<CustomDesignEvent[]> {
  return apiRequest<CustomDesignEvent[]>(
    `/api/v1/admin/custom-design-requests/${encodeURIComponent(requestId)}/events`,
    { signal },
  )
}

export async function getCustomDesignMaterialPreviews(
  materialIds: string[],
  signal?: AbortSignal,
): Promise<CustomDesignMaterialPreview[]> {
  const ids = [...new Set(materialIds.map((item) => item.trim()).filter(Boolean))]
  if (!ids.length) return []
  const payload = await apiRequest<{ materials?: CustomDesignMaterialPreview[] }>(
    `/api/v1/materials?compact=true&slim=true&ids=${encodeURIComponent(ids.join(','))}`,
    { signal },
  )
  return Array.isArray(payload.materials) ? payload.materials : []
}
