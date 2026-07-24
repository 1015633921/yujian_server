const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const template = fs.readFileSync(path.join(root, 'miniprogram/pages/workspace/workspace.wxml'), 'utf8');
const script = fs.readFileSync(path.join(root, 'miniprogram/pages/workspace/workspace.js'), 'utf8');

test('workspace material cards do not show raw effect tags', () => {
  assert.doesNotMatch(template, /material-effect|item\.effectText/);
  assert.doesNotMatch(script, /effectText:/);
});
