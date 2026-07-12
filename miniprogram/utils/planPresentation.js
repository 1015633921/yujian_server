function editablePlanPresentation(source = 'saved', item = {}) {
  const hasSavedIdentity = Boolean(item.designId || item.design_id);
  const isDraft = source === 'current' && !hasSavedIdentity;
  return isDraft
    ? {
        type: 'draft',
        statusKey: 'draft',
        statusText: '自动草稿',
        statusClass: 'draft',
        deleteText: '清除草稿'
      }
    : {
        type: 'saved',
        statusKey: 'saved',
        statusText: '已保存',
        statusClass: 'saved',
        deleteText: '删除'
      };
}

function countPlanStatuses(plans = [], statusKeys = []) {
  return statusKeys.reduce((counts, key) => {
    counts[key] = plans.filter(item => item.statusKey === key).length;
    return counts;
  }, { all: plans.length });
}

module.exports = {
  countPlanStatuses,
  editablePlanPresentation
};
