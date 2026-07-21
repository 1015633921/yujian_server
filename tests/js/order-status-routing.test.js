const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const apiPath = path.resolve(__dirname, '../../miniprogram/utils/api.js');
const authPath = path.resolve(__dirname, '../../miniprogram/utils/auth.js');
const assetsPath = path.resolve(__dirname, '../../miniprogram/utils/assets.js');
const envPath = path.resolve(__dirname, '../../miniprogram/config/env.js');
const listPath = path.resolve(__dirname, '../../miniprogram/pages/order-list/order-list.js');
const profilePath = path.resolve(__dirname, '../../miniprogram/pages/profile/profile.js');

function cacheModule(modulePath, exports) {
  require.cache[modulePath] = {
    id: modulePath,
    filename: modulePath,
    loaded: true,
    exports
  };
}

function loadPage(pagePath) {
  for (const modulePath of [pagePath, apiPath, authPath, assetsPath, envPath]) {
    delete require.cache[modulePath];
  }
  const noop = async () => ({});
  cacheModule(apiPath, {
    getOrders: noop,
    getOrder: noop,
    payOrder: noop,
    mockPayOrder: noop,
    mockShipOrder: noop,
    confirmReceipt: noop,
    refundOrder: noop,
    getOrderLogistics: noop,
    getCartItems: noop,
    getCommunityFavorites: noop
  });
  cacheModule(authPath, { getStoredUser: () => ({ user_id: 'user-1' }) });
  cacheModule(assetsPath, { assetUrl: value => value });
  cacheModule(envPath, { isLocalApi: false });

  let definition = null;
  global.Page = config => { definition = config; };
  global.wx = {
    getStorageSync: () => [],
    setStorageSync() {},
    setNavigationBarTitle() {}
  };
  require(pagePath);
  assert.ok(definition, `${pagePath} was not registered`);
  return {
    ...definition,
    data: { ...(definition.data || {}) },
    setData(update) { Object.assign(this.data, update); }
  };
}

test('profile routes active after-sale and refunded orders into the after-sale bucket', () => {
  const page = loadPage(profilePath);

  assert.equal(page.statusKey({ rawStatus: 'completed', afterSaleStatus: 'requested' }), 'after');
  assert.equal(page.statusKey({ rawStatus: 'shipped', afterSaleStatus: 'returning' }), 'after');
  assert.equal(page.statusKey({ rawStatus: 'refunded', paymentStatus: 'refunded' }), 'after');
  assert.equal(page.statusKey({ rawStatus: 'completed', afterSaleStatus: 'resolved' }), 'done');
  assert.equal(page.statusKey({ rawStatus: 'shipped' }), 'receive');
});

test('order list preserves fulfillment text while exposing the active after-sale state', () => {
  const page = loadPage(listPath);
  const active = page.normalizeOrder({
    order_id: 'ORDER-AFTER-SALE',
    status: 'completed',
    status_text: '已完成',
    payment_status: 'paid',
    after_sale_status: 'requested',
    total_amount: '129.00',
    design: {},
    sequence: [],
    bom: []
  });
  const refunded = page.normalizeOrder({
    order_id: 'ORDER-REFUNDED',
    status: 'refunded',
    status_text: '已退款',
    payment_status: 'refunded',
    total_amount: '129.00',
    design: {},
    sequence: [],
    bom: []
  });

  assert.equal(active.statusKey, 'after');
  assert.equal(active.status, '已完成 · 售后待审核');
  assert.equal(refunded.statusKey, 'after');
  assert.equal(refunded.status, '已退款');
});
