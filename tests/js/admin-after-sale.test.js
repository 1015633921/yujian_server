const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
const html = fs.readFileSync(path.join(root, 'static/admin/index.html'), 'utf8');
const script = fs.readFileSync(path.join(root, 'static/admin/admin.js'), 'utf8');
const style = fs.readFileSync(path.join(root, 'static/admin/admin.css'), 'utf8');

function adminRuntime(elements = {}) {
  const context = {
    window: { location: { pathname: '/admin' } },
    localStorage: { getItem: () => '' },
    document: { getElementById: (id) => elements[id] || null },
    console,
    URLSearchParams,
    setTimeout,
    clearTimeout,
  };
  vm.createContext(context);
  vm.runInContext(script, context);
  return context;
}

function renderedSteps(html) {
  return [...html.matchAll(/<div class="fulfillment-step ([^"]*)">.*?<b>([^<]+)<\/b>/gs)]
    .map((match) => ({ label: match[2], done: match[1].split(/\s+/).includes('done') }));
}

test('admin exposes a dedicated after-sale review page backed by structured cases', () => {
  assert.match(html, /data-page="afterSales"/);
  assert.match(html, /id="afterSales"/);
  assert.match(html, /id="afterSaleStatus"/);
  assert.match(html, /id="afterSaleType"/);
  assert.match(script, /\/api\/v1\/admin\/after-sales\?/);
  assert.match(script, /function openAfterSale\(id\)/);
  assert.match(style, /\.after-sale-summary-grid/);
});

test('after-sale detail names an unsaved DIY order from its immutable snapshot', () => {
  const { orderDesignLabel } = adminRuntime();
  assert.equal(
    orderDesignLabel({
      design: { name: 'Yustream DIY 手串方案' },
      sequence: Array.from({ length: 16 }, () => ({})),
    }),
    'Yustream DIY 手串方案 · 订单快照',
  );
  assert.equal(
    orderDesignLabel({}, { sequence: Array.from({ length: 8 }, () => ({})) }),
    '订单快照方案 · 8 颗',
  );
  assert.match(script, /detailItem\('DIY 方案',orderDesignLabel\(order,snapshot\)\)/);
});

test('opening a drawer resets the previous scroll position', () => {
  const classList = { remove() {} };
  const elements = {
    drawerEyebrow: { textContent: '' },
    drawerTitle: { textContent: '' },
    drawerBody: { innerHTML: '' },
    drawerMask: { classList },
    drawer: { classList, scrollTop: 960 },
  };
  const { openDrawer } = adminRuntime(elements);

  openDrawer('CONTENT', 'Edit content', '<p>content</p>');

  assert.equal(elements.drawer.scrollTop, 0);
  assert.equal(elements.drawerTitle.textContent, 'Edit content');
  assert.equal(elements.drawerBody.innerHTML, '<p>content</p>');
});

test('refund approval and actual WeChat refund remain separate operator actions', () => {
  assert.match(script, /prepare_direct_refund/);
  assert.match(script, /确认并原路退款/);
  assert.match(script, /\/after-sales\/\$\{encodeURIComponent\(id\)\}\/review/);
  assert.match(script, /\/after-sales\/\$\{encodeURIComponent\(id\)\}\/refund/);
  assert.match(script, /本步会生成待退款记录，但不会调用微信支付/);
});

test('uncertain refunds expose an explicit query-before-retry recovery action', () => {
  assert.match(script, /核对并恢复退款/);
  assert.match(script, /不会生成新的退款单号/);
  assert.match(script, /\/after-sales\/\$\{encodeURIComponent\(id\)\}\/refund\/retry/);
  assert.match(script, /\/orders\/\$\{encodeURIComponent\(id\)\}\/refund\/retry/);
});

test('legacy order controls cannot treat a bare refund status as a real request', () => {
  assert.match(script, /\['requested','approved'\]\.includes\(state\)/);
  assert.match(script, /缺少真实退款申请，已阻止审核操作/);
  assert.match(script, /退款中和已退款状态只能由真实售后工单及微信退款结果产生/);
  assert.doesNotMatch(script, /\['refund_requested','退款中'\],\['refunded','已退款'\]/);
});

test('pre-shipping refund does not invent fulfillment or logistics stages', () => {
  const { fulfillmentSteps } = adminRuntime();
  const steps = renderedSteps(fulfillmentSteps({
    status: 'refund_requested',
    payment_status: 'paid',
    created_at: '2026-07-14T00:00:00Z',
    paid_at: '2026-07-14T00:01:00Z',
    updated_at: '2026-07-14T00:02:00Z',
    status_history: [
      { status: 'pending_ship', time: '2026-07-14T00:01:00Z' },
      { status: 'refund_requested', time: '2026-07-14T00:02:00Z' },
    ],
  }));

  assert.deepEqual(steps.map((step) => step.label), ['订单创建', '支付成功', '待发货', '退款申请']);
  assert.ok(steps.every((step) => step.done));
});

