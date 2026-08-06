const TEST_PREFIX = '/test-api'
const ADMIN_V2_PATH = '/admin-v2'
const DEDICATED_TEST_ADMIN_HOST = 'operation-test.yustream.cn'

export function isDedicatedTestAdminHost(hostname = window.location.hostname): boolean {
  return hostname.trim().toLowerCase() === DEDICATED_TEST_ADMIN_HOST
}

function isTestDeployment(pathname = window.location.pathname, hostname = window.location.hostname): boolean {
  return isDedicatedTestAdminHost(hostname) || pathname === TEST_PREFIX || pathname.startsWith(`${TEST_PREFIX}/`)
}

export function deploymentPrefix(pathname = window.location.pathname, hostname = window.location.hostname): string {
  return isDedicatedTestAdminHost(hostname) ? '' : pathname === TEST_PREFIX || pathname.startsWith(`${TEST_PREFIX}/`) ? TEST_PREFIX : ''
}

export function apiPath(path: string, pathname = window.location.pathname, hostname = window.location.hostname): string {
  const normalized = path.startsWith('/') ? path : `/${path}`
  return `${deploymentPrefix(pathname, hostname)}${normalized}`
}

export function adminRouterBase(pathname = window.location.pathname, hostname = window.location.hostname): string {
  if (isDedicatedTestAdminHost(hostname)) return '/'
  const deployedBase = `${deploymentPrefix(pathname, hostname)}${ADMIN_V2_PATH}`
  if (pathname === deployedBase || pathname.startsWith(`${deployedBase}/`)) {
    return deployedBase
  }
  return '/'
}

export function adminTokenKey(pathname = window.location.pathname, hostname = window.location.hostname): string {
  return isTestDeployment(pathname, hostname) ? 'adminToken:test' : 'adminToken:prod'
}

export function legacyAdminPath(pathname = window.location.pathname, hostname = window.location.hostname): string {
  if (isDedicatedTestAdminHost(hostname)) return 'https://api.yustream.cn/test-api/admin'
  return `${deploymentPrefix(pathname, hostname)}/admin`
}

export function legacyDesignRequestPath(
  requestId: string,
  pathname = window.location.pathname,
  hostname = window.location.hostname,
): string {
  const query = new URLSearchParams({
    page: 'designRequests',
    request: requestId,
  })
  return `${legacyAdminPath(pathname, hostname)}?${query.toString()}`
}

export function environmentLabel(pathname = window.location.pathname, hostname = window.location.hostname): string {
  if (isTestDeployment(pathname, hostname)) return '测试环境'
  return import.meta.env.DEV ? '本地开发' : '正式环境'
}
