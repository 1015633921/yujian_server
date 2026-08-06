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
  return Object.fromEntries(String(style || '').split(';').flatMap(declaration => {
    const separator = declaration.indexOf(':');
    if (separator < 0) return [];
    const name = declaration.slice(0, separator).trim();
    const value = declaration.slice(separator + 1).trim();
    return [[name, Number.parseFloat(value)]];
  }));
}

function waitFor(predicate, timeoutMs = 800) {
  const startedAt = Date.now();
  return new Promise((resolve, reject) => {
    const poll = () => {
      if (predicate()) {
        resolve();
        return;
      }
      if (Date.now() - startedAt >= timeoutMs) {
        reject(new Error(`condition not met within ${timeoutMs}ms`));
        return;
      }
      setTimeout(poll, 10);
    };
    poll();
  });
}

function createViewportHarness(page, viewportHeights) {
  let viewportReads = 0;
  const infoForHeight = windowHeight => ({
    windowWidth: 375,
    windowHeight,
    screenHeight: 844,
    statusBarHeight: 47,
    safeArea: { bottom: 810 },
    platform: 'devtools'
  });
  global.wx = {
    getWindowInfo() {
      const index = Math.min(viewportReads, viewportHeights.length - 1);
      const info = infoForHeight(viewportHeights[index]);
      viewportReads += 1;
      return info;
    },
    hideTabBar(options) {
      options.complete();
    },
    showTabBar() {},
    nextTick(callback) {
      callback();
    }
  };

  const initialInfo = infoForHeight(viewportHeights[0]);
  const instance = Object.assign({}, page, {
    data: {
      ...page.data,
      workspaceLoading: false,
      workspaceCanvasVisible: false,
      deviceInfo: initialInfo
    },
    historyStack: [],
    workspacePageVisible: true,
    workspaceViewportSyncToken: 0,
    workspaceViewportSignature: page.getWorkspaceViewportSignature(initialInfo),
    setData(update, callback) {
      Object.assign(this.data, update);
      if (callback) callback();
    },
    markWorkspaceReady() {}
  });

  return {
    instance,
    viewportReads: () => viewportReads
  };
}

async function assertDelayedViewportSequence(viewportHeights) {
  const page = loadPage('miniprogram/pages/workspace/workspace.js');
  const harness = createViewportHarness(page, viewportHeights);

  harness.instance.hideTabBarAndSyncWorkspaceViewport();
  await waitFor(() => harness.instance.data.deviceInfo.windowHeight === 670);

  assert.ok(
    harness.viewportReads() >= viewportHeights.indexOf(670) + 1,
    'viewport polling must not stop after repeated stale heights'
  );
  assert.equal(harness.instance.workspaceViewportSignature, '375:670:844:47:810');
  const layout = parseWorkspaceLayoutStyle(harness.instance.data.workspaceLayoutStyle);
  assert.equal(
    layout['--workspace-canvas-height'],
    undefined,
    'CSS flex layout, not a sampled JS height, must own the workbench/drawer seam'
  );
}

test('workspace waits past two stale viewport samples after hiding the native tab bar', async t => {
  const previousWx = global.wx;
  const previousPage = global.Page;
  t.after(() => {
    global.wx = previousWx;
    global.Page = previousPage;
  });

  await assertDelayedViewportSequence([620, 620, 670, 670]);
});

test('workspace accepts a viewport update that arrives after several stale samples', async t => {
  const previousWx = global.wx;
  const previousPage = global.Page;
  t.after(() => {
    global.wx = previousWx;
    global.Page = previousPage;
  });

  await assertDelayedViewportSequence([620, 620, 620, 670, 670]);
});

test('workspace cancels an in-flight viewport probe when the page is hidden', async t => {
  const previousWx = global.wx;
  const previousPage = global.Page;
  t.after(() => {
    global.wx = previousWx;
    global.Page = previousPage;
  });

  const page = loadPage('miniprogram/pages/workspace/workspace.js');
  const harness = createViewportHarness(page, [620, 620, 670, 670]);
  Object.assign(harness.instance, {
    pauseMaterialBackgroundPreload() {},
    pausePhysics() {},
    stopCanvasRenderLoop() {}
  });

  harness.instance.hideTabBarAndSyncWorkspaceViewport();
  await waitFor(() => harness.viewportReads() >= 1);
  const readsBeforeHide = harness.viewportReads();
  const tokenBeforeHide = harness.instance.workspaceViewportSyncToken;

  harness.instance.onHide();
  await new Promise(resolve => setTimeout(resolve, 180));

  assert.equal(harness.instance.workspacePageVisible, false);
  assert.ok(harness.instance.workspaceViewportSyncToken > tokenBeforeHide);
  assert.equal(harness.viewportReads(), readsBeforeHide);
  assert.equal(harness.instance.data.deviceInfo.windowHeight, 620);
});

