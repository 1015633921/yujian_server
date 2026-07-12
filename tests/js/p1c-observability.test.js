const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const apiPath = path.join(root, 'miniprogram/utils/api.js');

test('mini program attaches a privacy-safe request id and keeps it across retries', () => {
  const source = fs.readFileSync(apiPath, 'utf8');
  assert.match(source, /function createRequestId\(\)/);
  assert.match(source, /headers\['X-Request-ID'\] = options\.requestId/);
  assert.match(source, /const tracedOptions = options\.requestId \? options/);
  assert.match(source, /\.\.\.options, idempotencyKey, networkRetried: true/);
  assert.doesNotMatch(source, /X-Request-ID.*userId/);
});
