const CHAKRA_OPTIONS = [
  { value: 'state_expression', label: '想表达但有点卡住', desc: '表达感' },
  { value: 'state_soft_heart', label: '关系里容易心软消耗', desc: '关系感' },
  { value: 'state_low_confidence', label: '做决定时不够有底气', desc: '行动力' },
  { value: 'state_unsettled', label: '缺少安全感，心容易飘', desc: '稳定感' },
  { value: 'state_low_inspiration', label: '灵感变少，直觉变钝', desc: '灵感' },
  { value: 'need_grounding', label: '稳定和落地', desc: '稳定感' },
  { value: 'need_flow', label: '流动和创造力', desc: '情绪流动' },
  { value: 'need_action', label: '自信和行动力', desc: '行动力' },
  { value: 'need_acceptance', label: '接纳和关系柔和', desc: '关系感' },
  { value: 'need_clarity', label: '表达和清晰沟通', desc: '表达感' }
];

const MOOD_PALETTES = [
  { value: 'sea_salt_blue', label: '海盐蓝白', desc: '表达 · 清澈', colors: ['#DCEFF2', '#F8F7F2', '#6D8FA3'] },
  { value: 'rose_garden', label: '粉绿花园', desc: '接纳 · 关系', colors: ['#F0B7C3', '#DDEAD7', '#7EA27E'] },
  { value: 'sunlit_gold', label: '金橙日光', desc: '自信 · 行动', colors: ['#F1C75B', '#E9924E', '#FFF1C8'] },
  { value: 'moon_violet', label: '紫白月光', desc: '灵感 · 安静', colors: ['#DDD7EF', '#F7F5F0', '#8177B4'] },
  { value: 'earth_red', label: '红棕大地', desc: '稳定 · 安全', colors: ['#8E3F35', '#B9835A', '#E8D8C7'] },
  { value: 'black_gold', label: '黑金镜面', desc: '边界 · 保护', colors: ['#1F2225', '#C8A95B', '#F5F2EA'] }
];

function labelForAssessmentValue(value, options = [], fallback = '未填写') {
  if (value && typeof value === 'object') {
    return String(value.label || value.name || value.value || value.id || '').trim() || fallback;
  }
  const text = String(value || '').trim();
  if (!text) return fallback;
  const match = options.find(item => String(item.value) === text);
  return match ? match.label : text;
}

function labelsForAssessmentValues(value, options = [], fallback = '未填写') {
  const values = Array.isArray(value) ? value : (value ? [value] : []);
  const labels = values
    .map(item => labelForAssessmentValue(item, options, ''))
    .filter(Boolean);
  return labels.join('、') || fallback;
}

module.exports = {
  CHAKRA_OPTIONS,
  MOOD_PALETTES,
  labelForAssessmentValue,
  labelsForAssessmentValues
};
