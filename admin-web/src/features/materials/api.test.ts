import { beforeEach, describe, expect, it, vi } from 'vitest'

import { storeToken } from '@/api/client'

import {
  deleteEmptyMaterialCategory,
  disableMaterialTaxonomyItem,
  bindMaterialAssets,
  listMaterialTaxonomy,
  listMaterialTypes,
  saveMaterialSeries,
  uploadMaterialAsset,
} from './api'

describe('material directory api', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/admin-v2/material-directory')
    storeToken('operator-token')
    vi.restoreAllMocks()
  })

  it('reads types and the complete three-level taxonomy through authenticated admin endpoints', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(
      new Response(JSON.stringify({ code: 0, data: [] }), { status: 200, headers: { 'content-type': 'application/json' } }),
    ))
    vi.stubGlobal('fetch', fetchMock)

    await listMaterialTypes(true)
    await listMaterialTaxonomy('bead', true)

    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('material-types?include_disabled=true')
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('material-taxonomy?top=bead&include_disabled=true')
    const [, request] = fetchMock.mock.calls[1] as [string, RequestInit]
    expect(new Headers(request.headers).get('authorization')).toBe('Bearer operator-token')
  })

  it('uses the guarded directory mutations instead of a direct SKU mutation', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(
      new Response(JSON.stringify({ code: 0, data: {} }), { status: 200, headers: { 'content-type': 'application/json' } }),
    ))
    vi.stubGlobal('fetch', fetchMock)

    await saveMaterialSeries({ category_id: 'category-1', name: '海蓝宝', sort_order: 10, enabled: true })
    await disableMaterialTaxonomyItem('series-1')
    await deleteEmptyMaterialCategory('category-1')

    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('material-taxonomy/series')
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ method: 'POST' })
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('material-taxonomy/series-1')
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({ method: 'DELETE' })
    expect(String(fetchMock.mock.calls[2]?.[0])).toContain('material-taxonomy/categories/batch-delete')
    expect(fetchMock.mock.calls[2]?.[1]).toMatchObject({ method: 'POST' })
  })

  it('uploads only processed file data and binds the returned COS keys to a series gallery', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(
      new Response(JSON.stringify({ code: 0, data: { key: 'materials/processed/sample.webp' } }), { status: 200, headers: { 'content-type': 'application/json' } }),
    ))
    vi.stubGlobal('fetch', fetchMock)

    await uploadMaterialAsset(new Blob(['webp'], { type: 'image/webp' }), 'sample.webp')
    await bindMaterialAssets('series-1', ['materials/processed/sample.webp'], 'replace')

    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('material-assets/upload')
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ method: 'POST' })
    expect(fetchMock.mock.calls[0]?.[1]?.body).toBeInstanceOf(FormData)
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('material-assets/bind')
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({ method: 'POST' })
  })
})
