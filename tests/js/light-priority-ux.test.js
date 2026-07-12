const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

function loadPage(relativePath) {
  const absolutePath = path.resolve(__dirname, '../..', relativePath);
  delete require.cache[require.resolve(absolutePath)];
  let pageConfig = null;
  global.Page = config => {
    pageConfig = config;
  };
  require(absolutePath);
  return pageConfig;
}

test('order and favorites content do not repeat the native page title', () => {
  const orderWxml = fs.readFileSync(
    path.resolve(__dirname, '../../miniprogram/pages/order-list/order-list.wxml'),
    'utf8'
  );
  const favoritesWxml = fs.readFileSync(
    path.resolve(__dirname, '../../miniprogram/pages/community-favorites/community-favorites.wxml'),
    'utf8'
  );

  assert.doesNotMatch(orderWxml, /class="list-title"/);
  assert.doesNotMatch(favoritesWxml, /class="section-title">我的收藏/);
});

test('backend recommendation uses its descriptive payload name for the fresh draft', () => {
  const page = loadPage('miniprogram/pages/workspace/workspace.js');
  const payload = {
    name: '小羽的专属搭配手串',
    wrist_size_cm: 16,
    bracelet_plan: {
      title: '',
      layout: [{ crystal_code: 'clear_quartz' }]
    }
  };
  let importedDraft = null;
  const instance = Object.assign({}, page, {
    data: { ...page.data, wristSize: 16 },
    materialPayloadReady: true,
    buildBackendRecommendationSelected: () => ['clearQuartz8'],
    findMaterialById: id => ({ id, size: 8, size_mm: 8, type: 'bead' }),
    resetWorkspaceRuntime() {},
    pushHistory() {},
    normalizePlacements: selected => selected.map(id => ({ id })),
    replaceCurrentDesignWithImportedDraft(options) {
      importedDraft = options;
    },
    setData(patch) {
      Object.assign(this.data, patch);
    },
    recalculate() {}
  });
  global.wx = {
    getStorageSync(key) {
      if (key === 'diyWorkbenchPayload') return payload;
      return '';
    },
    setStorageSync() {},
    showToast() {}
  };

  const applied = instance.applyBackendRecommendation({ silent: true });

  assert.equal(applied, true);
  assert.equal(importedDraft.name, '小羽的专属搭配手串');
});

test('assessment prefetches the last confirmed size and report reads the cached plan', () => {
  const assessmentJs = fs.readFileSync(
    path.resolve(__dirname, '../../miniprogram/pages/assessment/assessment.js'),
    'utf8'
  );
  const reportJs = fs.readFileSync(
    path.resolve(__dirname, '../../miniprogram/pages/report/report.js'),
    'utf8'
  );

  assert.match(assessmentJs, /recommendedWristSize/);
  assert.match(assessmentJs, /recommendedBeadSize/);
  assert.match(assessmentJs, /wrist_size_cm: preferredWristSize/);
  assert.match(reportJs, /正在读取方案/);
});
