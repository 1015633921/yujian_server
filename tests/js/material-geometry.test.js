const test = require('node:test');
const assert = require('node:assert/strict');

const {
  resolveMaterialGeometry,
  stringedMaterialOffset,
  stringedMaterialRotationDeg
} = require('../../miniprogram/utils/materialGeometry');

test('round beads keep diameter-based display and spacing', () => {
  const geometry = resolveMaterialGeometry({
    top: 'bead',
    size: 10,
    material_params: { bead_shape: 'round' }
  });

  assert.equal(geometry.isRound, true);
  assert.equal(geometry.displaySizeRpx, 54);
  assert.equal(geometry.spacingSizeRpx, 54);
  assert.equal(geometry.specComplete, true);
});

test('irregular materials separate visual dimensions from string occupancy', () => {
  const geometry = resolveMaterialGeometry({
    top: 'accessory',
    size: 12,
    material_params: {
      bead_shape: 'nugget',
      string_axis_width_mm: 5,
      body_width_mm: 12,
      body_height_mm: 8
    }
  });

  assert.equal(geometry.isRound, false);
  assert.equal(geometry.displaySizeRpx, 64.8);
  assert.equal(geometry.spacingSizeRpx, 27);
  assert.equal(geometry.collisionWidthRpx, 64.8);
  assert.equal(geometry.collisionHeightRpx, 43.2);
  assert.equal(geometry.specComplete, true);
  assert.equal(geometry.cardSpecText, '12×8mm');
});

test('non-round accessories without measured dimensions fail closed', () => {
  const geometry = resolveMaterialGeometry({
    top: 'accessory',
    size: 0,
    material_params: { bead_shape: 'special' }
  });

  assert.equal(geometry.specComplete, false);
  assert.equal(geometry.specText, '规格待补充');
});

test('single-terminated beads use non-round measured geometry', () => {
  const geometry = resolveMaterialGeometry({
    top: 'accessory',
    size: 12,
    material_params: {
      bead_shape: 'single_terminated',
      string_axis_width_mm: 7.5,
      body_width_mm: 12,
      body_height_mm: 9
    }
  });

  assert.equal(geometry.shape, 'single_terminated');
  assert.equal(geometry.isRound, false);
  assert.equal(geometry.collisionShape, 'rectangle');
  assert.equal(geometry.specComplete, true);
});

test('image string axis controls threaded rotation while charms hang upright', () => {
  const horizontalAxis = resolveMaterialGeometry({
    top: 'accessory',
    size: 12,
    material_params: {
      bead_shape: 'barrel',
      image_string_axis_deg: 0,
      string_axis_width_mm: 12,
      body_width_mm: 12,
      body_height_mm: 6
    }
  });
  const hanging = resolveMaterialGeometry({
    top: 'accessory',
    size: 16,
    material_params: {
      bead_shape: 'charm',
      placement_mode: 'hanging',
      string_axis_width_mm: 3,
      body_width_mm: 12,
      body_height_mm: 16
    }
  });

  assert.equal(stringedMaterialRotationDeg(-Math.PI / 2, horizontalAxis), 0);
  assert.equal(stringedMaterialRotationDeg(Math.PI / 3, hanging), 0);
  assert.deepEqual(stringedMaterialOffset(hanging), { x: 0, y: hanging.displaySizeRpx * 0.34 });
});

test('bead caps are side attachments and require a compatible host size', () => {
  const cap = resolveMaterialGeometry({
    top: 'accessory',
    size: 8,
    material_params: {
      bead_shape: 'bead_cap',
      placement_mode: 'attached_side',
      string_axis_width_mm: 1.2,
      body_width_mm: 5,
      body_height_mm: 2.4,
      compatible_bead_size_mm: 8,
      compatible_size_tolerance_mm: 0.5
    }
  });

  assert.equal(cap.isAttachedSide, true);
  assert.equal(cap.placementMode, 'attached_side');
  assert.equal(cap.compatibleBeadSizeMm, 8);
  assert.equal(cap.specComplete, true);

  const incomplete = resolveMaterialGeometry({
    top: 'accessory',
    material_params: {
      bead_shape: 'bead_cap',
      placement_mode: 'attached_side',
      string_axis_width_mm: 1.2,
      body_width_mm: 5,
      body_height_mm: 2.4
    }
  });
  assert.equal(incomplete.specComplete, false);
});
