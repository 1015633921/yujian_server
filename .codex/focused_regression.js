const fs = require('fs');
const path = require('path');
const automator = require('./miniprogram-automator-tmp/node_modules/miniprogram-automator');

const outDir = path.resolve('.codex/acceptance-shots/regression');
fs.mkdirSync(outDir, { recursive: true });

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function hasInternalId(text = '') {
  return /(mat|real)[_-]/i.test(String(text || ''));
}

function sampleDesign() {
  const sequence = [
    {
      index: 1,
      id: 'mat_10650215010',
      sku: 'mat_10650215010',
      name: '白水随型',
      category: '配饰',
      size: 8,
      price: 0.01,
      color: '#e6e6e2',
      shine: '#ffffff'
    },
    {
      index: 2,
      id: 'real_1033571840809',
      sku: 'real_1033571840809',
      name: '紫锂云母',
      category: '云母',
      size: 10,
      price: 0.01,
      color: '#8f68bf',
      shine: '#f5eaff'
    },
    {
      index: 3,
      id: 'clearQuartz8',
      sku: 'clearQuartz8',
      name: '白水晶',
      category: '白色晶石',
      size: 8,
      price: 0.01,
      color: '#dfe3e5',
      shine: '#ffffff'
    },
    {
      index: 4,
      id: 'real_no_name_001',
      sku: 'real_no_name_001',
      category: '兔毛水晶',
      size: 9,
      price: 0.01,
      color: '#d9798a',
      shine: '#fff2f4'
    }
  ];
  const selected = sequence.map(item => item.id);
  const placements = sequence.map((item, index) => ({
    id: item.id,
    looseX: index === 0 ? 285 : 120 + index * 70,
    looseY: index === 0 ? 60 : 260 + index * 24,
    dx: 0,
    dy: 0,
    rotation: index * 45,
    beadSize: item.size * 5.2
  }));
  return {
    id: 'regression-design-1',
    key: 'regression-design-1',
    name: 'DIY 手串方案',
    wristSize: 15.5,
    wearStyle: 'single',
    selected,
    sequence,
    placements,
    createdAt: Date.now() - 3600000,
    summary: {
      count: sequence.length,
      price: 0.04,
      priceText: '0.04',
      length: '3.5'
    }
  };
}

