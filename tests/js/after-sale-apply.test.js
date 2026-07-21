const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const apiPath = path.resolve(__dirname, '../../miniprogram/utils/api.js');
const authPath = path.resolve(__dirname, '../../miniprogram/utils/auth.js');
const pagePath = path.resolve(__dirname, '../../miniprogram/pages/after-sale-apply/after-sale-apply.js');

function cacheModule(modulePath, exports) {
  require.cache[modulePath] = {
    id: modulePath,
    filename: modulePath,
    loaded: true,
    exports
  };
}

function loadPage(apiOverrides = {}) {
  delete require.cache[pagePath];
  delete require.cache[apiPath];
  delete require.cache[authPath];

  cacheModule(apiPath, {
    getOrder: async () => ({
      order_id: 'ORDER-1',
      status: 'completed',
      status_text: '已完成',
      payment_status: 'paid',
      total_amount: '129.00',
      sequence: [{ name: '白水晶' }]
    }),
    getAfterSaleCases: async () => [],
    createAfterSaleCase: async (_orderId, payload) => ({
      case_id: 'AS-1',
      order_id: 'ORDER-1',
      type: payload.type,
      type_text: '退货退款',
      status: 'requested',
      status_text: '待审核',
      created_at: '2026-07-13T12:00:00+08:00'
    }),
    ...apiOverrides
  });
  cacheModule(authPath, {
    getStoredUser: () => ({ user_id: 'user-1' }),
    silentLogin: async () => ({ user_id: 'user-1' })
  });

  let definition = null;
  global.Page = config => { definition = config; };
  global.wx = {
    showToast() {},
    navigateBack() {},
    redirectTo() {}
  };
  global.getCurrentPages = () => [{ route: 'pages/after-sale-apply/after-sale-apply' }];
  require(pagePath);
  assert.ok(definition, 'after-sale apply page was not registered');
  return {
    ...definition,
    data: { ...(definition.data || {}) },
    setData(update) { Object.assign(this.data, update); }
  };
}

test('after-sale form requires type, reason, detail and explicit confirmation', () => {
  const page = loadPage();
  page.data.orderSummary = { eligible: true };

  page.selectType({ currentTarget: { dataset: { key: 'return_refund' } } });
  assert.equal(page.data.canSubmit, false);
  page.selectReason({ currentTarget: { dataset: { key: 'quality_issue' } } });
  page.onDetailInput({ detail: { value: '破损' } });
  page.toggleAgreement();
  assert.equal(page.data.canSubmit, false);

  page.onDetailInput({ detail: { value: '收到后发现主石有明显破损' } });
  assert.equal(page.data.canSubmit, true);
});

test('refund request submits structured type and never submits a client refund amount', async () => {
  let submitted = null;
  const page = loadPage({
    createAfterSaleCase: async (orderId, payload) => {
      submitted = { orderId, payload };
      return {
        case_id: 'AS-REFUND-1',
        order_id: orderId,
        type: payload.type,
        type_text: '退货退款',
        status: 'requested',
        status_text: '待审核',
        created_at: '2026-07-13T12:00:00+08:00'
      };
    }
  });
  page.data.orderId = 'ORDER-REFUND-1';
  page.data.orderSummary = { eligible: true };
  page.activeUser = { user_id: 'user-1' };
  page.idempotencyKey = 'after-sale-test-refund';
  page.selectType({ currentTarget: { dataset: { key: 'return_refund' } } });
  page.selectReason({ currentTarget: { dataset: { key: 'quality_issue' } } });
  page.onDetailInput({ detail: { value: '收到后发现主石有明显破损' } });
  page.toggleAgreement();

  await page.submitApplication();

  assert.equal(submitted.orderId, 'ORDER-REFUND-1');
  assert.equal(submitted.payload.type, 'return_refund');
  assert.equal(submitted.payload.reason_code, 'quality_issue');
  assert.deepEqual(submitted.payload.evidence_urls, []);
  assert.equal(Object.hasOwn(submitted.payload, 'refund_fee'), false);
  assert.equal(page.data.submittedCase.case_id, 'AS-REFUND-1');
  assert.equal(page.data.canSubmit, false);
});

test('existing active after-sale case opens the result state instead of a new form', async () => {
  const page = loadPage({
    getAfterSaleCases: async () => [{
      case_id: 'AS-EXISTING',
      order_id: 'ORDER-1',
      type: 'repair',
      type_text: '重新穿制／维修',
      status: 'requested',
      status_text: '待审核',
      created_at: '2026-07-13T12:00:00+08:00'
    }]
  });
  page.data.orderId = 'ORDER-1';

  await page.loadPage();

  assert.equal(page.data.isExistingCase, true);
  assert.equal(page.data.submittedCase.case_id, 'AS-EXISTING');
  assert.match(page.data.submittedCase.nextStepText, /工作室审核/);
});
