const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const script = fs.readFileSync(path.join(root, 'static/admin/admin.js'), 'utf8');
const style = fs.readFileSync(path.join(root, 'static/admin/admin.css'), 'utf8');

assert.match(script, /function customDesignBriefSection\(request,\{compact=false\}=\{\}\)/);
assert.match(script, /DESIGN BRIEF/);
assert.match(script, /customDesignBriefSection\(x\)/);
assert.match(script, /customDesignBriefSection\(workbench\.request,\{compact:true\}\)/);
assert.match(script, /USER PREFERENCE/);
assert.match(script, /佩戴场景/);
assert.match(script, /本轮调整/);
assert.match(script, /<details class="detail-section custom-design-evidence">/);
assert.match(script, /元素分布均衡度/);
assert.match(script, /mood\.name\|\|mood\.palette_name\|\|mood\.palette_id/);
assert.match(style, /\.custom-design-brief\{/);
assert.match(style, /\.designer-stage \.custom-design-brief--compact/);
assert.match(style, /\.custom-design-evidence summary/);

console.log('admin custom design brief UI contract passed');
