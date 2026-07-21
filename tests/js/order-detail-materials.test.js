const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const apiPath = path.resolve(__dirname, '../../miniprogram/utils/api.js');
const authPath = path.resolve(__dirname, '../../miniprogram/utils/auth.js');
const detailPath = path.resolve(__dirname, '../../miniprogram/pages/order-detail/order-detail.js');
const detailTemplatePath = path.resolve(__dirname, '../../miniprogram/pages/order-detail/order-detail.wxml');

function cacheModule(modulePath, exports) {
  require.cache[modulePath] = {
    id: modulePath,
    filename: modulePath,
    loaded: true,
    exports
  };
}

function loadOrderDetailPage(apiOverrides = {}) {
  delete require.cache[detailPath];
  delete require.cache[apiPath];
  delete require.cache[authPath];

  const noop = async () => ({});
  cacheModule(apiPath, {
    getOrder: noop,
    getOrderPaymentStatus: noop,
    payOrder: noop,
    mockPayOrder: noop,
    mockShipOrder: noop,
    confirmReceipt: noop,
    cancelOrder: noop,
    updateOrderReceiver: noop,
    requestAfterSale: noop,
    refundOrder: noop,
    getOrderLogistics: noop,
    ...apiOverrides
  });
  cacheModule(authPath, {
    getStoredUser: () => ({ user_id: 'user-1' }),
    silentLogin: async () => ({ user_id: 'user-1' })
  });

  let definition = null;
  global.Page = config => { definition = config; };
  global.wx = {
    getStorageSync: () => '',
    setStorageSync() {},
    showLoading() {},
    hideLoading() {},
    showToast() {}
  };
  require(detailPath);
  assert.ok(definition, 'order detail page was not registered');
  return {
    ...definition,
    data: { ...(definition.data || {}) },
    setData(update) { Object.assign(this.data, update); }
  };
}

test('order detail hides internal material classification and recommendation fields', () => {
  const page = loadOrderDetailPage();
  const [material] = page.normalizeMaterials([], [{
    id: 'clear-quartz-8',
    sku: 'sku-clear-quartz-8',
    name: '白水晶',
    category: '白水晶',
    series: '通透系列',
    grade: 'AAAA',
    element: 'metal',
    weight: 1.2,
    effect: 'focus',
    subtitle: 'calm',
    size: 8,
    type: '圆珠',
    price: 10
  }]);

  assert.equal(material.name, '白水晶');
  assert.equal(material.detail, '珠径 8mm · 圆珠');
  assert.equal(material.priceText, '10.00');
  assert.equal(Object.hasOwn(material, 'tags'), false);
  assert.equal(Object.hasOwn(material, 'effect'), false);
  assert.doesNotMatch(JSON.stringify(material), /AAAA|metal|focus|calm|1\.2g/);

  const template = fs.readFileSync(detailTemplatePath, 'utf8');
  assert.doesNotMatch(template, /item\.tags|item\.effect|material-tags|material-effect/);
});

test('order detail keeps one pending-shipment stage before waiting for pickup', () => {
  const page = loadOrderDetailPage();
  const history = [
    { status: 'pending_ship', time: '2026-07-13T11:58:26+00:00' },
    { status: 'shipped', time: '2026-07-13T12:08:20+00:00' }
  ];

  const packing = page.normalizeLogistics({}, history.slice(0, 1), 'ship');
  assert.equal(packing.show, true);
  assert.equal(packing.isFulfillmentProgress, true);
  assert.equal(packing.statusText, '待发货');
  assert.deepEqual(packing.traces.map(item => item.desc), ['工作室正在制作与打包，完成后将填写快递单号。']);

  const waitingPickup = page.normalizeLogistics({
    carrier: '顺丰速运',
    carrier_code: 'shunfeng',
    tracking_no: 'SF_TEST_001',
    source: 'local',
    status: 'in_transit',
    status_text: '运输中',
    traces: [
      { time: '2026-07-13T12:08:20+00:00', desc: '商家已打包，待快递揽收' },
      { time: '2026-07-13T12:08:20+00:00', desc: '商家已填写发货信息，等待物流公司更新轨迹' }
    ]
  }, history, 'receive');
  assert.equal(waitingPickup.statusText, '已发货待揽收');
  assert.equal(waitingPickup.isFulfillmentProgress, false);
  assert.equal(waitingPickup.hasCarrierUpdates, false);
  assert.deepEqual(waitingPickup.traces.map(item => item.desc), [
    '商家已发货，等待快递揽收'
  ]);

  const steps = page.buildStatusSteps('receive', {
    paidAt: history[0].time,
    statusHistory: history,
    logistics: { status: 'in_transit', source: 'local' },
    logisticsCard: waitingPickup
  });
  assert.deepEqual(steps.map(item => item.label), [
    '已支付',
    '待发货',
    '已发货待揽收',
    '运输中',
    '待签收'
  ]);
  assert.deepEqual(steps.map(item => item.active), [true, true, true, false, false]);
});

