const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const apiPath = path.resolve(__dirname, '../../miniprogram/utils/api.js');
const authPath = path.resolve(__dirname, '../../miniprogram/utils/auth.js');
const checkoutPath = path.resolve(__dirname, '../../miniprogram/pages/checkout/checkout.js');
const detailPath = path.resolve(__dirname, '../../miniprogram/pages/order-detail/order-detail.js');

function cacheModule(modulePath, exports) {
  require.cache[modulePath] = {
    id: modulePath,
    filename: modulePath,
    loaded: true,
    exports
  };
}

function loadPage(pagePath, apiExports, authExports) {
  delete require.cache[pagePath];
  delete require.cache[apiPath];
  delete require.cache[authPath];
  cacheModule(apiPath, apiExports);
  cacheModule(authPath, authExports);
  let definition = null;
  global.Page = config => { definition = config; };
  global.wx = {
    getDeviceInfo: () => ({ platform: 'devtools' }),
    getStorageSync: () => '',
    setStorageSync() {},
    hideLoading() {},
    showLoading() {},
    showToast() {},
    showModal() {},
    navigateTo() {},
    redirectTo() {},
    navigateBack() {},
    pageScrollTo() {}
  };
  require(pagePath);
  assert.ok(definition, `Page was not registered: ${pagePath}`);
  return definition;
}

function pageInstance(definition) {
  return {
    ...definition,
    data: { ...(definition.data || {}) },
    setData(update) { Object.assign(this.data, update); }
  };
}

function checkoutApi(getOrderPaymentStatus) {
  return {
    createOrder: async () => ({}),
    getOrder: async () => ({}),
    getOrderPaymentStatus,
    mockPayOrder: async () => ({}),
    getMaterials: async () => []
  };
}

function detailApi(getOrderPaymentStatus) {
  const noop = async () => ({});
  return {
    getOrder: noop,
    getOrderPaymentStatus,
    payOrder: noop,
    mockPayOrder: noop,
    mockShipOrder: noop,
    confirmReceipt: noop,
    cancelOrder: noop,
    updateOrderReceiver: noop,
    requestAfterSale: noop,
    refundOrder: noop,
    getOrderLogistics: noop
  };
}

test('checkout confirms paid only after the authenticated server status says paid', async () => {
  const statuses = [
    { paid: false, terminal: false, payment_status: 'unpaid' },
    { paid: true, terminal: true, payment_status: 'paid' }
  ];
  let calls = 0;
  const auth = { getStoredUser: () => ({ user_id: 'user-1' }) };
  const definition = loadPage(
    checkoutPath,
    checkoutApi(async () => statuses[calls++]),
    auth
  );
  const page = pageInstance(definition);
  page.waitForPaymentPoll = async () => true;

  const result = await page.confirmPaymentResult('order-1', 'user-1');

  assert.equal(result.state, 'paid');
  assert.equal(calls, 2);
});

test('checkout uses finite polling and returns pending without marking local payment paid', async () => {
  let calls = 0;
  const auth = { getStoredUser: () => ({ user_id: 'user-1' }) };
  const definition = loadPage(
    checkoutPath,
    checkoutApi(async () => {
      calls += 1;
      return { paid: false, terminal: false, payment_status: 'processing' };
    }),
    auth
  );
  const page = pageInstance(definition);
  page.waitForPaymentPoll = async () => true;

  const result = await page.confirmPaymentResult('order-1', 'user-1');

  assert.equal(result.state, 'pending');
  assert.equal(calls, 6);
});

test('payment confirmation stops on account change and page unload', async () => {
  let calls = 0;
  const auth = { getStoredUser: () => ({ user_id: 'user-2' }) };
  const definition = loadPage(
    checkoutPath,
    checkoutApi(async () => {
      calls += 1;
      return { paid: true, terminal: true };
    }),
    auth
  );
  const page = pageInstance(definition);
  const result = await page.confirmPaymentResult('order-1', 'user-1');
  assert.equal(result.state, 'account_changed');
  assert.equal(calls, 0);

  let released = false;
  page._paymentPollResolve = value => { released = value === false; };
  page._paymentPollTimer = setTimeout(() => {}, 1000);
  page.onUnload();
  assert.equal(released, true);
  assert.equal(page._paymentPollTimer, null);
});

test('order detail polls server status and reloads from server on page entry', async () => {
  let calls = 0;
  const auth = { getStoredUser: () => ({ user_id: 'user-1' }) };
  const definition = loadPage(
    detailPath,
    detailApi(async () => {
      calls += 1;
      return calls === 1
        ? { paid: false, terminal: false }
        : { paid: true, terminal: true };
    }),
    auth
  );
  const page = pageInstance(definition);
  page.waitForPaymentPoll = async () => true;
  const result = await page.confirmPaymentResult('order-1', 'user-1');
  assert.equal(result.state, 'paid');
  assert.equal(calls, 2);
  assert.match(definition.onShow.toString(), /loadOrder/);
});

test('client payment success is confirmation-only and cancel/failure copy is distinct', () => {
  const checkoutSource = fs.readFileSync(checkoutPath, 'utf8');
  const detailSource = fs.readFileSync(detailPath, 'utf8');
  assert.match(checkoutSource, /正在确认支付结果/);
  assert.match(checkoutSource, /confirmPaymentResult/);
  assert.match(checkoutSource, /已取消支付/);
  assert.match(checkoutSource, /支付未完成/);
  assert.match(checkoutSource, /支付结果确认中/);
  assert.match(checkoutSource, /支付状态待确认/);
  assert.match(checkoutSource, /客户端未能确认支付结果/);
  assert.doesNotMatch(checkoutSource, /title:\s*'支付完成'/);
  assert.match(detailSource, /_paymentActionRunning/);
  assert.match(detailSource, /支付状态待确认/);
  assert.match(detailSource, /onUnload\(\)[\s\S]*stopPaymentConfirmation/);
  assert.match(detailSource, /item\.userId === currentUserId/);
});
