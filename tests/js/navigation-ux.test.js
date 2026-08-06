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

test('mini program explicitly launches on the home page', () => {
  const appConfig = JSON.parse(fs.readFileSync(
    path.resolve(__dirname, '../../miniprogram/app.json'),
    'utf8'
  ));

  assert.equal(appConfig.entryPagePath, 'pages/home/home');
  assert.equal(appConfig.pages[0], 'pages/home/home');
});

test('home enables friend and timeline sharing with a stable entry path', () => {
  let menus = [];
  global.wx = {
    showShareMenu(options) {
      menus = options.menus;
    }
  };
  const page = loadPage('miniprogram/pages/home/home.js');

  page.onLoad();

  assert.deepEqual(menus, ['shareAppMessage', 'shareTimeline']);
  assert.deepEqual(page.onShareAppMessage(), {
    title: '宇涧水晶｜测算、搭配与 DIY 定制',
    path: '/pages/home/home'
  });
  assert.deepEqual(page.onShareTimeline(), {
    title: '宇涧水晶｜测算、搭配与 DIY 定制',
    query: ''
  });
});

test('workspace back always returns to home and relaunches on switch failure', () => {
  const page = loadPage('miniprogram/pages/workspace/workspace.js');
  const calls = [];
  global.wx = {
    switchTab(options) {
      calls.push(['switchTab', options.url]);
      options.fail();
    },
    reLaunch(options) {
      calls.push(['reLaunch', options.url]);
    }
  };

  page.goBack();

  assert.deepEqual(calls, [
    ['switchTab', '/pages/home/home'],
    ['reLaunch', '/pages/home/home']
  ]);
});

test('custom navigation does not render controls underneath the native capsule', () => {
  const root = path.resolve(__dirname, '../..');
  const workspaceWxml = fs.readFileSync(
    path.join(root, 'miniprogram/pages/workspace/workspace.wxml'),
    'utf8'
  );
  const workspaceWxss = fs.readFileSync(
    path.join(root, 'miniprogram/pages/workspace/workspace.wxss'),
    'utf8'
  );
  const decorativeCapsulePages = [
    'miniprogram/pages/community/community.wxml',
    'miniprogram/pages/community-detail/community-detail.wxml',
    'miniprogram/pages/custom-mode/custom-mode.wxml',
    'miniprogram/pages/assessment-guide/assessment-guide.wxml'
  ];
  const arSource = fs.readFileSync(
    path.join(root, 'miniprogram/package-ar/pages/ar-tryon/ar-tryon.js'),
    'utf8'
  );
  const arTemplate = fs.readFileSync(
    path.join(root, 'miniprogram/package-ar/pages/ar-tryon/ar-tryon.wxml'),
    'utf8'
  );
  const arStyles = fs.readFileSync(
    path.join(root, 'miniprogram/package-ar/pages/ar-tryon/ar-tryon.wxss'),
    'utf8'
  );

  assert.doesNotMatch(workspaceWxml, /aria-label="更多操作"|class="more-btn"/);
  assert.doesNotMatch(workspaceWxss, /\.more-btn|\.more-dot/);
  decorativeCapsulePages.forEach(relativePath => {
    const template = fs.readFileSync(path.join(root, relativePath), 'utf8');
    assert.doesNotMatch(template, /class="(?:nav-tools|nav-capsule|guide-nav-mark)"/);
  });
  assert.match(arSource, /getMenuButtonBoundingClientRect/);
  assert.match(arTemplate, /--capsule-safe-right: \{\{capsuleSafeRight\}\}px/);
  assert.match(arStyles, /padding:\s*var\(--safe-top\)\s+var\(--capsule-safe-right\)/);
});

