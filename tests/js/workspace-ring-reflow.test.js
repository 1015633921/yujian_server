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

test('ring reorder reflows every material instead of preserving stale per-item slots', () => {
  const page = loadWorkspacePage();
  const geometry = {
    center: 100,
    radius: 60,
    angles: [-Math.PI / 2, 0, Math.PI / 2],
    beadSizes: [40, 40, 40]
  };
  const source = [
    { id: 'accessory', dx: -28, dy: 17 },
    { id: 'bead-a', dx: 19, dy: -24 },
    { id: 'bead-b', dx: 8, dy: 31 }
  ];
  const instance = Object.assign({}, page, {
    normalizePlacements(selected, placements) {
      return placements.map((placement, index) => ({ ...placement, id: selected[index] }));
    },
    getCachedSelectedMaterials(selected) {
      return selected.map(id => ({ id, size: 8 }));
    },
    getCachedBraceletGeometry() {
      return geometry;
    },
    getMaterialDisplaySize() {
      return 40;
    }
  });

  const placements = instance.rebuildRingPlacementsForVisualSlots(
    ['bead-a', 'accessory', 'bead-b'],
    source,
    0
  );

  assert.deepEqual(
    placements.map(item => [item.dx, item.dy]),
    [[0, 0], [0, 0], [0, 0]]
  );
});

test('ring reorder retains a coherent whole-ring rotation without carrying item offsets', () => {
  const page = loadWorkspacePage();
  const oldGeometry = {
    center: 100,
    radius: 60,
    angles: [-Math.PI / 2, 0, Math.PI / 2]
  };
  const rotation = 0.3;
  const placements = oldGeometry.angles.map(angle => {
    const baseX = oldGeometry.center + Math.cos(angle) * oldGeometry.radius;
    const baseY = oldGeometry.center + Math.sin(angle) * oldGeometry.radius;
    return {
      dx: oldGeometry.center + Math.cos(angle + rotation) * oldGeometry.radius - baseX,
      dy: oldGeometry.center + Math.sin(angle + rotation) * oldGeometry.radius - baseY
    };
  });
  const instance = Object.assign({}, page, { normalizeAngleDelta: page.normalizeAngleDelta });

  assert.ok(Math.abs(instance.getRingRotationDelta(placements, oldGeometry) - rotation) < 0.0001);
});

test('removing several stringed beads reflows every remaining slot without losing whole-ring rotation', () => {
  const page = loadWorkspacePage();
  const ringRotation = 0.48;
  const selected = Array.from({ length: 9 }, (_, index) => `bead-${index}`);
  const ringGeometry = count => {
    const center = 160;
    // A real bracelet recalculates its tangent radius when its bead count
    // changes. Make that change explicit so stale dx/dy values cannot happen
    // to look valid against an unchanged radius.
    const radius = 76 + count * 4;
    return {
      center,
      radius,
      angles: Array.from(
        { length: count },
        (_, index) => -Math.PI / 2 + index * Math.PI * 2 / count
      ),
      beadSizes: Array.from({ length: count }, () => 40),
      materialGeometries: Array.from(
        { length: count },
        () => ({ displaySizeRpx: 40, placementMode: 'threaded' })
      )
    };
  };
  const initialGeometry = ringGeometry(selected.length);
  const placements = initialGeometry.angles.map((angle, index) => {
    const x = initialGeometry.center
      + Math.cos(angle + ringRotation) * initialGeometry.radius;
    const y = initialGeometry.center
      + Math.sin(angle + ringRotation) * initialGeometry.radius;
    return {
      id: selected[index],
      dx: x - (initialGeometry.center + Math.cos(angle) * initialGeometry.radius),
      dy: y - (initialGeometry.center + Math.sin(angle) * initialGeometry.radius),
      looseX: x,
      looseY: y,
      beadSize: 40
    };
  });
  let recalculations = 0;
  const instance = Object.assign({}, page, {
    data: {
      ...page.data,
      isLooseMode: false,
      selected,
      placements
    },
    findMaterialById(id) {
      return { id, size: 8 };
    },
    materialImageCandidates() {
      return [];
    },
    getCachedSelectedMaterials(ids) {
      return ids.map(id => ({ id, size: 8 }));
    },
    getCachedBraceletGeometry(items) {
      return ringGeometry(items.length);
    },
    getMaterialDisplaySize() {
      return 40;
    },
    pushHistory() {},
    recalculate() {
      recalculations += 1;
    },
    setData(updates, callback) {
      this.data = { ...this.data, ...updates };
      if (callback) callback();
    }
  });

  [3, 1, 2].forEach(index => {
    instance.removeItemAt(index);
    const context = instance.getStringedRingContext();
    const slots = instance.getRingVisualSlots(
      context.items,
      context.placements,
      context.geometry
    );
    const radii = slots.map(slot => Math.hypot(
      slot.x - context.geometry.center,
      slot.y - context.geometry.center
    ));

    assert.equal(context.placements.length, context.selected.length);
    assert.deepEqual(context.placements.map(item => item.id), context.selected);
    assert.ok(
      Math.abs(instance.getRingRotationDelta(context.placements, context.geometry) - ringRotation) < 0.0001,
      'the retained offsets should describe one coherent whole-ring rotation'
    );
    assert.ok(
      Math.max(...radii) - Math.min(...radii) < 0.0001,
      'all remaining beads should share one ring radius instead of leaving a gap'
    );
    slots.forEach((slot, slotIndex) => {
      const angle = context.geometry.angles[slotIndex] + ringRotation;
      const expectedX = context.geometry.center + Math.cos(angle) * context.geometry.radius;
      const expectedY = context.geometry.center + Math.sin(angle) * context.geometry.radius;
      assert.ok(Math.abs(radii[slotIndex] - context.geometry.radius) < 0.0001);
      assert.ok(Math.hypot(slot.x - expectedX, slot.y - expectedY) < 0.0001);
    });
  });

  assert.equal(recalculations, 3);
});
