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

test('order preview can force a closed ring instead of saved partial drag positions', () => {
  const sequence = sequenceWithPlacements([
    { x: 205, y: 280 },
    { x: 260, y: 360 },
    { x: 350, y: 370 },
    { x: 405, y: 280 },
    { x: 340, y: 205 },
    { x: 250, y: 205 }
  ]);
  const beads = buildDesignPreviewBeads(sequence, [], {
    isLooseMode: false,
    previewForceRing: true,
    workspaceStageCenter: 300
  });
  const distances = beads.map(item => Math.hypot(item.previewX - 280, item.previewY - 280));
  assert.ok(Math.max(...distances) - Math.min(...distances) < 1);
});

test('preview keeps an unbound bead-cap record visible instead of leaving a missing bead', () => {
  const sequence = [
    ...sequenceWithPlacements([{ x: 205, y: 280 }, { x: 395, y: 280 }]),
    {
      id: 'legacy-cap-without-host',
      name: '历史隔珠',
      size: 8,
      attachment_mode: 'bead_cap',
      material_params: { bead_shape: 'bead_cap', placement_mode: 'attached_side' },
      image_url: 'https://cdn.example.com/legacy-cap.webp'
    }
  ];
  const beads = buildDesignPreviewBeads(sequence, [], { previewForceRing: true });
  assert.equal(beads.filter(item => !item.isAttachment).length, 3);
});

test('workspace checkout snapshot keeps the visual fields used by the preview', () => {
  const workspaceSource = fs.readFileSync(path.resolve(
    __dirname,
    '../../miniprogram/pages/workspace/workspace.js'
  ), 'utf8');

  assert.match(
    workspaceSource,
    /rotation:\s*stringedMaterialRotationDeg\(angle, physical\)/
  );
  ['dx', 'dy', 'looseX', 'looseY', 'rotation', 'beadSize'].forEach(field => {
    assert.match(workspaceSource, new RegExp(`${field}: placement\\.${field}`));
  });
});

test('preview uses measured irregular dimensions and string occupancy metadata', () => {
  const sequence = Array.from({ length: 8 }, (_, index) => ({
    id: `irregular-${index}`,
    top: 'accessory',
    size: 12,
    material_params: {
      bead_shape: 'nugget',
      string_axis_width_mm: 5,
      body_width_mm: 12,
      body_height_mm: 8,
      image_string_axis_deg: 0
    },
    image_url: `https://cdn.example.com/irregular-${index}.webp`
  }));
  const beads = buildDesignPreviewBeads(sequence, [], {
    isLooseMode: false,
    wristSize: 16
  });

  assert.equal(beads.length, 8);
  assert.ok(beads.every(bead => bead.previewSize > 52));
  assert.match(beads[0].style, /rotate\(0\.0deg\)/);
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

test('preview overlays single-sided and back-to-back bead caps without adding ring hosts', () => {
  const sequence = sequenceWithPlacements([
    {
      x: 240,
      y: 180,
      bead_caps: {
        right: {
          id: 'cap-a',
          image_url: 'https://cdn.example.com/cap-a.webp',
          material_params: { bead_shape: 'bead_cap', placement_mode: 'attached_side' }
        }
      }
    },
    {
      x: 320,
      y: 180,
      bead_caps: {
        left: {
          id: 'cap-b',
          image_url: 'https://cdn.example.com/cap-b.webp',
          material_params: { bead_shape: 'bead_cap', placement_mode: 'attached_side' }
        }
      }
    }
  ]);
  const preview = buildDesignPreviewBeads(sequence, [], {
    isLooseMode: false,
    workspaceStageCenter: 300
  });
  const hosts = preview.filter(item => !item.isAttachment);
  const caps = preview.filter(item => item.isAttachment);

  assert.equal(hosts.length, 2);
  assert.equal(caps.length, 2);
  assert.ok(caps.every(item => item.previewSize < hosts[0].previewSize));
});
