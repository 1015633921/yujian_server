const test = require('node:test');
const assert = require('node:assert/strict');

const { effectiveWristText } = require('../../miniprogram/utils/designSummary');
const { countPlanStatuses, editablePlanPresentation } = require('../../miniprogram/utils/planPresentation');
const {
  CHAKRA_OPTIONS,
  MOOD_PALETTES,
  labelForAssessmentValue,
  labelsForAssessmentValues
} = require('../../miniprogram/utils/assessmentOptions');

test('checkout uses the same effective wrist value as the workspace', () => {
  assert.equal(effectiveWristText({ currentWrist: '16.7', length: '17.5' }), '16.7');
  assert.equal(effectiveWristText({ length: '17.5' }), '16.7');
  assert.equal(effectiveWristText({ currentWrist: '', length: '17.5' }), '16.7');
});

test('automatic drafts are separate from saved plans', () => {
  const draft = editablePlanPresentation('current', {});
  const saved = editablePlanPresentation('saved', { designId: 'design-1' });
  const counts = countPlanStatuses([
    { statusKey: draft.statusKey },
    { statusKey: saved.statusKey },
    { statusKey: 'ordered' }
  ], ['draft', 'saved', 'ordered', 'completed']);

  assert.equal(draft.statusText, '自动草稿');
  assert.equal(saved.statusText, '已保存');
  assert.deepEqual(counts, { all: 3, draft: 1, saved: 1, ordered: 1, completed: 0 });
});

test('privacy values use the same Chinese labels as assessment options', () => {
  assert.equal(labelsForAssessmentValues(['state_expression'], CHAKRA_OPTIONS), '想表达但有点卡住');
  assert.equal(labelForAssessmentValue('sea_salt_blue', MOOD_PALETTES), '海盐蓝白');
});
