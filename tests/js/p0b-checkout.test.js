const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const apiPath = path.resolve(__dirname, '../../miniprogram/utils/api.js');
const checkoutPath = path.resolve(__dirname, '../../miniprogram/pages/checkout/checkout.js');

test('order network timeout retries once with the exact same idempotency key', async () => {
  delete require.cache[require.resolve(apiPath)];
  const requests = [];
  global.wx = {
    getDeviceInfo: () => ({ platform: 'devtools' }),
    getStorageSync: key => (key === 'accessToken' ? 'access-token' : ''),
    showModal() {},
    request(options) {
      requests.push(options);
      if (requests.length === 1) {
        options.fail({ errMsg: 'request:fail timeout' });
        return;
      }
      options.success({
        statusCode: 200,
        data: { code: 0, data: { order: { order_id: 'order-1' }, payment: {} } }
      });
    }
  };
  const originalError = console.error;
  console.error = () => {};
  try {
    const api = require(apiPath);
    const result = await api.createOrder({ sequence: [{ id: 'sku-1' }] }, {
      idempotencyKey: 'checkout-network-key-123'
    });
    assert.equal(result.order.order_id, 'order-1');
  } finally {
    console.error = originalError;
  }
  assert.equal(requests.length, 2);
  assert.equal(requests[0].header['Idempotency-Key'], 'checkout-network-key-123');
  assert.equal(requests[1].header['Idempotency-Key'], 'checkout-network-key-123');
});

test('checkout creates one key per explicit submit and blocks payment on price change', () => {
  const source = fs.readFileSync(checkoutPath, 'utf8');
  assert.match(source, /const idempotencyKey = createCheckoutIdempotencyKey\(\)/);
  assert.match(source, /createOrder\([\s\S]*\{ idempotencyKey \}\)/);
  assert.match(source, /价格已更新，请确认/);
  assert.match(source, /本次支付已阻止/);
});
