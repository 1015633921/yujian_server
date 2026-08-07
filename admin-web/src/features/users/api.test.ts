import { beforeEach, describe, expect, it, vi } from 'vitest'

import { storeToken } from '@/api/client'

import { createAdmin, disableAdmin, getAssessmentDetail, getCheckinDetail, getDailyEnergyDetail, getDailyRules, getSystemStatus, getUser, listAdmins, listAssessments, listCheckins, listDailyEnergies, listLoginLogs, listUsers, saveDailyRules, updateAdmin } from './api'

describe('user api', () => {
  beforeEach(() => { window.history.replaceState({}, '', '/admin-v2/users'); storeToken('operator-token'); vi.restoreAllMocks() })
  it('uses protected filtered user and individual-detail endpoints', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ code: 0, data: [] }), { status: 200, headers: { 'content-type': 'application/json' } })))
    vi.stubGlobal('fetch', fetchMock)
    await listUsers({ keyword: '小涧', profileStatus: 'complete', energyTag: '喜水', spendLevel: 'paid', startDate: '2026-08-01', endDate: '2026-08-06' })
    await getUser('user-1')
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('users?keyword=%E5%B0%8F%E6%B6%A7&profile_status=complete&energy_tag=%E5%96%9C%E6%B0%B4&spend_level=paid&start_date=2026-08-01&end_date=2026-08-06&limit=200')
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('users/user-1')
  })

  it('uses read-only energy insight endpoints with the existing filters', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ code: 0, data: [] }), { status: 200, headers: { 'content-type': 'application/json' } })))
    vi.stubGlobal('fetch', fetchMock)
    await listAssessments({ keyword: 'u-1', wish: '招财', hideTests: true })
    await listDailyEnergies('u-1')
    await listCheckins('u-1')
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('assessments?keyword=u-1&core_wish=%E6%8B%9B%E8%B4%A2&hide_tests=true&limit=200')
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('daily-energies?keyword=u-1&limit=200')
    expect(String(fetchMock.mock.calls[2]?.[0])).toContain('checkins?keyword=u-1&limit=200')
  })

  it('reads protected detail endpoints for all energy data records', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ code: 0, data: {} }), { status: 200, headers: { 'content-type': 'application/json' } })))
    vi.stubGlobal('fetch', fetchMock)
    await getAssessmentDetail('assessment-1')
    await getDailyEnergyDetail('user/1', '2026-08-07')
    await getCheckinDetail('user/1', '2026-08-07')
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('assessments/assessment-1')
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('daily-energies/user%2F1/2026-08-07')
    expect(String(fetchMock.mock.calls[2]?.[0])).toContain('checkins/user%2F1/2026-08-07')
    for (const [, init] of fetchMock.mock.calls) expect(new Headers((init as RequestInit).headers).get('authorization')).toBe('Bearer operator-token')
  })

  it('reads, saves and resets daily rules through the protected rules endpoint', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ code: 0, data: {} }), { status: 200, headers: { 'content-type': 'application/json' } })))
    vi.stubGlobal('fetch', fetchMock)
    await getDailyRules(); await saveDailyRules({ scenes: [] }); await saveDailyRules({}, true)
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('daily-energy-rules')
    expect(fetchMock.mock.calls.slice(1).map(([, init]) => (init as RequestInit).method)).toEqual(['PUT', 'PUT'])
    expect(String(fetchMock.mock.calls[2]?.[1]?.body)).toContain('"reset_to_default":true')
  })

  it('reads service readiness without requesting sensitive configuration values', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ code: 0, data: { checks: [] } }), { status: 200, headers: { 'content-type': 'application/json' } })))
    vi.stubGlobal('fetch', fetchMock)
    await getSystemStatus()
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('/api/v1/admin/system-status')
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit
    expect(init.method).toBeUndefined()
    expect(init.body).toBeUndefined()
  })

  it('uses the protected administrator account and login trace endpoints', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ code: 0, data: [] }), { status: 200, headers: { 'content-type': 'application/json' } })))
    vi.stubGlobal('fetch', fetchMock)
    await listAdmins(); await listLoginLogs(); await createAdmin({ username: 'ops_01', display_name: '运营一号', role: 'operator', status: 'active', password: 'secure123' }); await updateAdmin('admin-1', { display_name: '运营二号', role: 'viewer', status: 'active' }); await disableAdmin('admin-1')
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('/api/v1/admin/admins')
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('/api/v1/admin/login-logs?limit=120')
    expect(fetchMock.mock.calls.slice(2).map(([, init]) => (init as RequestInit).method)).toEqual(['POST', 'PUT', 'DELETE'])
    expect(String(fetchMock.mock.calls[2]?.[1]?.body)).toContain('"password":"secure123"')
    expect(String(fetchMock.mock.calls[4]?.[0])).toContain('/api/v1/admin/admins/admin-1')
  })
})