test('existing assessment report shows a transition before navigation', () => {
  const page = loadPage('miniprogram/pages/assessment/assessment.js');
  const storage = {
    energyReport: { assessment_id: 'assessment-1' }
  };
  let navigatedTo = '';
  const instance = Object.assign({}, page, {
    data: { ...page.data },
    setData(patch, callback) {
      Object.assign(this.data, patch);
      if (callback) callback();
    }
  });
  global.wx = {
    getStorageSync(key) {
      return storage[key];
    },
    setStorageSync(key, value) {
      storage[key] = value;
    },
    removeStorageSync(key) {
      delete storage[key];
    },
    navigateTo(options) {
      assert.equal(instance.data.redirectingToReport, true);
      navigatedTo = options.url;
      options.complete();
    }
  };

  instance.openExistingReportIfNeeded();

  assert.equal(navigatedTo, '/pages/report/report?from=assessment');
  assert.equal(instance.data.redirectingToReport, true);
  assert.equal(instance.autoReportNavigating, false);
  const wxml = fs.readFileSync(
    path.resolve(__dirname, '../../miniprogram/pages/assessment/assessment.wxml'),
    'utf8'
  );
  assert.match(wxml, /正在打开搭配报告/);
});

test('assessment back returns to home even when the tab page has a page stack', () => {
  const page = loadPage('miniprogram/pages/assessment/assessment.js');
  const calls = [];
  global.getCurrentPages = () => [
    { route: 'pages/home/home' },
    { route: 'pages/assessment/assessment' }
  ];
  global.wx = {
    switchTab(options) {
      calls.push(['switchTab', options.url]);
    },
    navigateBack() {
      calls.push(['navigateBack']);
    }
  };

  page.goBack();

  assert.deepEqual(calls, [['switchTab', '/pages/home/home']]);
});

test('home tab navigation relaunches the requested tab when switching fails', () => {
  const page = loadPage('miniprogram/pages/home/home.js');
  const calls = [];
  global.getCurrentPages = () => [{ route: 'pages/home/home' }];
  global.wx = {
    switchTab(options) {
      calls.push(['switchTab', options.url]);
      options.fail();
    },
    reLaunch(options) {
      calls.push(['reLaunch', options.url]);
    }
  };

  page.navigateHomeUrl('/pages/profile/profile');

  assert.deepEqual(calls, [
    ['switchTab', '/pages/profile/profile'],
    ['reLaunch', '/pages/profile/profile']
  ]);
});

test('assessment keeps its page navigation above the step action dock', () => {
  const root = path.resolve(__dirname, '../..');
  const assessmentWxml = fs.readFileSync(
    path.join(root, 'miniprogram/pages/assessment/assessment.wxml'),
    'utf8'
  );
  const assessmentWxss = fs.readFileSync(
    path.join(root, 'miniprogram/pages/assessment/assessment.wxss'),
    'utf8'
  );
  const page = loadPage('miniprogram/pages/assessment/assessment.js');
  const calls = [];
  const instance = Object.assign({}, page, {
    data: { ...page.data, submitting: false }
  });
  global.wx = {
    switchTab(options) {
      calls.push(['switchTab', options.url]);
    },
    navigateTo(options) {
      calls.push(['navigateTo', options.url]);
    }
  };

  instance.goToPage({ currentTarget: { dataset: { url: '/pages/home/home' } } });
  instance.goToPage({ currentTarget: { dataset: { url: '/pages/my-plans/my-plans' } } });

  assert.deepEqual(calls, [
    ['switchTab', '/pages/home/home'],
    ['navigateTo', '/pages/my-plans/my-plans']
  ]);
  assert.match(assessmentWxml, /class="lab-tabbar"/);
  assert.match(assessmentWxml, /aria-label="测算，当前页"/);
  assert.match(assessmentWxml, /data-url="\/pages\/home\/home"/);
  assert.match(assessmentWxss, /--assessment-fixed-reserve/);
  assert.match(assessmentWxss, /\.assessment-bottom\s*\{[\s\S]*?bottom: calc\(/);
  assert.match(assessmentWxss, /\.lab-tabbar\s*\{[\s\S]*?position: fixed;/);
});

test('report layers provide a one-tap route back to the home tab', () => {
  const report = loadPage('miniprogram/pages/report/report.js');
  const basis = loadPage('miniprogram/pages/report-basis/report-basis.js');
  const calls = [];
  global.wx = {
    switchTab(options) {
      calls.push(options.url);
    }
  };

  report.goHome();
  basis.goHome();

  assert.deepEqual(calls, ['/pages/home/home', '/pages/home/home']);
});
