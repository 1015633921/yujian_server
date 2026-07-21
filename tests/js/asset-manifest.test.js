const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const env = require('../../miniprogram/config/env');
const manifest = require('../../miniprogram/config/asset-manifest.json');
const runtimeManifest = require('../../miniprogram/config/asset-manifest');
const { assetUrl } = require('../../miniprogram/utils/assets');

test('runtime asset manifest stays in sync with the deployment manifest', () => {
  assert.deepEqual(runtimeManifest, manifest);
});

test('assetUrl resolves through the environment CDN and the shared manifest', () => {
  const logical = 'home/aquamarine.webp';
  const expectedObject = manifest.assets[logical].object;
  assert.equal(assetUrl(logical), `${env.assetBaseUrl}/${expectedObject}`);
});

test('assetUrl keeps an explicit fallback for API-provided paths', () => {
  assert.equal(assetUrl('dynamic/example.webp'), `${env.assetBaseUrl}/dynamic/example.webp`);
});

test('workspace runtime images use immutable CDN manifest entries', () => {
  const workspaceIcons = [
    'share-button-gold.png',
    'workspace-clear-pastel.png',
    'workspace-energy-five-elements.png',
    'workspace-save-download.png',
    'workspace-save-pastel.png',
    'workspace-string-dice.png',
    'workspace-undo.png',
    'workspace-wrist.png'
  ];
  workspaceIcons.forEach(filename => {
    const logical = `workspace-icons/${filename}`;
    const entry = manifest.assets[logical];
    assert.ok(entry, `${logical} is missing from the asset manifest`);
    assert.match(entry.sha256, /^[0-9a-f]{64}$/);
    assert.match(entry.object, /^releases\/[0-9a-f]{16}\/workspace-icons\//);
  });

  const root = path.resolve(__dirname, '../..');
  const workspaceWxml = fs.readFileSync(path.join(root, 'miniprogram/pages/workspace/workspace.wxml'), 'utf8');
  const workspaceJs = fs.readFileSync(path.join(root, 'miniprogram/pages/workspace/workspace.js'), 'utf8');
  const profileJs = fs.readFileSync(path.join(root, 'miniprogram/pages/profile/profile.js'), 'utf8');
  assert.doesNotMatch(`${workspaceWxml}\n${workspaceJs}\n${profileJs}`, /\/images\/workspace-icons\//);

  const projectConfig = JSON.parse(fs.readFileSync(path.join(root, 'miniprogram/project.config.json'), 'utf8'));
  assert.ok(projectConfig.packOptions.ignore.some(item => item.type === 'folder' && item.value === 'assets'));
});
