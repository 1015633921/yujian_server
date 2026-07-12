const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const TEST_MARKERS = ['/test-api', 'cdn-test.'];

function load(target) {
  const filename = path.join(ROOT, 'miniprogram', 'config', `env.${target}.js`);
  delete require.cache[require.resolve(filename)];
  return require(filename);
}

function fail(message) {
  console.error(message);
  process.exitCode = 1;
}

function requireHttps(label, value) {
  if (!String(value || '').startsWith('https://')) {
    fail(`${label} must use https`);
  }
}

const test = load('test');
const prod = load('prod');

for (const [target, config] of [['test', test], ['prod', prod]]) {
  if (config.envName !== target) fail(`${target}: envName mismatch`);
  for (const key of ['fallbackBaseUrl', 'deviceBaseUrl', 'assetBaseUrl']) {
    requireHttps(`${target}.${key}`, config[key]);
  }
}

if (!test.fallbackBaseUrl.includes('/test-api') || !test.assetBaseUrl.includes('cdn-test.')) {
  fail('test config must point only to test API and test assets');
}
if (TEST_MARKERS.some((marker) => prod.fallbackBaseUrl.includes(marker) || prod.assetBaseUrl.includes(marker))) {
  fail('prod config must not contain test endpoints');
}
if (test.useTestApi !== true || prod.useTestApi !== false) {
  fail('useTestApi must match the selected environment');
}

for (const [target, config] of [['test', test], ['prod', prod]]) {
  for (const forbidden of ['productionBaseUrl', 'testBaseUrl', 'productionAssetBaseUrl', 'testAssetBaseUrl']) {
    if (Object.prototype.hasOwnProperty.call(config, forbidden)) {
      fail(`${target}: cross-environment field ${forbidden} is forbidden`);
    }
  }
}

if (!process.exitCode) console.log('miniprogram environment isolation check passed');
