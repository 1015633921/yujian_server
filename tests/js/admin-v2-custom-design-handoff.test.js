const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const legacyScript = fs.readFileSync(path.join(root, 'static/admin/admin.js'), 'utf8');
const runtime = fs.readFileSync(path.join(root, 'admin-web/src/runtime/environment.ts'), 'utf8');

assert.match(runtime, /page:\s*'designRequests'/);
assert.match(runtime, /request:\s*requestId/);
assert.match(legacyScript, /new URLSearchParams\(location\.search\)/);
assert.match(legacyScript, /Object\.prototype\.hasOwnProperty\.call\(pageMeta,targetPage\)/);
assert.match(legacyScript, /targetPage==='designRequests'&&\/\^\[A-Za-z0-9_/);
assert.match(legacyScript, /openCustomDesignRequest\(targetRequest\)/);
assert.ok(
  legacyScript.indexOf("targetPage==='designRequests'") <
    legacyScript.indexOf('await Promise.all([loadDashboard(),loadSystemStatus()])'),
  'direct design-request handoff must open before unrelated dashboard requests',
);

console.log('admin v2 custom design handoff contract passed');
