const {
  createDIYRecommendation,
  createReportDIYRecommendation,
  getReport,
  getReportBasis,
  getReportPoster
} = require('../../utils/api');
const auth = require('../../utils/auth');
const reportCache = require('../../utils/reportCache');

const ELEMENT_META = {
  木: { key: 'wood', color: '#548B62', softColor: 'rgba(84,139,98,.12)' },
  火: { key: 'fire', color: '#C75B4B', softColor: 'rgba(199,91,75,.12)' },
  土: { key: 'earth', color: '#C89A45', softColor: 'rgba(200,154,69,.14)' },
  金: { key: 'metal', color: '#9B9FA3', softColor: 'rgba(155,159,163,.14)' },
  水: { key: 'water', color: '#4E7893', softColor: 'rgba(78,120,147,.12)' }
};
const ELEMENT_STYLE_GUIDANCE = {
  木: {
    keyword: '清新舒展',
    character: '偏清新、舒展，有生长感',
    focus: '轻盈与生长感',
    colors: '青绿、雾蓝、米白',
    texture: '清透、自然、轻盈',
    structure: '线条舒展、适当留白、疏密有序',
    reduce: '过多同类绿色、过于松散的结构'
  },
  火: {
    keyword: '明亮有活力',
    character: '偏明亮、直接，有行动感',
    focus: '明亮与行动感',
    colors: '暖红、蜜橙、柔金',
    texture: '明亮、温润、有光泽',
    structure: '重点明确、节奏利落、适量点缀',
    reduce: '大面积高饱和暖色、过强视觉对比'
  },
  土: {
    keyword: '沉稳可靠',
    character: '偏沉稳、包容，有分量感',
    focus: '稳定与承托感',
    colors: '米白、浅黄、暖棕',
    texture: '温润、柔和、有质感',
    structure: '圆润线条、重心稳定、排列有序',
    reduce: '大面积黄棕、过密排列与厚重堆叠'
  },
  金: {
    keyword: '利落克制',
    character: '偏利落、克制，有秩序感',
    focus: '清晰与秩序感',
    colors: '白色、银灰、冷调浅色',
    texture: '通透、干净、细腻',
    structure: '轮廓清晰、比例规整、少量留白',
    reduce: '过多冷白灰、过于规整的重复'
  },
  水: {
    keyword: '安静细腻',
    character: '偏安静、细腻，有流动感',
    focus: '柔和与流动感',
    colors: '雾蓝、月光白、浅灰蓝',
    texture: '清透、柔和、有流动光泽',
    structure: '圆润过渡、层次柔和、节奏舒缓',
    reduce: '大面积深色、过度沉静的组合'
  }
};
const COLOR_FAMILY_LABELS = {
  clear: '透明',
  white: '米白',
  gray: '浅灰',
  black: '黑色',
  green: '青绿',
  blue: '雾蓝',
  purple: '柔紫',
  pink: '柔粉',
  red: '暖红',
  orange: '蜜橙',
  yellow: '浅黄',
  gold: '柔金',
  brown: '暖棕',
  earth: '大地色'
};
const TRANSPARENCY_LABELS = {
  transparent: '无色通透',
  semi_transparent: '半透明',
  translucent: '温润通透',
  opaque: '沉稳不透'
};
const TEXTURE_FEATURE_LABELS = {
  clean: '净透',
  cloud: '柔雾',
  mineral_inclusion: '天然包体',
  texture: '天然纹理',
  color_band: '色带层次',
  sparkling: '细闪光泽'
};
const ELEMENT_ORDER = ['木', '火', '土', '金', '水'];
const API_ELEMENT_ORDER = ['金', '木', '水', '火', '土'];
const ELEMENT_NAME_ALIASES = {
  metal: '金',
  wood: '木',
  water: '水',
  fire: '火',
  earth: '土',
  jin: '金',
  mu: '木',
  shui: '水',
  huo: '火',
  tu: '土'
};
const MBTI_DIMENSION_LABELS = {
  I: '安静聚焦',
  E: '开放表达',
  N: '灵感探索',
  S: '具体务实',
  T: '理性清晰',
  F: '柔和共情',
  J: '计划有序',
  P: '弹性自由'
};
const MOOD_COLOR_LABELS = {
  '#DCEFF2': '海盐浅蓝',
  '#F8F7F2': '柔白',
  '#6D8FA3': '灰雾蓝',
  '#F0B7C3': '玫瑰粉',
  '#DDEAD7': '雾感浅绿',
  '#7EA27E': '花园绿',
  '#F1C75B': '日光金',
  '#E9924E': '蜜橙',
  '#FFF1C8': '奶油浅黄',
  '#DDD7EF': '薰衣草紫',
  '#F7F5F0': '月光白',
  '#8177B4': '柔雾紫',
  '#8E3F35': '深砖红',
  '#B9835A': '暖棕',
  '#E8D8C7': '沙雾米',
  '#1F2225': '镜面黑',
  '#C8A95B': '柔金',
  '#F5F2EA': '暖白'
};
const STEPS = [
  { key: 'basic', index: 1, label: '基础', activeClass: 'done' },
  { key: 'wish', index: 2, label: '目标', activeClass: 'done' },
  { key: 'mbti', index: 3, label: '性格', activeClass: 'done' },
  { key: 'state', index: 4, label: '状态', activeClass: 'done' },
  { key: 'palette', index: 5, label: '色彩', activeClass: 'done' },
  { key: 'analysis', index: 6, label: '报告', activeClass: 'active' }
];
const POSTER_WIDTH = 750;
const POSTER_MIN_HEIGHT = 2180;
const POSTER_MAX_HEIGHT = 4096;
const POSTER_MAX_BITMAP_SIDE = 4096;
const WRIST_RULER_MIN = 10;
const WRIST_RULER_MAX = 25;
const WRIST_RULER_STEP = 0.1;
const WRIST_RULER_TICK_RPX = 22;
const ASSESSMENT_RECALCULATE_KEY = 'assessmentRecalculateMode';
const ASSESSMENT_SUPPRESS_AUTO_REPORT_ONCE_KEY = 'assessmentSuppressAutoReportOnce';
const ASSESSMENT_REQUESTED_STEP_KEY = 'assessmentRequestedStep';
const ASSESSMENT_REPORT_SEED_KEY = 'assessmentReportSeed';
const REPORT_BASIS_VIEW_KEY = 'reportBasisView';

const LOWEST_ELEMENT_EFFECT = {
  木: '容易显得偏厚重',
  火: '容易显得不够明快',
  土: '容易显得承托感不足',
  金: '容易显得边界不够清晰',
  水: '容易显得流动感不足'
};

const ADJUSTMENT_ACTIONS = {
  木: '提升轻盈舒展',
  火: '增加明亮活力',
  土: '加强稳定承托',
  金: '建立清晰秩序',
  水: '增加柔和流动'
};

const STEM_ELEMENTS = {
  甲: '木',
  乙: '木',
  丙: '火',
  丁: '火',
  戊: '土',
  己: '土',
  庚: '金',
  辛: '金',
  壬: '水',
  癸: '水'
};

const BAZI_STRENGTH_DISPLAY = {
  身强: { label: '偏强', description: '整体稳定感较明显' },
  偏强: { label: '偏强', description: '整体稳定感较明显' },
  身弱: { label: '偏弱', description: '更适合通过搭配增加承托感' },
  偏弱: { label: '偏弱', description: '更适合通过搭配增加承托感' },
  中和: { label: '较均衡', description: '整体结构相对协调' },
  平和: { label: '较均衡', description: '整体结构相对协调' }
};

function safeText(value, fallback = '') {
  if (value === null || value === undefined) return fallback;
  const text = String(value).trim();
  return text || fallback;
}

function formatReportTimestamp(value) {
  const text = safeText(value);
  if (!text) return '';
  const match = text.match(/^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})/);
  return match ? `${match[1]}-${match[2]}-${match[3]} ${match[4]}:${match[5]}` : text;
}

function uniqueTextValues(values = []) {
  return Array.from(new Set((values || []).map(value => safeText(value)).filter(Boolean)));
}

function normalizeDisplayPercentages(items = []) {
  const total = (items || []).reduce((sum, item) => sum + Math.max(0, Number(item.rawValue) || 0), 0);
  if (total <= 0) return (items || []).map(() => 0);
  const exact = items.map(item => Math.max(0, Number(item.rawValue) || 0) / total * 100);
  const percentages = exact.map(value => Math.floor(value));
  let remaining = 100 - percentages.reduce((sum, value) => sum + value, 0);
  const allocationOrder = exact
    .map((value, index) => ({ index, remainder: value - Math.floor(value) }))
    .sort((a, b) => b.remainder - a.remainder || a.index - b.index);
  for (let cursor = 0; cursor < remaining; cursor += 1) {
    percentages[allocationOrder[cursor % allocationOrder.length].index] += 1;
  }
  return percentages;
}

