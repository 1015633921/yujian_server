const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const apiPath = path.resolve(__dirname, '../../miniprogram/utils/api.js');
const authPath = path.resolve(__dirname, '../../miniprogram/utils/auth.js');
const workspacePath = path.resolve(__dirname, '../../miniprogram/pages/workspace/workspace.js');
const appPath = path.resolve(__dirname, '../../miniprogram/app.js');

function loadApiWithWx(storage = {}) {
  delete require.cache[require.resolve(apiPath)];
  let lastRequest = null;
  global.wx = {
    getDeviceInfo: () => ({ platform: 'devtools' }),
    getStorageSync: key => storage[key] || '',
    request(options) {
      lastRequest = options;
      options.success({ statusCode: 200, data: { code: 0, data: [] } });
    }
  };
  return { api: require(apiPath), lastRequest: () => lastRequest };
}

test('private requests inject bearer token while public requests remain anonymous', async () => {
  const loaded = loadApiWithWx({ accessToken: 'test-access-token' });
  await loaded.api.getUserProfile('user-a');
  assert.equal(loaded.lastRequest().header.Authorization, 'Bearer test-access-token');

  await loaded.api.getMaterials();
  assert.equal(loaded.lastRequest().header.Authorization, undefined);
});

test('401 handling has one retry guard and never retries non-GET writes', () => {
  const apiSource = fs.readFileSync(apiPath, 'utf8');
  assert.match(apiSource, /options\.authRetried/);
  assert.match(apiSource, /authRetried: true/);
  assert.match(apiSource, /isSafeRetryMethod/);
  assert.match(apiSource, /toUpperCase\(\) === 'GET'/);
});

test('logout clears token and private cross-account caches before network revocation', () => {
  const authSource = fs.readFileSync(authPath, 'utf8');
  const clearIndex = authSource.indexOf('clearPrivateCaches();', authSource.indexOf('function logout'));
  const revokeIndex = authSource.indexOf('api.logoutSession', authSource.indexOf('function logout'));
  assert.ok(clearIndex > -1 && revokeIndex > clearIndex);
  for (const key of ['accessToken', 'orders', 'userAddresses', 'currentDesign', 'energyReport']) {
    assert.match(authSource, new RegExp(`['"]${key}['"]`));
  }
});

test('app launch clears private caches before pages render when the session is expired', () => {
  const appSource = fs.readFileSync(appPath, 'utf8');
  const sessionCheck = appSource.indexOf('!auth.hasUsableSession()');
  const cacheClear = appSource.indexOf('auth.clearPrivateCaches()', sessionCheck);
  const deferredRefresh = appSource.indexOf('setTimeout(() =>');
  assert.ok(sessionCheck > -1 && cacheClear > sessionCheck);
  assert.ok(cacheClear < deferredRefresh);
});

test('workspace sharing publishes and opens opaque share tokens instead of design ids', () => {
  const workspaceSource = fs.readFileSync(workspacePath, 'utf8');
  assert.match(workspaceSource, /publishDIYDesign\(designId/);
  assert.match(workspaceSource, /shareToken=/);
  assert.match(workspaceSource, /getSharedDIYDesign\(shareToken/);
  assert.doesNotMatch(workspaceSource, /shareDesignId=/);
});
