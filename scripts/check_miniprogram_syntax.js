const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const roots = [path.join(ROOT, 'miniprogram'), path.join(ROOT, 'scripts')];
const ignored = new Set(['node_modules', '.codex']);
const files = [];

function walk(current) {
  for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
    if (ignored.has(entry.name)) continue;
    const target = path.join(current, entry.name);
    if (entry.isDirectory()) walk(target);
    else if (entry.isFile() && entry.name.endsWith('.js')) files.push(target);
  }
}

for (const root of roots) walk(root);
for (const file of files.sort()) {
  const result = spawnSync(process.execPath, ['--check', file], { stdio: 'inherit' });
  if (result.status !== 0) process.exit(result.status || 1);
}
console.log(`checked ${files.length} JavaScript files`);
