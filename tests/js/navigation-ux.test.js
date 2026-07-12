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
