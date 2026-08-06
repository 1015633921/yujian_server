const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const script = fs.readFileSync(path.join(root, 'static/admin/admin.js'), 'utf8');
const style = fs.readFileSync(path.join(root, 'static/admin/admin.css'), 'utf8');

assert.match(script, /function customDesignCandidateHtml\(\)/);
assert.match(script, /BRIEF CANDIDATES/);
assert.match(script, /不会自动加入手串/);
assert.match(script, /function refreshCustomDesignCandidates\(\)/);
assert.match(script, /\/material-candidates/);
assert.match(script, /selected_material_ids:/);
assert.match(script, /wrist_size_cm:workbench\.wristSize/);
assert.match(script, /bead_size_mm:workbench\.beadSize/);
assert.match(script, /candidates:null/);
assert.match(script, /Math\.max\(10,Math\.min\(25/);
assert.match(script, /reserved=num\(material\.reserved_stock\?\?sku\.reserved_stock,0\)/);
assert.match(style, /\.designer-candidates\{/);
assert.match(style, /\.designer-candidate\{/);

console.log('admin custom design candidate UI contract passed');