function createDeferredSelectorQuery(callbacks) {
  return {
    in() {
      return this;
    },
    select() {
      return this;
    },
    fields() {
      return this;
    },
    boundingClientRect() {
      return this;
    },
    exec(callback) {
      callbacks.push(callback);
    }
  };
}

function canvasMeasurementResult(tag) {
  return [
    { node: {}, width: 300, height: 300, tag: `${tag}-bracelet` },
    { node: {}, width: 375, height: 670, tag: `${tag}-flight` },
    { left: 40, top: 120, width: 300, height: 300, tag: `${tag}-circle` },
    { left: 0, top: 420, width: 375, height: 250, tag: `${tag}-drawer` },
    { left: 0, top: 0, width: 375, height: 670, tag: `${tag}-page` },
    { left: 0, top: 61, width: 375, height: 359, tag: `${tag}-canvas-area` }
  ];
}

function createCanvasMeasureHarness(page, callbacks) {
  const setupTags = [];
  global.wx = {
    createSelectorQuery() {
      return createDeferredSelectorQuery(callbacks);
    },
    showTabBar() {}
  };
  return Object.assign({}, page, {
    data: {
      ...page.data,
      workspaceCanvasVisible: true,
      visibleMaterials: [],
      canvasRenderError: false,
      deviceInfo: { windowWidth: 375, windowHeight: 670 }
    },
    workspacePageVisible: true,
    workspaceCanvasMeasureToken: 0,
    setupTags,
    setupCanvasNode(info) {
      setupTags.push(info.tag);
      return { ctx: {}, tag: info.tag };
    },
    scheduleCanvasRender() {},
    scheduleMaterialPreload() {},
    scheduleWorkspaceInteractionWarmup() {},
    markWorkspaceReady() {},
    setData(update, callback) {
      Object.assign(this.data, update);
      if (callback) callback();
    }
  });
}

test('workspace ignores a stale canvas measurement that finishes after a newer one', t => {
  const previousWx = global.wx;
  const previousPage = global.Page;
  t.after(() => {
    global.wx = previousWx;
    global.Page = previousPage;
  });

  const page = loadPage('miniprogram/pages/workspace/workspace.js');
  const callbacks = [];
  const instance = createCanvasMeasureHarness(page, callbacks);

  instance.initWorkspaceCanvases();
  instance.initWorkspaceCanvases();
  assert.equal(callbacks.length, 2);

  callbacks[1](canvasMeasurementResult('new'));
  callbacks[0](canvasMeasurementResult('stale'));

  assert.deepEqual(instance.setupTags, ['new-bracelet', 'new-flight']);
  assert.equal(instance.braceletCanvasState.tag, 'new-bracelet');
  assert.equal(instance.flightCanvasState.tag, 'new-flight');
  assert.equal(instance.workspaceCircleRect.tag, 'new-circle');
  assert.equal(instance.materialDrawerRect.tag, 'new-drawer');
  assert.equal(instance.workspacePageRect.tag, 'new-page');
  assert.equal(instance.workspaceCanvasAreaRect.tag, 'new-canvas-area');
});

test('workspace invalidates an unfinished canvas measurement when hidden', t => {
  const previousWx = global.wx;
  const previousPage = global.Page;
  t.after(() => {
    global.wx = previousWx;
    global.Page = previousPage;
  });

  const page = loadPage('miniprogram/pages/workspace/workspace.js');
  const callbacks = [];
  const instance = createCanvasMeasureHarness(page, callbacks);
  Object.assign(instance, {
    pauseMaterialBackgroundPreload() {},
    pausePhysics() {},
    stopCanvasRenderLoop() {}
  });

  instance.initWorkspaceCanvases();
  const tokenBeforeHide = instance.workspaceCanvasMeasureToken;
  instance.onHide();
  callbacks[0](canvasMeasurementResult('hidden'));

  assert.equal(instance.workspacePageVisible, false);
  assert.ok(instance.workspaceCanvasMeasureToken > tokenBeforeHide);
  assert.deepEqual(instance.setupTags, []);
  assert.equal(instance.braceletCanvasState, undefined);
  assert.equal(instance.workspacePageRect, undefined);
});

function cssRule(source, selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = source.match(new RegExp(`${escaped}\\s*\\{([^}]+)\\}`));
  assert.ok(match, `missing CSS rule: ${selector}`);
  return match[1];
}

function flexContract(rule, selector) {
  const match = rule.match(
    /(?:^|\n)\s*flex:\s*([\d.]+)\s+([\d.]+)\s+var\((--[\w-]+)\)\s*;/
  );
  assert.ok(match, `${selector} must use a CSS variable as its flex basis`);
  return {
    grow: Number.parseFloat(match[1]),
    shrink: Number.parseFloat(match[2]),
    basisVariable: match[3]
  };
}