test('carrier traces retain merchant stages and mark the full signed journey', () => {
  const page = loadOrderDetailPage();
  const history = [
    { status: 'pending_ship', time: '2026-07-13T11:58:26+00:00' },
    { status: 'shipped', time: '2026-07-13T12:08:20+00:00' },
    { status: 'completed', time: '2026-07-13T12:09:44+00:00' }
  ];
  const logistics = {
    carrier: '顺丰速运',
    carrier_code: 'shunfeng',
    tracking_no: 'SF_TEST_002',
    source: 'kuaidi100',
    status: 'signed',
    status_text: '已签收',
    traces: [
      { time: '2026-07-13 12:09:44', location: '重庆', desc: '您的快件已派送成功' },
      { time: '2026-07-13 12:08:50', location: '重庆', desc: '正在派送途中' }
    ]
  };

  const detail = page.normalizeLogistics(logistics, history, 'done');
  assert.equal(detail.hasCarrierUpdates, true);
  assert.deepEqual(detail.traces.map(item => item.desc), [
    '您的快件已派送成功',
    '正在派送途中',
    '商家已发货，等待快递揽收'
  ]);

  const steps = page.buildStatusSteps('done', {
    paidAt: history[0].time,
    statusHistory: history,
    logistics,
    logisticsCard: detail
  });
  assert.deepEqual(steps.map(item => item.label), [
    '已支付',
    '待发货',
    '已揽收',
    '运输中',
    '已签收',
    '已完成'
  ]);
  assert.equal(steps.every(item => item.active), true);
});

test('signed delivery stays waiting for user receipt and keeps transport in the journey', () => {
  const page = loadOrderDetailPage();
  const history = [
    { status: 'pending_payment', time: '2026-07-13T11:58:15+00:00' },
    { status: 'pending_ship', time: '2026-07-13T11:58:26+00:00' },
    { status: 'shipped', time: '2026-07-13T12:08:20+00:00' }
  ];
  const order = page.normalizeOrder({
    order_id: 'order-signed-awaiting-receipt',
    status: 'shipped',
    payment_status: 'paid',
    total_amount: '10.00',
    paid_at: history[1].time,
    created_at: history[0].time,
    updated_at: history[2].time,
    receiver: {},
    sequence: [],
    bom: [],
    logistics: {
      carrier: '顺丰速运',
      tracking_no: 'SF_SIGNED_001',
      source: 'kuaidi100',
      status: 'signed',
      status_text: '已签收',
      auto_complete_at: '2026-07-20T06:30:00+00:00',
      traces: [{ time: '2026-07-13 14:30:00', desc: '快件已签收' }]
    },
    status_history: history
  });

  assert.equal(order.statusKey, 'receive');
  assert.equal(order.statusTitle, '待收货');
  assert.equal(order.statusDisplayText, '快递已签收');
  assert.equal(order.canReceive, true);
  assert.match(order.etaText, /请确认收货/);
  assert.match(order.etaText, /自动完成/);
  assert.deepEqual(order.statusSteps.map(item => item.label), [
    '已支付',
    '待发货',
    '已揽收',
    '运输中',
    '已签收',
    '待确认收货'
  ]);
  assert.equal(order.statusSteps[3].active, true);
  assert.equal(order.statusSteps[4].active, true);
  assert.equal(order.statusSteps[5].active, false);
  assert.equal(order.statusStepsScrollable, true);
});

test('refunded order keeps the full shipped journey from status history', () => {
  const page = loadOrderDetailPage();
  const history = [
    { status: 'pending_payment', time: '2026-07-13T11:58:15+00:00' },
    { status: 'pending_ship', time: '2026-07-13T11:58:26+00:00' },
    { status: 'shipped', time: '2026-07-13T12:08:20+00:00' },
    { status: 'refund_requested', time: '2026-07-13T12:18:20+00:00' },
    { status: 'refunded', time: '2026-07-13T12:28:20+00:00' }
  ];

  const order = page.normalizeOrder({
    order_id: 'order-refunded-after-shipping',
    status: 'refunded',
    payment_status: 'refunded',
    total_amount: '10.00',
    paid_at: history[1].time,
    created_at: history[0].time,
    updated_at: history[4].time,
    receiver: {},
    sequence: [],
    bom: [],
    logistics: {
      carrier: '顺丰速运',
      tracking_no: 'SF_REFUND_001',
      shipped_at: history[2].time
    },
    status_history: history
  });

  assert.deepEqual(order.statusSteps.map(item => item.label), [
    '订单创建',
    '已支付',
    '已发货',
    '退款申请',
    '已退款'
  ]);
  assert.equal(order.statusSteps[2].time, page.formatDateTime(history[2].time));
  assert.equal(order.statusStepsScrollable, false);
  assert.equal(order.statusStepsClass, 'steps-5');
});

