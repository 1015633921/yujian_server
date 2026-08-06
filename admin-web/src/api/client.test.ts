import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiRequest, ApiError, AUTH_UNAUTHORIZED_EVENT, storeToken } from './client'

describe('admin api client', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/admin-v2/overview')
    vi.restoreAllMocks()
  })

  it('adds the existing bearer token and unwraps successful data', async () => {
    storeToken('admin-token')
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ code: 0, message: 'ok', data: { username: 'operator' } }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await apiRequest<{ username: string }>('/api/v1/admin/me')

    expect(result.username).toBe('operator')
    const [, request] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(new Headers(request.headers).get('authorization')).toBe('Bearer admin-token')
  })

  it('emits one unauthorized event and returns a typed error', async () => {
    storeToken('expired-token')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ code: 401, detail: '登录状态已失效' }), {
          status: 401,
          headers: { 'content-type': 'application/json' },
        }),
      ),
    )
    const unauthorized = vi.fn()
    window.addEventListener(AUTH_UNAUTHORIZED_EVENT, unauthorized, { once: true })

    await expect(apiRequest('/api/v1/admin/me')).rejects.toMatchObject({
      status: 401,
      message: '登录状态已失效',
    } satisfies Partial<ApiError>)
    expect(unauthorized).toHaveBeenCalledTimes(1)
  })
})
