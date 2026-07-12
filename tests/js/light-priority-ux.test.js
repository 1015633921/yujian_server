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

function parseWorkspaceLayoutStyle(style) {
  return Object.fromEntries(style.split(';').map(declaration => {
    const [name, value] = declaration.split(':');
    return [name, Number.parseFloat(value)];
  }));
}

test('workspace gives the material drawer more room without collapsing the tray', () => {
  const page = loadPage('miniprogram/pages/workspace/workspace.js');
  const shortViewport = Math.round(568 * 750 / 320);
  const tallViewport = Math.round(844 * 750 / 390);
  const shortLayout = page.buildResponsiveWorkspaceLayout({
    windowWidth: 320,
    windowHeight: 568,
    viewportRpx: shortViewport,
    bottomInsetRpx: 0
  });
  const tallLayout = page.buildResponsiveWorkspaceLayout({
    windowWidth: 390,
    windowHeight: 844,
    viewportRpx: tallViewport,
    bottomInsetRpx: 0
  });
  const shortStyle = parseWorkspaceLayoutStyle(shortLayout.style);
  const tallStyle = parseWorkspaceLayoutStyle(tallLayout.style);

  assert.ok(shortStyle['--workspace-drawer-height'] >= shortViewport * 0.36);
  assert.ok(tallStyle['--workspace-drawer-height'] >= tallViewport * 0.42);
  assert.ok(tallStyle['--workspace-drawer-height'] > shortStyle['--workspace-drawer-height']);
  assert.ok(shortLayout.stageLayout.size >= 580);
  assert.ok(tallLayout.stageLayout.size >= 670);
  const shortOverlap =
    shortStyle['--workspace-top-chrome']
      + shortStyle['--workspace-canvas-height']
      + shortStyle['--workspace-drawer-height']
      - shortViewport;
  const tallOverlap =
    tallStyle['--workspace-top-chrome']
      + tallStyle['--workspace-canvas-height']
      + tallStyle['--workspace-drawer-height']
      - tallViewport;
  assert.ok(shortOverlap >= 64 && shortOverlap <= 72);
  assert.ok(tallOverlap >= 88 && tallOverlap <= 96);
});

test('workspace reserves the device bottom inset inside the expanded material drawer', () => {
  const page = loadPage('miniprogram/pages/workspace/workspace.js');
  const viewportRpx = Math.round(844 * 750 / 390);
  const withoutInset = parseWorkspaceLayoutStyle(page.buildResponsiveWorkspaceLayout({
    windowWidth: 390,
    windowHeight: 844,
    viewportRpx,
    bottomInsetRpx: 0
  }).style);
  const withInset = parseWorkspaceLayoutStyle(page.buildResponsiveWorkspaceLayout({
    windowWidth: 390,
    windowHeight: 844,
    viewportRpx,
    bottomInsetRpx: 65
  }).style);

  assert.equal(withInset['--workspace-safe-bottom'], 65);
  assert.equal(
    withInset['--workspace-drawer-height'] - withoutInset['--workspace-drawer-height'],
    65
  );
  assert.equal(withInset['--workspace-stage-size'], withoutInset['--workspace-stage-size']);
});

test('workspace keeps all physics collisions silent and only shakes on tray-wall impact', () => {
  const page = loadPage('miniprogram/pages/workspace/workspace.js');
  page.ensurePhysicsRuntime();
  const played = [];
  const feedback = [];
  const instance = Object.assign({}, page, {
    data: { ...page.data, isShuffling: false, isStringingFinishing: false },
    soundEnabled: true,
    lastSoundAt: {},
    handleFrozenImpactCollision() {},
    handleTrayWallCollision() {},
    containImpactCollisionBodies() {},
    applyCollisionSpin() {},
    dampenNeighborBeadCollision() {},
    triggerTrayImpactFeedback(vector) {
      feedback.push(vector);
    },
    playSoundEffect(name, throttleMs, options) {
      played.push({ name, throttleMs, options });
    }
  });
  const engine = {};
  const bead = (index, velocity) => ({
    label: `bead-${index}`,
    plugin: { materialId: `material-${index}`, designIndex: index },
    velocity
  });
  const trayWall = { label: 'tray-wall', velocity: { x: 0, y: 0 }, plugin: {} };
  const decoration = { label: 'decoration', velocity: { x: 0, y: 0 }, plugin: {} };

  instance.bindPhysicsCollisionHandlers(engine);
  const collisionStart = engine.events.collisionStart[0];
  collisionStart({
    pairs: [{ bodyA: bead(0, { x: 5, y: 0 }), bodyB: bead(1, { x: -5, y: 0 }) }]
  });
  collisionStart({
    pairs: [{ bodyA: bead(2, { x: 5, y: 0 }), bodyB: decoration }]
  });

  assert.equal(played.length, 0);
  assert.equal(feedback.length, 0);

  collisionStart({
    pairs: [{ bodyA: bead(3, { x: 3, y: 1 }), bodyB: trayWall }]
  });

  assert.equal(played.length, 0);
  assert.equal(feedback.length, 1);
});