(async () => {
  const mp = await automator.connect({ wsEndpoint: 'ws://127.0.0.1:9420' });
  const results = [];
  const design = sampleDesign();

  async function shot(name) {
    const file = path.join(outDir, `${name}.png`);
    await mp.screenshot({ path: file });
    return file;
  }

  async function currentPath() {
    const page = await mp.currentPage();
    return page.path;
  }

  try {
    await mp.callWxMethod('setStorageSync', 'diyDesignCart', [design]);
    await mp.callWxMethod('setStorageSync', 'currentDesign', design);
    await mp.callWxMethod('setStorageSync', 'workspaceTrayThemeV1', 'warm');
    await mp.callWxMethod('removeStorageSync', 'workspacePreset');
    await mp.callWxMethod('removeStorageSync', 'recommendedRecipe');

    let page = await mp.reLaunch('/pages/home/home');
    await page.waitFor(2500);
    const cta = await page.$('.hero-cta');
    if (cta) {
      await cta.tap();
      await sleep(2500);
    }
    results.push({
      area: '首页',
      check: 'Hero 主按钮可跳转',
      pass: (await currentPath()) !== 'pages/home/home',
      current: await currentPath()
    });

    page = await mp.reLaunch('/pages/search/search');
    await page.waitFor(1600);
    let data = await page.data();
    results.push({
      area: '搜索',
      check: '默认推荐灵感不为空',
      pass: (data.recommendedInspirations || []).length > 0,
      count: (data.recommendedInspirations || []).length
    });
    const input = await page.$('.search-input');
    if (input) {
      await input.input('白水晶');
      await sleep(2500);
    } else {
      await page.setData({ keyword: '白水晶' });
      await page.callMethod('search', '白水晶');
      await sleep(2500);
    }
    data = await page.data();
    results.push({
      area: '搜索',
      check: '关键词搜索返回珠材或灵感',
      pass: ((data.materialResults || []).length + (data.inspirationResults || []).length) > 0,
      materials: (data.materialResults || []).length,
      inspirations: (data.inspirationResults || []).length,
      shot: await shot('search-results')
    });

    page = await mp.reLaunch('/pages/community-detail/community-detail?id=morning-clear-quartz');
    await page.waitFor(2500);
    const sameButton = await page.$('.primary-button');
    if (sameButton) {
      await sameButton.tap();
      await sleep(4500);
    }
    page = await mp.currentPage();
    data = await page.data();
    const workspaceCount = Number(data.summary && data.summary.count);
    results.push({
      area: '社区带入 DIY',
      check: '带入后珠子数量不超过 18 且有可见方案',
      pass: page.path === 'pages/workspace/workspace' && workspaceCount > 0 && workspaceCount <= 18,
      current: page.path,
      count: workspaceCount,
      price: data.summary && data.summary.priceText,
      shot: await shot('community-to-workspace')
    });

    await mp.callWxMethod('setStorageSync', 'currentDesign', design);
    page = await mp.reLaunch('/pages/my-plans/my-plans');
    await page.waitFor(1800);
    data = await page.data();
    const recipeText = (((data.visiblePlans || [])[0] || {}).recipeText) || '';
    results.push({
      area: '我的方案',
      check: '方案摘要不暴露内部材料 ID',
      pass: !hasInternalId(recipeText),
      recipeText,
      shot: await shot('my-plans-no-raw-id')
    });

    await mp.callWxMethod('setStorageSync', 'diyDesignCart', [design]);
    page = await mp.reLaunch('/pages/inspiration-cart/inspiration-cart');
    await page.waitFor(2400);
    data = await page.data();
    const cartItem = (data.items || [])[0] || {};
    results.push({
      area: '购物车',
      check: '方案卡片仅突出缩略图、价格、时间和操作入口',
      pass: Boolean(cartItem.priceText && cartItem.createdTime && (cartItem.miniBeads || []).length),
      priceText: cartItem.priceText,
      createdTime: cartItem.createdTime,
      beads: (cartItem.miniBeads || []).length,
      shot: await shot('cart-card')
    });
    const cartRow = await page.$('.cart-item');
    if (cartRow) {
      await cartRow.tap();
      await sleep(2800);
    }
    page = await mp.currentPage();
    data = await page.data();
    const checkoutPreview = data.previewBeads || [];
    results.push({
      area: '确认订单',
      check: '预览使用托盘 + 圆串排布，信息单独展示',
      pass: page.path === 'pages/checkout/checkout' && checkoutPreview.length === design.sequence.length && !data.trayPreviewImageFailed,
      current: page.path,
      previewBeads: checkoutPreview.length,
      trayFailed: data.trayPreviewImageFailed,
      shot: await shot('checkout-preview')
    });

    const fakeReport = {
      assessment_id: 'regression-assessment',
      final_energy_profile: { 金: 2, 木: 1, 水: 3, 火: 1, 土: 2 },
      input_summary: { name: '测试', mbti: '', core_wishes: ['情绪平衡'] },
      interpretation: {
        headline: '测试能量报告',
        balance_index: 72,
        strongest: '水元素较强。',
        weakest: '火元素可补。'
      },
      strongest_element: '水',
      weakest_element: '火',
      chart: { values: [2, 1, 3, 1, 2] },
      energy_keywords: ['测试']
    };
    await mp.callWxMethod('setStorageSync', 'energyReport', fakeReport);
    await mp.callWxMethod('removeStorageSync', 'assessmentSuppressAutoReportOnce');
    page = await mp.reLaunch('/pages/assessment/assessment');
    await page.waitFor(3200);
    const autoPath = await currentPath();
    if (autoPath === 'pages/report/report') {
      await mp.navigateBack();
      await sleep(2800);
    }
    const afterBackPath = await currentPath();
    results.push({
      area: '测算',
      check: '已有报告自动打开后返回不会再次回弹',
      pass: autoPath === 'pages/report/report' && afterBackPath === 'pages/assessment/assessment',
      autoPath,
      afterBackPath,
      shot: await shot('assessment-after-back')
    });

    console.log(JSON.stringify(results, null, 2));
  } finally {
    mp.disconnect();
  }
})().catch(error => {
  console.error(error);
  process.exit(1);
});
