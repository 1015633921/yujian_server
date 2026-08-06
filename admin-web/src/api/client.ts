import { adminTokenKey, apiPath } from '@/runtime/environment'
import type { ApiEnvelope } from './types'

export const AUTH_UNAUTHORIZED_EVENT = 'yujian-admin:unauthorized'

export class ApiError extends Error {
  readonly status: number
  readonly code: number | string
  readonly detail: unknown

  constructor(message: string, status: number, code: number | string, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.detail = detail
  }
}

type ApiRequestOptions = RequestInit & {
  auth?: boolean
}

function errorMessage(body: Partial<ApiEnvelope<unknown>>, status: number): string {
  if (typeof body.detail === 'string' && body.detail.trim()) return body.detail
  if (typeof body.message === 'string' && body.message.trim()) return body.message
  return `请求失败（${status}）`
}

export function readStoredToken(): string {
  return window.localStorage.getItem(adminTokenKey()) || ''
}

export function storeToken(token: string): void {
  if (token) window.localStorage.setItem(adminTokenKey(), token)
  else window.localStorage.removeItem(adminTokenKey())
}

export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const { auth = true, ...requestOptions } = options
  const headers = new Headers(requestOptions.headers)
  const token = readStoredToken()

  if (requestOptions.body && !(requestOptions.body instanceof FormData) && !headers.has('content-type')) {
    headers.set('content-type', 'application/json')
  }
  if (auth && token) headers.set('authorization', `Bearer ${token}`)

  const response = await fetch(apiPath(path), { ...requestOptions, headers })
  const body = (await response.json().catch(() => ({}))) as Partial<ApiEnvelope<T>>

  if (!response.ok || body.code !== 0) {
    if (response.status === 401 && auth) {
      window.dispatchEvent(new Event(AUTH_UNAUTHORIZED_EVENT))
    }
    throw new ApiError(
      errorMessage(body, response.status),
      response.status,
      body.code ?? response.status,
      body.detail,
    )
  }

  return body.data as T
}