test('workspace plays one soft sound when an accepted material lands in the tray', () => {
  const page = loadPage('miniprogram/pages/workspace/workspace.js');
  const played = [];
  const instance = Object.assign({}, page, {
    playSoundEffect(name, throttleMs, options) {
      played.push({ name, throttleMs, options });
    }
  });

  instance.playMaterialLandingSound({ velocity: { x: 36, y: 12 } });

  assert.equal(played.length, 1);
  assert.equal(played[0].name, 'collisionSoft');
  assert.equal(played[0].throttleMs, 0);
  assert.ok(played[0].options.volume >= 0.15);
  assert.ok(played[0].options.volume <= 0.20);
});

test('workspace never plays an impact sound when a launched bead hits another bead', () => {
  const workspaceJs = fs.readFileSync(
    path.resolve(__dirname, '../../miniprogram/pages/workspace/workspace.js'),
    'utf8'
  );
  const releaseStart = workspaceJs.indexOf('releaseFrozenBodiesFromImpact(launcher, hitBody)');
  const feedbackStart = workspaceJs.indexOf('\n  triggerTrayImpactFeedback(', releaseStart);
  const releaseSource = workspaceJs.slice(releaseStart, feedbackStart);
  const commitStart = workspaceJs.indexOf('commitMaterial(id, placement, physicsOptions = {}, onReady)');
  const finishFlightStart = workspaceJs.indexOf('\n  finishFlight()', commitStart);
  const commitSource = workspaceJs.slice(commitStart, finishFlightStart);

  assert.ok(releaseStart >= 0 && feedbackStart > releaseStart);
  assert.ok(commitStart >= 0 && finishFlightStart > commitStart);
  assert.doesNotMatch(releaseSource, /playSoundEffect/);
  assert.equal((commitSource.match(/playMaterialLandingSound/g) || []).length, 1);
  assert.match(workspaceJs, /if \(materialIsPendant\(material\)\)[\s\S]*?this\.ensureAudioPlayers\(\);/);
  assert.doesNotMatch(workspaceJs, /collision: assetUrl/);
  assert.doesNotMatch(workspaceJs, /collisionBright: assetUrl/);
  assert.match(workspaceJs, /collisionSoft: 1/);
});

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
  const basisWxml = fs.readFileSync(
    path.resolve(__dirname, '../../miniprogram/pages/report-basis/report-basis.wxml'),
    'utf8'
  );
  const reportJs = fs.readFileSync(
    path.resolve(__dirname, '../../miniprogram/pages/report/report.js'),
    'utf8'
  );
  const appJson = fs.readFileSync(
    path.resolve(__dirname, '../../miniprogram/app.json'),
    'utf8'
  );
  const answerIndex = reportWxml.indexOf('class="answer-hero"');
  const adviceIndex = reportWxml.indexOf('class="advice-section"');
  const evidenceIndex = reportWxml.indexOf('class="why-section"');
  const detailsIndex = reportWxml.indexOf('class="details-section"');

  assert.ok(answerIndex >= 0);
  assert.ok(answerIndex < adviceIndex);
  assert.ok(adviceIndex < evidenceIndex);
  assert.ok(evidenceIndex < detailsIndex);
  assert.doesNotMatch(reportWxml, /class="element-card/);
  assert.doesNotMatch(reportWxml, /class="details-content/);
  assert.match(reportWxml, /bindtap="openReportBasis"/);
  assert.match(reportWxml, /aria-label="生成报告海报"/);
  assert.match(reportWxml, /posterGenerating \? '生成中' : '生成海报'/);
  assert.match(reportWxml, /aria-disabled="\{\{posterGenerating\}\}"/);
  assert.match(reportWxml, /已隐藏个人输入 · 长按图片可转发或保存/);
  assert.match(reportWxml, /\{\{viewReport\.score\}\}<text>\/100<\/text>/);
  assert.equal((reportWxml.match(/\{\{viewReport\.score\}\}/g) || []).length, 1);
  assert.match(reportWxml, /<view class="energy-label">五行占比<\/view>/);
  assert.match(reportWxml, /aria-label="查看元素分布均衡度说明"/);
  assert.match(reportWxml, />元素分布：<\/view>/);
  assert.match(reportWxml, /balance-score-label">均衡度<\/text>/);
  assert.match(reportWxml, />调节策略<\/view>/);
  assert.match(reportWxml, />当前元素占比<\/view>/);
  assert.doesNotMatch(reportWxml, /<text>五行结构<\/text>/);
  assert.doesNotMatch(reportWxml, /class="energy-score"/);
  assert.match(reportWxml, /class="state-prompt[^>]+aria-role="button"/);
  assert.doesNotMatch(reportWxml, /class="recommend-band/);
  assert.equal((reportWxml.match(/查看专属手串方案/g) || []).length, 1);
  assert.doesNotMatch(reportWxml, /MBTI 偏好如何参与/);
  assert.match(reportWxml, />为什么这样推荐<\/view>/);
  assert.match(appJson, /pages\/report-basis\/report-basis/);
  assert.match(basisWxml, /MBTI 偏好影响/);
  assert.match(basisWxml, /当下状态与直觉色彩/);
  assert.match(basisWxml, /方案生成逻辑/);
  assert.doesNotMatch(basisWxml, /方案还参考了什么/);
  assert.doesNotMatch(basisWxml, /item\.poeticLabel/);
  assert.match(basisWxml, />个人输入<\/view>/);
  assert.match(basisWxml, /aria-label="\{\{item\.label\}\}"/);
  assert.match(basisWxml, /class="season-pill"/);
  assert.match(basisWxml, /信息有误？重新填写/);
  assert.match(basisWxml, /本次报告生成于/);
  assert.match(basisWxml, /本页用于查看个人测算输入，生成或分享海报时默认隐藏这些内容/);
  assert.match(basisWxml, /class="basis-fact basis-time-fact"/);
  assert.match(basisWxml, /class="color-swatch-item"/);
  assert.match(basisWxml, />辅助参考<\/view>/);
  assert.doesNotMatch(basisWxml, /辅助权重/);
  assert.match(reportWxml, /已综合出生信息\{\{viewReport\.hasMbtiInput/);
  assert.match(reportWxml, /性格偏好/);
  assert.match(reportWxml, /viewReport\.hasLiveInput/);
  assert.doesNotMatch(reportWxml, /MBTI\{\{/);
  assert.match(reportWxml, /class="result-share-icon"/);
  assert.match(reportJs, /数值越低，代表元素越集中；数值越高，代表分布越接近/);
  assert.match(basisWxml, /catchtap="showSolarTimeInfo"/);
});

test('report turns element ratios and poetic tags into actionable styling guidance', () => {
  const page = loadPage('miniprogram/pages/report/report.js');
  const instance = Object.assign({}, page);
  const view = instance.buildViewReport({
    assessment_id: 'assessment-style',
    created_at: '2026-07-12T14:33:00+08:00',
    calibration_status: 'applied',
    solar_time: { true_solar_time: '2000-01-01 12:02' },
    final_energy_profile: { 木: 9, 火: 19, 土: 28, 金: 16, 水: 27 },
    strongest_element: '土',
    weakest_element: '木',
    useful_elements: ['金', '水', '木'],
    recommendation_strategy: '土元素偏强，建议参考金、水、木元素进行调和。',
    interpretation: { balance_index: 44 },
    input_summary: { mbti: 'INTJ', core_wishes: ['事业专注'], chakra_answers: [], mood_palette_id: null },
    energy_breakdown: { mbti: { 金: 2.13, 木: 0.53, 水: 2.68, 火: 0.53, 土: 2.13 } },
    bazi_basis: {
      pillars: { year: '己卯', month: '丙子', day: '戊午', time: '戊午' },
      day_master: '戊',
      day_master_strength: '身强'
    },
    seasonal_energy: {
      summary: '暑火最盛，注意急躁、节奏偏急与过度社交',
      seasonal_copy: '暑火最盛，注意急躁、节奏偏急与过度社交',
      notice: '注意安排过满',
      drain_point: '容易同时开启太多计划',
      suggestion: '避免一口气铺太开'
    },
    mood_analysis: {
      name: '紫白月光',
      colors: ['#DDD7EF', '#F7F5F0', '#8177B4']
    },
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
  assert.deepEqual(view.keyElements.map(item => item.label), ['主导元素', '次高元素', '最低元素']);
  assert.deepEqual(view.keyElements.map(item => item.status), ['偏高', '偏高', '偏低']);
  assert.equal(view.styleAnswer.recommendedElementsText, '金 / 水 / 木');
  assert.deepEqual(view.styleAnswer.adjustmentElements.map(item => item.role), ['主要调整', '辅助调整', '少量点缀']);
  assert.deepEqual(view.styleAnswer.adjustmentElements.map(item => item.name), ['金', '水', '木']);
  assert.equal(view.styleAnswer.recommendationSource, 'backend');
  assert.equal(view.statusText, '倾向明显');
  assert.match(view.balanceStrategyNote, /不等同于简单补足最低元素/);
  assert.equal(view.styleAnswer.source, 'recommendation');
  assert.equal(view.styleAnswer.adviceTitle, '你的真实方案建议');
  assert.deepEqual(view.styleAnswer.advice.map(item => item.label), ['推荐色彩', '推荐质感', '结构方向', '尽量避免']);
  assert.equal(view.styleAnswer.advice[0].value, '青绿、雾蓝、米白');
  assert.equal(view.styleAnswer.advice[1].value, '无色通透、天然包体、温润通透、净透');
  assert.equal(view.styleAnswer.advice[2].value, '中心主石 + 对称点睛 + 调和配珠');
  assert.match(view.styleAnswer.summary, /木元素相对较低/);
  assert.equal((view.styleAnswer.summary.match(/轻盈舒展/g) || []).length, 1);
  assert.match(view.styleAnswer.summaryLead, /木元素相对较低/);
  assert.match(view.styleAnswer.summaryAdvice, /以金建立清晰秩序/);
  assert.match(view.styleAnswer.evidence, /以金为主、水为辅、木作少量点缀/);
  assert.match(view.styleAnswer.evidence, /并非简单补足占比最低的元素/);
  assert.deepEqual(view.keywords.map(item => item.label), ['沉稳可靠', '安静细腻', '增加轻盈与生长感']);
  assert.deepEqual(view.keywords.map(item => item.poeticLabel), ['厚载', '静澜', '含章']);
  assert.equal(view.hasMbtiInput, true);
  assert.equal(view.mbti.type, 'INTJ');
  assert.deepEqual(view.mbti.keywords, ['安静聚焦', '灵感探索', '理性清晰', '计划有序']);
  assert.deepEqual(view.mbti.topElements, ['水', '金']);
  assert.match(view.mbti.influence, /不单独决定元素结论或最终方案/);
  assert.doesNotMatch(view.mbti.influence, /\d+\/100/);
  assert.deepEqual(view.mood.colorSwatches.map(item => item.label), ['薰衣草紫', '月光白', '柔雾紫']);
  assert.equal(view.bazi.dayMaster, '戊土');
  assert.equal(view.bazi.strength, '偏强');
  assert.match(view.bazi.strengthDescription, /稳定感/);
  assert.equal(view.assessmentId, 'assessment-style');
  assert.equal(view.generatedAtText, '2026-07-12 14:33');
  assert.equal(view.trueSolarTimeLabel, '校准后时间');
  assert.equal(view.hasTrueSolarTime, true);
  assert.equal(view.trueSolarTimeDescription, '按出生地点与日期校准');
  assert.equal(view.seasonal.seasonal_copy, '近期节奏可能更快，可留意急躁、安排过满或社交消耗');
  assert.equal(view.seasonal.notice, '可留意安排过满');
  assert.match(view.seasonal.drain_point, /可能/);
  assert.equal(view.recommendationReasons[2].title, '性格与当下状态');
  assert.match(view.recommendationReasons[2].desc, /INTJ/);
  assert.equal(view.needsMoreInput, true);

  const unsupported = instance.buildViewReport({
    ...{
      final_energy_profile: { 木: 20, 火: 20, 土: 20, 金: 20, 水: 20 },
      interpretation: { balance_index: 100 },
      input_summary: {}
    },
    calibration_status: 'unsupported',
    solar_time: { true_solar_time: '2000-01-01 12:00' }
  });
  assert.equal(unsupported.hasTrueSolarTime, false);
  assert.equal(unsupported.trueSolarTime, '');
  assert.equal(unsupported.trueSolarTimeLabel, '未完成地点校准');
});

test('report derives stable key elements for tied and incomplete profiles', () => {
  const page = loadPage('miniprogram/pages/report/report.js');
  const instance = Object.assign({}, page);
  const tied = instance.buildViewReport({
    final_energy_profile: { 木: 25, 火: 25, 土: 20, 金: 15, 水: 15 },
    useful_elements: ['水'],
    interpretation: { balance_index: 70 },
    input_summary: {}
  });

  assert.deepEqual(tied.keyElements.map(item => item.value), ['木 25%', '火 25%', '水 15%']);
  assert.deepEqual(tied.keyElements.map(item => item.status), ['偏高', '偏高', '偏低']);
  assert.equal(tied.balanceExplanation, '五种元素略有侧重，搭配时做少量调和即可。');
  assert.equal(tied.statusText, '轻微侧重');

  const empty = instance.buildViewReport({ input_summary: {} });
  assert.deepEqual(empty.keyElements.map(item => item.value), ['木 0%', '火 0%', '水 0%']);
  assert.ok(empty.keyElements.every(item => item.status === '偏低'));
  assert.deepEqual(empty.styleAnswer.adjustmentElements.map(item => item.role), ['建议元素']);
});

test('report keeps element ranking and percentages stable across edge-case payloads', () => {
  const page = loadPage('miniprogram/pages/report/report.js');
  const instance = Object.assign({}, page);
  const profileA = { 木: 25, 火: 25, 土: 25, 金: 15, 水: 10 };
  const profileB = { 水: 10, 金: 15, 土: 25, 火: 25, 木: 25 };
  const first = instance.buildViewReport({
    final_energy_profile: profileA,
    interpretation: { balance_index: 0 },
    input_summary: {}
  });
  const reordered = instance.buildViewReport({
    final_energy_profile: profileB,
    interpretation: { balance_index: 100 },
    input_summary: {}
  });
  const invalid = instance.buildViewReport({
    final_energy_profile: { 木: 0, 火: -9, 土: 'bad', 金: 0.1, 水: 0.1 },
    interpretation: { balance_index: -20 },
    input_summary: {},
    bracelet_plan: { pattern: '', items: [] }
  });
  const close = instance.buildViewReport({
    final_energy_profile: { 木: 20.01, 火: 20, 土: 20, 金: 20, 水: 19.99 },
    interpretation: { balance_index: 99.9 },
    input_summary: {}
  });

  assert.deepEqual(first.keyElements.map(item => item.name), ['木', '火', '水']);
  assert.deepEqual(reordered.keyElements.map(item => item.name), ['木', '火', '水']);
  [first, reordered, invalid, close].forEach(view => {
    assert.equal(view.elements.reduce((sum, item) => sum + item.percent, 0), 100);
  });
  assert.equal(first.score, 0);
  assert.equal(reordered.score, 100);
  assert.equal(invalid.score, 0);
  assert.equal(close.score, 100);
  assert.equal(first.statusText, '倾向明显');
  assert.equal(close.statusText, '分布接近');
  assert.ok(invalid.styleAnswer.advice.every(item => item.value));
});

test('report preserves long dynamic copy and keeps responsive actions safe', () => {
  const page = loadPage('miniprogram/pages/report/report.js');
  const writes = {};
  let navigatedTo = '';
  const instance = Object.assign({}, page, {
    data: { ...page.data },
    setData(patch) {
      Object.assign(this.data, patch);
    }
  });
  const longPattern = '中心主石与两侧点睛珠保持对称，同时在辅助珠之间保留自然留白和清晰节奏';
  const view = instance.buildViewReport({
    final_energy_profile: { 木: 18, 火: 18, 土: 28, 金: 18, 水: 18 },
    useful_elements: ['木'],
    interpretation: { balance_index: 68 },
    input_summary: {},
    bracelet_plan: {
      pattern: longPattern,
      items: [{ name: '绿幽灵', role: '主石', color_families: ['green'] }]
    }
  });

  assert.equal(view.styleAnswer.advice[2].value, longPattern);
  assert.equal(view.styleAnswer.advice[3].label, '尽量避免');
  assert.equal(view.needsMoreInput, true);
  instance.data.viewReport = view;
  instance.data.report = {
    assessment_id: 'assessment-long',
    created_at: '2026-07-12T15:20:00+08:00'
  };
  global.wx = {
    setStorageSync(key, value) {
      writes[key] = value;
    },
    navigateTo({ url }) {
      navigatedTo = url;
    }
  };
  instance.openReportBasis();
  assert.equal(writes.reportBasisView.assessmentId, 'assessment-long');
  assert.equal(writes.reportBasisView.createdAt, '2026-07-12T15:20:00+08:00');
  assert.equal(writes.reportBasisView.viewReport, view);
  assert.equal(navigatedTo, '/pages/report-basis/report-basis');

  const reportWxml = fs.readFileSync(
    path.resolve(__dirname, '../../miniprogram/pages/report/report.wxml'),
    'utf8'
  );
  const reportWxss = fs.readFileSync(
    path.resolve(__dirname, '../../miniprogram/pages/report/report.wxss'),
    'utf8'
  );
  const basisWxss = fs.readFileSync(
    path.resolve(__dirname, '../../miniprogram/pages/report-basis/report-basis.wxss'),
    'utf8'
  );
  assert.match(reportWxml, /约需 10 秒/);
  assert.doesNotMatch(reportWxml, /showDetails/);
  assert.match(reportWxss, /\.result-bottom\s*\{[\s\S]*?position: fixed;/);
  assert.match(reportWxss, /env\(safe-area-inset-bottom\)/);
  assert.match(reportWxss, /@media \(max-width: 350px\)/);
  assert.match(reportWxss, /\.result-share\s*\{[\s\S]*?height: 88rpx;/);
  assert.match(reportWxss, /\.balance-answer\s*\{[\s\S]*?min-height: 112rpx;/);
  assert.match(reportWxss, /\.details-toggle\s*\{[\s\S]*?min-height: 88rpx;/);
  assert.match(reportWxml, /class="result-share-visual"/);
  assert.match(basisWxss, /font-size: 26rpx/);
  assert.match(basisWxss, /@media \(max-width: 350px\)/);
  assert.match(basisWxss, /\.basis-facts\s*\{[\s\S]*?grid-template-columns: repeat\(2/);
  assert.match(basisWxss, /\.basis-time-fact\s*\{[\s\S]*?grid-column: 1 \/ -1;/);
  assert.match(basisWxss, /\.keyword-tags\s*\{[\s\S]*?grid-template-columns: repeat\(2/);
  assert.match(basisWxss, /\.basis-edit-entry\s*\{[\s\S]*?min-height: 96rpx;/);
  assert.doesNotMatch(reportWxss, /line-clamp/);
});

test('report refreshes only when the stored report version changes', () => {
  const page = loadPage('miniprogram/pages/report/report.js');
  let storedReport = {
    assessment_id: 'assessment-a',
    created_at: '2026-07-12T10:00:00+08:00',
    final_energy_profile: { 木: 20, 火: 20, 土: 20, 金: 20, 水: 20 },
    interpretation: { balance_index: 100 },
    input_summary: { user_id: 'user-report', name: '小宇' }
  };
  let updateCount = 0;
  const instance = Object.assign({}, page, {
    data: { ...page.data, beadSizeOptions: [...page.data.beadSizeOptions] },
    setData(patch) {
      updateCount += 1;
      Object.assign(this.data, patch);
    }
  });
  global.wx = {
    getStorageSync(key) {
      if (key === 'energyReport') return storedReport;
      if (key === 'currentUser') return { user_id: 'user-report' };
      return '';
    },
    removeStorageSync() {}
  };

  instance.onLoad();
  assert.equal(updateCount, 1);
  instance.onShow();
  assert.equal(updateCount, 1);

  storedReport = {
    ...storedReport,
    assessment_id: 'assessment-b',
    created_at: '2026-07-12T10:05:00+08:00',
    final_energy_profile: { 木: 10, 火: 20, 土: 40, 金: 10, 水: 20 }
  };
  instance.data.posterPath = '/tmp/old-poster.png';
  instance.onShow();
  assert.equal(updateCount, 2);
  assert.equal(instance.data.viewReport.assessmentId, 'assessment-b');
  assert.equal(instance.data.posterPath, '');

  storedReport = '';
  instance.onShow();
  assert.equal(instance.data.report, null);
  assert.equal(instance.data.viewReport, null);
});

test('private report caches are not rendered without a matching logged-in user', () => {
  const page = loadPage('miniprogram/pages/report/report.js');
  const removed = [];
  const instance = Object.assign({}, page, {
    data: { ...page.data },
    setData(patch) {
      Object.assign(this.data, patch);
    }
  });
  global.wx = {
    getStorageSync(key) {
      if (key === 'energyReport') {
        return {
          assessment_id: 'private-assessment',
          created_at: '2026-07-12T11:00:00+08:00',
          input_summary: { user_id: 'user-owner', name: '私密输入' }
        };
      }
      if (key === 'currentUser') return null;
      return '';
    },
    removeStorageSync(key) {
      removed.push(key);
    }
  };

  instance.onLoad();

  assert.equal(instance.data.report, null);
  assert.equal(instance.data.viewReport, null);
  assert.ok(removed.includes('energyReport'));
  assert.ok(removed.includes('reportBasisView'));
});

test('report basis page reads the prepared view and summarizes participating inputs', () => {
  const page = loadPage('miniprogram/pages/report-basis/report-basis.js');
  const viewReport = {
    assessmentId: 'assessment-basis',
    createdAt: '2026-07-12T16:40:00+08:00',
    wish: '事业专注',
    hasMbtiInput: true,
    hasLiveInput: true,
    mbti: { keywords: ['安静聚焦', '理性清晰'] }
  };
  const instance = Object.assign({}, page, {
    data: { ...page.data },
    setData(patch) {
      Object.assign(this.data, patch);
    }
  });
  global.wx = {
    getStorageSync(key) {
      if (key === 'reportBasisView') {
        return {
          assessmentId: 'assessment-basis',
          createdAt: '2026-07-12T16:40:00+08:00',
          viewReport
        };
      }
      if (key === 'energyReport') {
        return {
          assessment_id: 'assessment-basis',
          created_at: '2026-07-12T16:40:00+08:00',
          input_summary: { user_id: 'user-basis' }
        };
      }
      if (key === 'currentUser') return { user_id: 'user-basis' };
      return '';
    },
    showModal(options) {
      this.lastModal = options;
    }
  };

  instance.onLoad();

  assert.equal(instance.data.viewReport, viewReport);
  assert.equal(instance.data.mbtiKeywordText, '安静聚焦、理性清晰');
  assert.equal(instance.data.inputSummaryText, '本方案综合元素结构、佩戴目标、性格偏好、当前状态生成。');
  assert.equal(instance.data.generationLogicText, '元素结构影响调节方向，佩戴目标影响使用场景，性格偏好影响材质与排列，当下状态影响本次氛围建议。');
  assert.equal(instance.data.generatedAtText, '2026-07-12 16:40');
  instance.showSolarTimeInfo();
  assert.match(global.wx.lastModal.content, /经度、时区与日期/);
});

test('report basis rejects an outdated snapshot after the report changes', () => {
  const page = loadPage('miniprogram/pages/report-basis/report-basis.js');
  const instance = Object.assign({}, page, {
    data: { ...page.data },
    setData(patch) {
      Object.assign(this.data, patch);
    }
  });
  global.wx = {
    getStorageSync(key) {
      if (key === 'reportBasisView') {
        return { assessmentId: 'assessment-old', viewReport: { assessmentId: 'assessment-old' } };
      }
      if (key === 'energyReport') return { assessment_id: 'assessment-new', input_summary: { user_id: 'user-stale' } };
      if (key === 'currentUser') return { user_id: 'user-stale' };
      return '';
    },
    removeStorageSync() {}
  };

  instance.onLoad();

  assert.equal(instance.data.viewReport, null);
  assert.equal(instance.data.emptyTitle, '报告已经更新');
  assert.match(instance.data.emptyCopy, /最新搭配报告/);
});

test('report basis invalidates itself when a newer report appears in the background', () => {
  const page = loadPage('miniprogram/pages/report-basis/report-basis.js');
  let currentAssessmentId = 'assessment-current';
  const viewReport = { assessmentId: 'assessment-current', mbti: { keywords: [] } };
  const instance = Object.assign({}, page, {
    data: { ...page.data },
    setData(patch) {
      Object.assign(this.data, patch);
    }
  });
  global.wx = {
    getStorageSync(key) {
      if (key === 'reportBasisView') {
        return { assessmentId: 'assessment-current', viewReport };
      }
      if (key === 'energyReport') return { assessment_id: currentAssessmentId, input_summary: { user_id: 'user-current' } };
      if (key === 'currentUser') return { user_id: 'user-current' };
      return '';
    },
    removeStorageSync() {}
  };

  instance.onLoad();
  assert.equal(instance.data.viewReport, viewReport);
  currentAssessmentId = 'assessment-new';
  instance.onShow();
  assert.equal(instance.data.viewReport, null);
  assert.equal(instance.data.emptyTitle, '报告已经更新');
});

test('report basis can reopen the existing inputs at the basic step', () => {
  const page = loadPage('miniprogram/pages/report-basis/report-basis.js');
  const writes = {};
  let switchedTo = '';
  const instance = Object.assign({}, page);
  global.wx = {
    getStorageSync(key) {
      if (key === 'energyReport') {
        return {
          created_at: '2026-07-12T16:40:00+08:00',
          input_summary: { mbti: 'INTP', wrist_size_cm: 16.2 }
        };
      }
      return '';
    },
    setStorageSync(key, value) {
      writes[key] = value;
    },
    switchTab({ url }) {
      switchedTo = url;
    }
  };

  instance.restartAssessment();

  assert.deepEqual(writes.assessmentReportSeed.input_summary, { mbti: 'INTP', wrist_size_cm: 16.2 });
  assert.equal(writes.assessmentRecalculateMode, true);
  assert.equal(writes.assessmentRequestedStep, 'basic');
  assert.equal(switchedTo, '/pages/assessment/assessment');
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
  assert.deepEqual(view.styleAnswer.advice.map(item => item.label), ['推荐色彩', '推荐质感', '结构方向', '尽量避免']);
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
  assert.match(assessmentJs, /if \(this\.data\.submitting\) return;/);
  assert.match(assessmentJs, /applyReportSeed/);
  assert.match(assessmentJs, /this\.goToStep\(requestedIndex\)/);
  assert.match(reportJs, /const styleAnswer = view\.styleAnswer/);
  assert.doesNotMatch(reportJs, /drawPosterTextCard\(ctx, '当下状态'/);
  const posterStart = reportJs.indexOf('drawReportPoster(state)');
  const posterEnd = reportJs.indexOf('\n  goBack()', posterStart);
  const posterSource = reportJs.slice(posterStart, posterEnd);
  assert.match(posterSource, /仅展示搭配结论，不包含个人测算输入/);
  assert.doesNotMatch(posterSource, /input_summary|recommendationReasons|目标：|MBTI|chakra|mood/);
  assert.doesNotMatch(posterSource, /safeText\(input\.name/);
});

test('report poster prevents duplicate generation and rejects a stale report result', async () => {
  const page = loadPage('miniprogram/pages/report/report.js');
  let resolvePoster;
  let generateCount = 0;
  const toasts = [];
  const instance = Object.assign({}, page, {
    data: {
      ...page.data,
      report: { assessment_id: 'assessment-poster' }
    },
    setData(patch) {
      Object.assign(this.data, patch);
    },
    generateReportPoster() {
      generateCount += 1;
      return new Promise(resolve => {
        resolvePoster = resolve;
      });
    }
  });
  global.wx = {
    showLoading() {},
    hideLoading() {},
    showToast(options) {
      toasts.push(options.title);
    }
  };

  const firstGeneration = instance.shareReport();
  const duplicateGeneration = instance.shareReport();
  assert.equal(generateCount, 1);
  assert.equal(instance.data.posterGenerating, true);
  assert.equal(await duplicateGeneration, undefined);
  resolvePoster('/tmp/report-poster.png');
  await firstGeneration;
  assert.equal(instance.data.posterGenerating, false);
  assert.equal(instance.data.posterPath, '/tmp/report-poster.png');
  assert.equal(instance.data.showPosterModal, true);

  instance.data.report = { assessment_id: 'assessment-old' };
  instance.data.showPosterModal = false;
  instance.generateReportPoster = async () => {
    instance.data.report = { assessment_id: 'assessment-new' };
    return '/tmp/stale-poster.png';
  };
  const originalWarn = console.warn;
  console.warn = () => {};
  try {
    await instance.shareReport();
  } finally {
    console.warn = originalWarn;
  }
  assert.equal(instance.data.showPosterModal, false);
  assert.match(toasts.at(-1), /报告已更新/);
});

test('logout and personalization deletion clear private report snapshots', () => {
  const removed = [];
  global.wx = {
    getStorageSync() {
      return '';
    },
    removeStorageSync(key) {
      removed.push(key);
    }
  };
  global.getApp = () => ({ globalData: { userInfo: { user_id: 'user-1' } } });
  const authPath = path.resolve(__dirname, '../../miniprogram/utils/auth.js');
  delete require.cache[require.resolve(authPath)];
  const auth = require(authPath);

  auth.logout();

  ['energyReport', 'reportBasisView', 'assessmentReportSeed', 'diyWorkbenchPayload'].forEach(key => {
    assert.ok(removed.includes(key), `${key} should be cleared on logout`);
  });

  const privacyCenterJs = fs.readFileSync(
    path.resolve(__dirname, '../../miniprogram/pages/privacy-center/privacy-center.js'),
    'utf8'
  );
  assert.match(privacyCenterJs, /'reportBasisView'/);
  assert.match(privacyCenterJs, /'assessmentReportSeed'/);
  assert.match(privacyCenterJs, /'diyWorkbenchPayload'/);
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
