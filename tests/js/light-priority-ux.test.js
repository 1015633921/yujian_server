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

test('backend recommendation recalculates only after selected beads reach page data', () => {
  const page = loadPage('miniprogram/pages/workspace/workspace.js');
  const payload = {
    name: '测试推荐手串',
    wrist_size_cm: 16,
    bracelet_plan: {
      title: '',
      layout: [{ crystal_code: 'clear_quartz' }]
    }
  };
  let pendingSetData = null;
  let countSeenByRecalculate = -1;
  const instance = Object.assign({}, page, {
    data: { ...page.data, selected: [], placements: [], wristSize: 16 },
    materialPayloadReady: true,
    buildBackendRecommendationSelected: () => ['clearQuartz8'],
    findMaterialById: id => ({ id, size: 8, size_mm: 8, type: 'bead' }),
    resetWorkspaceRuntime() {},
    pushHistory() {},
    normalizePlacements: selected => selected.map(id => ({ id })),
    replaceCurrentDesignWithImportedDraft() {},
    setData(patch, callback) {
      pendingSetData = { patch, callback };
    },
    recalculate() {
      countSeenByRecalculate = this.data.selected.length;
    }
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
  assert.equal(countSeenByRecalculate, -1);
  assert.ok(pendingSetData);
  Object.assign(instance.data, pendingSetData.patch);
  pendingSetData.callback();
  assert.ok(instance.data.selected.length > 0);
  assert.equal(countSeenByRecalculate, instance.data.selected.length);
});

test('workspace falls back to DOM beads when canvas rendering fails', () => {
  const page = loadPage('miniprogram/pages/workspace/workspace.js');
  let fallbackReason = '';
  let restoreCount = 0;
  const instance = Object.assign({}, page, {
    data: { ...page.data, selected: ['clearQuartz8'] },
    materialPayloadReady: true,
    braceletCanvasState: {
      width: 320,
      height: 320,
      ctx: {
        clearRect() {},
        save() {},
        translate() {},
        restore() {
          restoreCount += 1;
        }
      }
    },
    getCanvasImpactOffset: () => ({ x: 0, y: 0 }),
    drawCanvasBeadSprites() {
      throw new Error('offscreen canvas draw failed');
    },
    switchToDomRendererFallback(reason) {
      fallbackReason = reason;
    }
  });

  instance.renderBraceletCanvas();

  assert.equal(restoreCount, 1);
  assert.equal(fallbackReason, 'bracelet canvas render failed');
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

test('report leads with a plain-language answer and keeps technical evidence secondary', () => {
  const reportWxml = fs.readFileSync(
    path.resolve(__dirname, '../../miniprogram/pages/report/report.wxml'),
    'utf8'
  );
  const answerIndex = reportWxml.indexOf('class="answer-hero"');
  const adviceIndex = reportWxml.indexOf('class="advice-section"');
  const recommendationIndex = reportWxml.indexOf('class="recommend-band');
  const evidenceIndex = reportWxml.indexOf('class="why-section"');
  const detailsIndex = reportWxml.indexOf('class="details-section"');

  assert.ok(answerIndex >= 0);
  assert.ok(answerIndex < adviceIndex);
  assert.ok(adviceIndex < recommendationIndex);
  assert.ok(recommendationIndex < evidenceIndex);
  assert.ok(evidenceIndex < detailsIndex);
  assert.doesNotMatch(reportWxml, /class="element-card/);
  assert.match(reportWxml, /wx:if="\{\{showDetails\}\}" class="details-content"/);
  assert.match(reportWxml, /\{\{viewReport\.score\}\}<text>\/100<\/text>/);
  assert.match(reportWxml, /class="state-prompt[^>]+aria-role="button"/);
  assert.match(reportWxml, /class="recommend-band[^>]+aria-role="button"/);
});

test('report turns element ratios and poetic tags into actionable styling guidance', () => {
  const page = loadPage('miniprogram/pages/report/report.js');
  const instance = Object.assign({}, page);
  const view = instance.buildViewReport({
    final_energy_profile: { 木: 9, 火: 19, 土: 28, 金: 16, 水: 27 },
    strongest_element: '土',
    weakest_element: '木',
    useful_elements: ['金', '水', '木'],
    recommendation_strategy: '土元素偏强，建议参考金、水、木元素进行调和。',
    interpretation: { balance_index: 44 },
    input_summary: { core_wishes: ['事业专注'], chakra_answers: [], mood_palette_id: null },
    bracelet_plan: {
      pattern: '中心主石 + 对称点睛 + 调和配珠',
      items: [
        {
          name: '绿幽灵',
          role: '主石',
          color_families: ['green', 'clear'],
          reason: '绿幽灵承接事业专注的佩戴目标。',
          material_params: { transparency_level: 'transparent', texture_features: ['mineral_inclusion'] }
        },
        {
          name: '海蓝宝',
          role: '调和配珠',
          color_families: ['blue', 'white'],
          reason: '海蓝宝用于让整体表达更清晰。',
          material_params: { transparency_level: 'translucent', texture_features: ['clean'] }
        },
        {
          name: '白水晶',
          role: '点睛配珠',
          color_families: ['white', 'clear'],
          reason: '白水晶负责两侧的视觉过渡。',
          material_params: { transparency_level: 'transparent', texture_features: ['clean'] }
        }
      ]
    },
    energy_keywords: [
      { label: '厚载', source: '主元素', element: '土' },
      { label: '静澜', source: '辅助气质', element: '水' },
      { label: '含章', source: '调和方向', element: '木' }
    ]
  });

  assert.equal(view.styleAnswer.headline, '沉稳可靠，适合加入清晰与秩序感');
  assert.equal(view.elements.reduce((sum, item) => sum + item.percent, 0), 100);
  assert.deepEqual(view.keyElements.map(item => item.value), ['土 29%', '水 27%', '木 9%']);
  assert.deepEqual(view.keyElements.map(item => item.label), ['主要倾向', '次要倾向', '比例较低']);
  assert.equal(view.styleAnswer.recommendedElementsText, '金 / 水 / 木');
  assert.equal(view.styleAnswer.recommendationSource, 'backend');
  assert.equal(view.statusText, '侧重非常鲜明');
  assert.equal(view.styleAnswer.source, 'recommendation');
  assert.equal(view.styleAnswer.adviceTitle, '你的真实方案建议');
  assert.deepEqual(view.styleAnswer.advice.map(item => item.label), ['实际配色', '实际材质', '实际结构', '搭配逻辑']);
  assert.equal(view.styleAnswer.advice[0].value, '青绿、透明、雾蓝、米白');
  assert.equal(view.styleAnswer.advice[1].value, '绿幽灵、海蓝宝、白水晶');
  assert.equal(view.styleAnswer.advice[2].value, '中心主石 + 对称点睛 + 调和配珠');
  assert.match(view.styleAnswer.evidence, /事业专注/);
  assert.deepEqual(view.keywords.map(item => item.label), ['沉稳可靠', '安静细腻', '增加轻盈与生长感']);
  assert.deepEqual(view.keywords.map(item => item.poeticLabel), ['厚载', '静澜', '含章']);
  assert.equal(view.needsMoreInput, true);
});

test('report labels element-only guidance honestly before wrist confirmation', () => {
  const page = loadPage('miniprogram/pages/report/report.js');
  const instance = Object.assign({}, page);
  const view = instance.buildViewReport({
    final_energy_profile: { 木: 10, 火: 20, 土: 35, 金: 15, 水: 20 },
    strongest_element: '土',
    weakest_element: '木',
    interpretation: { balance_index: 25 },
    input_summary: {}
  });

  assert.equal(view.styleAnswer.source, 'element-fallback');
  assert.equal(view.styleAnswer.adviceTitle, '你的元素风格建议');
  assert.deepEqual(view.styleAnswer.advice.map(item => item.label), ['色彩方向', '质感方向', '结构方向', '搭配提醒']);
});

test('report supplement action requests the state step and poster uses the simplified answer', () => {
  const page = loadPage('miniprogram/pages/report/report.js');
  const writes = {};
  let switchedTo = '';
  global.wx = {
    setStorageSync(key, value) {
      writes[key] = value;
    },
    switchTab({ url }) {
      switchedTo = url;
    }
  };

  page.data.report = {
    created_at: '2026-07-12T12:00:00+08:00',
    input_summary: {
      name: '小宇',
      birthday: '1994-05-18',
      birth_time: '08:30',
      birth_place: '杭州市',
      core_wishes: ['招财进宝/事业腾飞'],
      chakra_answers: [],
      mood_palette_id: null
    }
  };
  page.supplementAssessment();

  assert.equal(writes.assessmentRecalculateMode, true);
  assert.equal(writes.assessmentRequestedStep, 'state');
  assert.equal(writes.assessmentReportSeed.input_summary.name, '小宇');
  assert.equal(switchedTo, '/pages/assessment/assessment');

  const reportJs = fs.readFileSync(
    path.resolve(__dirname, '../../miniprogram/pages/report/report.js'),
    'utf8'
  );
  const assessmentJs = fs.readFileSync(
    path.resolve(__dirname, '../../miniprogram/pages/assessment/assessment.js'),
    'utf8'
  );
  assert.match(assessmentJs, /ASSESSMENT_REQUESTED_STEP_KEY/);
  assert.match(assessmentJs, /applyReportSeed/);
  assert.match(assessmentJs, /this\.goToStep\(requestedIndex\)/);
  assert.match(reportJs, /const styleAnswer = view\.styleAnswer/);
  assert.doesNotMatch(reportJs, /drawPosterTextCard\(ctx, '当下状态'/);
});

test('assessment restores required fields from an older report before opening the state step', () => {
  const page = loadPage('miniprogram/pages/assessment/assessment.js');
  const instance = Object.assign({}, page, {
    data: {
      ...page.data,
      form: { ...page.data.form, wishes: [], chakraAnswers: [] }
    },
    setData(patch, callback) {
      Object.assign(this.data, patch);
      if (callback) callback();
    }
  });
  global.wx = {
    getStorageSync(key) {
      if (key === 'assessmentLastProfile') {
        return {
          name: '小宇',
          birthDate: '1994-05-18',
          birthTimeUnknown: true
        };
      }
      return '';
    }
  };

  let completed = false;
  instance.applyReportSeed({
    input_summary: {
      name: '小宇',
      birthday: '1994-05-18',
      birth_time: '12:00',
      birth_place: '杭州市',
      mbti: 'INTJ',
      core_wishes: ['招财进宝/事业腾飞'],
      chakra_answers: ['表达感'],
      mood_palette_id: 'mist_blue'
    }
  }, () => {
    completed = true;
  });

  assert.equal(completed, true);
  assert.equal(instance.data.form.name, '小宇');
  assert.equal(instance.data.form.birthDate, '1994-05-18');
  assert.equal(instance.data.form.birthPlace, '杭州市');
  assert.equal(instance.data.form.birthTimeUnknown, true);
  assert.deepEqual(instance.data.form.wishes, ['事业专注']);
  assert.deepEqual(instance.data.form.chakraAnswers, ['表达感']);
  assert.equal(instance.data.form.moodPaletteId, 'mist_blue');
});
