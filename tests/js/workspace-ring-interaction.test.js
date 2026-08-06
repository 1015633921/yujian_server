const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
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

test('stringed bead touches always reorder while only empty outer ring touches rotate', () => {
  const page = loadWorkspacePage();
  const geometry = { center: 100, radius: 50, beadSizes: [40, 40, 40] };
  const instance = Object.assign({}, page, {
    data: { ...page.data, isLooseMode: false, selected: ['a', 'b', 'c'] },
    getStringedRingContext() {
      return { geometry };
    }
  });

  assert.equal(instance.shouldStartRingSlide({
    index: 0,
    point: { x: 168, y: 100 },
    isOuterEdge: true
  }), false);
  assert.equal(instance.shouldStartRingSlide({
    index: -1,
    point: { x: 168, y: 100 }
  }), true);
  assert.equal(instance.shouldStartRingSlide({
    index: -1,
    point: { x: 120, y: 100 }
  }), false);
});

test('ring reorder no longer converts a bead drag into whole-ring rotation', () => {
  const page = loadWorkspacePage();
  let slideCalls = 0;
  const geometry = {
    center: 100,
    radius: 50,
    angles: [0, Math.PI, Math.PI * 1.5],
    beadSizes: [40, 40, 40],
    materialGeometries: []
  };
  const placements = [{ dx: 0, dy: 0 }, { dx: 0, dy: 0 }, { dx: 0, dy: 0 }];
  const items = [{ id: 'a' }, { id: 'b' }, { id: 'c' }];
  const instance = Object.assign({}, page, {
    data: { ...page.data, isLooseMode: false, selected: ['a', 'b', 'c'], placements },
    getStringedRingContext() {
      return { selected: this.data.selected, placements, items, geometry };
    },
    touchToTrayPoint() {
      return { x: 150, y: 100 };
    },
    getRingVisualSlots() {
      return [
        { x: 150, y: 100, angle: 0 },
        { x: 50, y: 100, angle: Math.PI },
        { x: 100, y: 50, angle: Math.PI * 1.5 }
      ];
    },
    beginRingSlide() {
      slideCalls += 1;
    },
    buildSelectedBeadInfo() {
      return { position: 1 };
    },
    setData(updates) {
      this.data = { ...this.data, ...updates };
    },
    scheduleCanvasRender() {}
  });

  instance.beginRingReorder(0, { clientX: 150, clientY: 100 }, { width: 200 });

  assert.equal(slideCalls, 0);
  assert.equal(instance.ringDragState.currentIndex, 0);
  assert.equal(instance.data.draggingBeadIndex, 0);
});

test('workspace keeps gestures separate without adding rotation controls or hints', () => {
  const source = fs.readFileSync(
    path.join(root, 'miniprogram/pages/workspace/workspace.js'),
    'utf8'
  );
  const wxml = fs.readFileSync(
    path.join(root, 'miniprogram/pages/workspace/workspace.wxml'),
    'utf8'
  );
  const wxss = fs.readFileSync(
    path.join(root, 'miniprogram/pages/workspace/workspace.wxss'),
    'utf8'
  );

  assert.doesNotMatch(source, /getRingGestureIntent|convertRingReorderToSlide/);
  assert.match(source, /if \(hit\.index >= 0\) return false/);
  assert.doesNotMatch(wxml, /ring-rotation-guide|ring-center-controls|stringed-gesture-guide/);
  assert.doesNotMatch(wxml, /拖珠换位 · 拖外环旋转|rotateStringedRingStep/);
  assert.doesNotMatch(wxss, /ring-rotation-handle|ring-interaction-status|stringed-gesture-guide/);
});

test('finishing stringing clears loose per-item offsets before rendering the ring', () => {
  const source = fs.readFileSync(
    path.join(root, 'miniprogram/pages/workspace/workspace.js'),
    'utf8'
  );
  const start = source.indexOf('  startStringingPhysics() {');
  const end = source.indexOf('\n  removeItem(e) {', start);
  const method = source.slice(start, end);

  assert.match(method, /dx:\s*0,\s*\n\s*dy:\s*0,/);
  assert.match(source, /completeStringing\(\)[\s\S]*map\(placement => \(\{ \.\.\.placement, dx: 0, dy: 0 \}\)\)/);
});
