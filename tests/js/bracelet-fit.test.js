const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const {
  calculateBraceletFit,
  estimateInnerCircumferenceMm
} = require('../../miniprogram/utils/braceletSizing');
const {
  buildClosedRingLayout,
  tangentDistances
} = require('../../miniprogram/utils/closedRingLayout');

test('the fit model matches the shared server golden vector', () => {
  const fixture = JSON.parse(fs.readFileSync(
    path.resolve(__dirname, '../fixtures/bracelet-sizing-golden.json'), 'utf8'
  ));
  const sample = fixture.cases[0];
  const fit = calculateBraceletFit(sample.items, sample.wrist_size_cm, {
    allowanceMm: sample.allowance_mm,
    toleranceMm: 5,
    minCount: 8,
    maxCount: 40
  });

  assert.equal(fit.modelVersion, fixture.model_version);
  assert.equal(fit.status, sample.expected_status);
  assert.equal(fit.recommendedCount, sample.expected_recommended_count);
  assert.ok(Math.abs(fit.actualInnerMm - sample.expected_inner_mm) < 0.001);
});

test('nested physical dimensions drive irregular material wrist sizing', () => {
  const round = { size: 8 };
  const flatSpacer = {
    top: 'accessory',
    material_params: {
      bead_shape: 'barrel',
      string_axis_width_mm: 1.2,
      body_width_mm: 8,
      body_height_mm: 1.2,
      image_string_axis_deg: 0
    }
  };
  const items = [round, round, round, round, flatSpacer, round, round, round, round, round];
  const effectiveLength = estimateInnerCircumferenceMm(items);

  assert.ok(effectiveLength > 0);
  assert.notEqual(effectiveLength, estimateInnerCircumferenceMm(items.map(item => item.size || 8)));
});

test('closed ring layout recomputes all slots and leaves no start/end gap after removal', () => {
  const full = buildClosedRingLayout({
    beadSizes: Array(25).fill(48),
    spacingSizes: Array(25).fill(48),
    gap: 0.5,
    centerX: 280,
    centerY: 280,
    maxOuterRadius: 250
  });
  const reduced = buildClosedRingLayout({
    beadSizes: Array(24).fill(48),
    spacingSizes: Array(24).fill(48),
    gap: 0.5,
    centerX: 280,
    centerY: 280,
    maxOuterRadius: 250
  });

  assert.ok(Math.abs(reduced.closingAngle - Math.PI * 2) < 1e-8);
  assert.ok(reduced.radius < full.radius);
  const distances = tangentDistances(reduced.spacingSizes, 0.5);
  reduced.points.forEach((point, index) => {
    const next = reduced.points[(index + 1) % reduced.points.length];
    const distance = Math.hypot(point.x - next.x, point.y - next.y);
    assert.ok(Math.abs(distance - distances[index]) < 1e-7);
  });
});