function allocatePositiveFlexSpace(availableHeight, items) {
  const basisTotal = items.reduce((sum, item) => sum + item.basis, 0);
  const freeSpace = availableHeight - basisTotal;
  assert.ok(freeSpace >= 0, 'viewport simulation requires positive free space');
  const growTotal = items.reduce((sum, item) => sum + item.grow, 0);
  assert.ok(growTotal > 0, 'at least one region must absorb positive viewport free space');
  return Object.fromEntries(items.map(item => [
    item.name,
    item.basis + freeSpace * item.grow / growTotal
  ]));
}

test('workspace fixes the workbench to its content height and lets the material drawer grow', () => {
  const workspaceWxss = fs.readFileSync(
    path.resolve(__dirname, '../../miniprogram/pages/workspace/workspace.wxss'),
    'utf8'
  );
  const studioPageRule = cssRule(workspaceWxss, '.studio-page');
  const canvasAreaRule = cssRule(workspaceWxss, '.canvas-area');
  const materialDrawerRule = cssRule(workspaceWxss, '.material-drawer');

  assert.match(studioPageRule, /height:\s*100vh\s*;/);
  assert.match(studioPageRule, /min-height:\s*0\s*;/);
  assert.match(studioPageRule, /display:\s*flex\s*;/);
  assert.match(studioPageRule, /flex-direction:\s*column\s*;/);

  const canvasFlex = flexContract(canvasAreaRule, '.canvas-area');
  const drawerFlex = flexContract(materialDrawerRule, '.material-drawer');
  const canvasHeight = canvasAreaRule.match(/(?:^|\n)\s*height:\s*var\((--[\w-]+)\)\s*;/);

  assert.equal(canvasFlex.grow, 0, 'late viewport growth must not enlarge the workbench');
  assert.equal(canvasFlex.shrink, 0, 'the workbench content height must remain stable');
  assert.ok(canvasHeight, '.canvas-area height must follow its content-height variable');
  assert.equal(canvasHeight[1], canvasFlex.basisVariable);
  assert.match(canvasAreaRule, /min-height:\s*0\s*;/);

  assert.match(materialDrawerRule, /position:\s*relative\s*;/);
  assert.ok(drawerFlex.grow > 0, 'the material drawer must absorb late viewport growth');
  assert.equal(drawerFlex.basisVariable, '--workspace-drawer-height');
  assert.doesNotMatch(materialDrawerRule, /position:\s*fixed\s*;/);
  assert.doesNotMatch(materialDrawerRule, /(?:^|\n)\s*bottom:\s*0\s*;/);
});

test('a CSS viewport 92px taller than the sampled JS viewport grows only the material drawer', () => {
  const workspaceWxss = fs.readFileSync(
    path.resolve(__dirname, '../../miniprogram/pages/workspace/workspace.wxss'),
    'utf8'
  );
  const canvasFlex = flexContract(cssRule(workspaceWxss, '.canvas-area'), '.canvas-area');
  const drawerFlex = flexContract(cssRule(workspaceWxss, '.material-drawer'), '.material-drawer');
  const page = loadPage('miniprogram/pages/workspace/workspace.js');
  const windowWidth = 390;
  const sampledWindowHeight = 844;
  const actualCssViewportHeight = sampledWindowHeight + 92;
  const sampledViewportRpx = Math.round(sampledWindowHeight * 750 / windowWidth);
  const actualCssViewportRpx = Math.round(actualCssViewportHeight * 750 / windowWidth);
  const viewportDeltaRpx = actualCssViewportRpx - sampledViewportRpx;
  const style = parseWorkspaceLayoutStyle(page.buildResponsiveWorkspaceLayout({
    windowWidth,
    windowHeight: sampledWindowHeight,
    viewportRpx: sampledViewportRpx,
    bottomInsetRpx: 65
  }).style);
  const canvasBasis = style[canvasFlex.basisVariable];
  const drawerBasis = style[drawerFlex.basisVariable];

  assert.ok(Number.isFinite(canvasBasis), `${canvasFlex.basisVariable} must be emitted by JS`);
  assert.ok(Number.isFinite(drawerBasis), `${drawerFlex.basisVariable} must be emitted by JS`);

  const items = [
    { name: 'canvas', basis: canvasBasis, grow: canvasFlex.grow },
    { name: 'drawer', basis: drawerBasis, grow: drawerFlex.grow }
  ];
  const baseline = allocatePositiveFlexSpace(
    sampledViewportRpx - style['--workspace-top-chrome'],
    items
  );
  const expanded = allocatePositiveFlexSpace(
    actualCssViewportRpx - style['--workspace-top-chrome'],
    items
  );

  assert.ok(viewportDeltaRpx > 0);
  assert.ok(Math.abs(expanded.canvas - baseline.canvas) < 0.001,
    'late viewport height must not become blank workbench space');
  assert.ok(Math.abs((expanded.drawer - baseline.drawer) - viewportDeltaRpx) < 0.001,
    'the material drawer must receive the full late viewport-height delta');
});
