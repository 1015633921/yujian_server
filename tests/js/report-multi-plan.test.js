const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');

function loadReportPage() {
  const reportPath = path.join(root, 'miniprogram/pages/report/report.js');
  delete require.cache[require.resolve(reportPath)];
  let pageConfig = null;
  global.Page = config => {
    pageConfig = config;
  };
  require(reportPath);
  return pageConfig;
}

test('report formats three backend design directions for selection', () => {
  const page = loadReportPage();
  const plans = [
    {
      title: '日常克制',
      subtitle: '通勤',
      estimated_bead_count: 22,
      estimated_price: 199,
      accessory_names: [],
      items: [{ name: '白水晶', image_url: 'https://cdn.example.com/white.webp' }]
    },
    {
      title: '层次平衡',
      subtitle: '推荐',
      estimated_bead_count: 24,
      estimated_price: 268,
      accessory_names: ['银隔片'],
      is_recommended: true,
      items: [
        { name: '白水晶', image_url: 'https://cdn.example.com/white.webp' },
        { name: '银隔片', image_url: 'https://cdn.example.com/silver.webp' }
      ]
    },
    {
      title: '个性点睛',
      subtitle: '设计感',
      estimated_bead_count: 25,
      estimated_price: 328,
      accessory_names: ['三角牌'],
      items: [{ name: '三角牌', image_url: 'https://cdn.example.com/triangle.webp' }]
    }
  ];

  const decorated = page.decorateRecommendationPlans(plans);

  assert.equal(decorated.length, 3);
  assert.equal(decorated[1].isRecommended, true);
  assert.equal(decorated[1].accessoryText, '含银隔片');
  assert.equal(decorated[1].priceText, '¥268.00');
  assert.deepEqual(decorated[1].previewImages, [
    'https://cdn.example.com/white.webp',
    'https://cdn.example.com/silver.webp'
  ]);
});

test('selected design direction is written to the workbench payload without changing its layout', () => {
  const page = loadReportPage();
  const storage = { workspaceOpenDesign: 'stale-design-id' };
  let switchedTo = '';
  global.wx = {
    setStorageSync(key, value) {
      storage[key] = value;
    },
    removeStorageSync(key) {
      delete storage[key];
    },
    switchTab({ url }) {
      switchedTo = url;
    }
  };
  const selectedPlan = {
    plan_id: 'balanced-layers',
    wrist_size_cm: 16,
    layout: [
      { material_id: 'bead-1' },
      { material_id: 'accessory-1' },
      { material_id: 'bead-2' }
    ]
  };
  const instance = Object.assign({}, page, {
    data: { ...page.data, report: { report_id: 'report-1' } },
    setData(updates) {
      this.data = { ...this.data, ...updates };
    }
  });

  instance.enterWorkspaceWithRecommendation(
    {
      bracelet_plan: { plan_id: 'fallback', layout: [] },
      workbench_payload: { wrist_size_cm: 16 }
    },
    selectedPlan
  );

  assert.equal(storage.diyWorkbenchPayload.selected_plan_id, 'balanced-layers');
  assert.deepEqual(storage.diyWorkbenchPayload.bracelet_plan.layout, selectedPlan.layout);
  assert.equal(storage.workspacePreset, 'backend-recommended');
  assert.equal(storage.workspaceOpenDesign, undefined);
  assert.equal(switchedTo, '/pages/workspace/workspace');
});

test('report UI exposes the three-plan selector and workspace trusts a validated backend layout', () => {
  const wxml = fs.readFileSync(
    path.join(root, 'miniprogram/pages/report/report.wxml'),
    'utf8'
  );
  const workspace = fs.readFileSync(
    path.join(root, 'miniprogram/pages/workspace/workspace.js'),
    'utf8'
  );

  assert.match(wxml, /wx:if="\{\{showPlanModal\}\}"/);
  assert.match(wxml, /bindtap="chooseRecommendationPlan"/);
  assert.match(wxml, /返回修改手围和珠径/);
  assert.match(workspace, /backendValidation\.is_valid === true/);
  assert.match(workspace, /backendLayoutIsTrusted[\s\S]*\\? baseSelected/);
});