test('refund before shipping does not invent shipping and long after-sale history scrolls', () => {
  const page = loadOrderDetailPage();
  const beforeShippingLogistics = page.normalizeLogistics({}, [], 'after');
  const beforeShippingActions = page.buildFooterActions({
    statusKey: 'after',
    paymentStatus: 'paid',
    logisticsCard: beforeShippingLogistics,
    afterSaleStatus: 'refund_pending',
    refundStatus: 'requested'
  });
  assert.equal(beforeShippingLogistics.show, false);
  assert.equal(beforeShippingActions.canViewLogistics, false);

  const beforeShipping = page.buildStatusSteps('refunded', {
    createdAt: '2026-07-13T11:58:15+00:00',
    paidAt: '2026-07-13T11:58:26+00:00',
    rawStatus: 'refunded',
    updatedAt: '2026-07-13T12:28:20+00:00',
    statusHistory: [
      { status: 'pending_payment', time: '2026-07-13T11:58:15+00:00' },
      { status: 'pending_ship', time: '2026-07-13T11:58:26+00:00' },
      { status: 'refund_requested', time: '2026-07-13T12:18:20+00:00' },
      { status: 'refunded', time: '2026-07-13T12:28:20+00:00' }
    ],
    logistics: {}
  });
  assert.deepEqual(beforeShipping.map(item => item.label), [
    '订单创建',
    '已支付',
    '退款申请',
    '已退款'
  ]);

  const afterShippingLogistics = page.normalizeLogistics({
    tracking_no: 'SF_AFTER_SALE_001',
    source: 'kuaidi100',
    status: 'in_transit',
    status_text: '运输中',
    traces: [{ time: '2026-07-13T12:08:20+00:00', desc: '快件正在运输途中' }]
  }, [{ status: 'shipped', time: '2026-07-13T12:08:20+00:00' }], 'after');
  const afterShippingActions = page.buildFooterActions({
    statusKey: 'after',
    paymentStatus: 'paid',
    logisticsCard: afterShippingLogistics,
    afterSaleStatus: 'returning',
    refundStatus: 'requested'
  });
  assert.equal(afterShippingLogistics.show, true);
  assert.equal(afterShippingActions.canViewLogistics, true);

  const longHistory = page.buildStatusSteps('refunded', {
    rawStatus: 'refunded',
    statusHistory: [
      { status: 'pending_payment', time: '2026-07-13T11:58:15+00:00' },
      { status: 'pending_ship', time: '2026-07-13T11:58:26+00:00' },
      { status: 'shipped', time: '2026-07-13T12:08:20+00:00' },
      { status: 'completed', time: '2026-07-13T12:18:20+00:00' },
      { status: 'refund_requested', time: '2026-07-13T12:38:20+00:00' },
      { status: 'refunded', time: '2026-07-13T12:48:20+00:00' }
    ],
    logistics: {}
  });
  const layout = page.buildStatusStepsLayout(longHistory);
  assert.deepEqual(longHistory.map(item => item.label), [
    '订单创建',
    '已支付',
    '已发货',
    '已完成',
    '退款申请',
    '已退款'
  ]);
  assert.equal(layout.statusStepsScrollable, true);
  assert.equal(layout.statusStepsScrollLeft, 99999);
  assert.match(layout.statusStepsStyle, /min-width:792rpx/);

  const template = fs.readFileSync(detailTemplatePath, 'utf8');
  assert.match(template, /class="status-steps-scroll"/);
  assert.match(template, /scroll-left="\{\{order\.statusStepsScrollLeft\}\}"/);
  assert.match(template, /style="\{\{order\.statusStepsStyle\}\}"/);
});

test('opening a shipped order silently refreshes logistics once', async () => {
  let logisticsCalls = 0;
  let logisticsOptions = null;
  const history = [
    { status: 'pending_ship', time: '2026-07-13T11:58:26+00:00' },
    { status: 'shipped', time: '2026-07-13T12:08:20+00:00' }
  ];
  const page = loadOrderDetailPage({
    getOrder: async () => ({
      order_id: 'order-live-logistics',
      user_id: 'user-1',
      status: 'shipped',
      payment_status: 'paid',
      total_amount: '10.00',
      paid_at: history[0].time,
      created_at: '2026-07-13T11:58:15+00:00',
      updated_at: history[1].time,
      receiver: {},
      sequence: [],
      bom: [],
      logistics: {},
      status_history: history
    }),
    getOrderLogistics: async (_orderId, _userId, options) => {
      logisticsCalls += 1;
      logisticsOptions = options;
      return {
        logistics: {
          carrier: '顺丰速运',
          carrier_code: 'shunfeng',
          tracking_no: 'SF_TEST_LIVE',
          source: 'kuaidi100',
          status: 'in_transit',
          status_text: '运输中',
          traces: [{ time: '2026-07-13 12:10:00', desc: '快件运输中' }]
        },
        status_history: history
      };
    }
  });
  page.data.id = 'order-live-logistics';

  await page.loadOrder();

  assert.equal(logisticsCalls, 1);
  assert.deepEqual(logisticsOptions, { silent: true });
  assert.equal(page.data.logisticsDetail.statusText, '运输中');
  assert.equal(page.data.order.logisticsCard.hasCarrierUpdates, true);
  assert.deepEqual(page.data.order.statusSteps.map(item => item.label), [
    '已支付',
    '待发货',
    '已揽收',
    '运输中',
    '待签收'
  ]);
});
