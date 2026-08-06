import { beforeEach, describe, expect, it, vi } from 'vitest'

import { storeToken } from '@/api/client'

import {
  deleteEmptyMaterialCategory,
  disableMaterialTaxonomyItem,
  bindMaterialAssets,
  batchUpdateMaterialSkus,
  createMaterialSku,
  getMaterialSeries,
  listMaterialSpus,
  listMaterialTaxonomy,
  listMaterialTypes,
  patchMaterialSku,
  saveMaterialSeries,
  updateMaterialSeries,
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
    await getMaterialSeries('series-1')

    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('material-types?include_disabled=true')
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('material-taxonomy?top=bead&include_disabled=true')
    const [, request] = fetchMock.mock.calls[1] as [string, RequestInit]
    expect(new Headers(request.headers).get('authorization')).toBe('Bearer operator-token')
    expect(String(fetchMock.mock.calls[2]?.[0])).toContain('material-taxonomy/series/series-1')
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

  it('keeps SKU edits and immutable series edits on separate endpoints', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(
      new Response(JSON.stringify({ code: 0, data: {} }), { status: 200, headers: { 'content-type': 'application/json' } }),
    ))
    vi.stubGlobal('fetch', fetchMock)

    await patchMaterialSku('sku-1', { price: 18, enabled: true, expected_revision: 2 })
    await updateMaterialSeries('series-1', { category_id: 'category-1', name: '重命名品种', sort_order: 1, enabled: true })

    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('materials/sku-1')
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ method: 'PATCH' })
    expect(String(fetchMock.mock.calls[0]?.[1]?.body)).toContain('"expected_revision":2')
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('material-taxonomy/series/series-1')
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({ method: 'PATCH' })
  })

  it('loads series-first rows and sends revisions for conflict-safe SKU batch changes', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(
      new Response(JSON.stringify({ code: 0, data: { items: [], pagination: {} } }), { status: 200, headers: { 'content-type': 'application/json' } }),
    ))
    vi.stubGlobal('fetch', fetchMock)

    await listMaterialSpus({ keyword: '', top: 'bead', category: '', status: '', stockState: 'low', assetState: '', specState: '', profileState: '', page: 1, pageSize: 20 })
    await batchUpdateMaterialSkus({ ids: ['sku-1'], action: 'stock', value: 12, expectedRevisions: { 'sku-1': 3 } })
    await createMaterialSku({ id: 'mat_retry_safe_id', top: 'bead', category: '水晶', series: '海蓝宝', name: '海蓝宝', price: 9.9, size: 8, weight: 1, stock: 0 })

    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('material-spus?')
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('include_facets=true')
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('materials/batch')
    expect(String(fetchMock.mock.calls[1]?.[1]?.body)).toContain('"expected_revisions":{"sku-1":3}')
    expect(String(fetchMock.mock.calls[2]?.[0])).toContain('materials')
    expect(fetchMock.mock.calls[2]?.[1]).toMatchObject({ method: 'POST' })
    expect(String(fetchMock.mock.calls[2]?.[1]?.body)).toContain('"id":"mat_retry_safe_id"')
  })

  it('uploads only processed file data and binds the returned COS keys to a series gallery', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(
      new Response(JSON.stringify({ code: 0, data: { key: 'materials/processed/sample.webp' } }), { status: 200, headers: { 'content-type': 'application/json' } }),
    ))
    vi.stubGlobal('fetch', fetchMock)

    await uploadMaterialAsset(new Blob(['webp'], { type: 'image/webp' }), 'sample.webp')
    await bindMaterialAssets('series-1', ['materials/processed/sample.webp'], 'replace', {
      expectedVersion: 3,
      idempotencyKey: 'publish-1',
    })

    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('material-assets/upload')
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ method: 'POST' })
    expect(fetchMock.mock.calls[0]?.[1]?.body).toBeInstanceOf(FormData)
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('material-assets/bind')
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({ method: 'POST' })
    expect(String(fetchMock.mock.calls[1]?.[1]?.body)).toContain('"expected_version":3')
    expect(String(fetchMock.mock.calls[1]?.[1]?.body)).toContain('"idempotency_key":"publish-1"')
  })
})
