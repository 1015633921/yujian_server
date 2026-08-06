import { describe, expect, it } from 'vitest'

import {
  adminRouterBase,
  adminTokenKey,
  apiPath,
  deploymentPrefix,
  environmentLabel,
  isDedicatedTestAdminHost,
  legacyDesignRequestPath,
  legacyAdminPath,
} from './environment'

describe('admin runtime environment', () => {
  it('keeps production paths at the origin root', () => {
    expect(deploymentPrefix('/admin-v2/overview')).toBe('')
    expect(apiPath('/api/v1/admin/me', '/admin-v2/overview')).toBe('/api/v1/admin/me')
    expect(adminRouterBase('/admin-v2/overview')).toBe('/admin-v2')
    expect(adminTokenKey('/admin-v2/overview')).toBe('adminToken:prod')
    expect(legacyAdminPath('/admin-v2/overview')).toBe('/admin')
    expect(legacyDesignRequestPath('CD100', '/admin-v2/design-requests')).toBe(
      '/admin?page=designRequests&request=CD100',
    )
  })

  it('preserves the test reverse-proxy prefix', () => {
    const pathname = '/test-api/admin-v2/overview'
    expect(deploymentPrefix(pathname)).toBe('/test-api')
    expect(apiPath('/api/v1/admin/me', pathname)).toBe('/test-api/api/v1/admin/me')
    expect(adminRouterBase(pathname)).toBe('/test-api/admin-v2')
    expect(adminTokenKey(pathname)).toBe('adminToken:test')
    expect(legacyAdminPath(pathname)).toBe('/test-api/admin')
    expect(legacyDesignRequestPath('CD 200', pathname)).toBe(
      '/test-api/admin?page=designRequests&request=CD+200',
    )
  })

  it('uses the Vite root while running outside a deployed admin path', () => {
    expect(adminRouterBase('/')).toBe('/')
  })

  it('treats the dedicated operations test host as test while keeping root paths', () => {
    const host = 'operation-test.yustream.cn'
    expect(isDedicatedTestAdminHost(host)).toBe(true)
    expect(deploymentPrefix('/users', host)).toBe('')
    expect(apiPath('/api/v1/admin/me', '/users', host)).toBe('/api/v1/admin/me')
    expect(adminRouterBase('/users', host)).toBe('/')
    expect(adminTokenKey('/users', host)).toBe('adminToken:test')
    expect(legacyAdminPath('/users', host)).toBe('https://api.yustream.cn/test-api/admin')
    expect(legacyDesignRequestPath('CD 300', '/users', host)).toBe(
      'https://api.yustream.cn/test-api/admin?page=designRequests&request=CD+300',
    )
    expect(environmentLabel('/users', host)).toBe('测试环境')
  })
})
