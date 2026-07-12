const test = require('node:test');
const assert = require('node:assert/strict');

const {
  estimateInnerCircumferenceMm,
  expandSequenceToCount,
  recommendBeadCount
} = require('../../miniprogram/utils/braceletSizing');
const { buildFreshWorkspaceDraft } = require('../../miniprogram/utils/workspaceImport');

test('backend recommendation expands evenly to the requested wrist count', () => {
  const source = Array.from({ length: 20 }, (_, index) => `bead-${index}`);
  const targetCount = recommendBeadCount(Array(20).fill(8), 16, {
    allowanceMm: 8,
    minCount: 8,
    maxCount: 40
  });
  const expanded = expandSequenceToCount(source, targetCount);
  const effectiveWristCm = estimateInnerCircumferenceMm(Array(expanded.length).fill(8)) / 10 - 0.8;

  assert.equal(targetCount, 25);
  assert.equal(expanded.length, 25);
  source.forEach(id => assert.ok(expanded.includes(id)));
  assert.ok(effectiveWristCm >= 16);
});

test('community recipe rounds up so the effective wrist size is never undersized', () => {
  const recipe = ['clearQuartz8', 'moonstone8'];
  const targetCount = recommendBeadCount([8, 8], 16, {
    allowanceMm: 8,
    minCount: 8,
    maxCount: 40
  });
  const selected = expandSequenceToCount(recipe, targetCount);
  const effectiveWristCm = estimateInnerCircumferenceMm(Array(selected.length).fill(8)) / 10 - 0.8;

  assert.equal(selected.length, 25);
  assert.ok(effectiveWristCm >= 16);
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
