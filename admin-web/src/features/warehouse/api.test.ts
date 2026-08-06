import { beforeEach, describe, expect, it, vi } from 'vitest'

import { storeToken } from '@/api/client'

import { createWarehouseInbound, createWarehouseOutbound, listWarehouseBatches, listWarehouseItems, listWarehouseMovements, saveWarehouseChannel, saveWarehouseLocation, saveWarehouseSupplier, warehouseOverview } from './api'

describe('warehouse read api', () => {
  beforeEach(() => { window.history.replaceState({}, '', '/admin-v2/warehouse'); storeToken('operator-token'); vi.restoreAllMocks() })

  it('uses the read-only overview and filtered inventory endpoints', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ code: 0, data: {} }), { status: 200, headers: { 'content-type': 'application/json' } })))
    vi.stubGlobal('fetch', fetchMock)
    await warehouseOverview()
    await listWarehouseItems({ keyword: '海蓝宝', category: '蓝色系', itemType: 'bead', enabled: '1' })
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('warehouse/overview')
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('warehouse/items?keyword=%E6%B5%B7%E8%93%9D%E5%AE%9D')
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('item_type=bead&enabled=1&limit=500')
  })

  it('submits ledger mutations through inbound and outbound endpoints only', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ code: 0, data: {} }), { status: 200, headers: { 'content-type': 'application/json' } })))
    vi.stubGlobal('fetch', fetchMock)
    await createWarehouseInbound({ item_id: 'item-1', quantity: 12, unit_cost: 3.5 })
    await createWarehouseOutbound({ item_id: 'item-1', quantity: 3, movement_type: 'sale_out' })
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('warehouse/inbound')
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ method: 'POST' })
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('warehouse/outbound')
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({ method: 'POST' })
  })

  it('passes batch and movement filters to their server-side ledger endpoints', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ code: 0, data: [] }), { status: 200, headers: { 'content-type': 'application/json' } })))
    vi.stubGlobal('fetch', fetchMock)
    await listWarehouseBatches({ keyword: 'batch-08', itemId: 'item-1', status: 'active' })
    await listWarehouseMovements({ keyword: 'order-8', itemId: 'item-1', movementType: 'sale_out', channelId: 'channel-1', startDate: '2026-08-01', endDate: '2026-08-06' })
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('warehouse/batches?item_id=item-1&status=active&keyword=batch-08&limit=300')
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('warehouse/movements?keyword=order-8&item_id=item-1&movement_type=sale_out&channel_id=channel-1&start_date=2026-08-01&end_date=2026-08-06&limit=300')
  })

  it('saves supplier, location and channel references through their dedicated endpoints', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ code: 0, data: {} }), { status: 200, headers: { 'content-type': 'application/json' } })))
    vi.stubGlobal('fetch', fetchMock)
    await saveWarehouseSupplier({ name: '云岭供应商', enabled: true })
    await saveWarehouseLocation({ name: 'A-01', enabled: true })
    await saveWarehouseChannel({ name: '线下工作室', channel_type: 'offline', enabled: true })
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('warehouse/suppliers')
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('warehouse/locations')
    expect(String(fetchMock.mock.calls[2]?.[0])).toContain('warehouse/channels')
    expect(fetchMock.mock.calls.every(([, init]) => (init as RequestInit).method === 'POST')).toBe(true)
  })
})
