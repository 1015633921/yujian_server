export const CUSTOM_DESIGN_STATUSES = [
  'deposit_pending',
  'submitted',
  'designing',
  'proposed',
  'revision_requested',
  'completed',
  'confirmed',
  'closed',
] as const

export type CustomDesignStatus = (typeof CUSTOM_DESIGN_STATUSES)[number]

export interface CustomDesignPreference {
  style_preference?: string
  wrist_size_cm?: number | string
  bead_size_mm?: number | string
  budget?: number | string
  color_preference?: string
  accessory_preference?: string
  wear_scene?: string
  note?: string
}

export interface CustomDesignDepositSummary {
  amount_fee?: number
  amount_text?: string
  status?: string
}

export interface CustomDesignProposalSummary {
  proposal_id?: string
  proposal_version?: number
  title?: string
  status?: string
  created_at?: string
}

export interface CustomDesignBriefColor {
  key?: string
  label?: string
  hex?: string
}

export interface CustomDesignBrief {
  status?: string
  design_goal?: { title?: string; summary?: string }
  intervention?: { label?: string; score?: number; reason?: string }
  hard_constraints?: Array<{ key?: string; label?: string; value?: string; source?: string }>
  preferences?: { style?: string; accessory?: string; wear_scene?: string; source?: string }
  palette?: Record<string, CustomDesignBriefColor[]>
  optics?: { tags?: string[]; existing_baseline?: string }
  material_roles?: Array<{ key?: string; label?: string; element?: string; purpose?: string; reason?: string }>
  structure?: { direction?: string; max_bead_materials?: number; max_accessories?: number; reduce?: string }
  supplementary_context?: { core_wishes?: string[]; keywords?: string[] }
  source_evidence?: Array<{ source?: string; level?: string; value?: string; effect?: string }>
  warnings?: Array<{ level?: string; label?: string; message?: string }>
}

export interface CustomDesignDraftSummary {
  draft_id?: string
  draft_version?: number
  created_by?: string
  created_at?: string
  updated_at?: string
}

export interface CustomDesignOverview extends CustomDesignListItem {
  design_brief?: CustomDesignBrief
  draft?: CustomDesignDraftSummary | null
}

export interface CustomDesignAssessmentEvidence {
  request_id: string
  report_id: string
  report_code?: string
  report_version?: number
  report_summary?: Record<string, unknown>
}

export interface CustomDesignProposal extends CustomDesignProposalSummary {
  description?: string
  image_urls?: string[]
}

export interface CustomDesignComposition {
  proposal_id: string
  proposal_version?: number
  wrist_size_cm?: number | string | null
  bead_size_mm?: number | string | null
  layout?: Array<Record<string, unknown>>
}

export interface CustomDesignEvent {
  event_type?: string
  from_status?: string
  to_status?: string
  actor_type?: string
  note?: string
  created_at?: string
}

export interface CustomDesignMaterialPreview {
  id: string
  name?: string
  image_url?: string
  image_urls?: string[]
  top?: string
  size?: number
}

export interface CustomDesignWorkbenchLayoutItem {
  id?: string
  material_id?: string
  sku_id?: string
  skuId?: string
  name?: string
  price?: number | string
  selected_image_url?: string
  image_url?: string
  gallery_image_urls?: string[]
  image_urls?: string[]
  size_mm?: number | string
  size?: number | string
  top?: string
  sku?: Record<string, unknown>
  visual?: Record<string, unknown>
  [key: string]: unknown
}

export interface CustomDesignWorkbenchData {
  wrist_size_cm?: number | string
  bead_size_mm?: number | string
  notes?: string
  layout?: CustomDesignWorkbenchLayoutItem[]
}

export interface CustomDesignWorkbenchBootstrap {
  overview: CustomDesignOverview
  source_kind: 'draft' | 'proposal' | 'empty' | string
  workbench?: CustomDesignWorkbenchData
  proposal?: CustomDesignProposal | null
}

export interface CustomDesignCandidateItem {
  material_id: string
  name?: string
  top?: string
  price?: number
  size_mm?: number
  available_stock?: number
  image_url?: string
  reasons?: string[]
  cautions?: string[]
}

export interface CustomDesignCandidateResult {
  status?: string
  message?: string
  estimated_bead_count?: number
  budget?: { raw?: string }
  candidate_groups?: Array<{ role?: string; label?: string; items?: CustomDesignCandidateItem[] }>
}

export interface CustomDesignAdminMaterial extends CustomDesignWorkbenchLayoutItem {
  id: string
  sku?: Record<string, unknown>
  visual?: Record<string, unknown>
  ops?: Record<string, unknown>
}

export interface CustomDesignMaterialPage {
  items: CustomDesignAdminMaterial[]
  pagination?: { page?: number; page_size?: number; total?: number; has_next?: boolean }
}

export interface CustomDesignWorkbenchPayload {
  wrist_size_cm: number
  bead_size_mm: number
  notes: string
  layout: Array<{ id: string; material_id: string; price: number; quantity: number; selected_image_url: string }>
}

export interface CustomDesignListItem {
  request_id: string
  report_id: string
  report_code?: string
  report_version?: number
  status: string
  request?: CustomDesignPreference
  deposit?: CustomDesignDepositSummary | null
  first_draft_due_at?: string | null
  proposal_count?: number
  latest_proposal?: CustomDesignProposalSummary | null
  latest_proposal_title?: string
  proposals?: CustomDesignProposalSummary[]
  created_at?: string
  updated_at?: string
}

export interface CustomDesignListPage {
  items: CustomDesignListItem[]
  total: number
  limit: number
  offset: number
  has_more: boolean
}

export interface CustomDesignListQuery {
  status?: string
  limit: number
  offset: number
}
