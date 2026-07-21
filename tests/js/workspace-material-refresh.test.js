const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(root, 'miniprogram/pages/workspace/workspace.js'), 'utf8');

test('workspace bypasses stored material caches during a background refresh', () => {
  assert.match(source, /workspaceMaterialCatalogV9/);
  assert.match(source, /refreshMaterialCatalogInBackground\(\)/);
  assert.match(source, /force: true,[\s\S]*background: true/);
  assert.match(source, /!options\.force && materialCache\[cacheKey\]/);
});

test('workspace evicts decoded images and textures when the material version changes', () => {
  assert.match(source, /applyMaterialPayloadVersion\(data = \{\}\)/);
  assert.match(source, /this\.canvasImageCache = \{\}/);
  assert.match(source, /this\.canvasTextureCache = \{\}/);
  assert.match(source, /this\.materialImagePreloadSet = \{\}/);
  assert.match(source, /refreshSelectedMaterialDetails\(\)/);
  assert.match(source, /fetchMaterialsByIds\(ids, \{ force: true \}\)/);
});
