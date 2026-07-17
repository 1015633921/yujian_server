const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const apiPath = path.resolve(__dirname, '../../miniprogram/utils/api.js');
const authPath = path.resolve(__dirname, '../../miniprogram/utils/auth.js');
const pagePath = path.resolve(
  __dirname,
  '../../miniprogram/pages/web-login-confirm/web-login-confirm.js'
);

function loadApi(storage = {}) {
  delete require.cache[require.resolve(apiPath)];
  let lastRequest = null;
  global.wx = {
    getDeviceInfo: () => ({ platform: 'devtools' }),
    getStorageSync: key => storage[key] || '',
    request(options) {
      lastRequest = options;
      options.success({
        statusCode: 200,
        data: { code: 0, data: { status: 'confirmed' } }
      });
    }
  };
  return { api: require(apiPath), lastRequest: () => lastRequest };
}

function cachedModule(filename, exports) {
  require.cache[filename] = {
    id: filename,
    filename,
    loaded: true,
    exports
  };
}

function loadPage({ response, loggedIn = true } = {}) {
  delete require.cache[pagePath];
  delete require.cache[apiPath];
  delete require.cache[authPath];
  let confirmCalls = [];
  const user = loggedIn ? { user_id: 'user-1', nickname: '测试用户' } : null;
  cachedModule(authPath, {
    getStoredUser: () => user,
    hasUsableSession: () => loggedIn,
    loginWithWechatProfile: async () => user,
    requireLogin: async () => user
  });
  cachedModule(apiPath, {
    confirmWebLoginPairing: async (...args) => {
      confirmCalls.push(args);
      if (response instanceof Error) throw response;
      return response || { status: 'confirmed' };
    }
  });
  let config = null;
  global.Page = value => { config = value; };
  require(pagePath);
  const instance = Object.assign({}, config, {
    data: { ...config.data },
    setData(patch) {
      Object.assign(this.data, patch);
    }
  });
  global.wx = {
    showModal(options) {
      options.success({ confirm: true });
    },
    showToast() {},
    navigateBack() {},
    switchTab() {}
  };
  return { instance, confirmCalls };
}

test('pairing confirmation uses the existing authenticated request pipeline', async () => {
  const loaded = loadApi({ accessToken: 'mini-session-token' });
  await loaded.api.confirmWebLoginPairing('wp_test-pairing_1234567890123456', '7K9M2QXZ');

  const request = loaded.lastRequest();
  assert.match(request.url, /\/api\/v1\/auth\/web-pairings\/wp_test-pairing_1234567890123456\/confirm$/);
  assert.equal(request.method, 'POST');
  assert.deepEqual(request.data, { verification_code: '7K9M2QXZ' });
  assert.equal(request.header.Authorization, 'Bearer mini-session-token');
  assert.equal(request.header['X-Yustream-BFF-Token'], undefined);
});

test('page requires both the full pairing id and the generated eight-character code', async () => {
  const { instance, confirmCalls } = loadPage();
  instance.onShow();
  instance.setData({ pairingId: 'short', verificationCode: '12345678' });
  await instance.submitConfirmation();

  assert.equal(instance.data.status, 'error');
  assert.match(instance.data.errorText, /pairing_id/);
  assert.equal(confirmCalls.length, 0);
});

test('page normalizes the code, confirms once, and renders success', async () => {
  const { instance, confirmCalls } = loadPage();
  instance.onShow();
  instance.onPairingIdInput({ detail: { value: 'wp_test-pairing_1234567890123456' } });
  instance.onVerificationCodeInput({ detail: { value: '7k9m-2qxz' } });
  await instance.submitConfirmation();

  assert.equal(instance.data.verificationCode, '');
  assert.equal(instance.data.status, 'success');
  assert.equal(instance.data.submitting, false);
  assert.equal(confirmCalls.length, 1);
  assert.deepEqual(confirmCalls[0].slice(0, 2), [
    'wp_test-pairing_1234567890123456',
    '7K9M2QXZ'
  ]);
});

test('page exposes a dedicated expired state without persisting pairing secrets', async () => {
  const expired = new Error('登录配对已过期');
  expired.statusCode = 410;
  const { instance } = loadPage({ response: expired });
  instance.onShow();
  instance.setData({
    pairingId: 'wp_test-pairing_1234567890123456',
    verificationCode: '7K9M2QXZ'
  });
  await instance.submitConfirmation();

  assert.equal(instance.data.status, 'expired');
  assert.match(instance.data.errorText, /过期/);
  const source = fs.readFileSync(pagePath, 'utf8');
  assert.doesNotMatch(source, /setStorageSync/);
});

test('page keeps logged-out users and disabled backend responses in explicit states', async () => {
  const loggedOut = loadPage({ loggedIn: false });
  loggedOut.instance.onShow();
  loggedOut.instance.setData({
    pairingId: 'wp_test-pairing_1234567890123456',
    verificationCode: '7K9M2QXZ'
  });
  await loggedOut.instance.submitConfirmation();
  assert.equal(loggedOut.instance.data.isLoggedIn, false);
  assert.match(loggedOut.instance.data.errorText, /请先登录/);
  assert.equal(loggedOut.confirmCalls.length, 0);

  const unavailable = new Error('网站登录配对当前未开放');
  unavailable.statusCode = 503;
  const disabledBackend = loadPage({ response: unavailable });
  disabledBackend.instance.onShow();
  disabledBackend.instance.setData({
    pairingId: 'wp_test-pairing_1234567890123456',
    verificationCode: '7K9M2QXZ'
  });
  await disabledBackend.instance.submitConfirmation();
  assert.equal(disabledBackend.instance.data.status, 'error');
  assert.match(disabledBackend.instance.data.errorText, /暂未开放/);
});

test('personal center registers the real confirmation entry', () => {
  const app = JSON.parse(fs.readFileSync(
    path.resolve(__dirname, '../../miniprogram/app.json'),
    'utf8'
  ));
  const profileSource = fs.readFileSync(
    path.resolve(__dirname, '../../miniprogram/pages/profile/profile.js'),
    'utf8'
  );
  const profileMarkup = fs.readFileSync(
    path.resolve(__dirname, '../../miniprogram/pages/profile/profile.wxml'),
    'utf8'
  );

  assert.ok(app.pages.includes('pages/web-login-confirm/web-login-confirm'));
  assert.match(profileSource, /openWebLoginConfirm/);
  assert.match(profileSource, /\/pages\/web-login-confirm\/web-login-confirm/);
  assert.match(profileMarkup, /确认网页登录/);
});
