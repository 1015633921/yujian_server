const test = require('node:test');
const assert = require('node:assert/strict');

const {
  estimateInnerCircumferenceMm,
  expandSequenceToCount,
  recommendBeadCount
} = require('../../miniprogram/utils/braceletSizing');
const { buildFreshWorkspaceDraft } = require('../../miniprogram/utils/workspaceImport');

test('recommendation chooses the closest physical wrist fit instead of always rounding up', () => {
  const source = Array.from({ length: 20 }, (_, index) => `bead-${index}`);
  const targetCount = recommendBeadCount(Array(20).fill(8), 16, {
    allowanceMm: 8,
    minCount: 8,
    maxCount: 40
  });
  const expanded = expandSequenceToCount(source, targetCount);
  const effectiveWristCm = estimateInnerCircumferenceMm(Array(expanded.length).fill(8)) / 10 - 0.8;

  assert.equal(targetCount, 24);
  assert.equal(expanded.length, 24);
  source.forEach(id => assert.ok(expanded.includes(id)));
  assert.ok(Math.abs(effectiveWristCm - 16) <= 0.5);
});

test('community recipe uses the same closest-fit count as the backend', () => {
  const recipe = ['clearQuartz8', 'moonstone8'];
  const targetCount = recommendBeadCount([8, 8], 16, {
    allowanceMm: 8,
    minCount: 8,
    maxCount: 40
  });
  const selected = expandSequenceToCount(recipe, targetCount);
  const effectiveWristCm = estimateInnerCircumferenceMm(Array(selected.length).fill(8)) / 10 - 0.8;

  assert.equal(selected.length, 24);
  assert.ok(Math.abs(effectiveWristCm - 16) <= 0.5);
});

test('recommended count remains stable even when the current sequence is already too long', () => {
  const targetCount = recommendBeadCount(Array(30).fill(8), 16, {
    allowanceMm: 8,
    minCount: 8,
    maxCount: 40
  });

  assert.equal(targetCount, 24);
});

test('new imports start with a fresh design identity and the source title', () => {
  const draft = buildFreshWorkspaceDraft({
    name: '晨光白水晶',
    fallbackName: 'Yustream DIY 手串方案',
    selected: ['clearQuartz8'],
    placements: [{ id: 'clearQuartz8' }],
    wristSize: 16,
    sourceContext: { source: 'community_inspiration', title: '晨光白水晶' }
  });

  assert.equal(draft.designId, '');
  assert.equal(draft.design_id, '');
  assert.equal(draft.name, '晨光白水晶');
  assert.equal(draft.title, '晨光白水晶');
  assert.equal(draft.userId, '');
  assert.deepEqual(draft.selected, ['clearQuartz8']);
  assert.equal(draft.sourceContext.title, '晨光白水晶');
  assert.equal('preview_image' in draft, false);
  assert.equal('cart_item_id' in draft, false);
});
