const test = require('node:test');
const assert = require('node:assert/strict');

const {
  attachmentFromMaterial,
  beadCapCompatibility,
  beadCapSlotsFromPlacement,
  beadCapRenderMetrics,
  beadCapSprite,
  beadCapTotals,
  isBeadCap
} = require('../../miniprogram/utils/materialAttachments');

function cap(overrides = {}) {
  return {
    id: 'cap-8-gold',
    name: '8mm 金色包珠隔片',
    size: 8,
    price: 2.5,
    image_url: 'https://cdn.example/cap.webp',
    material_params: {
      bead_shape: 'bead_cap',
      placement_mode: 'attached_side',
      string_axis_width_mm: 1.2,
      body_width_mm: 5,
      body_height_mm: 2.4,
      compatible_bead_size_mm: 8,
      compatible_size_tolerance_mm: 0.5
    },
    ...overrides
  };
}

test('bead cap compatibility accepts only matching round threaded hosts', () => {
  assert.equal(isBeadCap(cap()), true);
  assert.equal(beadCapCompatibility(cap(), { size: 8, material_params: { bead_shape: 'round' } }).compatible, true);
  assert.equal(beadCapCompatibility(cap(), { size: 9, material_params: { bead_shape: 'round' } }).compatible, false);
  assert.equal(beadCapCompatibility(cap(), {
    size: 8,
    material_params: {
      bead_shape: 'barrel',
      string_axis_width_mm: 8,
      body_width_mm: 8,
      body_height_mm: 6
    }
  }).compatible, false);
});

test('left and right slots remain independent for single-sided and back-to-back layouts', () => {
  const leftCap = attachmentFromMaterial(cap({ id: 'cap-left' }));
  const rightCap = attachmentFromMaterial(cap({ id: 'cap-right' }));
  const firstHost = beadCapSlotsFromPlacement({ bead_caps: { right: rightCap } });
  const secondHost = beadCapSlotsFromPlacement({ bead_caps: { left: leftCap } });

  assert.equal(firstHost.left, undefined);
  assert.equal(firstHost.right.id, 'cap-right');
  assert.equal(secondHost.left.id, 'cap-left');
  assert.equal(secondHost.right, undefined);

  const totals = beadCapTotals([
    { bead_caps: { right: rightCap } },
    { bead_caps: { left: leftCap } }
  ]);
  assert.equal(totals.count, 2);
  assert.equal(totals.price, 5);
});

test('cap sprites render on the requested side without consuming a host slot', () => {
  const hostSprite = {
    item: { id: 'host', size: 8, material_params: { bead_shape: 'round' } },
    index: 3,
    x: 100,
    y: 80,
    size: 54,
    logicalX: 100,
    logicalY: 80,
    logicalSize: 54,
    attachmentAxisRotation: 0
  };
  const attachment = attachmentFromMaterial(cap());
  const left = beadCapSprite(hostSprite, attachment, 'left');
  const right = beadCapSprite(hostSprite, attachment, 'right');

  assert.ok(left.x < hostSprite.x);
  assert.ok(right.x > hostSprite.x);
  assert.equal(left.hostIndex, 3);
  assert.equal(right.hostIndex, 3);
  assert.equal(left.noShadow, true);
});

test('physical width and height directly control bead cap render dimensions', () => {
  const hostSprite = {
    item: { size: 8, material_params: { bead_shape: 'round' } },
    size: 54
  };
  const small = beadCapRenderMetrics(hostSprite, cap());
  const wide = beadCapRenderMetrics(hostSprite, cap({
    material_params: {
      ...cap().material_params,
      body_width_mm: 7,
      body_height_mm: 4
    }
  }));

  assert.ok(wide.width > small.width);
  assert.ok(wide.height > small.height);
  assert.equal(Number(wide.width.toFixed(2)), 47.25);
  assert.equal(Number(wide.height.toFixed(2)), 27);
});
