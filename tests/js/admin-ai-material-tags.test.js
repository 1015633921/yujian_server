const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const html = fs.readFileSync(path.join(root, 'static/admin/index.html'), 'utf8');
const script = fs.readFileSync(path.join(root, 'static/admin/admin.js'), 'utf8');
const style = fs.readFileSync(path.join(root, 'static/admin/admin.css'), 'utf8');

assert.match(html, /data-page="aiMaterialTags"/);
assert.match(html, /id="aiTagInspector"/);
assert.match(html, /id="aiTagStatus"/);
assert.match(script, /aiMaterialTags:loadAiMaterialTags/);
assert.match(script, /\/api\/v1\/admin\/material-ai-tags/);
assert.match(script, /async function reviewAiMaterialTag/);
assert.match(script, /async function applyAiMaterialTag/);
assert.match(script, /material-ai-tags\/\$\{encodeURIComponent\(item\.annotation_id\)\}\/apply/);
assert.match(html, /<option value="applied">已应用<\/option>/);
assert.match(style, /\.ai-tag-workspace/);
assert.match(style, /\.ai-tag-application-grid/);
assert.match(style, /@media\(max-width:900px\)[^{]*\{[^}]*\.ai-tag-workspace/s);

console.log('admin AI material review UI contract passed');
