const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const html = fs.readFileSync(path.join(root, 'static/admin/index.html'), 'utf8');
const script = fs.readFileSync(path.join(root, 'static/admin/admin.js'), 'utf8');

test('admin no longer exposes the unused content-block operations page', () => {
  assert.doesNotMatch(html, /data-page="content"/);
  assert.doesNotMatch(html, /<section id="content"/);
  assert.doesNotMatch(script, /content:\['CONTENT OPERATIONS','运营内容'\]/);
  assert.doesNotMatch(script, /switchPage\('content'\)/);
  assert.doesNotMatch(script, /content:loadBlocks/);
  assert.doesNotMatch(script, /\bloadBlocks\b/);
  assert.doesNotMatch(script, /\bnewBlock\b/);
  assert.doesNotMatch(script, /\bsaveBlock\b/);
  assert.doesNotMatch(script, /\bdeleteBlock\b/);
});
