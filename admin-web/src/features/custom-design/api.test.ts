import { beforeEach, describe, expect, it, vi } from 'vitest'

import { storeToken } from '@/api/client'

import {
  getCustomDesignMaterialPreviews,
  getCustomDesignOverview,
  getCustomDesignProposalComposition,
  getCustomDesignWorkbench,
  getCustomDesignCandidates,
  listCustomDesignMaterials,
  listCustomDesignRequests,
  publishCustomDesignProposal,
  saveCustomDesignDraft,
} from './api'

describe('custom design list api', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/admin-v2/design-requests')
    storeToken('operator-token')
    vi.restoreAllMocks()
  })

  it('requests a paged lightweight response and normalizes its metadata', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          code: 0,
          data: {
            items: [{ request_id: 'CD1', report_id: 'R1', status: 'submitted' }],
            total: 31,
            limit: 30,
            offset: 0,
            has_more: true,
          },
        }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    const page = await listCustomDesignRequests({ status: 'submitted', limit: 30, offset: 0 })

    expect(page.total).toBe(31)
    expect(page.has_more).toBe(true)
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      'status=submitted&limit=30&offset=0&include_meta=true',
    )
  })

  it('keeps compatibility with the legacy array envelope', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            code: 0,
            data: [{ request_id: 'CD2', report_id: 'R2', status: 'designing' }],
          }),
          { status: 200, headers: { 'content-type': 'application/json' } },
        ),
      ),
    )

    const page = await listCustomDesignRequests({ limit: 30, offset: 30 })
    expect(page.items).toHaveLength(1)
    expect(page.total).toBe(31)
  })

  it('uses the staged detail endpoints and only asks the material API for selected IDs', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ code: 0, data: { request_id: 'CD 1' } }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ code: 0, data: { proposal_id: 'P/1', layout: [] } }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ code: 0, data: { materials: [{ id: 'M1', name: '月光石' }] } }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await getCustomDesignOverview('CD 1')
    await getCustomDesignProposalComposition('CD 1', 'P/1')
    const materials = await getCustomDesignMaterialPreviews(['M1', 'M2', 'M1'])

    expect(materials).toEqual([{ id: 'M1', name: '月光石' }])
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('custom-design-requests/CD%201/overview')
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('proposals/P%2F1/composition')
    expect(String(fetchMock.mock.calls[2]?.[0])).toContain('materials?compact=true&slim=true&ids=M1%2CM2')
  })

  it('keeps the workbench library paged and sends mutations only to validated workbench endpoints', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(
      new Response(JSON.stringify({ code: 0, data: { items: [] } }), { status: 200 }),
    ))
    vi.stubGlobal('fetch', fetchMock)
    const workbench = { wrist_size_cm: 16, bead_size_mm: 8, notes: '', layout: [{ id: 'M1', material_id: 'M1', price: 10, quantity: 1, selected_image_url: 'https://cdn.example.com/gallery.webp' }] }

    await getCustomDesignWorkbench('CD-1')
    await listCustomDesignMaterials({ keyword: '海蓝宝', top: 'bead', page: 2, pageSize: 24 })
    await getCustomDesignCandidates('CD-1', { selected_material_ids: ['M1'], wrist_size_cm: 16, bead_size_mm: 8 })
    await saveCustomDesignDraft('CD-1', workbench)
    await publishCustomDesignProposal('CD-1', { title: '清透款', description: '', image_urls: [], workbench })

    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('custom-design-requests/CD-1/workbench')
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('admin/materials?keyword=%E6%B5%B7%E8%93%9D%E5%AE%9D&top=bead')
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('page=2&page_size=24')
    expect(fetchMock.mock.calls[2]?.[1]).toMatchObject({ method: 'POST' })
    expect(fetchMock.mock.calls[3]?.[1]).toMatchObject({ method: 'PUT' })
    expect(fetchMock.mock.calls[4]?.[1]).toMatchObject({ method: 'POST' })
  })
})
