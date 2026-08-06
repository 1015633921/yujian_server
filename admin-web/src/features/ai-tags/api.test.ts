import { beforeEach, describe, expect, it, vi } from 'vitest'

import { storeToken } from '@/api/client'

import { applyAiMaterialTag, listAiMaterialTags, reviewAiMaterialTag } from './api'

describe('ai material tag api', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/admin-v2/ai-material-tags')
    storeToken('operator-token')
    vi.restoreAllMocks()
  })

  it('only uses the state-machine review and apply routes', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(
      new Response(JSON.stringify({ code: 0, data: [] }), { status: 200, headers: { 'content-type': 'application/json' } }),
    ))
    vi.stubGlobal('fetch', fetchMock)

    await listAiMaterialTags('pending_review')
    await reviewAiMaterialTag('mat_ai_1', 'approved', '视觉判断可用', { target_id: 'spu_1', material_code: 'moonstone' })
    await applyAiMaterialTag('mat_ai_1')

    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('material-ai-tags?status=pending_review&limit=500')
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('material-ai-tags/mat_ai_1/review')
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({ method: 'POST' })
    expect(String(fetchMock.mock.calls[2]?.[0])).toContain('material-ai-tags/mat_ai_1/apply')
    expect(fetchMock.mock.calls[2]?.[1]).toMatchObject({ method: 'POST' })
  })
})
