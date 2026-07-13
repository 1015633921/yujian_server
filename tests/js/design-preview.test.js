const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const {
  buildDesignPreviewBeads,
  buildDesignPreviewGuide
} = require('../../miniprogram/utils/designPreview');

function sequenceWithPlacements(points) {
  return points.map((point, index) => ({
    id: `bead-${index}`,
    name: `珠子${index + 1}`,
    size: 10,
    placement: {
      ...point,
      beadSize: 54,
      image_url: `https://cdn.example.com/bead-${index}.webp`
    }
  }));
}

test('design preview preserves loose sequence placements and hides the circular guide', () => {
  const sequence = sequenceWithPlacements([
    { looseX: 210, looseY: 250, rotation: 8 },
    { looseX: 360, looseY: 205, rotation: -16 },
    { looseX: 300, looseY: 390, rotation: 27 }
  ]);
  const design = { isLooseMode: true, workspaceStageCenter: 300 };
  const beads = buildDesignPreviewBeads(sequence, [], design);
  const guide = buildDesignPreviewGuide(beads, design);

  assert.equal(beads.length, 3);
  assert.notEqual(beads[0].previewX, beads[1].previewX);
  assert.notEqual(beads[1].previewY, beads[2].previewY);
  assert.equal(guide.visible, false);
});

test('stringed preview guide passes through every rendered bead center', () => {
  const center = 300;
  const radius = 128;
  const sequence = sequenceWithPlacements(Array.from({ length: 8 }, (_, index) => {
    const angle = -Math.PI / 2 + index * Math.PI / 4;
    return {
      x: center + Math.cos(angle) * radius,
      y: center + Math.sin(angle) * radius,
      dx: 0,
      dy: 0,
      rotation: angle * 180 / Math.PI
    };
  }));
  const design = { isLooseMode: false, workspaceStageCenter: center };
  const beads = buildDesignPreviewBeads(sequence, [], design);
  const guide = buildDesignPreviewGuide(beads, design);

  assert.equal(guide.visible, true);
  beads.forEach(bead => {
    const distance = Math.sqrt(
      (bead.previewX - guide.centerX) ** 2 + (bead.previewY - guide.centerY) ** 2
    );
    assert.ok(Math.abs(distance - guide.radius) < 0.05);
  });
});

test('stringed preview derives the final workspace rotation from the bead center', () => {
  const center = 300;
  const sequence = sequenceWithPlacements([
    { x: center, y: 170, rotation: 27 },
    { x: 430, y: center, rotation: -41 },
    { x: center, y: 430, rotation: 13 }
  ]);
  const beads = buildDesignPreviewBeads(sequence, [], {
    isLooseMode: false,
    workspaceStageCenter: center
  });

  assert.match(beads[0].style, /rotate\(-90\.0deg\)/);
  assert.match(beads[1].style, /rotate\(0\.0deg\)/);
  assert.match(beads[2].style, /rotate\(90\.0deg\)/);
});

test('workspace checkout snapshot keeps the visual fields used by the preview', () => {
  const workspaceSource = fs.readFileSync(path.resolve(
    __dirname,
    '../../miniprogram/pages/workspace/workspace.js'
  ), 'utf8');

  assert.match(
    workspaceSource,
    /rotation:\s*stringedBeadRotationFromPoint\(visualX, visualY, center\)/
  );
  ['dx', 'dy', 'looseX', 'looseY', 'rotation', 'beadSize'].forEach(field => {
    assert.match(workspaceSource, new RegExp(`${field}: placement\\.${field}`));
  });
});

test('preview keeps transparent irregular materials in their original silhouette', () => {
  const sequence = sequenceWithPlacements([{ x: 300, y: 172, rotation: 32 }]);
  const beads = buildDesignPreviewBeads(sequence, [], {
    isLooseMode: false,
    workspaceStageCenter: 300
  });
  const wxml = fs.readFileSync(path.resolve(
    __dirname,
    '../../miniprogram/components/design-preview/design-preview.wxml'
  ), 'utf8');
  const wxss = fs.readFileSync(path.resolve(
    __dirname,
    '../../miniprogram/components/design-preview/design-preview.wxss'
  ), 'utf8');
  const imageRule = wxss.match(/\.design-preview-bead-image\s*\{([^}]*)\}/);

  assert.match(beads[0].style, /background:transparent/);
  assert.match(wxml, /class="design-preview-bead-image"[^>]+mode="aspectFit"/);
  assert.match(wxml, /wx:else class="design-preview-bead-fallback"/);
  assert.ok(imageRule);
  assert.doesNotMatch(imageRule[1], /border-radius:\s*50%/);
});