const DISPLAY_REPLACEMENTS = [
  ['招财进宝/事业腾飞', '事业专注/稳步推进'],
  ['正缘桃花/人际和合', '人际亲和/柔和沟通'],
  ['辟邪防小人/消除焦虑', '安定边界/舒缓压力'],
  ['健康护身/保持专注', '日常平衡/保持专注'],
  ['招财进宝', '稳步推进'],
  ['事业腾飞', '事业专注'],
  ['正缘桃花', '人际亲和'],
  ['辟邪防小人', '安定边界'],
  ['消除焦虑', '舒缓压力'],
  ['健康护身', '日常平衡'],
  ['修复睡眠', '放松休息'],
  ['睡眠修复', '放松休息'],
  ['休息修复', '放松休息'],
  ['改善睡眠', '帮助放松'],
  ['缓解焦虑', '舒缓压力'],
  ['助眠', '睡前放松'],
  ['太阳神经丛', '行动力'],
  ['海底轮', '稳定感'],
  ['脐轮', '情绪流动'],
  ['心轮', '关系感'],
  ['喉轮', '表达感'],
  ['眉心轮', '灵感'],
  ['顶轮', '思考感'],
  ['命盘底色', '风格底色'],
  ['日主与喜用', '基础参考'],
  ['日主', '基础点'],
  ['喜用', '搭配参考'],
  ['排盘', '生成参考'],
  ['命盘', '风格'],
  ['运势', '状态'],
  ['流月', '近期'],
  ['流失点', '留意点'],
  ['待补', '可调和'],
  ['缺失', '偏低'],
  ['补足', '调和'],
  ['五行能量', '五行元素'],
  ['能量分布', '元素比例'],
  ['能量报告', '搭配报告'],
  ['能量画像', '搭配画像'],
  ['能量标签', '搭配标签'],
  ['整体能量', '整体比例'],
  ['核心愿望', '佩戴目标'],
  ['愿望', '目标'],
  ['七脉轮', '状态线索'],
  ['招财', '目标感'],
  ['财运', '目标推进'],
  ['财富', '目标'],
  ['聚财', '积极行动'],
  ['桃花', '亲和'],
  ['正缘', '亲和'],
  ['贵人运', '协作感'],
  ['贵人', '协作'],
  ['辟邪', '安定'],
  ['防小人', '边界感'],
  ['护身', '安定'],
  ['疗愈', '舒缓'],
  ['治疗', '舒缓'],
  ['疗效', '搭配感受'],
  ['功效', '搭配特点'],
  ['上火', '节奏偏急'],
  ['低速修复', '慢节奏'],
  ['慢修复', '慢节奏'],
  ['净化磁场', '整理氛围'],
  ['磁场', '氛围'],
  ['净化', '清爽'],
  ['转运', '积极调整'],
  ['求好运', '积极期待'],
  ['好运', '积极感'],
  ['能量', '状态']
];

function sanitizeDisplayText(value, fallback = '') {
  let text = safeText(value, fallback);
  DISPLAY_REPLACEMENTS.forEach(([from, to]) => {
    text = text.split(from).join(to);
  });
  return text;
}

function softenSeasonalText(value, fallback = '') {
  let text = sanitizeDisplayText(value, fallback);
  const replacements = [
    ['暑火最盛，注意急躁、节奏偏急与过度社交', '近期节奏可能更快，可留意急躁、安排过满或社交消耗'],
    ['暑火最盛', '近期节奏可能更快'],
    ['过度社交', '社交消耗'],
    ['容易', '可能'],
    ['不宜', '可避免']
  ];
  replacements.forEach(([from, to]) => {
    text = text.split(from).join(to);
  });
  if (text.startsWith('注意') && !text.startsWith('注意力')) {
    text = `可留意${text.slice(2)}`;
  }
  return text;
}

function repairMojibakeText(value) {
  const text = safeText(value);
  if (!text) return '';
  const codes = [];
  for (let index = 0; index < text.length; index += 1) {
    const code = text.charCodeAt(index);
    if (code > 255) return text;
    codes.push(`%${code.toString(16).padStart(2, '0')}`);
  }
  try {
    return decodeURIComponent(codes.join(''));
  } catch (error) {
    return text;
  }
}

function normalizeElementName(value) {
  const text = safeText(value);
  if (ELEMENT_META[text]) return text;
  const repaired = repairMojibakeText(text);
  if (ELEMENT_META[repaired]) return repaired;
  const lowered = text.toLowerCase();
  return ELEMENT_NAME_ALIASES[lowered] || '';
}

function applyEnergyValue(target, name, value, options = {}) {
  const element = normalizeElementName(name);
  const numeric = Number(value);
  if (!element || !Number.isFinite(numeric)) return;
  if (options.onlyIfMissing && target[element] !== undefined) return;
  target[element] = Math.max(0, numeric);
}

function normalizeEnergyProfile(report = {}) {
  const normalized = {};
  const profile = report.final_energy_profile || {};
  Object.keys(profile).forEach(name => {
    applyEnergyValue(normalized, name, profile[name]);
  });

  const chart = report.chart || {};
  const values = Array.isArray(chart.values) ? chart.values : [];
  const indicators = Array.isArray(chart.indicator) ? chart.indicator : [];
  indicators.forEach((item, index) => {
    const name = typeof item === 'string' ? item : item && item.name;
    applyEnergyValue(normalized, name, values[index], { onlyIfMissing: true });
  });
  API_ELEMENT_ORDER.forEach((name, index) => {
    applyEnergyValue(normalized, name, values[index], { onlyIfMissing: true });
  });
  return normalized;
}

