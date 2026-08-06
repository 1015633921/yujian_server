export interface ApiEnvelope<T> {
  code: number | string
  message?: string
  detail?: unknown
  data: T
}

export interface AdminUser {
  admin_id?: string
  username: string
  display_name?: string
  role?: string
  enabled?: boolean
}

export interface LoginResult {
  token: string
  admin: AdminUser
}

export interface DashboardMetrics {
  users: number
  orders: number
  revenue: number
  materials: number
  pending_ship?: number
  after_sale?: number
  payment_compensations?: number
  metric_deltas?: Record<string, unknown>
}
