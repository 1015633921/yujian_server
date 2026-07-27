const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');

function loadWorkspacePage() {
  const workspacePath = path.join(root, 'miniprogram/pages/workspace/workspace.js');
  delete require.cache[require.resolve(workspacePath)];
  let pageConfig = null;
  global.Page = config => {
    pageConfig = config;
  };
  require(workspacePath);
  return pageConfig;
}

test('adding a material to a stringed bracelet keeps the ring intact', () => {
  const page = loadWorkspacePage();
  let physicsStopped = 0;
  let physicsCreated = 0;
  let finished = 0;
  const ringPlacements = [
    { id: 'a', dx: 2, dy: 3 },
    { id: 'b', dx: 2, dy: 3 },
    { id: 'c', dx: 2, dy: 3 }
  ];
  const instance = Object.assign({}, page, {
    data: {
      ...page.data,
      isLooseMode: false,
      selected: ['a', 'b', 'c'],
      placements: ringPlacements
    },
    buildStringedInsertion(id, placement) {
      assert.equal(id, 'd');
      assert.equal(placement.image_url, 'https://example.com/d.webp');
      return {
        selected: ['a', 'b', 'c', 'd'],
        placements: [...ringPlacements, { id: 'd', dx: 2, dy: 3, image_url: placement.image_url }]
      };
    },
    pushHistory() {},
    stopPhysics() { physicsStopped += 1; },
    createPhysicsEngine() { physicsCreated += 1; },
    playMaterialLandingSound() {},
    recalculate() {},
    scheduleCanvasRender() {},
    setData(updates, callback) {
      this.data = { ...this.data, ...updates };
      if (callback) callback();
    }
  });

  instance.commitMaterial('d', { image_url: 'https://example.com/d.webp' }, {}, () => { finished += 1; });

  assert.deepEqual(instance.data.selected, ['a', 'b', 'c', 'd']);
  assert.equal(instance.data.isLooseMode, false);
  assert.equal(instance.data.placements.length, 4);
  assert.deepEqual(instance.data.placements.slice(0, 3), ringPlacements);
  assert.equal(physicsStopped, 1);
  assert.equal(physicsCreated, 0);
  assert.equal(finished, 1);
});

test('stringed material flight targets the new ring slot', () => {
  const page = loadWorkspacePage();
  const instance = Object.assign({}, page, {
    data: { ...page.data, isLooseMode: false },
    buildStringedInsertion() {
      return {
        selected: ['a', 'b', 'c', 'd'],
        visualSlots: [{ x: 1, y: 2 }, { x: 3, y: 4 }, { x: 5, y: 6 }, { x: 88, y: 99 }]
      };
    }
  });

  const target = instance.resolveMaterialFlightTarget(
    { id: 'd', keepStringed: true, placement: {} },
    { size: 8 },
    { center: 300 }
  );

  assert.deepEqual({ x: target.x, y: target.y }, { x: 88, y: 99 });
});

test('a stale stringing state recovers and performs the requested toggle', () => {
  const page = loadWorkspacePage();
  let releases = 0;
  const instance = Object.assign({}, page, {
    data: {
      ...page.data,
      isLooseMode: false,
      isShuffling: true,
      isStringingFinishing: false,
      isReleasingString: false
    },
    stopPhysics() {},
    recalculate() {},
    releaseString() { releases += 1; },
    setData(updates, callback) {
      this.data = { ...this.data, ...updates };
      if (callback) callback();
    }
  });

  global.wx = { showToast() {} };
  instance.toggleStringMode();

  assert.equal(releases, 1);
  assert.equal(instance.data.isShuffling, false);
  assert.equal(instance.data.isStringingFinishing, false);
  assert.equal(instance.data.isReleasingString, false);
});