test('refund after completion preserves every fulfillment stage that really happened', () => {
  const { fulfillmentSteps } = adminRuntime();
  const steps = renderedSteps(fulfillmentSteps({
    status: 'refunded',
    payment_status: 'refunded',
    created_at: '2026-07-14T00:00:00Z',
    paid_at: '2026-07-14T00:01:00Z',
    updated_at: '2026-07-14T10:00:00Z',
    status_history: [
      { status: 'pending_ship', time: '2026-07-14T00:01:00Z' },
      { status: 'shipped', time: '2026-07-14T01:00:00Z' },
      { status: 'completed', time: '2026-07-14T08:00:00Z' },
      { status: 'refund_requested', time: '2026-07-14T09:00:00Z' },
      { status: 'refunded', time: '2026-07-14T10:00:00Z' },
    ],
    logistics: {
      tracking_no: 'SF1234567890',
      status: 'signed',
      source: 'kuaidi100',
      kuaidi100_state: '3',
      shipped_at: '2026-07-14T01:00:00Z',
      signed_at: '2026-07-14T07:00:00Z',
      traces: [
        { time: '2026-07-14T02:00:00Z', desc: '快件已揽收' },
        { time: '2026-07-14T03:00:00Z', desc: '快件运输中' },
        { time: '2026-07-14T07:00:00Z', desc: '快件已签收' },
      ],
    },
  }));

  assert.deepEqual(steps.map((step) => step.label), [
    '订单创建', '支付成功', '待发货', '已发货待揽收', '快递已揽收', '运输中',
    '已签收待确认', '订单完成', '退款申请', '已退款',
  ]);
  assert.ok(steps.every((step) => step.done));
});

test('manual receipt confirmation does not forge a carrier signed event', () => {
  const { fulfillmentSteps } = adminRuntime();
  const html = fulfillmentSteps({
    status: 'completed',
    payment_status: 'paid',
    created_at: '2026-07-14T00:00:00Z',
    paid_at: '2026-07-14T00:01:00Z',
    updated_at: '2026-07-14T02:00:00Z',
    status_history: [
      { status: 'pending_ship', time: '2026-07-14T00:01:00Z' },
      { status: 'shipped', time: '2026-07-14T01:00:00Z' },
      { status: 'completed', time: '2026-07-14T02:00:00Z' },
    ],
    logistics: {
      tracking_no: 'SF1234567890',
      status: 'awaiting_pickup',
      source: 'local',
      shipped_at: '2026-07-14T01:00:00Z',
    },
  });
  const steps = renderedSteps(html);

  assert.equal(steps.find((step) => step.label === '已发货待揽收').done, true);
  assert.equal(steps.find((step) => step.label === '快递已揽收').done, false);
  assert.equal(steps.find((step) => step.label === '运输中').done, false);
  assert.equal(steps.find((step) => step.label === '已签收待确认').done, false);
  assert.equal(steps.find((step) => step.label === '订单完成').done, true);
  assert.match(html, /--fulfillment-step-count:8/);
});

test('provider pickup and signed states remain distinct from order completion', () => {
  const { fulfillmentSteps } = adminRuntime();
  const pickedUp = renderedSteps(fulfillmentSteps({
    status: 'shipped',
    payment_status: 'paid',
    created_at: '2026-07-14T00:00:00Z',
    paid_at: '2026-07-14T00:01:00Z',
    status_history: [{ status: 'pending_ship' }, { status: 'shipped' }],
    logistics: { tracking_no: 'SF1234567890', status: 'in_transit', source: 'kuaidi100', kuaidi100_state: '1' },
  }));
  const signed = renderedSteps(fulfillmentSteps({
    status: 'shipped',
    payment_status: 'paid',
    created_at: '2026-07-14T00:00:00Z',
    paid_at: '2026-07-14T00:01:00Z',
    status_history: [{ status: 'pending_ship' }, { status: 'shipped' }],
    logistics: { tracking_no: 'SF1234567890', status: 'signed', source: 'kuaidi100', kuaidi100_state: '3' },
  }));

  assert.equal(pickedUp.find((step) => step.label === '快递已揽收').done, true);
  assert.equal(pickedUp.find((step) => step.label === '运输中').done, false);
  assert.equal(signed.find((step) => step.label === '已签收待确认').done, true);
  assert.equal(signed.find((step) => step.label === '订单完成').done, false);
});