function drawRoundRect(ctx, x, y, width, height, radius) {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + width - r, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + r);
  ctx.lineTo(x + width, y + height - r);
  ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
  ctx.lineTo(x + r, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function fillRoundRect(ctx, x, y, width, height, radius, color) {
  drawRoundRect(ctx, x, y, width, height, radius);
  ctx.fillStyle = color;
  ctx.fill();
}

function strokeRoundRect(ctx, x, y, width, height, radius, color, lineWidth = 1) {
  drawRoundRect(ctx, x, y, width, height, radius);
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  ctx.stroke();
}

function getWrappedTextLines(ctx, text, maxWidth, maxLines) {
  const chars = safeText(text).split('');
  const limit = Number.isFinite(maxLines) && maxLines > 0 ? maxLines : Infinity;
  const result = [];
  let line = '';
  for (let index = 0; index < chars.length; index += 1) {
    const testLine = line + chars[index];
    const isLast = index === chars.length - 1;
    if (ctx.measureText(testLine).width > maxWidth && line) {
      if (result.length >= limit - 1) {
        const ellipsis = `${line.slice(0, Math.max(0, line.length - 1))}…`;
        result.push(ellipsis);
        return result;
      }
      result.push(line);
      line = chars[index];
    } else {
      line = testLine;
    }
    if (isLast && line) {
      result.push(line);
    }
  }
  return result;
}

function drawWrappedText(ctx, text, x, y, maxWidth, lineHeight, maxLines) {
  const lines = getWrappedTextLines(ctx, text, maxWidth, maxLines);
  let cursorY = y;
  lines.forEach(line => {
    ctx.fillText(line, x, cursorY);
    cursorY += lineHeight;
  });
  return cursorY;
}

function measureWrappedText(ctx, text, maxWidth, lineHeight, maxLines) {
  return getWrappedTextLines(ctx, text, maxWidth, maxLines).length * lineHeight;
}

function fitTextToWidth(ctx, text, maxWidth) {
  const value = safeText(text);
  if (!value || ctx.measureText(value).width <= maxWidth) return value;
  let fitted = value;
  while (fitted.length > 1 && ctx.measureText(`${fitted}…`).width > maxWidth) {
    fitted = fitted.slice(0, -1);
  }
  return `${fitted}…`;
}

function drawWrappedTextTop(ctx, text, x, y, maxWidth, lineHeight, maxLines) {
  const lines = getWrappedTextLines(ctx, text, maxWidth, maxLines);
  let cursorY = y;
  lines.forEach(line => {
    ctx.fillText(line, x, cursorY);
    cursorY += lineHeight;
  });
  return cursorY;
}

function drawElementRing(ctx, elements, cx, cy, radius, lineWidth) {
  let start = -Math.PI / 2;
  const total = elements.reduce((sum, item) => sum + (Number(item.percent) || 0), 0) || 100;
  elements.forEach(item => {
    const sweep = ((Number(item.percent) || 0) / total) * Math.PI * 2;
    ctx.beginPath();
    ctx.arc(cx, cy, radius, start, start + sweep);
    ctx.strokeStyle = item.color;
    ctx.lineWidth = lineWidth;
    ctx.lineCap = 'round';
    ctx.stroke();
    start += sweep;
  });
}

function drawPosterElementRows(ctx, elements, x, y, width) {
  elements.forEach((item, index) => {
    const rowY = y + index * 54;
    ctx.fillStyle = item.color;
    ctx.font = '700 24px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText(item.name, x, rowY + 24);
    fillRoundRect(ctx, x + 58, rowY + 8, width - 132, 16, 8, '#ECE9E2');
    fillRoundRect(ctx, x + 58, rowY + 8, Math.max(18, (width - 132) * ((Number(item.percent) || 0) / 100)), 16, 8, item.color);
    ctx.fillStyle = '#20201F';
    ctx.textAlign = 'right';
    ctx.fillText(`${item.percent}%`, x + width, rowY + 24);
    ctx.textAlign = 'left';
  });
}

function drawPosterTags(ctx, keywords, x, y, maxWidth) {
  let cursorX = x;
  let cursorY = y;
    const tags = Array.isArray(keywords) && keywords.length ? keywords : [{ label: '清透' }, { label: '稳定' }, { label: '调和' }];
    tags.forEach(item => {
    const label = sanitizeDisplayText(item.label, '搭配标签');
    ctx.font = '700 24px "PingFang SC", "Microsoft YaHei", sans-serif';
    const tagWidth = Math.min(210, Math.max(104, ctx.measureText(label).width + 42));
    if (cursorX + tagWidth > x + maxWidth) {
      cursorX = x;
      cursorY += 54;
    }
    fillRoundRect(ctx, cursorX, cursorY, tagWidth, 40, 20, '#F8F6F1');
    strokeRoundRect(ctx, cursorX, cursorY, tagWidth, 40, 20, '#E5E2DC', 1);
    ctx.fillStyle = '#4F5F52';
    ctx.fillText(fitTextToWidth(ctx, label, tagWidth - 42), cursorX + 21, cursorY + 27);
    cursorX += tagWidth + 12;
  });
  return cursorY + 48;
}

function measurePosterTags(ctx, keywords, x, y, maxWidth) {
  let cursorX = x;
  let cursorY = y;
  const tags = Array.isArray(keywords) && keywords.length ? keywords : [{ label: '清透' }, { label: '稳定' }, { label: '调和' }];
  tags.forEach(item => {
    const label = sanitizeDisplayText(item.label, '搭配标签');
    ctx.font = '700 24px "PingFang SC", "Microsoft YaHei", sans-serif';
    const tagWidth = Math.min(210, Math.max(104, ctx.measureText(label).width + 42));
    if (cursorX + tagWidth > x + maxWidth) {
      cursorX = x;
      cursorY += 54;
    }
    cursorX += tagWidth + 12;
  });
  return cursorY + 48 - y;
}

function measurePosterTextCard(ctx, rows, width, options = {}) {
  const paddingX = 32;
  const paddingTop = 30;
  const paddingBottom = 32;
  const contentWidth = width - paddingX * 2;
  const safeRows = rows.filter(item => safeText(item && item.text));
  let height = paddingTop + 36 + 26 + paddingBottom;

  safeRows.forEach((item, index) => {
    if (index > 0) height += 26;
    if (item.label) height += 32;
    ctx.font = '500 22px "PingFang SC", "Microsoft YaHei", sans-serif';
    height += measureWrappedText(ctx, item.text, contentWidth, 34, item.maxLines || options.maxTextLines || 4);
    if (item.meta) {
      ctx.font = '600 20px "PingFang SC", "Microsoft YaHei", sans-serif';
      height += 10 + measureWrappedText(ctx, item.meta, contentWidth, 28, item.metaMaxLines || 2);
    }
  });
  return Math.max(options.minHeight || 160, height);
}

function drawPosterTextCard(ctx, title, rows, x, y, width, options = {}) {
  const paddingX = 32;
  const paddingTop = 30;
  const contentWidth = width - paddingX * 2;
  const safeRows = rows.filter(item => safeText(item && item.text));
  const height = measurePosterTextCard(ctx, rows, width, options);

  fillRoundRect(ctx, x, y, width, height, 28, options.background || '#FFFFFF');
  strokeRoundRect(ctx, x, y, width, height, 28, options.borderColor || '#E5E2DC', 1);

  ctx.fillStyle = '#20201F';
  ctx.font = '800 30px "PingFang SC", "Microsoft YaHei", sans-serif';
  ctx.textBaseline = 'top';
  ctx.fillText(title, x + paddingX, y + paddingTop);

  let cursorY = y + paddingTop + 62;
  safeRows.forEach((item, index) => {
    if (index > 0) {
      cursorY += 26;
      ctx.strokeStyle = 'rgba(32, 32, 31, .07)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x + paddingX, cursorY - 14);
      ctx.lineTo(x + width - paddingX, cursorY - 14);
      ctx.stroke();
    }
    if (item.label) {
      ctx.fillStyle = item.accent || options.accent || '#365C9C';
      ctx.font = '800 22px "PingFang SC", "Microsoft YaHei", sans-serif';
      ctx.fillText(fitTextToWidth(ctx, item.label, contentWidth), x + paddingX, cursorY);
      cursorY += 32;
    }
    ctx.fillStyle = item.color || '#64615B';
    ctx.font = '500 22px "PingFang SC", "Microsoft YaHei", sans-serif';
    cursorY = drawWrappedTextTop(
      ctx,
      item.text,
      x + paddingX,
      cursorY,
      contentWidth,
      34,
      item.maxLines || options.maxTextLines || 4
    );
    if (item.meta) {
      cursorY += 10;
      ctx.fillStyle = 'rgba(32, 32, 31, .45)';
      ctx.font = '600 20px "PingFang SC", "Microsoft YaHei", sans-serif';
      cursorY = drawWrappedTextTop(ctx, item.meta, x + paddingX, cursorY, contentWidth, 28, item.metaMaxLines || 2);
    }
  });

  ctx.textBaseline = 'alphabetic';
  return y + height;
}

Page({
  data: {
    report: null,
    viewReport: null,
    steps: STEPS,
    avatarChar: '',
    showWristModal: false,
    wristInput: '',
    wristRulerValue: '16.0',
    wristRulerTicks: [],
    wristRulerScrollLeft: 0,
    wristRulerTickWidth: 11,
    wristRulerSidePadding: 180,
    wristRulerRangeText: '10.0–25.0cm',
    beadSize: 8,
    beadSizeOptions: [6, 8, 10, 12],
    generating: false,
    posterGenerating: false,
    posterPath: '',
    posterSaving: false,
    showPosterModal: false
  },

  onLoad(options = {}) {
    const reportId = safeText(options.report_id);
    const reportVersion = Number(options.report_version);
    this.requestedReportRef = reportId && Number.isInteger(reportVersion) && reportVersion > 0
      ? { reportId, reportVersion }
      : null;
    this.syncReportFromStorage();
    if (this.requestedReportRef) this.loadRequestedReport();
  },

  onShow() {
    this.syncReportFromStorage();
  },

  syncReportFromStorage() {
    const storedUser = auth.getStoredUser() || {};
    const storedUserId = safeText(storedUser.user_id);
    const requestedRef = this.requestedReportRef || reportCache.getActiveRef(storedUserId);
    const versionedReport = requestedRef
      ? reportCache.loadReport(storedUserId, requestedRef.reportId, requestedRef.reportVersion)
      : null;
    const report = versionedReport
      || (this.requestedReportRef ? null : wx.getStorageSync('energyReport'));
    if (!report) {
      this.posterArtifact = null;
      if (this.data.report) this.setData({ report: null, viewReport: null, posterPath: '', showPosterModal: false });
      return;
    }
    const isVersioned = Boolean(report.report_id && report.report_version);
    const reportUserId = safeText(report.input_summary && report.input_summary.user_id);
    if (!storedUserId || (!isVersioned && (!reportUserId || storedUserId !== reportUserId))) {
      this.posterArtifact = null;
      ['energyReport', 'energyProfile', REPORT_BASIS_VIEW_KEY].forEach(key => wx.removeStorageSync(key));
      if (this.data.report) this.setData({ report: null, viewReport: null, posterPath: '', showPosterModal: false });
      return;
    }
    const current = this.data.report || {};
    const sameReport = isVersioned
      ? safeText(current.report_id) === safeText(report.report_id)
        && Number(current.report_version) === Number(report.report_version)
      : safeText(current.assessment_id) === safeText(report.assessment_id)
        && safeText(current.created_at) === safeText(report.created_at);
    if (sameReport) return;
    this.posterArtifact = null;
    const context = report.report_context || {};
    const inputSummary = report.input_summary || {
      name: context.name_initial || '',
      core_wishes: context.core_wishes || [],
      mbti: (report.mbti_analysis || {}).type || null,
      chakra_answers: context.has_chakra_input ? ['snapshot'] : [],
      mood_palette_id: context.has_mood_input ? 'snapshot' : null
    };
    const savedBeadSize = Number(wx.getStorageSync('recommendedBeadSize'));
    this.setData({
      report,
      viewReport: this.buildViewReport(report),
      avatarChar: safeText(inputSummary.name, '宇').slice(0, 1),
      beadSize: this.data.beadSizeOptions.includes(savedBeadSize) ? savedBeadSize : 8,
      posterPath: '',
      showPosterModal: false
    });
  },

  async loadRequestedReport() {
    const user = auth.getStoredUser() || {};
    const userId = safeText(user.user_id);
    const ref = this.requestedReportRef;
    if (!userId || !ref) return;
    try {
      const report = await getReport(ref.reportId, ref.reportVersion, { silent: true });
      if (!this.requestedReportRef
        || this.requestedReportRef.reportId !== ref.reportId
        || this.requestedReportRef.reportVersion !== ref.reportVersion) return;
      reportCache.saveReport(userId, report);
      this.syncReportFromStorage();
    } catch (error) {
      if (error && error.statusCode === 409) reportCache.removeReport(userId, ref.reportId, ref.reportVersion);
      wx.showToast({ title: error.message || '报告加载失败', icon: 'none' });
    }
  },

  onUnload() {
    if (this.skipSuppressAssessmentAutoReport) return;
    const pages = getCurrentPages();
    const previousPage = pages && pages.length > 1 ? pages[pages.length - 2] : null;
    if (previousPage && previousPage.route === 'pages/assessment/assessment') {
      wx.setStorageSync(ASSESSMENT_SUPPRESS_AUTO_REPORT_ONCE_KEY, true);
    }
  },

  buildViewReport(report) {
    const profile = normalizeEnergyProfile(report);
    const projection = report.report_projection || {};
    const projectionByName = {};
    (projection.elements || []).forEach(item => { projectionByName[item.name] = item; });
    const rawElements = ELEMENT_ORDER.map(name => {
      const projected = projectionByName[name] || {};
      return {
        ...ELEMENT_META[name],
        name,
        rawValue: Math.max(0, Number(projected.raw_value !== undefined ? projected.raw_value : profile[name]) || 0),
        serverPercent: Number(projected.percent),
        serverRank: Number(projected.rank)
      };
    });
    const hasServerPercentages = rawElements.every(item => Number.isFinite(item.serverPercent))
      && rawElements.reduce((sum, item) => sum + item.serverPercent, 0) === 100;
    const displayPercentages = hasServerPercentages
      ? rawElements.map(item => item.serverPercent)
      : normalizeDisplayPercentages(rawElements);
    const elements = rawElements.map((item, index) => {
      const percent = displayPercentages[index];
      return {
        ...item,
        value: item.rawValue.toFixed(2),
        percent,
        width: `${Math.min(100, percent)}%`
      };
    });
    const score = this.normalizeScore(
      projection.balance && projection.balance.score !== undefined
        ? projection.balance.score
        : report.interpretation && report.interpretation.balance_index
    );
    const sortedElements = elements.slice().sort((a, b) => {
      if (Number.isFinite(a.serverRank) && Number.isFinite(b.serverRank)) return a.serverRank - b.serverRank;
      return b.percent - a.percent || ELEMENT_ORDER.indexOf(a.name) - ELEMENT_ORDER.indexOf(b.name);
    });
    const styleAnswer = this.buildStyleAnswer(report, sortedElements);
    const context = report.report_context || {};
    const inputSummary = report.input_summary || {
      name: context.name_initial || '',
      core_wishes: context.core_wishes || [],
      mbti: (report.mbti_analysis || {}).type || null,
      chakra_answers: context.has_chakra_input ? ['snapshot'] : [],
      mood_palette_id: context.has_mood_input ? 'snapshot' : null
    };
    const chakraAnalysis = report.chakra_analysis || {};
    const moodAnalysis = report.mood_analysis || {};
    const mbti = this.buildMbtiView(report);
    const hasChakraInput = Boolean(
      (Array.isArray(inputSummary.chakra_answers) && inputSummary.chakra_answers.length)
      || (chakraAnalysis.primary_chakra && chakraAnalysis.primary_chakra !== 'none')
    );
    const hasMoodInput = Boolean(inputSummary.mood_palette_id || moodAnalysis.palette_id);
    const solarTime = report.solar_time || {};
    return {
      assessmentId: safeText(report.assessment_id),
      createdAt: safeText(report.created_at),
      generatedAtText: formatReportTimestamp(report.created_at),
      title: sanitizeDisplayText((report.interpretation && report.interpretation.headline) || '你的元素比例参考已生成'),
      mbti,
      wish: this.buildWishText(inputSummary),
      summary: this.buildSummary(report),
      strongest: report.strongest_element,
      weakest: report.weakest_element,
      balanceIndex: score,
      score,
      statusText: safeText(projection.balance && projection.balance.label, this.scoreStatus(score)),
      balanceExplanation: this.buildBalanceExplanation(score, sortedElements),
      balanceStrategyNote: '调节策略由元素关系综合判断，不等同于简单补足最低元素。',
      styleAnswer,
      keyElements: styleAnswer.keyElements,
      trueSolarTime: report.calibration_status === 'applied' ? (solarTime.true_solar_time || '') : '',
      trueSolarTimeLabel: report.calibration_status === 'applied' && solarTime.true_solar_time ? '校准后时间' : '未完成地点校准',
      hasTrueSolarTime: report.calibration_status === 'applied' && Boolean(solarTime.true_solar_time),
      trueSolarTimeDescription: report.calibration_status === 'applied' && solarTime.true_solar_time
        ? '按出生地点与日期校准'
        : '当前地点不在已验证坐标数据中，本次未显示校准时间',
      keywords: this.buildKeywordTags(report.energy_keywords),
      seasonal: this.buildSeasonalEnergy(report.seasonal_energy, report),
      bazi: this.buildBaziView(report.bazi_basis || {}),
      chakra: this.buildChakraView(report.chakra_analysis || {}),
      mood: this.buildMoodView(report.mood_analysis || {}),
      zodiac: this.buildZodiacView(report.zodiac_analysis || {}),
      hasMbtiInput: mbti.selected,
      hasChakraInput,
      hasMoodInput,
      hasLiveInput: hasChakraInput || hasMoodInput,
      needsMoreInput: !hasChakraInput || !hasMoodInput,
      missingInputText: this.buildMissingInputText(hasChakraInput, hasMoodInput),
      recommendationStrategy: sanitizeDisplayText(report.recommendation_strategy || ''),
      recommendationReasons: this.buildRecommendationReasons(report, elements, mbti),
      elements,
      ringGradient: this.buildRingGradient(elements)
    };
  },

  normalizeScore(value) {
    const score = Number(value);
    if (!Number.isFinite(score)) return 72;
    return Math.max(0, Math.min(100, Math.round(score)));
  },

  scoreStatus(score) {
    if (score >= 85) return '分布接近';
    if (score >= 70) return '轻微侧重';
    if (score >= 55) return '侧重明显';
    return '倾向明显';
  },

  showBalanceIndexInfo() {
    wx.showModal({
      title: '元素分布均衡度说明',
      content: '均衡度仅表示五种元素的分布差异。数值越低，代表元素越集中；数值越高，代表分布越接近。它不代表性格、运势、健康或方案质量的好坏。调节策略会综合元素关系判断，不等同于简单补足最低元素。',
      showCancel: false,
      confirmText: '知道了'
    });
  },

  buildStyleAnswer(report = {}, sortedElements = []) {
    const primary = sortedElements[0] || { name: '土', percent: 0, ...ELEMENT_META.土 };
    const secondary = sortedElements[1] || primary;
    const lowest = sortedElements[sortedElements.length - 1] || primary;
    const primaryGuide = ELEMENT_STYLE_GUIDANCE[primary.name] || ELEMENT_STYLE_GUIDANCE.土;
    const rawUsefulElements = Array.isArray(report.useful_elements) && report.useful_elements.length
      ? report.useful_elements
      : ((report.bazi_basis && Array.isArray(report.bazi_basis.useful_elements))
        ? report.bazi_basis.useful_elements
        : []);
    const usefulElements = uniqueTextValues(rawUsefulElements.map(normalizeElementName)).filter(name => ELEMENT_META[name]);
    const recommendedElements = usefulElements.length ? usefulElements : [lowest.name];
    const recommendedElement = recommendedElements[0];
    const recommendedGuide = ELEMENT_STYLE_GUIDANCE[recommendedElement] || ELEMENT_STYLE_GUIDANCE[lowest.name] || ELEMENT_STYLE_GUIDANCE.木;
    const plan = report.bracelet_plan || {};
    const planItems = Array.isArray(plan.items) && plan.items.length
      ? plan.items.filter(Boolean)
      : [report.primary_crystal, ...(Array.isArray(report.supporting_crystals) ? report.supporting_crystals : [])].filter(Boolean);
    const materialNames = uniqueTextValues(planItems.map(item => item.name));
    const colorLabels = uniqueTextValues(planItems.reduce((values, item) => values.concat(
      Array.isArray(item.color_families)
        ? item.color_families
          .filter(color => color !== 'clear')
          .map(color => COLOR_FAMILY_LABELS[color] || color)
        : []
    ), [])).slice(0, 4);
    const textureLabels = uniqueTextValues(planItems.reduce((values, item) => {
      const params = item.material_params || {};
      const itemValues = [TRANSPARENCY_LABELS[params.transparency_level]];
      if (Array.isArray(item.color_families) && item.color_families.includes('clear')) {
        itemValues.push('无色通透');
      }
      (Array.isArray(params.texture_features) ? params.texture_features : []).forEach(feature => {
        itemValues.push(TEXTURE_FEATURE_LABELS[feature] || '天然纹理');
      });
      return values.concat(itemValues);
    }, [])).slice(0, 4);
    const hasPlan = materialNames.length > 0;
    const recommendedElementsText = recommendedElements.join(' / ');
    const adjustmentRoles = usefulElements.length
      ? ['主要调整', '辅助调整', '少量点缀']
      : ['建议元素'];
    const adjustmentElements = recommendedElements.slice(0, 3).map((name, index) => {
      const guidance = ELEMENT_STYLE_GUIDANCE[name] || ELEMENT_STYLE_GUIDANCE.木;
      return {
        name,
        role: adjustmentRoles[index] || '辅助调整',
        focus: guidance.focus,
        description: `增加${guidance.focus}`,
        color: (ELEMENT_META[name] || {}).color || 'var(--yu-color-text-regular)'
      };
    });
    const strategySummary = this.buildAdjustmentSummary(adjustmentElements);
    const strategyOrder = this.buildAdjustmentOrder(adjustmentElements);
    const summaryLead = `${primary.name}元素占比较高，整体${primaryGuide.keyword}；${lowest.name}元素相对较低，${LOWEST_ELEMENT_EFFECT[lowest.name] || '需要适度调和'}。`;
    const summaryAdvice = `建议${strategySummary}。`;
    return {
      adviceTitle: hasPlan ? '你的真实方案建议' : '你的元素风格建议',
      headline: `${primaryGuide.keyword}，适合加入${recommendedGuide.focus}`,
      summary: `${summaryLead}${summaryAdvice}`,
      summaryLead,
      summaryAdvice,
      keyElements: [
        this.buildKeyElement('主导元素', primary),
        this.buildKeyElement('次高元素', secondary),
        this.buildKeyElement('最低元素', lowest)
      ],
      recommendedElementsText,
      adjustmentElements,
      recommendationBasisLabel: usefulElements.length ? '搭配建议参考' : '比例调和参考',
      advice: [
        { label: '推荐色彩', value: colorLabels.length ? colorLabels.join('、') : recommendedGuide.colors, tone: 'color' },
        { label: '推荐质感', value: textureLabels.length ? textureLabels.join('、') : recommendedGuide.texture, tone: 'texture' },
        { label: '结构方向', value: safeText(plan.pattern, recommendedGuide.structure), tone: 'structure' },
        {
          label: '尽量避免',
          value: primaryGuide.reduce,
          tone: 'caution'
        }
      ],
      evidence: `推荐顺序由元素关系与佩戴目标综合得出：${strategyOrder}，并非简单补足占比最低的元素。`,
      source: hasPlan ? 'recommendation' : 'element-fallback',
      recommendationSource: usefulElements.length ? 'backend' : 'ratio-fallback',
      materialNames,
      colorLabels,
      textureLabels
    };
  },

  buildAdjustmentSummary(elements = []) {
    if (!elements.length) return '围绕整体比例做温和调整';
    const [primary, secondary, accent] = elements;
    const parts = [`以${primary.name}${ADJUSTMENT_ACTIONS[primary.name] || primary.description}`];
    if (secondary) parts.push(`以${secondary.name}${ADJUSTMENT_ACTIONS[secondary.name] || secondary.description}`);
    if (accent) parts.push(`再用少量${accent.name}${ADJUSTMENT_ACTIONS[accent.name] || accent.description}`);
    return parts.join('，');
  },

  buildAdjustmentOrder(elements = []) {
    if (!elements.length) return '围绕整体比例温和调整';
    if (elements.length === 1) return `参考${elements[0].name}元素`;
    if (elements.length === 2) return `以${elements[0].name}为主、${elements[1].name}为辅`;
    return `以${elements[0].name}为主、${elements[1].name}为辅、${elements[2].name}作少量点缀`;
  },

  buildKeyElement(label, element = {}) {
    const percent = Math.max(0, Math.min(100, Math.round(Number(element.percent) || 0)));
    let status = '适中';
    if (percent >= 25) status = '偏高';
    if (percent <= 15) status = '偏低';
    return {
      label,
      name: safeText(element.name, '未定'),
      percent,
      status,
      value: `${safeText(element.name, '未定')} ${percent}%`,
      color: element.color || 'var(--yu-color-text-regular)'
    };
  },

  buildBalanceExplanation(score, sortedElements = []) {
    if (score >= 85) return '五种元素分布较接近，搭配时可优先保持整体协调。';
    if (score >= 70) return '五种元素略有侧重，搭配时做少量调和即可。';
    if (score >= 55) return '五种元素已有明显侧重，搭配会通过色彩、材质和结构适度调和。';
    return '五种元素分布差异较大，搭配会重点通过色彩、材质和结构进行调和。';
  },

  buildMissingInputText(hasChakraInput, hasMoodInput) {
    if (!hasChakraInput && !hasMoodInput) return '尚未补充当下状态和直觉色彩，当前建议按中性信息生成。';
    if (!hasChakraInput) return '尚未补充当下状态，当前建议按中性状态生成。';
    if (!hasMoodInput) return '尚未补充直觉色彩，当前建议未额外偏向某组颜色。';
    return '';
  },

  buildWishText(inputSummary) {
    const wishes = inputSummary.core_wishes || (inputSummary.core_wish ? [inputSummary.core_wish] : []);
    return wishes.length ? wishes.map(item => sanitizeDisplayText(item)).join(' / ') : '未填写目标';
  },

  buildSummary(report) {
    const interpretation = report.interpretation || {};
    const strongest = interpretation.strongest || `${report.strongest_element || '优势'}元素倾向较为鲜明。`;
    const weakest = interpretation.weakest || `${report.weakest_element || '可调和'}元素适合慢慢调和。`;
    return sanitizeDisplayText(`${strongest}${weakest}`);
  },

  buildKeywordTags(keywords) {
    const list = Array.isArray(keywords) ? keywords : [];
    return list.map(item => {
      if (typeof item === 'string') return { label: sanitizeDisplayText(item), source: '搭配标签' };
      const source = sanitizeDisplayText(item.source || '搭配标签');
      const poeticLabel = sanitizeDisplayText(item.label || '');
      const element = normalizeElementName(item.element);
      const guidance = ELEMENT_STYLE_GUIDANCE[element];
      const label = guidance
        ? (source.includes('调和') ? `增加${guidance.focus}` : guidance.keyword)
        : poeticLabel;
      return {
        label,
        poeticLabel: poeticLabel && poeticLabel !== label ? poeticLabel : '',
        source,
        element
      };
    }).filter(item => item.label);
  },

  openReportBasis() {
    if (!this.data.viewReport) return;
    const report = this.data.report || {};
    if (report.report_id && report.report_version) {
      wx.navigateTo({
        url: `/pages/report-basis/report-basis?report_id=${encodeURIComponent(report.report_id)}&report_version=${report.report_version}`
      });
      return;
    }
    wx.setStorageSync(REPORT_BASIS_VIEW_KEY, {
      assessmentId: safeText(report.assessment_id),
      createdAt: safeText(report.created_at),
      viewReport: this.data.viewReport
    });
    wx.navigateTo({ url: '/pages/report-basis/report-basis' });
  },

  buildSeasonalEnergy(seasonal, report) {
    if (seasonal && seasonal.summary) {
      return {
        ...seasonal,
        title: sanitizeDisplayText(seasonal.title || '近期状态提示'),
        period: sanitizeDisplayText(seasonal.period || '近期参考'),
        seasonal_copy: softenSeasonalText(seasonal.seasonal_copy || ''),
        notice: softenSeasonalText(seasonal.notice || ''),
        drain_point: softenSeasonalText(seasonal.drain_point || ''),
        suggestion: softenSeasonalText(seasonal.suggestion || ''),
        summary: softenSeasonalText(seasonal.summary || '')
      };
    }
    const strongest = report.strongest_element || '优势';
    const weakest = report.weakest_element || '可调和';
    return {
      title: '近期状态提示',
      period: '近期参考',
      seasonal_element: strongest,
      seasonal_copy: '当下适合观察自己的状态节奏。',
      notice: `你的${strongest}元素倾向较明显。`,
      drain_point: `${weakest}元素适合慢慢调和，不宜一次调整太多。`,
      suggestion: '保持规律作息，把注意力放回最重要的一件事。',
      summary: `你的${strongest}元素倾向较明显，${weakest}元素适合慢慢调和。保持规律作息，把注意力放回最重要的一件事。`
    };
  },

  buildBaziView(bazi) {
    const pillars = bazi.pillars || {};
    const useful = Array.isArray(bazi.useful_elements) ? bazi.useful_elements.join(' / ') : '';
    const rawDayMaster = safeText(bazi.day_master);
    const dayMasterStem = rawDayMaster.slice(0, 1);
    const dayMasterElement = STEM_ELEMENTS[dayMasterStem] || '';
    const professionalStrength = sanitizeDisplayText(bazi.day_master_strength || '');
    const strengthDisplay = BAZI_STRENGTH_DISPLAY[professionalStrength] || {
      label: professionalStrength || '已生成',
      description: professionalStrength ? '作为基础结构的专业参考' : '已形成基础结构参考'
    };
    return {
      pillarsText: [pillars.year, pillars.month, pillars.day, pillars.time].filter(Boolean).join(' · '),
      dayMaster: rawDayMaster ? `${dayMasterStem}${dayMasterElement}` : '',
      dayMasterDescription: dayMasterElement ? `以${dayMasterElement}元素作为基础结构参考` : '用于形成基础结构参考',
      strength: strengthDisplay.label,
      strengthDescription: strengthDisplay.description,
      professionalStrength,
      usefulText: useful,
      strategy: sanitizeDisplayText(bazi.strategy || '')
    };
  },

  buildChakraView(chakra) {
    const keywords = Array.isArray(chakra.keywords) ? chakra.keywords.join(' / ') : '';
    return {
      name: chakra.primary_chakra_name || '未选择',
      keywords,
      summary: sanitizeDisplayText(chakra.summary || '未选择当下状态，系统按中性状态参与计算。'),
      colors: Array.isArray(chakra.colors) ? chakra.colors : []
    };
  },

  buildMoodView(mood) {
    const name = mood.name || '未选择';
    const colors = Array.isArray(mood.colors) ? mood.colors : [];
    return {
      name,
      subtitle: mood.subtitle || '未选择直觉色彩',
      summary: sanitizeDisplayText(mood.summary || '未选择色彩时，系统不额外偏向某一组情绪色。'),
      colors,
      colorSwatches: colors.map((value, index) => ({
        id: `${index}-${value}`,
        value,
        label: MOOD_COLOR_LABELS[safeText(value).toUpperCase()] || `${name}配色 ${index + 1}`
      }))
    };
  },

  buildMbtiView(report = {}) {
    const inputSummary = report.input_summary || {};
    const analysis = report.mbti_analysis || {};
    const type = safeText(analysis.type || inputSummary.mbti).toUpperCase();
    const selected = Boolean(type && /^[IE][NS][TF][JP]$/.test(type));
    if (!selected) {
      return {
        selected: false,
        type: '',
        weight: 8,
        keywords: [],
        topElements: [],
        topElementsText: '',
        preference: '',
        summary: '未填写 MBTI，本次不加入性格偏好方向。',
        influence: 'MBTI 只作为搭配偏好辅助，不单独决定元素结论或推荐结果。'
      };
    }

    const mbtiProfile = (report.energy_breakdown && report.energy_breakdown.mbti) || {};
    const fallbackElements = Object.keys(mbtiProfile)
      .filter(element => ELEMENT_META[element])
      .sort((a, b) => (Number(mbtiProfile[b]) || 0) - (Number(mbtiProfile[a]) || 0))
      .slice(0, 2);
    const topElements = uniqueTextValues(
      Array.isArray(analysis.top_elements) && analysis.top_elements.length
        ? analysis.top_elements
        : fallbackElements
    ).slice(0, 2);
    const keywords = uniqueTextValues(
      Array.isArray(analysis.keywords) && analysis.keywords.length
        ? analysis.keywords
        : type.split('').map(letter => MBTI_DIMENSION_LABELS[letter])
    );
    const fallbackPreference = topElements
      .map(element => (ELEMENT_STYLE_GUIDANCE[element] || {}).keyword)
      .filter(Boolean)
      .join('、');
    return {
      selected: true,
      type,
      weight: Number(analysis.weight) || 8,
      keywords,
      topElements,
      topElementsText: topElements.join(' / '),
      preference: sanitizeDisplayText(analysis.preference || fallbackPreference),
      summary: sanitizeDisplayText(
        analysis.summary
        || `${type} 的偏好线索更接近${keywords.join('、')}，搭配上可参考${fallbackPreference}的表达。`
      ),
      influence: '用于微调材质气质、排列偏好与推荐排序，不单独决定元素结论或最终方案。'
    };
  },

  buildZodiacView(zodiac) {
    const keywords = Array.isArray(zodiac.keywords)
      ? zodiac.keywords
      : (Array.isArray(zodiac.traits) ? zodiac.traits : []);
    return {
      name: zodiac.name || '',
      englishName: zodiac.english_name || '',
      dateRange: zodiac.date_range || '',
      element: zodiac.element || '',
      modality: zodiac.modality || '',
      keywords,
      keywordText: keywords.join(' / '),
      summary: sanitizeDisplayText(zodiac.summary || ''),
      wuxingHint: sanitizeDisplayText(zodiac.wuxing_hint || ''),
      integration: sanitizeDisplayText(zodiac.integration || ''),
      suggestion: sanitizeDisplayText(zodiac.suggestion || '')
    };
  },

  buildRecommendationReasons(report, elements, mbtiView) {
    const inputSummary = report.input_summary || {};
    const wishes = inputSummary.core_wishes || (inputSummary.core_wish ? [inputSummary.core_wish] : []);
    const bazi = report.bazi_basis || {};
    const usefulElements = Array.isArray(bazi.useful_elements) ? bazi.useful_elements.filter(Boolean) : [];
    const strategy = safeText(bazi.strategy || report.recommendation_strategy);
    const strongest = safeText(report.strongest_element, '优势');
    const weakest = safeText(report.weakest_element, '可调和');
    const chakra = report.chakra_analysis || {};
    const mood = report.mood_analysis || {};
    const mbti = mbtiView || this.buildMbtiView(report);
    const chakraName = sanitizeDisplayText(chakra.primary_chakra_name || '');
    const moodName = sanitizeDisplayText(mood.name || '');
    const topElements = (elements || [])
      .slice()
      .sort((a, b) => (Number(b.percent) || 0) - (Number(a.percent) || 0))
      .slice(0, 2)
      .map(item => item.name)
      .filter(Boolean);
    const usefulText = usefulElements.length ? usefulElements.join(' / ') : weakest;
    const baseDesc = strategy
      || `当前${strongest}元素倾向较明显，${usefulText}适合温柔调和，推荐会优先选择能让整体比例更平衡的材料。`;
    const wishDesc = wishes.length
      ? `你选择了「${wishes.slice(0, 2).map(item => sanitizeDisplayText(item)).join('、')}」，材料筛选会更偏向这个佩戴目标和场景。`
      : '未填写目标时，系统会先以元素比例和佩戴舒适度作为主要推荐依据。';
    const stateParts = [
      chakraName && chakraName !== '未选择' ? `状态线索偏向「${chakraName}」` : '',
      moodName && moodName !== '未选择' ? `直觉色彩选择「${moodName}」` : ''
    ].filter(Boolean);
    const stateDesc = stateParts.length
      ? `${stateParts.join('，')}，会影响辅助珠的颜色、寓意标签和排序权重。`
      : '尚未补充当下状态和直觉色彩，本次方案按中性信息生成，不额外偏向某一类颜色。';
    const preferenceDesc = mbti.selected
      ? `${mbti.type} 以 ${mbti.weight}/100 的偏好权重参与，主要微调材质气质和推荐排序。${stateDesc}`
      : stateDesc;
    const preferenceMeta = [
      mbti.selected ? `MBTI：${mbti.type}${mbti.topElementsText ? ` · ${mbti.topElementsText}` : ''}` : '',
      stateParts.length ? '状态线索 / 直觉色彩' : ''
    ].filter(Boolean).join(' · ');

    return [
      {
        index: '01',
        title: '风格与元素',
        desc: sanitizeDisplayText(baseDesc),
        meta: topElements.length ? `主要参考：${topElements.join(' / ')}` : '主要参考：元素比例'
      },
      {
        index: '02',
        title: '目标与场景',
        desc: wishDesc,
        meta: wishes.length ? `目标：${wishes.slice(0, 3).map(item => sanitizeDisplayText(item)).join(' / ')}` : '目标：未填写'
      },
      {
        index: '03',
        title: mbti.selected ? '性格与当下状态' : '当下状态',
        desc: preferenceDesc,
        meta: preferenceMeta || '当前按中性信息处理'
      }
    ];
  },

  buildRingGradient(elements) {
    let cursor = 0;
    const segments = elements.map(item => {
      const start = cursor;
      const end = cursor + (item.percent / 100) * 360;
      cursor = end;
      return `${item.color} ${start.toFixed(1)}deg ${end.toFixed(1)}deg`;
    });
    if (cursor < 360) {
      segments.push(`#ECE9E2 ${cursor.toFixed(1)}deg 360deg`);
    }
    return `conic-gradient(${segments.join(', ')})`;
  },

  openWristModal() {
    const savedWrist = Number(wx.getStorageSync('recommendedWristSize')) || 16;
    const wristSize = this.normalizeWristValue(savedWrist);
    const display = this.formatWristValue(wristSize);
    this.setData({
      showWristModal: true,
      wristInput: display,
      wristRulerValue: display
    });
    wx.nextTick(() => this.prepareWristRuler(wristSize));
  },

  closeWristModal() {
    if (!this.data.generating) this.setData({ showWristModal: false });
  },

  prepareWristRuler(value = 16) {
    const tickWidth = this.getWristTickWidthPx();
    const viewportWidth = this.getWristRulerViewportWidth();
    const sidePadding = Math.max(0, Math.round((viewportWidth - tickWidth) / 2));
    const wristValue = this.normalizeWristValue(value);
    const display = this.formatWristValue(wristValue);
    this.wristRulerTickWidthPx = tickWidth;
    this.wristRulerLastDisplay = display;
    this.setData({
      wristRulerTicks: this.buildWristRulerTicks(),
      wristRulerTickWidth: tickWidth,
      wristRulerSidePadding: sidePadding,
      wristRulerValue: display,
      wristInput: display,
      wristRulerScrollLeft: this.wristValueToScrollLeft(wristValue, tickWidth)
    });
  },

  getWindowWidthPx() {
    try {
      const info = wx.getWindowInfo ? wx.getWindowInfo() : wx.getSystemInfoSync();
      return Number(info && info.windowWidth) || 375;
    } catch (error) {
      return 375;
    }
  },

  getWristTickWidthPx() {
    const windowWidth = this.getWindowWidthPx();
    return Math.max(8, Math.round(WRIST_RULER_TICK_RPX * windowWidth / 750 * 10) / 10);
  },

  getWristRulerViewportWidth() {
    const windowWidth = this.getWindowWidthPx();
    const horizontalPaddingPx = 60 * windowWidth / 750;
    return Math.max(240, windowWidth - horizontalPaddingPx);
  },

  buildWristRulerTicks() {
    const total = Math.round((WRIST_RULER_MAX - WRIST_RULER_MIN) / WRIST_RULER_STEP);
    return Array.from({ length: total + 1 }).map((_, index) => {
      const value = this.normalizeWristValue(WRIST_RULER_MIN + index * WRIST_RULER_STEP);
      const isMajor = index % 10 === 0;
      const isMid = index % 5 === 0;
      return {
        index,
        value,
        label: isMajor ? String(Math.round(value)) : '',
        className: isMajor ? 'major' : (isMid ? 'middle' : 'minor')
      };
    });
  },

  normalizeWristValue(value) {
    const numeric = Number(value) || 16;
    const clamped = Math.max(WRIST_RULER_MIN, Math.min(WRIST_RULER_MAX, numeric));
    return Math.round(clamped * 10) / 10;
  },

  formatWristValue(value) {
    return this.normalizeWristValue(value).toFixed(1);
  },

  wristValueToScrollLeft(value, tickWidth = this.wristRulerTickWidthPx || this.getWristTickWidthPx()) {
    return Math.round((this.normalizeWristValue(value) - WRIST_RULER_MIN) * 10 * tickWidth);
  },

  scrollLeftToWristValue(scrollLeft) {
    const tickWidth = this.wristRulerTickWidthPx || this.getWristTickWidthPx();
    const maxIndex = Math.round((WRIST_RULER_MAX - WRIST_RULER_MIN) * 10);
    const index = Math.max(0, Math.min(maxIndex, Math.round((Number(scrollLeft) || 0) / tickWidth)));
    return this.normalizeWristValue(WRIST_RULER_MIN + index * WRIST_RULER_STEP);
  },

  onWristRulerTouchStart() {
    this.wristRulerInteracting = true;
    clearTimeout(this.wristRulerSnapTimer);
  },

  onWristRulerTouchEnd() {
    this.wristRulerInteracting = false;
    clearTimeout(this.wristRulerSnapTimer);
    this.wristRulerSnapTimer = setTimeout(() => this.snapWristRuler(), 220);
  },

  onWristRulerScroll(e) {
    const scrollLeft = Number(e.detail && e.detail.scrollLeft) || 0;
    const value = this.scrollLeftToWristValue(scrollLeft);
    const display = this.formatWristValue(value);
    this.currentWristRulerScrollLeft = scrollLeft;
    if (display !== this.wristRulerLastDisplay) {
      this.wristRulerLastDisplay = display;
      this.setData({
        wristRulerValue: display,
        wristInput: display
      });
    }
    if (!this.wristRulerInteracting) {
      clearTimeout(this.wristRulerSnapTimer);
      this.wristRulerSnapTimer = setTimeout(() => this.snapWristRuler(), 180);
    }
  },

  snapWristRuler() {
    if (!this.data.showWristModal) return;
    const value = this.scrollLeftToWristValue(this.currentWristRulerScrollLeft || this.data.wristRulerScrollLeft);
    const display = this.formatWristValue(value);
    this.setData({
      wristRulerValue: display,
      wristInput: display,
      wristRulerScrollLeft: this.wristValueToScrollLeft(value)
    });
  },

  selectBeadSize(e) {
    this.setData({ beadSize: Number(e.currentTarget.dataset.value) });
  },

  async confirmWristAndRecommend() {
    const wristSize = this.normalizeWristValue(Number(this.data.wristRulerValue || this.data.wristInput));
    if (!wristSize || wristSize < WRIST_RULER_MIN || wristSize > WRIST_RULER_MAX) {
      wx.showToast({ title: '请选择 10.0-25.0cm 的手腕围度', icon: 'none' });
      return;
    }
    this.setData({ generating: true });
    wx.showLoading({ title: '正在读取方案' });
    try {
      wx.setStorageSync('recommendedBeadSize', this.data.beadSize);
      const currentReport = this.data.report || {};
      const result = currentReport.report_id && currentReport.report_version
        ? await createReportDIYRecommendation(
          currentReport.report_id,
          currentReport.report_version,
          { wrist_size_cm: wristSize, bead_size_mm: this.data.beadSize }
        )
        : await createDIYRecommendation(currentReport.assessment_id, {
          wrist_size_cm: wristSize,
          bead_size_mm: this.data.beadSize
        });
      if (!currentReport.report_id) wx.setStorageSync('energyReport', result);
      wx.setStorageSync('recommendedWristSize', wristSize);
      wx.setStorageSync('workspaceWristConfirmed', true);
      wx.setStorageSync('diyWorkbenchPayload', result.workbench_payload);
      wx.setStorageSync('workspacePreset', 'backend-recommended');
      this.setData({ showWristModal: false });
      this.skipSuppressAssessmentAutoReport = true;
      wx.switchTab({ url: '/pages/workspace/workspace' });
    } catch (error) {
      wx.showToast({ title: error.message || '生成失败，请稍后重试', icon: 'none' });
    } finally {
      wx.hideLoading();
      this.setData({ generating: false });
    }
  },

  noop() {},

  async shareReport() {
    if (!this.data.report || this.data.posterGenerating) return;
    const sourceReport = this.data.report;
    const sourceIdentity = sourceReport.report_id
      ? `${sourceReport.report_id}:v${sourceReport.report_version}`
      : safeText(sourceReport.assessment_id);
    this.posterArtifact = null;
    this.setData({ posterGenerating: true, posterPath: '', showPosterModal: false });
    wx.showLoading({ title: '正在生成海报' });
    try {
      if (sourceReport.report_id && sourceReport.report_version) {
        const posterPayload = await getReportPoster(
          sourceReport.report_id,
          sourceReport.report_version,
          { silent: true }
        );
        this.posterPayloadHash = posterPayload.sanitized_payload_hash || '';
        this.posterRenderView = this.buildPosterRenderView(posterPayload);
      } else {
        this.posterRenderView = null;
      }
      const posterPath = await this.generateReportPoster();
      const currentReport = this.data.report || {};
      const currentIdentity = currentReport.report_id
        ? `${currentReport.report_id}:v${currentReport.report_version}`
        : safeText(currentReport.assessment_id);
      if (sourceIdentity !== currentIdentity) {
        throw new Error('报告已更新，请重新生成海报');
      }
      this.posterArtifact = {
        path: posterPath,
        reportId: sourceReport.report_id || '',
        reportVersion: Number(sourceReport.report_version) || 0,
        sanitizedPayloadHash: this.posterPayloadHash || ''
      };
      this.setData({ posterPath, showPosterModal: true });
    } catch (error) {
      console.warn('generate report poster failed:', error);
      wx.showToast({ title: error.message || '海报生成失败', icon: 'none' });
    } finally {
      this.posterRenderView = null;
      this.posterPayloadHash = '';
      wx.hideLoading();
      this.setData({ posterGenerating: false });
    }
  },

  buildPosterRenderView(payload = {}) {
    const conclusion = payload.core_conclusion || {};
    const guidance = payload.style_guidance || {};
    const balance = payload.balance || {};
    const elements = (payload.elements || []).map(item => ({
      ...ELEMENT_META[item.name],
      name: item.name,
      percent: Number(item.percent) || 0
    }));
    const adjustmentElements = (payload.adjustment_strategy || []).map(item => ({
      ...ELEMENT_META[item.element],
      name: item.element,
      role: item.role,
      description: ADJUSTMENT_ACTIONS[item.element] || '用于调和整体搭配'
    }));
    const advice = [
      { label: '推荐色彩', value: guidance.recommended_colors || '', tone: 'normal' },
      { label: '推荐质感', value: guidance.recommended_texture || '', tone: 'normal' },
      { label: '结构方向', value: guidance.structure_direction || '', tone: 'normal' },
      { label: '尽量避免', value: guidance.reduce || '', tone: 'caution' }
    ].filter(item => item.value);
    return {
      score: Number(balance.score) || 0,
      statusText: safeText(balance.label, '元素分布'),
      elements,
      keywords: payload.keywords || [],
      styleAnswer: {
        headline: safeText(conclusion.title, '找到适合你的搭配方向'),
        summary: safeText(conclusion.summary, '你的元素比例已经生成，适合继续有序调和。'),
        adviceTitle: '你的元素风格建议',
        advice,
        evidence: '推荐顺序由当前报告快照中的元素关系综合得出。',
        adjustmentElements
      }
    };
  },

  closePosterModal() {
    this.setData({ showPosterModal: false });
  },

  previewPoster() {
    if (!this.data.posterPath) return;
    if (!this.isPosterArtifactCurrent()) {
      wx.showToast({ title: '报告已更新，请重新生成海报', icon: 'none' });
      return;
    }
    wx.previewImage({
      current: this.data.posterPath,
      urls: [this.data.posterPath]
    });
  },

  savePosterImage() {
    if (!this.data.posterPath || this.data.posterSaving || this.photoAlbumPermissionPending) return;
    if (!this.isPosterArtifactCurrent()) {
      wx.showToast({ title: '报告已更新，请重新生成海报', icon: 'none' });
      return;
    }
    this.photoAlbumPermissionPending = true;
    this.ensurePhotoAlbumPermission()
      .then(() => {
        this.photoAlbumPermissionPending = false;
        this.savePosterToAlbum();
      })
      .catch(error => {
        this.photoAlbumPermissionPending = false;
        if (error && error.handled) return;
        const message = error && error.message ? error.message : '请稍后重试，或长按海报图片保存。';
        wx.showToast({ title: message, icon: 'none' });
      });
  },

  ensurePhotoAlbumPermission() {
    return new Promise((resolve, reject) => {
      if (!wx.getSetting) {
        resolve();
        return;
      }
      wx.getSetting({
        success: setting => {
          const authSetting = setting.authSetting || {};
          const albumScope = authSetting['scope.writePhotosAlbum'];
          if (albumScope === true) {
            resolve();
            return;
          }
          if (albumScope === false) {
            this.openPhotoAlbumSetting(resolve, reject);
            return;
          }
          if (!wx.authorize) {
            resolve();
            return;
          }
          this.requestPhotoAlbumAuthorize(resolve, reject);
        },
        fail: () => resolve()
      });
    });
  },

  requestPhotoAlbumAuthorize(resolve, reject) {
    wx.showModal({
      title: '保存海报到相册',
      content: '需要获得“保存到相册”权限，授权后我会自动把这张报告海报保存到你的手机相册。',
      confirmText: '允许保存',
      cancelText: '先不了',
      success: res => {
        if (!res.confirm) {
          reject({ handled: true });
          return;
        }
        wx.authorize({
          scope: 'scope.writePhotosAlbum',
          success: resolve,
          fail: error => {
            console.warn('authorize photo album failed:', error);
            this.openPhotoAlbumSetting(resolve, reject);
          }
        });
      },
      fail: () => reject({ handled: true })
    });
  },

  openPhotoAlbumSetting(resolve = () => {}, reject = () => {}) {
    wx.showModal({
      title: '开启保存权限',
      content: '刚才没有获得相册写入权限。请在下一页打开“保存到相册”开关，返回后我会继续保存海报。',
      confirmText: '去开启',
      cancelText: '先不了',
      success: res => {
        if (!res.confirm) {
          reject({ handled: true });
          return;
        }
        if (!wx.openSetting) {
          reject({ message: '当前微信版本不支持打开设置页' });
          return;
        }
        wx.openSetting({
          success: setting => {
            const authSetting = setting.authSetting || {};
            if (authSetting['scope.writePhotosAlbum']) {
              resolve();
              return;
            }
            wx.showModal({
              title: '还没有开启权限',
              content: '需要打开“保存到相册”开关后才能保存海报。你也可以长按海报图片，用系统菜单手动保存。',
              showCancel: false
            });
            reject({ handled: true });
          },
          fail: () => reject({ message: '无法打开设置页，请长按海报图片保存。' })
        });
      },
      fail: () => reject({ handled: true })
    });
  },

  savePosterToAlbum() {
    if (!this.isPosterArtifactCurrent()) {
      wx.showToast({ title: '报告已更新，请重新生成海报', icon: 'none' });
      return;
    }
    if (!wx.saveImageToPhotosAlbum) {
      wx.showModal({
        title: '当前微信版本不支持',
        content: '请长按海报图片，使用系统菜单保存到相册。',
        showCancel: false
      });
      return;
    }
    this.setData({ posterSaving: true });
    wx.showLoading({ title: '正在保存' });
    wx.saveImageToPhotosAlbum({
      filePath: this.data.posterPath,
      success: () => {
        wx.showToast({ title: '已保存到相册', icon: 'success' });
      },
      fail: error => {
        console.warn('save poster image failed:', error);
        const message = error.errMsg || '';
        if (this.isPhotoAlbumAuthError(message)) {
          wx.hideLoading();
          this.setData({ posterSaving: false });
          this.openPhotoAlbumSetting(
            () => this.savePosterToAlbum(),
            retryError => {
              if (retryError && retryError.handled) return;
              wx.showToast({ title: retryError.message || '请长按海报图片保存', icon: 'none' });
            }
          );
          return;
        }
        wx.showModal({
          title: '保存失败',
          content: '请长按海报图片保存，或稍后重试。',
          showCancel: false
        });
      },
      complete: () => {
        wx.hideLoading();
        this.setData({ posterSaving: false });
      }
    });
  },

  isPosterArtifactCurrent() {
    const report = this.data.report || {};
    if (!report.report_id) return Boolean(this.data.posterPath);
    const artifact = this.posterArtifact || {};
    return artifact.path === this.data.posterPath
      && artifact.reportId === report.report_id
      && Number(artifact.reportVersion) === Number(report.report_version)
      && Boolean(artifact.sanitizedPayloadHash);
  },

  isPhotoAlbumAuthError(message = '') {
    const text = String(message).toLowerCase();
    return text.includes('auth deny')
      || text.includes('auth denied')
      || text.includes('authorize')
      || text.includes('permission')
      || text.includes('scope.writephotosalbum')
      || text.includes('deny');
  },

  async restartAssessment() {
    await this.prepareAssessmentSeed('basic');
  },

  async supplementAssessment() {
    await this.prepareAssessmentSeed('state');
  },

  async prepareAssessmentSeed(step) {
    const report = this.data.report || {};
    let inputSummary = report.input_summary || null;
    if (report.report_id && report.report_version) {
      try {
        const basis = await getReportBasis(report.report_id, report.report_version, { silent: true });
        inputSummary = basis.input_snapshot || null;
      } catch (error) {
        wx.showToast({ title: error.message || '读取报告输入失败', icon: 'none' });
        return;
      }
    }
    if (inputSummary) {
      wx.setStorageSync(ASSESSMENT_REPORT_SEED_KEY, {
        input_summary: inputSummary,
        created_at: report.created_at || ''
      });
    }
    wx.setStorageSync(ASSESSMENT_RECALCULATE_KEY, true);
    wx.setStorageSync(ASSESSMENT_REQUESTED_STEP_KEY, step);
    wx.switchTab({ url: '/pages/assessment/assessment' });
  },

  ensurePosterCanvas() {
    if (this.posterCanvasState) return Promise.resolve(this.posterCanvasState);
    return new Promise((resolve, reject) => {
      const query = wx.createSelectorQuery().in(this);
      query.select('#reportPosterCanvas').fields({ node: true, size: true });
      query.exec(res => {
        const info = res && res[0];
        if (!info || !info.node) {
          reject(new Error('海报画布初始化失败'));
          return;
        }
        const canvas = info.node;
        const rawDpr = (wx.getWindowInfo && wx.getWindowInfo().pixelRatio)
          || (wx.getSystemInfoSync && wx.getSystemInfoSync().pixelRatio)
          || 1;
        const ctx = canvas.getContext('2d');
        this.posterCanvasState = { canvas, ctx, rawDpr, dpr: 1, width: POSTER_WIDTH, height: 0 };
        this.resizePosterCanvas(this.posterCanvasState, POSTER_MIN_HEIGHT);
        resolve(this.posterCanvasState);
      });
    });
  },

  getPosterDpr(height) {
    const rawDpr = Number(this.posterCanvasState && this.posterCanvasState.rawDpr) || 1;
    const sideSafeDpr = POSTER_MAX_BITMAP_SIDE / Math.max(1, height);
    return Math.max(1, Math.min(2, rawDpr, sideSafeDpr));
  },

  resizePosterCanvas(state, height) {
    const posterHeight = Math.max(POSTER_MIN_HEIGHT, Math.min(POSTER_MAX_HEIGHT, Math.ceil(height)));
    const dpr = this.getPosterDpr(posterHeight);
    if (state.height === posterHeight && state.dpr === dpr) return;
    state.dpr = dpr;
    state.height = posterHeight;
    state.canvas.width = Math.round(POSTER_WIDTH * dpr);
    state.canvas.height = Math.round(posterHeight * dpr);
    state.ctx = state.canvas.getContext('2d');
    if (state.ctx.setTransform) state.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    else state.ctx.scale(dpr, dpr);
  },

  generateReportPoster() {
    return this.ensurePosterCanvas().then(state => {
      const posterHeight = this.drawReportPoster(state);
      return new Promise((resolve, reject) => {
        wx.canvasToTempFilePath({
          canvas: state.canvas,
          fileType: 'jpg',
          quality: 0.94,
          destWidth: Math.round(POSTER_WIDTH * state.dpr),
          destHeight: Math.round(posterHeight * state.dpr),
          success: res => resolve(res.tempFilePath),
          fail: reject
        }, this);
      });
    });
  },

  drawReportPoster(state) {
    let ctx = state.ctx;
    const report = this.data.report || {};
    const view = this.posterRenderView || this.data.viewReport || this.buildViewReport(report);
    const mainTitle = '你的搭配答案';
    const styleAnswer = view.styleAnswer || {};
    const summaryText = sanitizeDisplayText(styleAnswer.summary || view.summary, '你的元素比例已经生成，适合以温和的方式继续调和。');
    const styleHeadline = safeText(styleAnswer.headline, '找到适合你的搭配方向');
    const elements = view.elements || [];
    const cardX = 44;
    const cardWidth = 662;
    const contentX = 76;
    const contentWidth = 598;
    const heroY = 140;
    const heroHeight = 380;
    const elementY = heroY + heroHeight + 26;
    const elementHeight = 302;
    const keywordY = elementY + elementHeight + 26;

    const adviceRows = (styleAnswer.advice || []).map(item => ({
      label: item.label,
      text: item.value,
      accent: item.tone === 'caution' ? '#C83B3D' : '#365C9C'
    }));
    const recommendRows = [
      {
        label: '策略说明',
        text: styleAnswer.evidence,
        accent: '#9D7A3F'
      },
      ...(styleAnswer.adjustmentElements || []).map(item => ({
        label: `${item.name} · ${item.role}`,
        text: item.description,
        accent: '#9D7A3F'
      }))
    ].filter(item => item.text);

    ctx.font = '700 24px "PingFang SC", "Microsoft YaHei", sans-serif';
    const tagHeight = measurePosterTags(ctx, view.keywords || [], contentX, 0, contentWidth);
    ctx.font = '500 22px "PingFang SC", "Microsoft YaHei", sans-serif';
    const summaryHeight = measureWrappedText(ctx, summaryText, contentWidth, 32);
    const keywordHeight = Math.max(280, 30 + 36 + 18 + tagHeight + 18 + summaryHeight + 32);
    const adviceHeight = measurePosterTextCard(ctx, adviceRows, cardWidth, { minHeight: 300 });
    const recommendHeight = measurePosterTextCard(ctx, recommendRows, cardWidth, { minHeight: 300 });

    let cursorY = keywordY + keywordHeight + 26;
    const adviceY = cursorY;
    cursorY += adviceHeight + 26;
    const recommendY = cursorY;
    cursorY += recommendHeight + 30;
    const footerY = cursorY;
    const posterHeight = Math.max(POSTER_MIN_HEIGHT, Math.min(POSTER_MAX_HEIGHT, footerY + 150));

    this.resizePosterCanvas(state, posterHeight);
    ctx = state.ctx;

    ctx.clearRect(0, 0, POSTER_WIDTH, posterHeight);
    const bg = ctx.createLinearGradient(0, 0, 0, posterHeight);
    bg.addColorStop(0, '#FBFAF7');
    bg.addColorStop(1, '#F1EEE7');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, POSTER_WIDTH, posterHeight);

    ctx.fillStyle = '#20201F';
    ctx.font = '800 28px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText('宇涧水晶', 58, 76);
    ctx.fillStyle = '#8B8881';
    ctx.font = '700 18px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText('ELEMENT STYLE REPORT', 58, 106);
    ctx.textAlign = 'right';
    ctx.fillText('LIGHT STUDIO LAB', 692, 82);
    ctx.textAlign = 'left';

    fillRoundRect(ctx, cardX, heroY, cardWidth, heroHeight, 32, '#FFFFFF');
    strokeRoundRect(ctx, cardX, heroY, cardWidth, heroHeight, 32, '#E5E2DC', 1);
    ctx.fillStyle = '#20201F';
    ctx.font = '900 44px "PingFang SC", "Microsoft YaHei", sans-serif';
    drawWrappedText(ctx, mainTitle, contentX, 206, 336, 54, 2);
    ctx.fillStyle = '#64615B';
    ctx.font = '500 24px "PingFang SC", "Microsoft YaHei", sans-serif';
    drawWrappedText(ctx, '仅展示搭配结论，不包含个人测算输入', contentX, 320, 340, 34, 2);
    ctx.fillStyle = '#647C70';
    ctx.font = '800 21px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText('搭配方向', contentX, 408);
    ctx.fillStyle = '#20201F';
    ctx.font = '750 25px "PingFang SC", "Microsoft YaHei", sans-serif';
    drawWrappedText(ctx, styleHeadline, contentX, 444, 340, 34, 2);

    drawElementRing(ctx, elements, 560, 296, 96, 24);
    fillRoundRect(ctx, 494, 230, 132, 132, 66, '#FBFAF7');
    ctx.textAlign = 'center';
    ctx.fillStyle = '#20201F';
    ctx.font = '900 54px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText(String(view.score), 560, 292);
    ctx.fillStyle = '#8B8881';
    ctx.font = '700 21px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText(view.statusText, 560, 330);
    ctx.textAlign = 'left';

    fillRoundRect(ctx, cardX, elementY, cardWidth, elementHeight, 28, '#FFFFFF');
    strokeRoundRect(ctx, cardX, elementY, cardWidth, elementHeight, 28, '#E5E2DC', 1);
    ctx.fillStyle = '#20201F';
    ctx.font = '800 30px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText('元素比例', contentX, elementY + 58);
    drawPosterElementRows(ctx, elements, contentX, elementY + 96, contentWidth);

    fillRoundRect(ctx, cardX, keywordY, cardWidth, keywordHeight, 28, '#FFFFFF');
    strokeRoundRect(ctx, cardX, keywordY, cardWidth, keywordHeight, 28, '#E5E2DC', 1);
    ctx.fillStyle = '#20201F';
    ctx.font = '800 30px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText('核心搭配结论', contentX, keywordY + 58);
    const afterTagsY = drawPosterTags(ctx, view.keywords || [], contentX, keywordY + 80, contentWidth);
    ctx.fillStyle = '#64615B';
    ctx.font = '500 22px "PingFang SC", "Microsoft YaHei", sans-serif';
    drawWrappedText(ctx, summaryText, contentX, afterTagsY + 14, contentWidth, 32);

    drawPosterTextCard(ctx, safeText(styleAnswer.adviceTitle, '元素风格建议'), adviceRows, cardX, adviceY, cardWidth, { minHeight: 300, accent: '#365C9C' });
    drawPosterTextCard(ctx, '推荐依据', recommendRows, cardX, recommendY, cardWidth, { minHeight: 300, accent: '#9D7A3F' });

    fillRoundRect(ctx, cardX, footerY, cardWidth, 92, 24, '#20201F');
    ctx.fillStyle = '#FFFFFF';
    ctx.font = '800 24px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText('生成专属手串', contentX, footerY + 38);
    ctx.font = '500 22px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText('打开小程序继续编辑 DIY 方案', contentX, footerY + 68);
    ctx.textAlign = 'right';
    ctx.fillStyle = '#D8D4CC';
    ctx.font = '700 20px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText('LIGHT STUDIO LAB', 674, footerY + 54);
    ctx.textAlign = 'left';

    ctx.fillStyle = '#8B8881';
    ctx.font = '500 18px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText('本分析仅用于文化体验、审美搭配与个性化 DIY 推荐', contentX, footerY + 128);

    return posterHeight;
  },

  goBack() {
    wx.setStorageSync(ASSESSMENT_SUPPRESS_AUTO_REPORT_ONCE_KEY, true);
    const pages = getCurrentPages();
    if (pages.length > 1) {
      wx.navigateBack();
      return;
    }
    wx.switchTab({ url: '/pages/assessment/assessment' });
  }
});