test('a recommended loose design preserves its order when returning to stringed preview', () => {
  const page = loadWorkspacePage();
  let restored = 0;
  let shuffled = 0;
  const instance = Object.assign({}, page, {
    data: {
      ...page.data,
      isLooseMode: true,
      selected: ['a', 'b', 'c'],
      sourceContext: {
        source: 'backend_recommendation',
        source_label: '推荐方案',
        title: '层次平衡'
      }
    },
    stringCurrentDesign() { restored += 1; },
    shuffleDesign() { shuffled += 1; }
  });

  global.wx = { showToast() {} };
  instance.toggleStringMode();

  assert.equal(restored, 1);
  assert.equal(shuffled, 0);
  assert.deepEqual(instance.data.selected, ['a', 'b', 'c']);
  assert.equal(instance.buildActionState().randomTitle, '成串预览');
});

test('starting a recommendation import clears the previous design history', () => {
  const page = loadWorkspacePage();
  const storage = {};
  const instance = Object.assign({}, page, {
    data: {
      ...page.data,
      canUndo: true,
      canRedo: true
    },
    historyStack: [{ selected: ['old-design'] }],
    redoStack: [{ selected: ['redo-design'] }],
    workspaceDesignRevision: 4,
    resetWorkspaceRuntime() {},
    setData(updates) {
      this.data = { ...this.data, ...updates };
    }
  });
  global.wx = {
    setStorageSync(key, value) {
      storage[key] = value;
    }
  };

  const revision = instance.beginWorkspaceImportSession('recommendation:new-plan');

  assert.equal(revision, 5);
  assert.equal(instance.activeWorkspaceImportId, 'recommendation:new-plan');
  assert.deepEqual(instance.historyStack, []);
  assert.deepEqual(instance.redoStack, []);
  assert.deepEqual(storage.workspaceHistory, []);
  assert.equal(instance.data.canUndo, false);
  assert.equal(instance.data.canRedo, false);
});

test('the string action exposes its current visual label to accessibility', () => {
  const workspaceWxml = require('node:fs').readFileSync(
    require('node:path').join(root, 'miniprogram/pages/workspace/workspace.wxml'),
    'utf8'
  );

  assert.match(workspaceWxml, /aria-label="\{\{randomTitle\}\}"/);
});

test('replacing a recommendation invalidates stale canvas hit-test sprites', () => {
  const page = loadWorkspacePage();
  const instance = Object.assign({}, page, {
    braceletCanvasDirty: false,
    lastBraceletCanvasRenderSignature: 'old-scene',
    lastBraceletCanvasRenderSnapshot: { signature: 'old-scene' },
    latestCanvasDrawSnapshot: { signature: 'old-scene' },
    canvasHitTestSpritesCache: { signature: 'old-scene', sprites: [{ index: 0 }] }
  });

  instance.invalidateCanvasInteractionSnapshot();

  assert.equal(instance.braceletCanvasDirty, true);
  assert.equal(instance.lastBraceletCanvasRenderSignature, '');
  assert.equal(instance.lastBraceletCanvasRenderSnapshot, null);
  assert.equal(instance.latestCanvasDrawSnapshot, null);
  assert.equal(instance.canvasHitTestSpritesCache, null);
});

test('finishing a scatter transition resets the canvas backing surface', () => {
  const page = loadWorkspacePage();
  let physicsStarts = 0;
  let canvasStops = 0;
  let canvasInits = 0;
  const placements = [{ id: 'a', looseX: 120, looseY: 180 }];
  const instance = Object.assign({}, page, {
    data: {
      ...page.data,
      selected: ['a'],
      placements: []
    },
    setLivePlacements() {},
    recalculate() {},
    startPhysicsFromCurrentDesign() { physicsStarts += 1; },
    stopCanvasRenderLoop() { canvasStops += 1; },
    initWorkspaceCanvases() { canvasInits += 1; },
    setData(updates, callback) {
      this.data = { ...this.data, ...updates };
      if (callback) callback();
    }
  });
  global.wx = {
    nextTick(callback) {
      callback();
    }
  };

  instance.completeReleaseString(placements);

  assert.equal(instance.data.isLooseMode, true);
  assert.deepEqual(instance.data.placements, placements);
  assert.equal(physicsStarts, 1);
  assert.equal(canvasStops, 1);
  assert.equal(canvasInits, 1);
  assert.equal(instance.braceletCanvasDirty, true);
});
