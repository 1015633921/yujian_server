const auth = require('../../utils/auth');
const {
  getMaterials,
  saveDIYDesign,
  getSharedDIYDesign,
  publishDIYDesign,
  uploadDesignPreview
} = require('../../utils/api');
const { assetUrl } = require('../../utils/assets');
const {
  expandSequenceToCount,
  estimateInnerCircumferenceMm,
  recommendBeadCount
} = require('../../utils/braceletSizing');
const { buildFreshWorkspaceDraft } = require('../../utils/workspaceImport');
const {
  resolveMaterialGeometry,
  stringedMaterialOffset,
  stringedMaterialRotationDeg
} = require('../../utils/materialGeometry');
const {
  attachmentFromMaterial,
  beadCapCompatibility,
  beadCapItemsFromPlacements,
  beadCapSlotsFromPlacement,
  beadCapSprite,
  isBeadCap
} = require('../../utils/materialAttachments');

let Body;
let Bodies;
let Composite;
let Engine;
let Events;
let Sleeping;

const MATERIAL_PAGE_SIZE = 24;
const MATERIAL_CACHE_TTL = 30 * 60 * 1000;
const MATERIAL_CACHE_KEY = 'workspaceMaterialCatalogV9';
const MATERIAL_BACKGROUND_REFRESH_INTERVAL = 5000;
const ALL_OPTION_LABEL = '\u5168\u90e8';
const LEGACY_ALL_OPTION_LABELS = [ALL_OPTION_LABEL, '鍏ㄩ儴'];
const TRAY_THEME_STORAGE_KEY = 'workspaceTrayThemeV1';
const WORKSPACE_WRIST_SIZE_STORAGE_KEY = 'workspaceWristSizeV1';
const WORKSPACE_GUIDE_STORAGE_KEY = 'workspaceFirstGuideDismissedV2';
const MAX_WORKSPACE_BEADS = 40;
const MAX_RECOMMENDED_RECIPE_BEADS = 40;
const MIN_STRING_BEAD_COUNT = 8;
const MAX_MATERIAL_FLIGHT_QUEUE = 6;
const MATERIAL_TAP_GUARD_MS = 80;
const MATERIAL_LONG_PRESS_TAP_SUPPRESS_MS = 520;
const MATERIAL_QUEUE_TOAST_GUARD_MS = 1200;
const MATERIAL_SEARCH_DEBOUNCE_MS = 260;
const MATERIAL_PRELOAD_BATCH_SIZE = 3;
const MATERIAL_PRELOAD_BATCH_DELAY_MS = 72;
const MATERIAL_PRELOAD_IDLE_RETRY_MS = 180;
const MATERIAL_PRELOAD_MAX_DEFER_MS = 1800;
const SHARED_DESIGN_IMAGE_PRELOAD_CONCURRENCY = 6;
const SHARED_DESIGN_IMAGE_PRELOAD_TIMEOUT_MS = 6000;
const STRINGED_BEAD_GAP_RPX = 0.5;
const STRINGED_COMFORT_ALLOWANCE_MM = 8;
const RING_SLIDE_EDGE_RATIO = 0.38;
const RING_REORDER_CENTER_DEAD_ZONE_RATIO = 0.35;
const RING_SLIDE_MIN_MOVE_RAD = 0.018;
const MAX_BEAD_ANGULAR_VELOCITY = 0.16;
const COLLISION_SPIN_FACTOR = 0.018;
const ROLLING_SPIN_FACTOR = 0.10;
const DRAG_ROLLING_SPIN_FACTOR = 0.82;
const BILLIARD_BEAD_RESTITUTION = 0.22;
const BILLIARD_NEIGHBOR_REBOUND_DAMPING = 0.58;
const BILLIARD_NEIGHBOR_REBOUND_MIN_SPEED = 0.35;
const BILLIARD_NEIGHBOR_REBOUND_MAX_CORRECTION = 4.8;
const BILLIARD_WALL_RESTITUTION = 0.50;
const BILLIARD_FRICTION = 0.08;
const BILLIARD_STATIC_FRICTION = 0.18;
const BILLIARD_FRICTION_AIR = 0.004;
const BILLIARD_LINEAR_DAMPING = 0.984;
const BILLIARD_ANGULAR_DAMPING = 0.58;
const BILLIARD_LAUNCH_MIN_SPEED = 58.0;
const BILLIARD_LAUNCH_MAX_SPEED = 86.0;
const BILLIARD_LAUNCH_SOFT_MIN_SPEED = 46.0;
const BILLIARD_LAUNCH_STRENGTH_MIN = 0.72;
const BILLIARD_LAUNCH_STRENGTH_MAX = 1.18;
const BILLIARD_LAUNCH_SPEED_SCALE = 0.8;
const BILLIARD_LAUNCH_RANDOM_X_RPX = 0;
const BILLIARD_LAUNCH_AIM_RANDOM_X_RPX = 0;
const TRAY_BOUNDARY_PADDING_RPX = 8;
const TRAY_BOUNDARY_GUARD_RPX = 16;
const TRAY_BOUNDARY_TOUCH_GUARD_RPX = 3;
const TRAY_BOUNDARY_LOOKAHEAD_FRAMES = 2.4;
const TRAY_BOUNDARY_MAX_LOOKAHEAD_FRAMES = 7.2;
const TRAY_IMPACT_TOUCH_GUARD_RPX = 5;
const TRAY_LAUNCH_ENTRY_PADDING_RPX = 6;
const TRAY_LAUNCH_AIM_PADDING_RPX = 14;
const TRAY_IMPACT_CONTAIN_PADDING_RPX = 8;
const TRAY_IMPACT_CONTAIN_GUARD_RPX = 24;
const TRAY_IMPACT_CONTAIN_MS = 1250;
const TRAY_ESCAPE_RESET_GUARD_RPX = 120;
const TRAY_IMPACT_ESCAPE_RESET_GUARD_RPX = 34;
const TRAY_IMPACT_KEEPALIVE_SPEED_RPX = 2.8;
const TRAY_IMPACT_REARM_SPEED_RPX = 4.2;
const TRAY_IMPACT_KEEPALIVE_MS = 360;
const CANVAS_IMAGE_CACHE_LIMIT = 72;
const CANVAS_TEXTURE_CACHE_LIMIT = 96;
const CANVAS_SHADOW_CACHE_LIMIT = 36;
const CANVAS_TEXTURE_BUCKET_STEP = 8;
const CANVAS_SHADOW_BUCKET_STEP = 8;
const DECORATED_MATERIAL_CACHE_LIMIT = 360;
const MATERIAL_ELEMENT_KEY_CACHE_LIMIT = 520;
const MATERIAL_PRELOAD_RECORD_LIMIT = 360;
const MATERIAL_FLIGHT_MIN_DURATION = 18;
const MATERIAL_FLIGHT_SPEED_PX_PER_MS = 36;
const MATERIAL_FLIGHT_DURATION_SCALE = 1.25;
const MATERIAL_FLIGHT_REAL_DURATION = 42;
const MATERIAL_FLIGHT_DEV_DURATION = 38;
const MATERIAL_FLIGHT_LOW_PERF_DURATION = 58;
const STRINGING_FLIGHT_DURATION = 150;
const STRINGING_LOW_PERF_DURATION = 176;
const STRINGING_STAGGER_MS = 5;
const STRINGING_LOW_PERF_STAGGER_MS = 7;
const RELEASE_STRING_FLIGHT_DURATION = 180;
const RELEASE_STRING_LOW_PERF_DURATION = 220;
const RELEASE_STRING_STAGGER_MS = 10;
const RELEASE_STRING_LOW_PERF_STAGGER_MS = 12;
const materialSearchTextCache = typeof WeakMap !== 'undefined' ? new WeakMap() : null;
const DEFAULT_DESIGN_NAME = 'Yustream DIY 手串方案';
const DESIGN_NAME_MODAL_HINT = '给这条手串起个名字，方便后续在我的方案中识别。';
const WORKSPACE_DEBUG_LOGS = false;
const WORKSPACE_SOUND_URLS = {
  collisionSoft: assetUrl('sounds/bead-duang-soft-quick.wav'),
  shuffle: assetUrl('sounds/string-shuffle.wav')
};
const WORKSPACE_ICON_URLS = {
  undo: assetUrl('workspace-icons/workspace-undo.png'),
  wrist: assetUrl('workspace-icons/workspace-wrist.png'),
  share: assetUrl('workspace-icons/share-button-gold.png'),
  save: assetUrl('workspace-icons/workspace-save-download.png'),
  energy: assetUrl('workspace-icons/workspace-energy-five-elements.png'),
  clear: assetUrl('workspace-icons/workspace-clear-pastel.png'),
  string: assetUrl('workspace-icons/workspace-string-dice.png')
};
const WORKSPACE_SOUND_POOL_SIZE = {
  // 连续选材的落地声允许短暂重叠，避免同一个音频实例 stop/play 连发时被系统吞掉。
  collisionSoft: 4,
  shuffle: 2
};
const WORKSPACE_SOUND_VOLUME = {
  collisionSoft: 0.17,
  shuffle: 0.18
};
const TRAY_IMPACT_FEEDBACK_MIN_SPEED = 1.05;
const WRIST_RULER_MIN = 10;
const WRIST_RULER_MAX = 25;
let materialCache = {};
let materialCacheAt = {};

function getWorkspaceSystemInfo() {
  const windowInfo = wx.getWindowInfo ? wx.getWindowInfo() : {};
  const deviceInfo = wx.getDeviceInfo ? wx.getDeviceInfo() : {};
  const appInfo = wx.getAppBaseInfo ? wx.getAppBaseInfo() : {};
  if (windowInfo && windowInfo.windowWidth) {
    return {
      ...windowInfo,
      ...deviceInfo,
      ...appInfo,
      pixelRatio: windowInfo.pixelRatio || deviceInfo.pixelRatio
    };
  }
  return wx.getSystemInfoSync ? wx.getSystemInfoSync() : {};
}

function cleanDesignName(value = '') {
  const text = String(value || '').trim();
  if (!text) return '';
  if (text === DESIGN_NAME_MODAL_HINT || text.includes('给这条手串起个名字')) return '';
  return text;
}

const DEFAULT_MATERIALS = [];

const TOP_TABS = [
  { key: 'bead', label: '珠珠' },
  { key: 'accessory', label: '配饰' }
];

const LEGACY_ID_MAP = {
  aquamarine: 'aquamarine8',
  amethyst: 'amethyst8',
  clearQuartz: 'clearQuartz8',
  moonstone: 'moonstone8',
  citrine: 'citrine8',
  tigerEye: 'tigerEye8',
  roseQuartz: 'roseQuartz8',
  obsidian: 'obsidian10',
  lapis: 'aquamarine8'
};

const BACKEND_CRYSTAL_MAP = {
  titanium_quartz: 'citrine10',
  citrine: 'citrine8',
  gold_rutilated_quartz: 'citrine10',
  rhodochrosite: 'roseQuartz8',
  strawberry_quartz: 'roseQuartz8',
  rose_quartz: 'roseQuartz8',
  blue_rutilated_quartz: 'blueRutilatedQuartz10',
  obsidian: 'obsidian10',
  black_rutilated_quartz: 'obsidian10',
  green_phantom: 'greenPhantom8',
  clear_quartz: 'clearQuartz8',
  aquamarine: 'aquamarine8',
  turquoise: 'turquoise6',
  garnet: 'garnet8',
  smoky_quartz: 'smokyQuartz8',
  hematite: 'hematite8'
};

const BACKEND_CRYSTAL_ALIASES = {
  titanium_quartz: ['钛晶', '金发晶', '黄水晶', '黄晶'],
  citrine: ['黄水晶', '黄晶', '金发晶', '钛晶'],
  gold_rutilated_quartz: ['金发晶', '钛晶', '黄水晶', '黄晶'],
  rhodochrosite: ['红纹石', '粉晶', '粉水晶', '南红玛瑙', '红玛瑙'],
  strawberry_quartz: ['草莓晶', '粉晶', '粉水晶', '南红玛瑙', '红玛瑙'],
  rose_quartz: ['粉晶', '粉水晶', '红纹石', '草莓晶'],
  blue_rutilated_quartz: ['蓝发晶', '海蓝宝', '蓝晶石', '青金石'],
  obsidian: ['黑曜石', '黑耀石', '曜石', '黑发晶', '黑玛瑙'],
  black_rutilated_quartz: ['黑发晶', '黑曜石', '黑耀石', '曜石', '黑玛瑙'],
  green_phantom: ['绿幽灵', '绿发晶', '东陵玉', '橄榄石'],
  clear_quartz: ['白水晶', '白晶', '透明水晶', '水晶'],
  aquamarine: ['海蓝宝', '蓝发晶', '蓝晶石'],
  turquoise: ['绿松石', '绿幽灵', '东陵玉'],
  garnet: ['石榴石', '南红玛瑙', '红玛瑙', '红发晶'],
  smoky_quartz: ['茶晶', '烟晶', '黄水晶'],
  hematite: ['赤铁矿', '银发晶', '白水晶', '黑曜石'],
  sunstone: ['太阳石', '日光石', '黄水晶', '石榴石'],
  tiger_eye: ['虎眼石', '金虎眼石', '黄虎眼石'],
  rhodonite: ['蔷薇辉石', '红纹石', '粉晶', '粉水晶'],
  prehnite: ['葡萄石', '绿幽灵', '绿东陵'],
  green_aventurine: ['绿东陵', '东陵玉', '绿幽灵'],
  malachite: ['孔雀石', '绿幽灵', '绿东陵'],
  red_phantom: ['红幽灵', '红兔毛', '红发晶', '南红玛瑙'],
  colorful_phantom: ['彩幽灵', '四季幽灵', '幽灵水晶'],
  blue_lace_agate: ['蓝纹玛瑙', '蓝玛瑙', '海蓝宝'],
  lapis_lazuli: ['青金石', '蓝晶石', '海蓝宝'],
  amazonite: ['天河石', '绿松石', '海蓝宝'],
  apatite: ['蓝磷灰石', '海蓝宝', '蓝晶石'],
  blue_fluorite: ['蓝萤石', '萤石', '海蓝宝'],
  amethyst: ['紫水晶', '紫萤石', '紫锂辉'],
  moonstone: ['月光石', '白月光石', '灰月光'],
  labradorite: ['拉长石', '月光石', '灰月光'],
  lepidolite: ['锂云母', '紫锂辉', '紫水晶']
};

const BACKEND_CRYSTAL_ELEMENT = {
  titanium_quartz: 'metal',
  citrine: 'earth',
  gold_rutilated_quartz: 'metal',
  rhodochrosite: 'fire',
  strawberry_quartz: 'fire',
  rose_quartz: 'wood',
  blue_rutilated_quartz: 'water',
  obsidian: 'water',
  black_rutilated_quartz: 'metal',
  green_phantom: 'wood',
  clear_quartz: 'metal',
  aquamarine: 'water',
  turquoise: 'wood',
  garnet: 'fire',
  smoky_quartz: 'earth',
  hematite: 'metal',
  sunstone: 'fire',
  tiger_eye: 'earth',
  rhodonite: 'fire',
  prehnite: 'wood',
  green_aventurine: 'wood',
  malachite: 'wood',
  red_phantom: 'fire',
  colorful_phantom: 'wood',
  blue_lace_agate: 'water',
  lapis_lazuli: 'water',
  amazonite: 'water',
  apatite: 'water',
  blue_fluorite: 'water',
  amethyst: 'water',
  moonstone: 'water',
  labradorite: 'water',
  lepidolite: 'water'
};

const ELEMENTS = [
  { key: 'wood', name: '木', color: '#4f8f6f' },
  { key: 'fire', name: '火', color: '#c75d45' },
  { key: 'earth', name: '土', color: '#b58b4f' },
  { key: 'metal', name: '金', color: '#9b9fa3' },
  { key: 'water', name: '水', color: '#477b91' }
];

const MATERIAL_ELEMENT_KEY = {
  clearQuartz: 'metal',
  amethyst: 'fire',
  citrine: 'earth',
  obsidian: 'metal',
  tigerEye: 'earth',
  moonstone: 'water',
  aquamarine: 'water',
  blueRutilatedQuartz: 'water',
  roseQuartz: 'wood',
  garnet: 'fire',
  turquoise: 'wood',
  greenPhantom: 'wood',
  smokyQuartz: 'earth',
  hematite: 'metal',
  silverSpacer: 'metal',
  goldSpacer: 'earth',
  calmIncense: 'earth',
  roseIncense: 'wood',
  lotusCap: 'metal'
};

const ELEMENT_CN_TO_EN = { '金': 'metal', '木': 'wood', '水': 'water', '火': 'fire', '土': 'earth' };
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
const ELEMENT_KEY_ALIASES = {
  ...ELEMENT_CN_TO_EN,
  metal: 'metal',
  wood: 'wood',
  water: 'water',
  fire: 'fire',
  earth: 'earth',
  jin: 'metal',
  mu: 'wood',
  shui: 'water',
  huo: 'fire',
  tu: 'earth'
};

function logWorkspaceWarning(...args) {
  if (WORKSPACE_DEBUG_LOGS) console.warn(...args);
}

function repairMojibakeElementText(value) {
  const text = String(value || '').trim();
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

function normalizeElementCnName(value) {
  const text = String(value || '').trim();
  if (ELEMENT_CN_TO_EN[text]) return text;
  const repaired = repairMojibakeElementText(text);
  if (ELEMENT_CN_TO_EN[repaired]) return repaired;
  return ELEMENT_NAME_ALIASES[text.toLowerCase()] || '';
}

function normalizeElementKey(value) {
  const text = String(value || '').trim();
  if (!text) return '';
  const repaired = repairMojibakeElementText(text);
  return ELEMENT_KEY_ALIASES[text]
    || ELEMENT_KEY_ALIASES[text.toLowerCase()]
    || ELEMENT_KEY_ALIASES[repaired]
    || ELEMENT_KEY_ALIASES[repaired.toLowerCase()]
    || '';
}

function materialTop(material = {}) {
  return String((material.sku && material.sku.top) || material.top || '').trim().toLowerCase();
}

function materialCardSpecText(physical = {}, isAccessory = false) {
  if (!physical.specComplete) return '规格待补';
  if (isAccessory || physical.isRound) return `${
    isAccessory ? physical.stringAxisWidthMm : physical.sizeMm
  }mm`;
  return `${physical.bodyWidthMm}×${physical.bodyHeightMm}mm`;
}

function materialDetailSpecText(physical = {}, isAccessory = false) {
  if (!physical.specComplete) return '规格待补';
  if (isAccessory) return materialCardSpecText(physical, true);
  return physical.specText || materialCardSpecText(physical);
}

function materialIsPendant(material = {}) {
  return materialTop(material) === 'pendant';
}

function materialIsSellable(material = {}) {
  const enabled = material.enabled;
  const stock = Number(material.stock);
  const price = Number(material.price);
  return enabled !== false
    && enabled !== 0
    && enabled !== '0'
    && Number.isFinite(stock)
    && stock > 0
    && Number.isFinite(price)
    && price > 0;
}

function materialIsWorkspaceSupported(material = {}) {
  return !materialIsPendant(material) && materialIsSellable(material);
}

function materialIdentifiers(material = {}) {
  return [
    material.id,
    material.skuId,
    material.sku_id,
    material.material_code,
    material.sku
  ].map(value => String(value || '').trim()).filter(Boolean);
}

function unsupportedWorkspaceMaterialIds(materials = []) {
  const ids = {};
  (materials || []).filter(item => item && !materialIsWorkspaceSupported(item)).forEach(item => {
    materialIdentifiers(item).forEach(id => {
      ids[id] = true;
    });
  });
  return ids;
}

function filterWorkspaceMaterials(materials = []) {
  return (materials || []).filter(materialIsWorkspaceSupported);
}

function estimateStringedLengthMm(itemsOrSizes = []) {
  return estimateInnerCircumferenceMm(itemsOrSizes);
}

function recommendedStringedBeadCount(itemsOrSizes = [], wristSize = 16) {
  return recommendBeadCount(itemsOrSizes, wristSize, {
    allowanceMm: STRINGED_COMFORT_ALLOWANCE_MM,
    defaultBeadSizeMm: 8,
    minCount: MIN_STRING_BEAD_COUNT,
    maxCount: MAX_RECOMMENDED_RECIPE_BEADS
  });
}

function filterWorkspaceTopTabs(list = []) {
  return (list || []).filter(item => item && item.key !== 'incense' && item.key !== 'pendant');
}

function firstWorkspaceImageUrl(entry = {}) {
  const urls = entry.image_urls || entry.image_pool || [];
  const list = Array.isArray(urls) ? urls : [urls];
  return list.concat(entry.image_url || []).filter(Boolean)[0] || '';
}

function sequenceItemIsPendant(item = {}) {
  return String(item.top || item.item_type || item.type || '').trim().toLowerCase() === 'pendant';
}

function sequenceItemIsBeadCap(item = {}) {
  const params = item.material_params || {};
  return item.attachment_mode === 'bead_cap'
    || item.attachment && item.attachment.mode === 'bead_cap'
    || item.placement_mode === 'attached_side'
    || params.placement_mode === 'attached_side';
}

function materialContributesEnergy(material = {}) {
  return !materialIsPendant(material);
}

function repairMaybeMojibakeText(value) {
  const text = String(value || '').trim();
  if (!text || /[�]/.test(text)) return '';
  const repaired = repairMojibakeElementText(text);
  return repaired && !/[�]/.test(repaired) ? repaired : text;
}

function safeMaterialDisplayText(value) {
  return repairMaybeMojibakeText(value)
    .replace(/改善睡眠|助眠/g, '睡前放松')
    .replace(/修复/g, '舒缓')
    .replace(/治疗|疗效/g, '搭配感受')
    .replace(/功效/g, '搭配特点')
    .replace(/太阳神经丛/g, '行动力')
    .replace(/海底轮/g, '稳定感')
    .replace(/脐轮/g, '情绪流动')
    .replace(/心轮/g, '关系感')
    .replace(/喉轮/g, '表达感')
    .replace(/眉心轮/g, '灵感')
    .replace(/顶轮/g, '思考感');
}

function isMaterialGradeText(value) {
  const text = repairMaybeMojibakeText(value);
  if (!text) return true;
  const normalized = text.trim().toLowerCase();
  if (!normalized) return true;
  if (/^(entry|grade|level|a\+?|aa\+?|aaa\+?|3a|4a|5a)$/.test(normalized)) return true;
  if (/(等级|级别|品级|品质|品相)/.test(text)) return true;
  if (/^(天然|普通|精选|精品|收藏|高货|优选|优化|通货).{0,4}级$/.test(text)) return true;
  return false;
}

const TRAY_THEMES = [
  { value: 'white', label: 'white', dotClass: 'white', imageUrl: `${assetUrl('workspace/tray-yustream-white-transparent-user-20260701.webp')}?v=20260701-user` },
  { value: 'warm', label: 'warm', dotClass: 'warm', imageUrl: `${assetUrl('workspace/tray-yustream-transparent-user-20260701-v6.webp')}?v=20260701-user6` },
  { value: 'black', label: 'black', dotClass: 'black', imageUrl: `${assetUrl('workspace/tray-yustream-black-transparent-user-20260701.webp')}?v=20260701-user` }
];

const WRIST_MEASURE_GUIDE_IMAGE_URL = `${assetUrl('workspace/wrist-measure-guide-20260701.webp')}?v=20260701`;

const WRIST_GUIDE_TABS = [
  { key: 'measure', label: '测手围' },
  { key: 'workspace', label: '用工作台' }
];

const WRIST_GUIDE_TABS_DISPLAY = [
  { key: 'workspace', label: '工作台指南' },
  { key: 'measure', label: '测手围' }
];

const WORKSPACE_USAGE_GUIDE = [
  { tag: '撤回', title: '撤销上一步', desc: '误加、误删或移动后，可以快速回到上一步。' },
  { tag: '腕围', title: '调整手围', desc: '修改手围后，方案长度会同步重算。' },
  { tag: '分享', title: '分享当前方案', desc: '生成方案分享入口，好友点开后直接进入工作台查看。' },
  { tag: '保存', title: '保存方案草稿', desc: '把当前搭配暂存，稍后可以继续编辑。' },
  { tag: '五行', title: '查看元素占比', desc: '打开当前方案的五行比例，方便对照分析结果。' },
  { tag: '清空', title: '清空盘面', desc: '移除当前盘面所有珠子，重新开始搭配。' },
  { tag: '成串', title: '随机成串/打散', desc: '在自由摆放和圆串整理之间切换，快速预览佩戴效果。' },
  { tag: '结算', title: '去结算', desc: '确认方案后直接进入订单确认页。' }
];

const WORKSPACE_USAGE_GUIDE_WITH_ICONS = [
  { tag: '撤回', iconUrl: WORKSPACE_ICON_URLS.undo, previewClass: 'preview-square', title: '撤回上一步', desc: '误加、误删或移动珠子后，点它回到上一步。' },
  { tag: '腕围', iconUrl: WORKSPACE_ICON_URLS.wrist, previewClass: 'preview-wrist', buttonText: '腕围16cm', title: '设置腕围', desc: '调整当前手围，系统会同步重算串长和适配。' },
  { tag: '分享', iconUrl: WORKSPACE_ICON_URLS.share, previewClass: 'preview-share', title: '分享方案', desc: '生成当前方案分享入口，好友打开后可直接查看。' },
  { tag: '保存', iconUrl: WORKSPACE_ICON_URLS.save, previewClass: 'preview-square preview-save', title: '保存方案', desc: '把当前搭配保存为草稿，之后可以继续编辑。' },
  { tag: '五行', iconUrl: WORKSPACE_ICON_URLS.energy, previewClass: 'preview-square preview-energy', title: '五行图', desc: '查看当前方案的五行元素占比。' },
  { tag: '清空', iconUrl: WORKSPACE_ICON_URLS.clear, previewClass: 'preview-square preview-clear', title: '清空盘面', desc: '移除当前盘面所有珠子，重新开始搭配。' },
  { tag: '成串', iconUrl: WORKSPACE_ICON_URLS.string, previewClass: 'preview-dark preview-string', buttonText: '随机成串', title: '随机成串 / 解除成串', desc: '成串后拖动珠子调整顺序，拖动外环旋转整串。' },
  { tag: '托盘', previewClass: 'preview-tray', buttonText: '托盘颜色', showSwatch: true, title: '切换托盘颜色', desc: '顺序切换托盘底色，方便看清不同颜色的珠子。' },
  { tag: '结算', previewClass: 'preview-dark preview-cart', buttonText: '去结算', title: '去结算', desc: '确认方案后直接进入订单确认页。' }
];

const WORKSPACE_GUIDE_STEPS = [
  { target: 'wrist', eyebrow: '01 · 设置腕围', title: '先确认你的佩戴腕围', desc: '点击高亮的腕围按钮，确认后继续下一步。' },
  { target: 'materials', eyebrow: '02 · 选择材料', title: '从这里挑选珠子和配饰', desc: '轻点下方材料卡片，即可把它加入托盘。' },
  { target: 'tray', eyebrow: '03 · 调整位置', title: '在托盘内自由排列', desc: '材料进入后可拖动调整；长按材料卡片还能查看实拍。' },
  { target: 'string', eyebrow: '04 · 一键成串', title: '切换成串，预览佩戴效果', desc: '成串后拖动珠子可换位，拖动外环可旋转整串。' },
  { target: 'checkout', eyebrow: '05 · 保存或结算', title: '完成后保存方案或去结算', desc: '你可以随时从左侧 ? 重新查看完整使用说明。' }
];

Page({
  data: {
    visibleMaterials: [],
    hasMoreMaterials: false,
    materialsLoading: true,
    materialsLoadingMore: false,
    materialsErrorText: '',
    workspaceLoading: true,
    workspaceLoadingClass: '',
    workspaceLoadingText: '正在准备工作台',
    workspaceLoadingSubtext: '同步盘面与珠材...',
    materialSkeletons: [1, 2, 3, 4],
    materialSearchKeyword: '',
    showMaterialDetail: false,
    materialDetail: null,
    categories: [],
    seriesOptions: ['全部'],
    filterSummary: '全部 · 全部 · 0 款',
    topTabs: TOP_TABS,
    activeTop: 'bead',
    activeCategory: '全部',
    activeSeries: '全部',
    seriesOptions: [ALL_OPTION_LABEL],
    filterSummary: `${ALL_OPTION_LABEL} · ${ALL_OPTION_LABEL} · 0 款`,
    activeCategory: ALL_OPTION_LABEL,
    activeSeries: ALL_OPTION_LABEL,
    activeCategoryAnchor: '',
    activeSeriesAnchor: '',
    showTip: true,
    showWorkspaceGuide: false,
    workspaceGuideStep: 0,
    workspaceGuideSteps: WORKSPACE_GUIDE_STEPS,
    activeWorkspaceGuide: WORKSPACE_GUIDE_STEPS[0],
    workspaceGuideFocusStyle: '',
    workspaceIcons: WORKSPACE_ICON_URLS,
    wristSize: 16,
    wearStyle: 'single',
    selected: [],
    placements: [],
    attachedPendants: [],
    selectedItems: [],
    attachedPendantItems: [],
    workspaceCanvasVisible: true,
    workspaceCanvasSuppressed: false,
    canvasRenderError: false,
    trayImageUrl: TRAY_THEMES[0].imageUrl,
    trayTheme: 'warm',
    trayThemeItems: [],
    trayImageFailed: false,
    canvasFlightActive: false,
    stringStyle: '',
    countOverClass: '',
    braceletStringClass: 'empty',
    completionWatermarkClass: '',
    shuffleButtonClass: '',
    randomIconText: '串',
    randomTitle: '随机成串',
    randomSubtitle: '随机排列珠面',
    workspacePlanLabel: '当前方案',
    cartActionText: '去结算',
    isAddingToCart: false,
    flightBead: null,
    launchingMaterialId: '',
    isShuffling: false,
    isStringingFinishing: false,
    isReleasingString: false,
    isLooseMode: true,
    selectedBeadIndex: -1,
    selectedBeadInfo: null,
    draggingBeadIndex: -1,
    dragDeleteArmed: false,
    canUndo: false,
    canRedo: false,
    deviceClass: 'device-regular',
    deviceInfo: {},
    workspaceLayoutStyle: '',
    wristOptions: [13, 14, 15, 16, 17, 18, 19, 20],
    wristOptionItems: [],
    showWristPicker: false,
    wristRulerValue: '16.0',
    energyChart: {
      hasProfile: false,
      matchScore: 0,
      matchText: '--',
      subtitle: '先测算可对比个人档案',
      currentPoints: [],
      targetPoints: [],
      elementRows: [],

    },
    energyChartSvgUrl: '',
    showEnergyPanel: false,
    showEnergyModal: false,
    showWristGuideModal: false,
    activeWristGuideTab: 'workspace',
    wristGuideTabs: WRIST_GUIDE_TABS_DISPLAY,
    wristMeasureGuideImageUrl: WRIST_MEASURE_GUIDE_IMAGE_URL,
    workspaceUsageGuide: WORKSPACE_USAGE_GUIDE_WITH_ICONS,
    showShareSheet: false,
    sharingDesign: false,
    sharedDesignLoading: false,
    sharedDesignFrozen: false,
    shareToken: '',
    shareDesignTitle: '宇涧水晶 DIY 手串方案',
    sharePreviewImage: '',
    sourceContext: null,
    summary: {
      count: 0,
      price: 0,
      priceText: '0.00',
      length: '0.0',
      currentWrist: '0.0',
      beadSizeText: '--',
      recommendedCount: 18,
      maxBeadCount: 19,
      weight: '0.00',
      maxLength: '16.8',
      warning: '',
      energy: []
    },
    lengthOverClass: ''
  },

  onLoad(query) {
    this.workspaceBootStartedAt = Date.now();
    this.workspaceReadyFlags = { layout: false, canvas: false, materials: false };
    this.armWorkspaceLoadingFallback();
    this.materialCatalog = DEFAULT_MATERIALS;
    this.rebuildMaterialLookup();
    this.filteredMaterialCatalog = [];
    this.flightQueue = [];
    this.flightActive = false;
    this.lastMaterialTapAt = 0;
    this.lastMaterialLongPress = { id: '', at: 0 };
    this.lastQueueToastAt = 0;
    this.physicsBodies = [];
    this.canvasRecoveryAttempts = 0;
    this.physicsFramePending = false;
    this.soundEnabled = true;
    this.audioPlayers = {};
    this.audioPlayerCursors = {};
    this.audioPlayersReady = false;
    this.interactionRuntimeWarmed = false;
    this.lastSoundAt = {};
    this.sourceContext = null;
    this.pendingBackendRecommendation = false;
    this.pendingBackendRecommendationRevision = 0;
    this.pendingRecommendedRecipe = false;
    this.pendingRecommendedRecipeRevision = 0;
    this.pendingSharedDesign = null;
    this.pendingShareToken = '';
    this.materialPayloadReady = false;
    this.workspaceDesignRevision = 0;
    this.activeWorkspaceImportId = '';
    this.materialPayloadVersion = '';
    this.lastMaterialRefreshAt = 0;
    this.workspaceHasShown = false;
    this.useServerMaterialPagination = true;
    this.materialPageState = { page: 0, pageSize: MATERIAL_PAGE_SIZE, total: 0, hasMore: false, key: '' };
    this.deferFirstShowProfileEnergy = true;
    this.historyStack = wx.getStorageSync('workspaceHistory') || [];
    this.redoStack = [];
    this.initDeviceLayout();
    this.initTrayTheme();
    this.initRememberedWristSize();
    this.initWorkspaceGuide();
    this.deferNonCriticalWorkspaceTasks();
    this.categoriesByTop = {};
    this.seriesByCategory = {};
    const shareToken = this.getShareTokenFromQuery(query);
    if (wx.showShareMenu) wx.showShareMenu({ menus: ['shareAppMessage'] });
    if (shareToken) {
      this.pendingShareToken = shareToken;
      this.loadSharedDesign(shareToken);
    } else if (query.preset === 'backend-recommended') {
      const importRevision = this.beginWorkspaceImportSession('query:backend-recommended');
      this.pendingBackendRecommendation = true;
      this.pendingBackendRecommendationRevision = importRevision;
      this.applyBackendRecommendation({ importRevision });
    } else if (query.preset === 'recommended') {
      const importRevision = this.beginWorkspaceImportSession('query:recommended');
      this.pendingRecommendedRecipe = true;
      this.pendingRecommendedRecipeRevision = importRevision;
      this.applyRecommendedRecipe({ importRevision });
    } else {
      this.loadDraft();
    }
    this.loadMaterials();
    this.wristPromptTimer = setTimeout(() => this.promptInitialWristSize(), 420);
  },

  armWorkspaceLoadingFallback() {
    clearTimeout(this.workspaceLoadingFallbackTimer);
    this.workspaceLoadingFallbackTimer = setTimeout(() => {
      this.finishWorkspaceLoading({ force: true });
    }, this.isLowPerformanceDevice ? 2400 : 1900);
  },

  markWorkspaceReady(flag) {
    if (!this.workspaceReadyFlags) {
      this.workspaceReadyFlags = { layout: false, canvas: false, materials: false };
    }
    if (flag) this.workspaceReadyFlags[flag] = true;
    this.finishWorkspaceLoading();
  },

  finishWorkspaceLoading(options = {}) {
    if (!this.data.workspaceLoading) return;
    // A shared composition must not be revealed one image at a time while its
    // bead assets are still warming up.
    if (this.data.sharedDesignLoading) return;
    const flags = this.workspaceReadyFlags || {};
    const ready = !!(flags.layout && flags.canvas && flags.materials);
    if (!options.force && !ready) return;
    clearTimeout(this.workspaceLoadingFallbackTimer);
    clearTimeout(this.workspaceLoadingDoneTimer);
    clearTimeout(this.workspaceLoadingHideTimer);
    const minDuration = this.isLowPerformanceDevice ? 820 : 620;
    const elapsed = Date.now() - Number(this.workspaceBootStartedAt || Date.now());
    const delay = Math.max(0, minDuration - elapsed);
    this.workspaceLoadingDoneTimer = setTimeout(() => {
      if (!this.data.workspaceLoading) return;
      this.setData({
        workspaceLoadingClass: 'leaving',
        workspaceLoadingText: '工作台已就绪',
        workspaceLoadingSubtext: '开始定制你的手串'
      });
      this.workspaceLoadingHideTimer = setTimeout(() => {
        this.setData({ workspaceLoading: false, workspaceLoadingClass: '' }, () => {
          this.maybeShowWorkspaceGuide();
        });
      }, 220);
    }, delay);
  },

  deferNonCriticalWorkspaceTasks() {
    clearTimeout(this.nonCriticalTaskTimer);
    this.nonCriticalTaskTimer = setTimeout(() => {
      this.loadProfileEnergy();
    }, this.isLowPerformanceDevice ? 520 : 260);
  },

  scheduleWorkspaceInteractionWarmup() {
    if (this.interactionRuntimeWarmed || this.interactionRuntimeWarmupTimer) return;
    this.interactionRuntimeWarmupTimer = setTimeout(() => {
      this.interactionRuntimeWarmupTimer = null;
      this.warmWorkspaceInteractionRuntime();
    }, this.isLowPerformanceDevice ? 90 : 40);
  },

  warmWorkspaceInteractionRuntime() {
    if (this.interactionRuntimeWarmed) return;
    try {
      this.ensurePhysicsRuntime();
      if (!this.physicsEngine && this.data.isLooseMode && !(this.data.selected || []).length) {
        this.createPhysicsEngine();
      }
    } catch (error) {
      logWorkspaceWarning('workspace physics warmup failed:', error && (error.message || error));
    }
    clearTimeout(this.audioRuntimeWarmupTimer);
    this.audioRuntimeWarmupTimer = setTimeout(() => {
      this.audioRuntimeWarmupTimer = null;
      try {
        this.ensureAudioPlayers();
      } catch (error) {
        logWorkspaceWarning('workspace audio warmup failed:', error && (error.message || error));
      }
      this.interactionRuntimeWarmed = true;
    }, this.isLowPerformanceDevice ? 80 : 40);
  },

  getShareTokenFromQuery(query = {}) {
    const raw = query.shareToken || query.share_token || '';
    if (!raw) return '';
    try {
      return decodeURIComponent(String(raw)).trim();
    } catch (error) {
      return String(raw).trim();
    }
  },

  async loadSharedDesign(shareToken) {
    if (!shareToken) return false;
    clearTimeout(this.workspaceLoadingFallbackTimer);
    clearTimeout(this.workspaceLoadingDoneTimer);
    clearTimeout(this.workspaceLoadingHideTimer);
    this.setData({
      sharedDesignLoading: true,
      workspaceLoading: true,
      workspaceLoadingClass: '',
      workspaceLoadingText: '正在打开分享方案',
      workspaceLoadingSubtext: '同步珠材与盘面...'
    });
    try {
      const sharedDesign = await getSharedDIYDesign(shareToken, { silent: true, timeout: 10000 });
      this.pendingSharedDesign = sharedDesign;
      this.pendingShareToken = shareToken;
      if (this.materialPayloadReady) {
        const applied = await this.ensurePendingMaterialDetails({ silent: true, keepPendingOnEmpty: true });
        if (applied) return true;
        return this.applySharedDesign(sharedDesign);
      }
      return false;
    } catch (error) {
      logWorkspaceWarning('load shared DIY design failed:', error);
      this.pendingSharedDesign = null;
      this.pendingShareToken = '';
      this.setData({ sharedDesignLoading: false, workspaceLoading: false, workspaceLoadingClass: '' });
      wx.showToast({ title: '分享方案暂时无法打开', icon: 'none' });
      this.loadDraft();
      return false;
    }
  },

  normalizeSharedDesignPayload(sharedDesign = {}) {
    const design = sharedDesign.design || {};
    const sequence = Array.isArray(sharedDesign.sequence)
      ? sharedDesign.sequence
      : (Array.isArray(design.sequence) ? design.sequence : []);
    const selectedFromDesign = Array.isArray(design.selected) ? design.selected : [];
    const selectedFromSequence = sequence
      .filter(item => !sequenceItemIsPendant(item || {}) && !sequenceItemIsBeadCap(item || {}))
      .map(item => item && (item.id || item.material_id || item.materialId || item.sku || item.skuId || item.sku_id))
      .filter(Boolean);
    const selected = (selectedFromDesign.length ? selectedFromDesign : selectedFromSequence)
      .map(id => String(id))
      .filter(Boolean);
    const sequencePlacements = sequence.map(item => item && item.placement).filter(Boolean);
    const placements = Array.isArray(design.placements) && design.placements.length
      ? design.placements
      : sequencePlacements;
    const attachedPendants = [];
    const summary = design.summary || {};
    const sourceContext = design.sourceContext || design.source_context || {
      source: 'shared_design',
      source_label: '分享方案',
      title: (summary && summary.name) || '好友分享方案',
      design_id: ''
    };
    return {
      ...design,
      designId: '',
      design_id: '',
      userId: '',
      user_id: '',
      selected,
      placements,
      attachedPendants,
      wristSize: Number(design.wristSize || design.wrist_size || summary.wristSize || 16) || 16,
      wearStyle: 'single',
      isLooseMode: design.isLooseMode === true,
      workspaceStageCenter: Number(design.workspaceStageCenter || design.workspace_stage_center || 0) || 0,
      sourceContext,
      summary: {
        ...summary,
        count: selected.length || summary.count || sequence.length || 0
      },
      sequence
    };
  },

  async applySharedDesign(sharedDesign = {}, options = {}) {
    if (!this.materialPayloadReady) return false;
    const normalized = this.normalizeSharedDesignPayload(sharedDesign);
    const selected = this.resolveSharedDesignSelectedIds(normalized);
    if (!selected.length) {
      if (!options.keepPendingOnEmpty) {
        this.pendingSharedDesign = null;
        this.pendingShareToken = '';
      }
      this.setData({ sharedDesignLoading: false });
      if (!options.silent) wx.showToast({ title: '分享方案缺少可用珠材', icon: 'none' });
      return false;
    }
    const sourceContext = normalized.sourceContext || {
      source: 'shared_design',
      source_label: '分享方案',
      design_id: normalized.designId || ''
    };
    const placements = this.scaleSharedPlacementsForStage(
      this.normalizePlacements(selected, normalized.placements),
      normalized.workspaceStageCenter
    );
    await this.preloadSharedDesignImages(placements);
    const draft = {
      ...normalized,
      selected,
      placements,
      attachedPendants: [],
      sourceContext,
      isSharedDesign: true
    };
    this.pendingSharedDesign = null;
    const activeShareToken = this.pendingShareToken || '';
    this.pendingShareToken = '';
    this.sourceContext = sourceContext;
    wx.setStorageSync('currentDesign', draft);
    wx.setStorageSync('workspaceWristConfirmed', true);
    this.resetWorkspaceRuntime();
    this.setData({
      selected,
      placements,
      attachedPendants: [],
      wristSize: normalized.wristSize,
      wearStyle: 'single',
      isLooseMode: normalized.isLooseMode,
      sourceContext,
      selectedBeadIndex: -1,
      showTip: false,
      canvasFlightActive: false,
      flightBead: null,
      launchingMaterialId: '',
      isShuffling: false,
      isStringingFinishing: false,
      isReleasingString: false,
      draggingBeadIndex: -1,
      dragDeleteArmed: false,
      sharedDesignLoading: false,
      sharedDesignFrozen: normalized.isLooseMode,
      workspaceLoading: false,
      workspaceLoadingClass: '',
      shareToken: activeShareToken,
      shareDesignTitle: this.buildShareDesignTitle(draft),
      sharePreviewImage: draft.preview_image || draft.previewImage || draft.image_url || ''
    });
    this.recalculate();
    if (!options.silent) wx.showToast({ title: '已打开分享方案', icon: 'success' });
    return true;
  },

  scaleSharedPlacementsForStage(placements = [], sourceCenter = 0) {
    const senderCenter = Number(sourceCenter);
    const receiverCenter = Number(this.getStageLayout().center);
    if (!Number.isFinite(senderCenter) || senderCenter <= 0 || !Number.isFinite(receiverCenter) || receiverCenter <= 0) {
      return placements;
    }
    const scale = receiverCenter / senderCenter;
    if (!Number.isFinite(scale) || Math.abs(scale - 1) < 0.001) return placements;
    return placements.map(placement => {
      const next = { ...placement };
      if (Number.isFinite(next.looseX)) next.looseX = receiverCenter + (next.looseX - senderCenter) * scale;
      if (Number.isFinite(next.looseY)) next.looseY = receiverCenter + (next.looseY - senderCenter) * scale;
      if (Number.isFinite(next.dx)) next.dx *= scale;
      if (Number.isFinite(next.dy)) next.dy *= scale;
      return next;
    });
  },

  preloadSharedDesignImages(placements = []) {
    const urls = Array.from(new Set((placements || [])
      .map(item => String(item && item.image_url || '').trim())
      .filter(Boolean)));
    if (!urls.length || !wx.getImageInfo) return Promise.resolve();
    let cursor = 0;
    const preloadOne = url => new Promise(resolve => {
      if (this.hasMaterialImagePreloadRecord(url)) {
        resolve();
        return;
      }
      this.rememberMaterialImagePreload(url, 'loading');
      let settled = false;
      const timeout = setTimeout(() => {
        done('timed_out');
      }, SHARED_DESIGN_IMAGE_PRELOAD_TIMEOUT_MS);
      const done = status => {
        if (settled) return;
        settled = true;
        clearTimeout(timeout);
        this.rememberMaterialImagePreload(url, status);
        resolve();
      };
      try {
        wx.getImageInfo({
          src: url,
          success: () => done('loaded'),
          fail: () => done('failed')
        });
      } catch (error) {
        done('failed');
      }
    });
    const worker = async () => {
      while (cursor < urls.length) {
        const url = urls[cursor];
        cursor += 1;
        await preloadOne(url);
      }
    };
    return Promise.all(Array.from(
      { length: Math.min(SHARED_DESIGN_IMAGE_PRELOAD_CONCURRENCY, urls.length) },
      () => worker()
    ));
  },

  onReady() {
    this.initWorkspaceCanvases();
  },

  initDeviceLayout(options = {}) {
    const info = getWorkspaceSystemInfo();
    const windowWidth = Number(info.windowWidth) || 375;
    const windowHeight = Number(info.windowHeight) || 667;
    const benchmarkLevel = Number(info.benchmarkLevel);
    const isRealDevice = info.platform && info.platform !== 'devtools';
    const isLowPerformanceDevice = isRealDevice
      && benchmarkLevel > 0
      && benchmarkLevel < 15;
    const screenHeight = Number(info.screenHeight) || windowHeight;
    const statusBarHeight = Number(info.statusBarHeight) || 0;
    const safeArea = info.safeArea || {};
    const bottomInset = safeArea.bottom ? Math.max(0, screenHeight - safeArea.bottom) : 0;
    const rpxRatio = 750 / windowWidth;
    const viewportRpx = Math.round(windowHeight * rpxRatio);
    const screenRpx = Math.round(screenHeight * rpxRatio);
    const bottomInsetRpx = Math.round(bottomInset * rpxRatio);
    const aspectRatio = windowHeight / windowWidth;
    const screenAspectRatio = screenHeight / windowWidth;
    const classes = ['device-regular'];
    if (windowWidth <= 340) classes.push('device-narrow');
    if (windowHeight <= 720) classes.push('device-short');
    if (windowHeight <= 780) classes.push('device-compact');
    if (aspectRatio >= 2.05 || screenAspectRatio >= 2.05) classes.push('device-tall');
    if (windowWidth >= 414) classes.push('device-wide');
    if (bottomInset > 0) classes.push('device-safe-bottom');
    if (statusBarHeight >= 40) classes.push('device-deep-status');
    if (isRealDevice) classes.push('device-real');
    if (isLowPerformanceDevice) classes.push('device-low-performance');
    this.isRealDevice = isRealDevice;
    this.isLowPerformanceDevice = isLowPerformanceDevice;
    if (this.data.workspaceLoading) this.armWorkspaceLoadingFallback();
    this.physicsStepMs = isLowPerformanceDevice ? 34 : (isRealDevice ? 20 : 1000 / 60);
    this.physicsTimerInterval = isLowPerformanceDevice ? 34 : (isRealDevice ? 20 : 16);
    this.physicsRenderInterval = isLowPerformanceDevice ? 58 : (isRealDevice ? 34 : 24);
    this.materialPageSize = isLowPerformanceDevice ? 16 : 24;
    this.physicsFrameSequence = 0;
    const workspaceLayout = this.buildResponsiveWorkspaceLayout({
      windowWidth,
      windowHeight,
      screenHeight,
      viewportRpx,
      screenRpx,
      bottomInsetRpx,
      aspectRatio,
      screenAspectRatio
    });
    this.stageLayout = workspaceLayout.stageLayout;
    this.energyPanelRect = workspaceLayout.energyPanelRect;
    this.setData({
      deviceClass: classes.join(' '),
      deviceInfo: {
        windowWidth,
        windowHeight,
        screenHeight,
        screenRpx,
        statusBarHeight,
        bottomInset,
        aspectRatio,
        screenAspectRatio,
        benchmarkLevel: benchmarkLevel || 0,
        isRealDevice,
        isLowPerformanceDevice
      },
      workspaceLayoutStyle: workspaceLayout.style,
      canUndo: this.historyStack.length > 0,
      canRedo: options.preserveActionState ? this.data.canRedo : false
    }, () => {
      this.markWorkspaceReady('layout');
    });
  },

  initTrayTheme() {
    const stored = wx.getStorageSync(TRAY_THEME_STORAGE_KEY);
    const activeTheme = this.getTrayThemeConfig(stored) || TRAY_THEMES[0];
    this.setData({
      trayTheme: activeTheme.value,
      trayImageUrl: activeTheme.imageUrl,
      trayThemeItems: this.buildTrayThemeItems(activeTheme.value)
    });
  },

  getTrayThemeConfig(theme) {
    return TRAY_THEMES.find(item => item.value === theme);
  },

  buildTrayThemeItems(activeTheme = this.data.trayTheme || 'white') {
    return TRAY_THEMES.map(item => ({
      ...item,
      activeClass: item.value === activeTheme ? 'active' : ''
    }));
  },

  applyTrayTheme(trayTheme) {
    const activeTheme = this.getTrayThemeConfig(trayTheme);
    if (!activeTheme) return false;
    if (trayTheme === this.data.trayTheme) return false;
    wx.setStorageSync(TRAY_THEME_STORAGE_KEY, trayTheme);
    this.setData({
      trayTheme,
      trayImageUrl: activeTheme.imageUrl,
      trayThemeItems: this.buildTrayThemeItems(trayTheme),
      trayImageFailed: false
    }, () => this.scheduleCanvasRender());
    return true;
  },

  cycleTrayTheme() {
    const activeIndex = TRAY_THEMES.findIndex(item => item.value === this.data.trayTheme);
    const nextTheme = TRAY_THEMES[(activeIndex + 1 + TRAY_THEMES.length) % TRAY_THEMES.length];
    this.applyTrayTheme(nextTheme.value);
  },

  selectTrayTheme(e) {
    const trayTheme = e.currentTarget.dataset.theme;
    this.applyTrayTheme(trayTheme);
  },

  getRememberedWristSize() {
    const stored = Number(wx.getStorageSync(WORKSPACE_WRIST_SIZE_STORAGE_KEY));
    if (!Number.isFinite(stored) || stored <= 0) return 0;
    return this.normalizeWristValue(stored);
  },

  initRememberedWristSize() {
    const wristSize = this.getRememberedWristSize();
    if (!wristSize) return;
    this.setData({ wristSize });
  },

  rememberWristSize(wristSize) {
    const normalized = this.normalizeWristValue(wristSize);
    try {
      wx.setStorageSync(WORKSPACE_WRIST_SIZE_STORAGE_KEY, normalized);
      wx.setStorageSync('workspaceWristConfirmed', true);
    } catch (error) {
      logWorkspaceWarning('remember wrist size failed:', error);
    }
    return normalized;
  },

  getTrayPalette(theme = this.data.trayTheme || 'warm') {
    if (theme === 'black') {
      return this.getSmoothTrayPalette({
        plateStops: [
          [0, '#2c2c2a'],
          [0.18, '#282827'],
          [0.32, '#242424'],
          [0.46, '#202020'],
          [0.60, '#1d1d1c'],
          [0.72, '#1a1a19'],
          [0.84, '#171716'],
          [0.93, '#141413'],
          [1, '#10100f']
        ],
        stroke: 'rgba(205,165,93,0.30)',
        centerStroke: 'rgba(205,165,93,0.22)',
        noiseAlpha: 0.018
      });
    }
    if (theme === 'warm') {
      return this.getSmoothTrayPalette({
        plateStops: [
          [0, '#ffffff'],
          [0.18, '#fffefd'],
          [0.32, '#fcfaf6'],
          [0.46, '#f8f4ee'],
          [0.60, '#f3eee5'],
          [0.72, '#eee6db'],
          [0.84, '#e7ded0'],
          [0.93, '#ded3c4'],
          [1, '#d4c8b9']
        ],
        stroke: 'rgba(104,101,91,0.16)',
        centerStroke: 'rgba(86,84,76,0.18)',
        noiseAlpha: 0.016
      });
    }
    return this.getSmoothTrayPalette();
  },

  getSmoothTrayPalette(options = {}) {
    const plateStops = options.plateStops || [
      [0, '#ffffff'],
      [0.20, '#ffffff'],
      [0.34, '#ffffff'],
      [0.48, '#fefefe'],
      [0.60, '#fdfdfd'],
      [0.70, '#fbfbfb'],
      [0.80, '#f8f8f8'],
      [0.88, '#f4f4f4'],
      [0.95, '#eeeeee'],
      [1, '#e9e9e9']
    ];
    return {
      page: '#ffffff',
      plateStops,
      inner0: plateStops[0][1],
      inner1: plateStops[Math.floor(plateStops.length / 2)][1],
      outer: plateStops[plateStops.length - 1][1],
      stroke: options.stroke || 'rgba(104,101,91,0.10)',
      centerStroke: options.centerStroke || 'rgba(86,84,76,0.12)',
      noiseAlpha: options.noiseAlpha || 0.014
    };
  },

  buildResponsiveWorkspaceLayout({ windowWidth, windowHeight, viewportRpx, bottomInsetRpx }) {
    const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
    const lerp = (from, to, progress) => from + (to - from) * clamp(progress, 0, 1);
    const widthRoom = clamp((windowWidth - 320) / 120, 0, 1);
    const heightRoom = clamp((viewportRpx - 1320) / 360, 0, 1);
    const layoutRoom = clamp(widthRoom * 0.45 + heightRoom * 0.55, 0, 1);
    const topChrome = 122;
    const summaryHeight = Math.round(lerp(72, 78, layoutRoom));
    const colorTop = summaryHeight + Math.round(lerp(8, 14, layoutRoom));
    const colorBlockHeight = 0;
    const stageGapTop = Math.round(lerp(8, 16, heightRoom));
    const stageTop = colorTop + colorBlockHeight + stageGapTop;
    const visualScale = 1.18;
    const drawerMin = Math.round(lerp(400, 560, heightRoom));
    const drawerPreferredMax = Math.round(lerp(650, 760, heightRoom));
    const drawerGap = Math.round(lerp(14, 22, layoutRoom));
    const maxStageByWidth = Math.round(lerp(650, 706, widthRoom));
    const minStage = Math.round(lerp(520, 650, heightRoom));
    const maxStageByHeight = (viewportRpx - topChrome - drawerMin - stageTop - drawerGap) / visualScale;
    let stageSize = Math.round(clamp(maxStageByHeight, minStage, maxStageByWidth));
    if (maxStageByHeight < minStage) {
      stageSize = Math.max(420, Math.round(maxStageByHeight));
    }
    const trayVisualSize = stageSize * 1.26;
    const trayVisualLeft = (750 - stageSize) / 2 - stageSize * 0.13;
    const trayVisualTop = stageTop - stageSize * 0.13;
    const plateToolWidth = Math.round(lerp(58, 62, layoutRoom));
    const plateToolHeight = plateToolWidth;
    const plateToolGap = Math.round(lerp(18, 22, layoutRoom));
    const shareToolSize = plateToolWidth;
    const wristGuideWidth = shareToolSize;
    const wristGuideHeight = shareToolSize;
    const undoButtonSize = plateToolWidth;
    const wristButtonWidth = Math.round(lerp(154, 164, layoutRoom));
    const wristButtonHeight = plateToolHeight;
    const leftStackGap = Math.round(lerp(18, 20, layoutRoom));
    const randomButtonWidth = Math.round(lerp(172, 188, layoutRoom));
    const randomButtonHeight = Math.round(lerp(58, 64, layoutRoom));
    const actionDrawerGap = Math.round(lerp(10, 12, layoutRoom));
    const randomButtonTrayOverlap = 0.72;
    const themeWidth = wristButtonWidth;
    const themeHeight = wristButtonHeight;
    const preferredRandomButtonTop = Math.round(trayVisualTop + trayVisualSize - randomButtonHeight * randomButtonTrayOverlap);
    const preferredDrawerTop = preferredRandomButtonTop + randomButtonHeight + actionDrawerGap;
    const idealDrawerHeight = viewportRpx - topChrome - preferredDrawerTop;
    const adaptiveDrawerMax = Math.max(drawerPreferredMax, idealDrawerHeight);
    const baseDrawerHeight = Math.round(clamp(idealDrawerHeight, drawerMin, adaptiveDrawerMax));
    const drawerTopInCanvas = Math.max(360, viewportRpx - topChrome - baseDrawerHeight);
    const safeBottom = clamp(Number(bottomInsetRpx) || 0, 0, 88);
    // Start the material drawer below every workbench action. Its safe-area
    // inset remains internal, so neither large screens nor home indicators can
    // lift the drawer over the tray controls.
    const drawerHeight = baseDrawerHeight;
    const railWidth = 90;
    const railSide = Math.round(lerp(10, 14, widthRoom));
    const railGap = Math.round(lerp(14, 18, layoutRoom));
    const toolItemHeight = Math.round(lerp(94, 100, layoutRoom));
    const leftRailHeight = Math.round(clamp(
      stageSize * 0.76,
      toolItemHeight * 2 + railGap,
      stageSize * 0.86
    ));
    const rightRailHeight = Math.round(clamp(
      stageSize * 0.74,
      toolItemHeight * 3 + railGap * 2,
      stageSize * 0.80
    ));
    const minRailTop = colorTop + colorBlockHeight + 12;
    const leftRailTop = Math.round(clamp(
      stageTop + stageSize * lerp(0.14, 0.15, layoutRoom),
      minRailTop,
      Math.max(minRailTop, drawerTopInCanvas - leftRailHeight - 16)
    ));
    const rightRailTop = Math.round(clamp(
      stageTop + stageSize * lerp(0.17, 0.18, layoutRoom),
      minRailTop,
      Math.max(minRailTop, drawerTopInCanvas - rightRailHeight - 16)
    ));
    const leftToolLeft = Math.round(clamp(
      trayVisualLeft + trayVisualSize * 0.10 - undoButtonSize * 0.5,
      24,
      116
    ));
    const wristToolLeft = Math.round(clamp(
      leftToolLeft,
      18,
      750 - wristButtonWidth - 18
    ));
    const leftOneTop = Math.round(clamp(
      trayVisualTop + trayVisualSize * 0.80,
      stageTop + stageSize * 0.56,
      drawerTopInCanvas - undoButtonSize - wristButtonHeight - themeHeight - leftStackGap * 2 - 20
    ));
    const leftTwoTop = leftOneTop + undoButtonSize + leftStackGap;
    const themeLeft = wristToolLeft;
    const themeTop = leftTwoTop + wristButtonHeight + leftStackGap;
    const trayVisualCenterX = trayVisualLeft + trayVisualSize / 2;
    const trayVisualCenterY = trayVisualTop + trayVisualSize / 2;
    const shareToolRadius = trayVisualSize / 2 + lerp(8, 10, layoutRoom);
    const shareToolLeft = Math.round(clamp(
      trayVisualCenterX + shareToolRadius * 0.70 - shareToolSize / 2,
      510,
      750 - shareToolSize - Math.round(lerp(26, 30, layoutRoom))
    ));
    const shareToolTop = Math.round(clamp(
      trayVisualCenterY - shareToolRadius * 0.70 - shareToolSize / 2,
      colorTop + 10,
      leftOneTop - shareToolSize - 24
    ));
    const wristGuideLeft = Math.round(clamp(
      750 - shareToolLeft - wristGuideWidth,
      Math.round(lerp(18, 24, layoutRoom)),
      trayVisualCenterX - wristGuideWidth - 84
    ));
    const wristGuideTop = shareToolTop;
    const rightToolLeft = Math.round(clamp(
      750 - plateToolWidth - Math.round(lerp(22, 28, layoutRoom)),
      24,
      750 - plateToolWidth - 20
    ));
    const rightOneTop = leftOneTop;
    const rightTwoTop = leftTwoTop;
    const rightThreeTop = themeTop;
    const randomButtonLeft = Math.round((750 - randomButtonWidth) / 2);
    const randomButtonTop = Math.round(drawerTopInCanvas - randomButtonHeight - actionDrawerGap);
    const toolHeight = toolItemHeight;
    const toolGap = railGap;
    const stageToolGap = drawerGap;
    const canvasHeight = Math.round(drawerTopInCanvas);
    const stageCenter = Math.round(stageSize / 2);
    const stageRadius = Math.round(stageSize * 0.57);
    return {
      stageLayout: {
        center: stageCenter,
        radius: stageRadius,
        size: stageSize,
        top: stageTop
      },
      energyPanelRect: {
        top: topChrome + colorTop - 18,
        left: railSide + railWidth + 18,
        width: 750 - (railSide + railWidth + 18) - 170,
        height: 66
      },
      style: [
        `--workspace-canvas-height:${canvasHeight}rpx`,
        `--workspace-top-chrome:${topChrome}rpx`,
        `--workspace-stage-top:${stageTop}rpx`,
        `--workspace-stage-size:${stageSize}rpx`,
        `--workspace-drawer-height:${drawerHeight}rpx`,
        `--workspace-color-top:${colorTop}rpx`,
        `--workspace-left-rail-top:${leftRailTop}rpx`,
        `--workspace-right-rail-top:${rightRailTop}rpx`,
        `--workspace-rail-side:${railSide}rpx`,
        `--workspace-rail-width:${railWidth}rpx`,
        `--workspace-rail-gap:${railGap}rpx`,
        `--workspace-left-rail-height:${leftRailHeight}rpx`,
        `--workspace-right-rail-height:${rightRailHeight}rpx`,
        `--workspace-tool-item-height:${toolItemHeight}rpx`,
        `--workspace-theme-left:${themeLeft}rpx`,
        `--workspace-theme-top:${themeTop}rpx`,
        `--workspace-theme-width:${themeWidth}rpx`,
        `--workspace-theme-height:${themeHeight}rpx`,
        `--workspace-plate-tool-width:${plateToolWidth}rpx`,
        `--workspace-plate-tool-height:${plateToolHeight}rpx`,
        `--workspace-wrist-guide-left:${wristGuideLeft}rpx`,
        `--workspace-wrist-guide-top:${wristGuideTop}rpx`,
        `--workspace-wrist-guide-width:${wristGuideWidth}rpx`,
        `--workspace-wrist-guide-height:${wristGuideHeight}rpx`,
        `--workspace-share-tool-left:${shareToolLeft}rpx`,
        `--workspace-share-tool-top:${shareToolTop}rpx`,
        `--workspace-share-tool-size:${shareToolSize}rpx`,
        `--workspace-undo-button-size:${undoButtonSize}rpx`,
        `--workspace-wrist-button-width:${wristButtonWidth}rpx`,
        `--workspace-wrist-button-height:${wristButtonHeight}rpx`,
        `--workspace-left-tool-left:${leftToolLeft}rpx`,
        `--workspace-wrist-tool-left:${wristToolLeft}rpx`,
        `--workspace-left-one-top:${leftOneTop}rpx`,
        `--workspace-left-two-top:${leftTwoTop}rpx`,
        `--workspace-right-tool-left:${rightToolLeft}rpx`,
        `--workspace-right-one-top:${rightOneTop}rpx`,
        `--workspace-right-two-top:${rightTwoTop}rpx`,
        `--workspace-right-three-top:${rightThreeTop}rpx`,
        `--workspace-random-left:${randomButtonLeft}rpx`,
        `--workspace-random-top:${randomButtonTop}rpx`,
        `--workspace-random-width:${randomButtonWidth}rpx`,
        `--workspace-random-height:${randomButtonHeight}rpx`,
        `--workspace-tool-bottom:${baseDrawerHeight + toolGap}rpx`,
        `--workspace-tool-height:${toolHeight}rpx`,
        `--workspace-tool-gap:${toolGap}rpx`,
        `--workspace-stage-tool-gap:${stageToolGap}rpx`,
        `--workspace-safe-bottom:${safeBottom}rpx`
      ].join(';')
    };
  },

  async loadMaterialsLegacy() {
    let cachedPayload = null;
    this.setData({ materialsLoading: true, materialsErrorText: '' });
    if (materialCache && Date.now() - materialCacheAt < MATERIAL_CACHE_TTL) {
      cachedPayload = materialCache;
      this.applyMaterialPayload(cachedPayload, { keepLoading: true });
    }
    if (!cachedPayload) {
      const stored = await new Promise(resolve => {
        wx.getStorage({
          key: MATERIAL_CACHE_KEY,
          success: result => resolve(result.data || null),
          fail: () => resolve(null)
        });
      });
      if (stored && stored.payload && Date.now() - Number(stored.savedAt || 0) < MATERIAL_CACHE_TTL) {
        cachedPayload = stored.payload;
        materialCache = cachedPayload;
        materialCacheAt = Number(stored.savedAt) || Date.now();
        this.applyMaterialPayload(cachedPayload, { keepLoading: true });
      }
    }
    try {
      const data = await getMaterials({ silent: true, timeout: 8000 });
      const optimized = this.optimizeMaterialPayload(data);
      const serverVersion = optimized.version || optimized.updated_at || '';
      const cachedVersion = cachedPayload && (cachedPayload.version || cachedPayload.updated_at || '');
      materialCache = optimized;
      materialCacheAt = Date.now();
      wx.setStorage({
        key: MATERIAL_CACHE_KEY,
        data: { savedAt: materialCacheAt, payload: optimized }
      });
      if (!cachedPayload || serverVersion !== cachedVersion) {
        this.applyMaterialPayload(optimized);
      } else {
        this.setData({ materialsLoading: false, materialsErrorText: '' }, () => this.markWorkspaceReady('materials'));
      }
    } catch (error) {
      logWorkspaceWarning('load materials fallback:', error.message || error);
      this.setData({
        materialsLoading: false,
        materialsErrorText: cachedPayload ? '已使用本地缓存，最新珠材稍后自动同步' : '珠材加载失败，请稍后重试'
      }, () => this.markWorkspaceReady('materials'));
    }
  },

  loadMaterials(options = {}) {
    return this.loadMaterialPage(1, { reset: true, useStorage: true, ...options });
  },

  isAllFilterValue(value) {
    return !value || LEGACY_ALL_OPTION_LABELS.includes(value);
  },

  materialRequestFilters() {
    const keyword = this.normalizeMaterialSearchKeyword(this.data.materialSearchKeyword);
    return {
      top: this.data.activeTop || 'bead',
      category: this.isAllFilterValue(this.data.activeCategory) ? '' : this.data.activeCategory,
      series: this.isAllFilterValue(this.data.activeSeries) ? '' : this.data.activeSeries,
      keyword
    };
  },

  materialRequestKey(page = 1) {
    const filters = this.materialRequestFilters();
    return [
      filters.top || '',
      filters.category || '',
      filters.series || '',
      filters.keyword || '',
      page,
      this.materialPageSize || MATERIAL_PAGE_SIZE
    ].join('::');
  },

  async readStoredMaterialPage(cacheKey) {
    const stored = await new Promise(resolve => {
      wx.getStorage({
        key: MATERIAL_CACHE_KEY,
        success: result => resolve(result.data || null),
        fail: () => resolve(null)
      });
    });
    if (!stored || !stored.pages || !stored.pages[cacheKey]) return null;
    const entry = stored.pages[cacheKey];
    if (Date.now() - Number(entry.savedAt || 0) >= MATERIAL_CACHE_TTL) return null;
    return entry.payload || null;
  },

  storeMaterialPage(cacheKey, payload) {
    materialCache[cacheKey] = payload;
    materialCacheAt[cacheKey] = Date.now();
    if (!payload || cacheKey.indexOf('::1::') === -1) return;
    wx.getStorage({
      key: MATERIAL_CACHE_KEY,
      complete: result => {
        const stored = result && result.data && result.data.pages ? result.data : { pages: {} };
        stored.pages[cacheKey] = { savedAt: materialCacheAt[cacheKey], payload };
        const keys = Object.keys(stored.pages).slice(-8);
        stored.pages = keys.reduce((pages, key) => {
          pages[key] = stored.pages[key];
          return pages;
        }, {});
        wx.setStorage({ key: MATERIAL_CACHE_KEY, data: stored });
      }
    });
  },

  materialPagePayloadSignature(payload = {}) {
    const pagination = payload.pagination || {};
    const materials = (payload.materials || []).map(item => {
      const physical = resolveMaterialGeometry(item);
      return [
        item.id || '',
        item.skuId || item.sku_id || '',
        item.material_code || '',
        item.name || '',
        item.series || '',
        item.category || '',
        item.image_url || '',
        item.size || '',
        item.price || '',
        item.grade || '',
        physical.shape,
        physical.placementMode,
        physical.imageStringAxisDeg,
        physical.stringAxisWidthMm,
        physical.bodyWidthMm,
        physical.bodyHeightMm
      ].join('~');
    });
    return JSON.stringify({
      version: payload.version || payload.updated_at || '',
      page: pagination.page || '',
      pageSize: pagination.page_size || '',
      total: pagination.total || '',
      hasMore: !!pagination.has_more,
      materials,
      topTabs: (payload.top_tabs || []).map(item => `${item.key || ''}:${item.label || ''}`),
      categories: payload.categories_by_top || {},
      series: payload.series_by_category || {}
    });
  },

  async loadMaterialPage(page = 1, options = {}) {
    const reset = options.reset !== false && page === 1;
    const cacheKey = this.materialRequestKey(page);
    const currentKey = this.materialRequestKey(1);
    if (this.materialPageRequesting === cacheKey && !options.force) return;
    this.materialPageRequesting = cacheKey;
    if (reset) {
      this.materialPageState = {
        page: 0,
        pageSize: this.materialPageSize || MATERIAL_PAGE_SIZE,
        total: 0,
        hasMore: false,
        key: currentKey
      };
      if (!options.background) {
        this.setData({
          visibleMaterials: [],
          hasMoreMaterials: false,
          materialsLoading: true,
          materialsLoadingMore: false,
          materialsErrorText: ''
        });
      }
    } else {
      this.setData({ materialsLoadingMore: true, materialsErrorText: '' });
    }

    let cachedPayload = null;
    let cachedPayloadSignature = '';
    let cachedAppendBaseMaterials = null;
    if (!options.force && materialCache[cacheKey] && Date.now() - Number(materialCacheAt[cacheKey] || 0) < MATERIAL_CACHE_TTL) {
      cachedPayload = materialCache[cacheKey];
      cachedPayloadSignature = this.materialPagePayloadSignature(cachedPayload);
      if (!reset) cachedAppendBaseMaterials = (this.data.visibleMaterials || []).slice();
      this.applyPagedMaterialPayload(cachedPayload, {
        append: !reset,
        keepLoading: true,
        fromCache: true,
        autoTargetSearch: options.autoTargetSearch
      });
    } else if (!options.force && options.useStorage && page === 1) {
      cachedPayload = await this.readStoredMaterialPage(cacheKey);
      if (cachedPayload) {
        if (this.materialPageRequesting !== cacheKey) return;
        materialCache[cacheKey] = cachedPayload;
        materialCacheAt[cacheKey] = Date.now();
        cachedPayloadSignature = this.materialPagePayloadSignature(cachedPayload);
        this.applyPagedMaterialPayload(cachedPayload, {
          append: false,
          keepLoading: true,
          fromCache: true,
          autoTargetSearch: options.autoTargetSearch
        });
      }
    }

    try {
      const filters = this.materialRequestFilters();
      const data = await getMaterials({
        ...filters,
        page,
        pageSize: this.materialPageSize || MATERIAL_PAGE_SIZE,
        slim: true,
        silent: true,
        timeout: reset ? 6500 : 8000
      });
      if (this.materialPageRequesting !== cacheKey) return;
      const optimized = this.optimizeMaterialPayload(data);
      this.lastMaterialRefreshAt = Date.now();
      this.storeMaterialPage(cacheKey, optimized);
      if (cachedPayload && cachedPayloadSignature === this.materialPagePayloadSignature(optimized)) {
        this.setData({
          materialsLoading: false,
          materialsLoadingMore: false,
          materialsErrorText: ''
        }, () => this.markWorkspaceReady('materials'));
        return;
      }
      this.applyPagedMaterialPayload(optimized, {
        append: !reset,
        appendBaseMaterials: cachedAppendBaseMaterials,
        autoTargetSearch: options.autoTargetSearch
      });
    } catch (error) {
      logWorkspaceWarning('load materials fallback:', error.message || error);
      if (options.background) return;
      this.setData({
        materialsLoading: false,
        materialsLoadingMore: false,
        materialsErrorText: cachedPayload ? '已使用本地缓存，最新珠材稍后自动同步' : '珠材加载失败，请稍后重试'
      }, () => this.markWorkspaceReady('materials'));
    } finally {
      if (this.materialPageRequesting === cacheKey) this.materialPageRequesting = '';
    }
  },

  optimizeMaterialPayload(data) {
    return {
      ...data,
      materials: (data.materials || []).map(item => {
        const material = this.normalizeMaterialContract(item);
        const imageUrls = (material.image_urls || material.image_pool || [])
          .map(url => this.optimizeImageUrl(url))
          .filter(Boolean);
        return {
          ...material,
          image_url: this.optimizeImageUrl(material.image_url),
          image_urls: imageUrls,
          image_pool: imageUrls
        };
      })
    };
  },

  normalizeMaterialContract(item = {}) {
    const sku = item.sku || {};
    const energy = item.energy || {};
    const visual = item.visual || {};
    const rules = item.rules || {};
    const asset = visual.asset || item.asset || {};
    const imageUrls = visual.image_urls || item.image_urls || item.image_pool || [];
    const rawEffects = energy.effects || item.effects || [];
    const effects = (Array.isArray(rawEffects) ? rawEffects : [rawEffects])
      .map(safeMaterialDisplayText)
      .filter(Boolean);
    const top = sku.top || item.top;
    const contributesEnergy = materialContributesEnergy({ ...item, sku, top });
    const primaryElement = contributesEnergy ? (energy.primary_element || item.primary_element || item.element || '') : '';
    const elementKey = contributesEnergy ? normalizeElementKey(primaryElement) : '';
    const normalizedEnergy = contributesEnergy
      ? energy
      : { ...energy, primary_element: '', secondary_elements: [] };
    const materialParams = {
      ...(item.material_params || {}),
      ...(visual.material_params || {}),
      ...(item.physical_specs || {})
    };
    const normalized = {
      ...item,
      sku,
      energy: normalizedEnergy,
      visual,
      rules,
      id: sku.id || item.id,
      skuId: sku.sku_id || item.skuId || item.sku_id,
      material_code: sku.material_code || item.material_code,
      top,
      category: repairMaybeMojibakeText(sku.category || item.category),
      series: repairMaybeMojibakeText(sku.series || item.series),
      grade: repairMaybeMojibakeText(sku.grade || item.grade),
      name: repairMaybeMojibakeText(sku.name || item.name),
      description: safeMaterialDisplayText(
        sku.description
        || item.description
        || item.introduction
        || visual.description
        || ''
      ),
      story: safeMaterialDisplayText(sku.story || item.story || visual.story || ''),
      price: Number(sku.price_per_bead ?? item.price ?? 0),
      size: Number(sku.size_mm ?? item.size ?? 8),
      weight: Number(sku.weight_g ?? item.weight ?? 1),
      stock: Number(sku.stock ?? item.stock ?? 0),
      enabled: sku.enabled ?? item.enabled,
      sort_order: Number(sku.sort_order ?? item.sort_order ?? item.sortOrder ?? 0),
      element: primaryElement,
      primary_element: primaryElement,
      element_key: elementKey,
      secondary_elements: contributesEnergy ? (energy.secondary_elements || item.secondary_elements || []) : [],
      effects,
      effect: effects.join(' / '),
      chakras: energy.chakras || item.chakras || [],
      wish_pools: energy.wish_pools || item.wish_pools || [],
      color: visual.color_hex || item.color,
      shine: visual.shine_hex || item.shine,
      image_url: visual.thumbnail_url || asset.thumbnail_url || item.thumbnail_url || item.image_url,
      image_urls: imageUrls,
      image_pool: imageUrls,
      allowed_roles: rules.allowed_roles || item.allowed_roles || [],
      material_params: materialParams,
      string_axis_width_mm: Number(
        materialParams.string_axis_width_mm
        || item.string_axis_width_mm
        || 0
      )
    };
    const physical = resolveMaterialGeometry(normalized);
    const isAccessory = materialTop(normalized) === 'accessory';
    return {
      ...normalized,
      bead_shape: physical.shape,
      placement_mode: physical.placementMode,
      physical_spec_complete: physical.specComplete,
      physical_spec_text: materialDetailSpecText(physical, isAccessory),
      card_spec_text: materialCardSpecText(physical, isAccessory),
      display_size_rpx: physical.displaySizeRpx,
      material_shape_class: physical.shapeClass
    };
  },

  optimizeImageUrl(url) {
    if (!url || !/^https:\/\/.+(?:myqcloud\.com|yustream\.cn)\//.test(url)) return url || '';
    if (url.includes('/materials/beads/real/')) return url;
    if (url.includes('imageMogr2/')) return url;
    const separator = url.includes('?') ? '&' : '?';
    return `${url}${separator}imageMogr2/thumbnail/360x360/format/webp/quality/88`;
  },

  applyMaterialPayload(data, options = {}) {
    this.applyMaterialPayloadVersion(data);
    const previousCatalog = this.materialCatalog || DEFAULT_MATERIALS;
    const rawCatalog = data.materials && data.materials.length ? data.materials : DEFAULT_MATERIALS;
    const unsupportedIds = unsupportedWorkspaceMaterialIds(rawCatalog);
    const nextCatalog = filterWorkspaceMaterials(rawCatalog);
    const topTabs = filterWorkspaceTopTabs(data.top_tabs || TOP_TABS);
    const activeTop = topTabs.some(item => item.key === this.data.activeTop) ? this.data.activeTop : 'bead';
    const selected = this.data.selected.map(id => {
      if (nextCatalog.some(item => item.id === id)) return id;
      const previous = previousCatalog.find(item => item.id === id);
      if (!previous) return id;
      const candidates = nextCatalog.filter(item => (
        item.skuId === previous.skuId
        || (item.category === previous.category && item.name === previous.name)
      ));
      if (!candidates.length) return id;
      return candidates.reduce((best, item) => (
        Math.abs(Number(item.size) - Number(previous.size))
          < Math.abs(Number(best.size) - Number(previous.size))
          ? item
          : best
      )).id;
    }).filter(id => {
      if (unsupportedIds[id]) return false;
      const material = nextCatalog.find(item => item.id === id) || this.findMaterialById(id);
      return !!material && materialIsWorkspaceSupported(material);
    });
    this.materialCatalog = nextCatalog;
    this.rebuildMaterialLookup();
    this.materialPayloadReady = true;
    this.categoriesByTop = data.categories_by_top || {};
    this.seriesByCategory = data.series_by_category || {};
    const placements = this.data.placements.map((item, index) => {
      const id = selected[index] || item.id;
      return {
        ...item,
        id,
        image_url: this.findCurrentMaterialImageUrl(id, item.image_url)
          || this.pickMaterialImageUrl(this.findMaterialById(id) || {})
      };
    });
    this.setData({
      topTabs,
      activeTop,
      selected,
      placements,
      materialsLoading: !!options.keepLoading,
      materialsErrorText: ''
    }, () => this.markWorkspaceReady('materials'));
    this.refreshFilters();
    if (this.pendingSharedDesign || this.pendingBackendRecommendation || this.pendingRecommendedRecipe) {
      this.ensurePendingMaterialDetails({ silent: true, keepPendingOnEmpty: true });
      return;
    }
    this.recalculate();
  },

  mergeMaterialCatalog(materials = [], options = {}) {
    const byId = {};
    filterWorkspaceMaterials(this.materialCatalog || DEFAULT_MATERIALS).forEach(item => {
      if (item && item.id) byId[item.id] = item;
    });
    filterWorkspaceMaterials(materials || []).forEach(item => {
      if (item && item.id) byId[item.id] = item;
    });
    this.materialCatalog = Object.keys(byId).map(id => byId[id]);
    this.rebuildMaterialLookup(this.materialCatalog, {
      resetDesignCaches: options.resetDesignCaches !== false
    });
  },

  selectedMaterialDependencySignature(selected = this.data.selected || []) {
    const lookup = this.materialLookup
      || this.rebuildMaterialLookup(this.materialCatalog || DEFAULT_MATERIALS, { resetDesignCaches: false });
    return (selected || []).map(id => {
      const material = lookup[String(id || '').trim()] || {};
      const physical = resolveMaterialGeometry(material);
      const effects = Array.isArray(material.effects) ? material.effects.join('|') : String(material.effects || '');
      const secondary = Array.isArray(material.secondary_elements)
        ? material.secondary_elements.join('|')
        : String(material.secondary_elements || '');
      return [
        id,
        material.id,
        material.skuId,
        material.sku_id,
        material.material_code,
        material.top,
        material.category,
        material.series,
        material.grade,
        material.name,
        material.size,
        material.price,
        material.weight,
        material.image_url,
        material.element,
        material.primary_element,
        material.element_key,
        secondary,
        effects,
        physical.shape,
        physical.placementMode,
        physical.imageStringAxisDeg,
        physical.stringAxisWidthMm,
        physical.bodyWidthMm,
        physical.bodyHeightMm
      ].map(value => String(value || '').trim()).join('~');
    }).join('||');
  },

  applyPagedMaterialPayload(data, options = {}) {
    const materialVersionChanged = this.applyMaterialPayloadVersion(data);
    const materials = filterWorkspaceMaterials(data.materials && data.materials.length ? data.materials : []);
    const pagination = data.pagination || {};
    const selectedDependencyBefore = this.selectedMaterialDependencySignature();
    this.mergeMaterialCatalog(materials, { resetDesignCaches: false });
    const selectedDependencyChanged = selectedDependencyBefore !== this.selectedMaterialDependencySignature();
    if (selectedDependencyChanged) {
      this.invalidateDesignMaterialCaches();
    }
    this.materialPayloadReady = true;
    const topTabs = filterWorkspaceTopTabs(data.top_tabs || this.data.topTabs || TOP_TABS);
    const activeTop = topTabs.some(item => item.key === this.data.activeTop) ? this.data.activeTop : 'bead';
    this.categoriesByTop = data.categories_by_top || this.categoriesByTop || {};
    this.seriesByCategory = data.series_by_category || this.seriesByCategory || {};
    const keyword = this.normalizeMaterialSearchKeyword(this.data.materialSearchKeyword);
    const searchTerms = this.materialSearchTerms(keyword);
    const shouldAutoTargetSearch = !options.append && searchTerms.length && options.autoTargetSearch !== false;
    const searchTarget = shouldAutoTargetSearch ? this.resolveMaterialSearchTarget(materials, searchTerms) : null;
    let categoryNames = (this.categoriesByTop || {})[activeTop] || [ALL_OPTION_LABEL];
    const currentCategory = this.data.activeCategory;
    if (!this.isAllFilterValue(currentCategory) && !categoryNames.includes(currentCategory)) {
      categoryNames = [...categoryNames, currentCategory];
    }
    if (searchTarget && searchTarget.category && !categoryNames.includes(searchTarget.category)) {
      categoryNames = [...categoryNames, searchTarget.category];
    }
    const targetCategory = searchTarget && searchTarget.category;
    const activeCategory = targetCategory && categoryNames.includes(targetCategory)
      ? targetCategory
      : (categoryNames.includes(this.data.activeCategory) ? this.data.activeCategory : ALL_OPTION_LABEL);
    const seriesKey = `${activeTop}::${activeCategory}`;
    let seriesOptions = this.isAllFilterValue(activeCategory)
      ? [ALL_OPTION_LABEL]
      : ((this.seriesByCategory || {})[seriesKey] || [ALL_OPTION_LABEL]);
    const currentSeries = this.data.activeSeries;
    if (!this.isAllFilterValue(currentSeries) && !seriesOptions.includes(currentSeries)) {
      seriesOptions = [...seriesOptions, currentSeries];
    }
    const targetSeries = searchTarget && searchTarget.category === activeCategory
      ? (searchTarget.series || searchTarget.name || '')
      : '';
    if (targetSeries && !seriesOptions.includes(targetSeries)) {
      seriesOptions = [...seriesOptions, targetSeries];
    }
    const activeSeries = targetSeries && seriesOptions.includes(targetSeries)
      ? targetSeries
      : (seriesOptions.includes(this.data.activeSeries) ? this.data.activeSeries : ALL_OPTION_LABEL);
    const decoratedCategories = this.decorateOptionList(categoryNames, activeCategory, '', 'category-filter');
    const decoratedSeriesOptions = this.decorateOptionList(seriesOptions, activeSeries, '', 'series-filter');
    const activeCategoryAnchor = this.getActiveOptionAnchor(decoratedCategories);
    const activeSeriesAnchor = this.getActiveOptionAnchor(decoratedSeriesOptions);
    const currentMaterials = options.append
      ? (options.appendBaseMaterials || this.data.visibleMaterials || [])
      : [];
    const scopedMaterials = materials.filter(item => {
      const series = item.series || item.name || '';
      const matchesCategory = this.isAllFilterValue(activeCategory) || item.category === activeCategory;
      const matchesSeries = this.isAllFilterValue(activeSeries) || series === activeSeries;
      return matchesCategory && matchesSeries && this.materialMatchesSearch(item, searchTerms);
    });
    const newVisibleMaterials = this.decorateVisibleMaterials(scopedMaterials, currentMaterials.length);
    const visibleMaterials = options.append
      ? [...currentMaterials, ...newVisibleMaterials]
      : newVisibleMaterials;
    const total = Number(pagination.total || visibleMaterials.length || scopedMaterials.length || 0);
    const filterSummary = `${activeCategory} · ${activeSeries} · ${total} 款`;
    this.materialPageState = {
      page: Number(pagination.page || 1),
      pageSize: Number(pagination.page_size || this.materialPageSize || MATERIAL_PAGE_SIZE),
      total,
      hasMore: !!pagination.has_more,
      key: this.materialRequestKey(1)
    };
    const updates = {
      topTabs: this.decorateOptionList(topTabs, activeTop, 'key'),
      activeTop,
      categories: decoratedCategories,
      activeCategory,
      activeCategoryAnchor,
      seriesOptions: decoratedSeriesOptions,
      activeSeries,
      activeSeriesAnchor,
      hasMoreMaterials: !!pagination.has_more,
      materialsLoading: !!options.keepLoading,
      materialsLoadingMore: false,
      materialsErrorText: '',
      filterSummary
    };
    if (materialVersionChanged || selectedDependencyChanged) {
      updates.placements = (this.data.placements || []).map((placement, index) => {
        const id = (this.data.selected || [])[index] || placement.id;
        const material = this.findMaterialById(id) || {};
        return {
          ...placement,
          id,
          image_url: this.findCurrentMaterialImageUrl(id, placement.image_url)
            || this.pickMaterialImageUrl(material),
          material_params: {
            ...(placement.material_params || {}),
            ...(material.material_params || {})
          },
          string_axis_width_mm: material.string_axis_width_mm || 0,
          beadSize: this.getMaterialDisplaySize(id)
        };
      });
    }
    if (options.append && options.appendBaseMaterials) {
      updates.visibleMaterials = visibleMaterials;
    } else if (options.append) {
      Object.assign(updates, this.buildVisibleMaterialAppendUpdates(newVisibleMaterials, currentMaterials.length));
    } else {
      updates.visibleMaterials = visibleMaterials;
    }
    this.setData(updates, () => {
      this.scheduleMaterialPreload(options.append ? newVisibleMaterials : visibleMaterials);
      this.markWorkspaceReady('materials');
    });

    if (materialVersionChanged) {
      this.refreshSelectedMaterialDetails();
    }

    if (this.pendingSharedDesign || this.pendingBackendRecommendation || this.pendingRecommendedRecipe) {
      this.ensurePendingMaterialDetails({ silent: true, keepPendingOnEmpty: true });
      return;
    }
    const selectedHasMissingMaterials = this.hasMissingSelectedMaterials();
    if (!selectedDependencyChanged && !selectedHasMissingMaterials) {
      return;
    }
    this.ensurePendingMaterialDetails();
    this.ensureMissingSelectedMaterials().then(handled => {
      if (!handled && selectedDependencyChanged) this.recalculate();
    });
  },

  pendingMaterialIds() {
    const ids = [];
    if (this.pendingSharedDesign) {
      this.sharedDesignMaterialCandidates(this.pendingSharedDesign).forEach(id => ids.push(LEGACY_ID_MAP[id] || id));
    }
    if (this.pendingBackendRecommendation) {
      const payload = wx.getStorageSync('diyWorkbenchPayload') || {};
      const plan = payload.bracelet_plan || {};
      (plan.items || []).forEach(item => {
        if (item && (item.material_id || item.source_material_id || item.id)) {
          ids.push(item.material_id || item.source_material_id || item.id);
        }
      });
      (plan.layout || []).forEach(item => {
        if (item && (item.material_id || item.source_material_id)) {
          ids.push(item.material_id || item.source_material_id);
        } else if (item && (item.material_code || item.crystal_code)) {
          ids.push(item.material_code || item.crystal_code);
        }
      });
    }
    if (this.pendingRecommendedRecipe) {
      const recipe = wx.getStorageSync('recommendedRecipe') || [];
      this.normalizedRecommendedRecipe(recipe).forEach(id => ids.push(LEGACY_ID_MAP[id] || id));
    }
    return Array.from(new Set(ids.map(id => String(id || '').trim()).filter(Boolean)));
  },

  async ensurePendingMaterialDetails(options = {}) {
    const importRevision = Number(
      options.importRevision
      || (this.pendingBackendRecommendation ? this.pendingBackendRecommendationRevision : 0)
      || (this.pendingRecommendedRecipe ? this.pendingRecommendedRecipeRevision : 0)
      || 0
    );
    if (importRevision && !this.isWorkspaceDesignRevisionCurrent(importRevision)) {
      return false;
    }
    const missing = this.pendingMaterialIds().filter(id => !this.hasResolvableMaterialIdentifier(id));
    if (missing.length) {
      await this.fetchMaterialsByIds(missing);
    }
    if (importRevision && !this.isWorkspaceDesignRevisionCurrent(importRevision)) {
      return false;
    }
    let applied = false;
    const applyOptions = {
      silent: options.silent !== false,
      keepPendingOnEmpty: options.keepPendingOnEmpty !== false,
      importRevision
    };
    if (this.pendingSharedDesign) {
      applied = (await this.applySharedDesign(this.pendingSharedDesign, applyOptions)) || applied;
    }
    if (this.pendingBackendRecommendation) {
      applied = this.applyBackendRecommendation(applyOptions) || applied;
    }
    if (this.pendingRecommendedRecipe) {
      applied = this.applyRecommendedRecipe(applyOptions) || applied;
    }
    return applied;
  },

  async ensureMissingSelectedMaterials() {
    const missing = (this.data.selected || []).filter(id => !this.hasMaterial(id));
    if (!missing.length) return false;
    await this.fetchMaterialsByIds(missing);
    const placements = this.data.placements.map((item, index) => {
      const id = this.data.selected[index] || item.id;
      return {
        ...item,
        id,
        image_url: this.findCurrentMaterialImageUrl(id, item.image_url)
          || this.pickMaterialImageUrl(this.findMaterialById(id) || {})
      };
    });
    this.setData({ placements }, () => this.recalculate());
    return true;
  },

  async refreshSelectedMaterialDetails() {
    const ids = Array.from(new Set((this.data.selected || []).map(id => String(id || '').trim()).filter(Boolean)));
    if (!ids.length) return false;
    const refreshed = await this.fetchMaterialsByIds(ids, { force: true });
    if (!refreshed) return false;
    const placements = (this.data.placements || []).map((placement, index) => {
      const id = (this.data.selected || [])[index] || placement.id;
      const material = this.findMaterialById(id) || {};
      return {
        ...placement,
        id,
        image_url: this.findCurrentMaterialImageUrl(id, placement.image_url)
          || this.pickMaterialImageUrl(material)
      };
    });
    this.setData({ placements }, () => this.recalculate());
    return true;
  },

  hasMissingSelectedMaterials() {
    return (this.data.selected || []).some(id => !this.hasMaterial(id));
  },

  async fetchMaterialsByIds(ids = [], options = {}) {
    const requested = Array.from(new Set((ids || []).map(id => String(id || '').trim()).filter(Boolean)));
    const targets = options.force
      ? requested
      : requested.filter(id => !this.hasResolvableMaterialIdentifier(id));
    if (!targets.length) return false;
    const requestKey = targets.slice().sort().join(',');
    if (this.materialDetailsRequesting === requestKey) return;
    this.materialDetailsRequesting = requestKey;
    try {
      const data = await getMaterials({ ids: targets, slim: true, silent: true, timeout: 8000 });
      const optimized = this.optimizeMaterialPayload(data);
      this.dropUnsupportedSelectedMaterials(optimized.materials || []);
      this.mergeMaterialCatalog(optimized.materials || []);
      return true;
    } catch (error) {
      logWorkspaceWarning('load selected material details fallback:', error.message || error);
      return false;
    } finally {
      this.materialDetailsRequesting = '';
    }
  },

  dropUnsupportedSelectedMaterials(materials = []) {
    const unsupportedIds = unsupportedWorkspaceMaterialIds(materials);
    if (!Object.keys(unsupportedIds).length) return;
    const selected = [];
    const placements = [];
    (this.data.selected || []).forEach((id, index) => {
      if (unsupportedIds[id]) return;
      selected.push(id);
      if (this.data.placements && this.data.placements[index]) {
        placements.push(this.data.placements[index]);
      }
    });
    if (selected.length === (this.data.selected || []).length) return;
    this.setData({
      selected,
      placements: this.normalizePlacements(selected, placements),
      attachedPendants: [],
      attachedPendantItems: [],
      selectedBeadIndex: -1,
      selectedBeadInfo: null
    });
  },

  materialLookupKeys(material = {}) {
    const sku = material.sku && typeof material.sku === 'object' ? material.sku : {};
    return [
      material.id,
      material.skuId,
      material.sku_id,
      material.material_code,
      typeof material.sku === 'string' ? material.sku : '',
      sku.id,
      sku.sku_id,
      sku.material_code
    ].map(value => String(value || '').trim()).filter(Boolean);
  },

  invalidateDesignMaterialCaches() {
    this.materialCatalogDesignVersion = Number(this.materialCatalogDesignVersion || 0) + 1;
    this.selectedMaterialsCache = null;
    this.canvasSelectedItemsCache = null;
    this.canvasPlacementsCache = null;
    this.canvasSpriteContextCache = null;
    this.braceletGeometryCache = null;
    this.workspaceSummaryCache = null;
    this.selectedBeadInfoCache = null;
    this.selectedItemStylePatchCache = null;
    this.clearLivePlacements();
  },

  applyMaterialPayloadVersion(data = {}) {
    const nextVersion = String(data.version || data.updated_at || '');
    const previousVersion = String(this.materialPayloadVersion || '');
    const changed = Boolean(previousVersion && nextVersion && previousVersion !== nextVersion);
    if (nextVersion) this.materialPayloadVersion = nextVersion;
    if (!changed) return false;
    this.canvasImageCache = {};
    this.canvasTextureCache = {};
    this.materialImagePreloadSet = {};
    this.materialNextImageUrlByGroup = Object.create(null);
    this.invalidateDesignMaterialCaches();
    return true;
  },

  refreshMaterialCatalogInBackground() {
    const now = Date.now();
    if (now - Number(this.lastMaterialRefreshAt || 0) < MATERIAL_BACKGROUND_REFRESH_INTERVAL) return;
    this.loadMaterialPage(1, {
      reset: true,
      useStorage: false,
      force: true,
      background: true
    });
  },

  rebuildMaterialLookup(materials = this.materialCatalog || DEFAULT_MATERIALS, options = {}) {
    const lookup = Object.create(null);
    (materials || []).forEach(material => {
      if (!material) return;
      this.materialLookupKeys(material).forEach(key => {
        if (!lookup[key]) lookup[key] = material;
      });
    });
    this.materialLookup = lookup;
    this.materialLookupSourceRef = materials;
    this.materialLookupMissCache = Object.create(null);
    this.materialImagePoolIndex = this.buildMaterialImagePoolIndex(materials);
    this.materialCatalogVersion = Number(this.materialCatalogVersion || 0) + 1;
    this.decoratedMaterialCache = null;
    this.materialElementKeyCache = null;
    if (options.resetDesignCaches !== false) this.invalidateDesignMaterialCaches();
    return lookup;
  },

  findMaterialById(id) {
    const target = String(id || '').trim();
    if (!target) return null;
    const source = this.materialCatalog || DEFAULT_MATERIALS;
    const lookupReady = this.materialLookup && this.materialLookupSourceRef === source;
    const lookup = lookupReady ? this.materialLookup : this.rebuildMaterialLookup(source);
    if (lookup[target]) return lookup[target];
    const missCache = this.materialLookupMissCache || (this.materialLookupMissCache = Object.create(null));
    if (missCache[target]) return null;
    this.materialLookupMissCache[target] = true;
    return null;
  },

  getCachedSelectedMaterials(selected = this.data.selected || []) {
    const selectedKey = (selected || []).map(id => String(id || '').trim()).join('|');
    const key = [
      this.materialCatalogVersion || 0,
      this.materialCatalogDesignVersion || 0,
      selectedKey
    ].join('::');
    if (this.selectedMaterialsCache && this.selectedMaterialsCache.key === key) {
      return this.selectedMaterialsCache.materials;
    }
    const materials = (selected || []).map(id => this.findMaterialById(id));
    this.selectedMaterialsCache = { key, materials };
    return materials;
  },

  materialImageGroupKey(material = {}) {
    const sku = material.sku || {};
    const top = materialTop(material) || 'bead';
    const textValue = value => repairMaybeMojibakeText(value).trim();
    const explicitVarietyKey = [
      sku.variety_id,
      material.variety_id,
      material.varietyId,
      sku.series_id,
      material.series_id,
      material.seriesId,
      sku.species_id,
      material.species_id,
      material.speciesId,
      sku.variety_code,
      material.variety_code,
      material.varietyCode,
      sku.series_code,
      material.series_code,
      material.seriesCode,
      sku.species_code,
      material.species_code,
      material.speciesCode
    ].map(value => String(value || '').trim()).find(Boolean);
    if (explicitVarietyKey) return `${top}::variety::${explicitVarietyKey}`;
    const varietyName = [
      sku.variety_name,
      material.variety_name,
      material.varietyName,
      sku.series_name,
      material.series_name,
      material.seriesName,
      sku.species_name,
      material.species_name,
      material.speciesName,
      sku.series,
      material.series,
      sku.name,
      material.name
    ].map(textValue).find(Boolean);
    if (varietyName) return `${top}::variety-name::${varietyName}`;
    const skuId = String(sku.sku_id || material.skuId || material.sku_id || '').trim();
    if (skuId) return `${top}::sku::${skuId}`;
    return `${top}::id::${material.id || ''}`;
  },

  materialOwnImageUrls(material = {}) {
    const urls = material.image_urls || material.image_pool || [];
    const list = Array.isArray(urls) ? urls : [urls];
    const seen = Object.create(null);
    // 选珠时只从图库随机取图；主图仅服务材料列表展示，不参与这里的候选计算。
    // 按 URL 身份去重，避免同一图库文件因 query string 或重复记录获得额外随机权重。
    return list.map(url => String(url || '').trim()).filter(url => {
      const identity = this.normalizeImageUrlIdentity(url);
      if (!identity || seen[identity]) return false;
      seen[identity] = true;
      return true;
    });
  },

  buildMaterialImagePoolIndex(materials = []) {
    const index = Object.create(null);
    const seenByGroup = Object.create(null);
    (materials || []).forEach(material => {
      if (!material || materialTop(material) !== 'bead') return;
      const groupKey = this.materialImageGroupKey(material);
      if (!groupKey) return;
      const seen = seenByGroup[groupKey] || (seenByGroup[groupKey] = Object.create(null));
      const group = index[groupKey] || (index[groupKey] = []);
      this.materialOwnImageUrls(material).forEach(url => {
        const key = this.normalizeImageUrlIdentity(url);
        if (!key || seen[key]) return;
        seen[key] = true;
        group.push(url);
      });
    });
    return index;
  },

  materialImageCandidates(material = {}) {
    return this.materialOwnImageUrls(material);
  },

  mergeMaterialImagePool(material = {}) {
    const payload = this.optimizeMaterialPayload({ materials: [material] });
    const hydrated = payload.materials && payload.materials[0];
    const hydratedImageUrls = hydrated ? this.materialOwnImageUrls(hydrated) : [];
    const accessoryGalleryReady = hydrated && materialTop(hydrated) === 'accessory' && hydratedImageUrls.length > 0;
    if (!hydrated || (!accessoryGalleryReady && hydratedImageUrls.length <= 1)) {
      return this.findMaterialById(material.id || material.skuId || material.sku_id) || material;
    }
    const groupKey = this.materialImageGroupKey(hydrated);
    const imageUrls = hydratedImageUrls;
    const mergeItem = item => {
      if (!item) return item;
      const sameGroup = this.materialImageGroupKey(item) === groupKey;
      const sameSku = [item.id, item.skuId, item.sku_id]
        .map(value => String(value || '').trim())
        .includes(String(hydrated.id || hydrated.skuId || hydrated.sku_id || '').trim());
      if (!sameGroup && !sameSku) return item;
      return {
        ...item,
        image_url: item.image_url || hydrated.image_url || imageUrls[0] || '',
        image_urls: imageUrls,
        image_pool: imageUrls
      };
    };
    this.materialCatalog = (this.materialCatalog || DEFAULT_MATERIALS).map(mergeItem);
    this.rebuildMaterialLookup();
    this.setData({
      visibleMaterials: (this.data.visibleMaterials || []).map(mergeItem)
    });
    return this.findMaterialById(hydrated.id || hydrated.skuId || hydrated.sku_id) || hydrated;
  },

  async ensureMaterialImagePool(material = {}) {
    const ownImageUrls = this.materialOwnImageUrls(material);
    if (materialTop(material) === 'accessory' ? ownImageUrls.length > 0 : ownImageUrls.length > 1) return material;
    const groupKey = this.materialImageGroupKey(material);
    this.materialImagePoolHydrated = this.materialImagePoolHydrated || {};
    this.materialImagePoolHydrating = this.materialImagePoolHydrating || {};
    if (this.materialImagePoolHydrated[groupKey]) return this.findMaterialById(material.id) || material;
    if (this.materialImagePoolHydrating[groupKey]) return this.materialImagePoolHydrating[groupKey];
    const ids = [material.id, material.skuId, material.sku_id]
      .map(value => String(value || '').trim())
      .filter(Boolean);
    if (!ids.length) return material;
    const request = getMaterials({
      ids: ids.slice(0, 1),
      page: 1,
      pageSize: 1,
      silent: true,
      timeout: 5000
    }).then(data => {
      const hydrated = data && data.materials && data.materials[0];
      if (!hydrated) return this.findMaterialById(material.id) || material;
      const merged = this.mergeMaterialImagePool(hydrated);
      this.materialImagePoolHydrated[groupKey] = true;
      return merged;
    }).catch(error => {
      logWorkspaceWarning('hydrate material image pool failed:', error && (error.message || error));
      return this.findMaterialById(material.id) || material;
    }).finally(() => {
      delete this.materialImagePoolHydrating[groupKey];
    });
    this.materialImagePoolHydrating[groupKey] = request;
    return request;
  },

  canUseHydratedMaterialImagePool(material = {}) {
    if (this.materialOwnImageUrls(material).length > 1) return true;
    const groupKey = this.materialImageGroupKey(material);
    return !!(this.materialImagePoolHydrated && this.materialImagePoolHydrated[groupKey]);
  },

  warmMaterialImagePool(material = {}) {
    const groupKey = this.materialImageGroupKey(material);
    if (!groupKey || (this.materialImagePoolHydrated && this.materialImagePoolHydrated[groupKey])) return;
    this.materialImagePoolWarmTimers = this.materialImagePoolWarmTimers || {};
    clearTimeout(this.materialImagePoolWarmTimers[groupKey]);
    const warmDelay = this.flightActive || (this.flightQueue && this.flightQueue.length) ? 720 : 420;
    this.materialImagePoolWarmTimers[groupKey] = setTimeout(() => {
      delete this.materialImagePoolWarmTimers[groupKey];
      this.ensureMaterialImagePool(material).then(hydrated => {
        const imageUrl = this.peekNextMaterialImageUrl(hydrated || material);
        if (imageUrl && this.braceletCanvasState) {
          this.getCanvasImage(imageUrl);
        }
      });
    }, warmDelay);
  },

  pickMaterialImageUrl(material = {}) {
    const pool = this.materialImageCandidates(material);
    if (!pool.length) return '';
    return pool[Math.floor(Math.random() * pool.length)] || '';
  },

  peekNextMaterialImageUrl(material = {}) {
    const pool = this.materialImageCandidates(material);
    if (!pool.length) return '';
    const groupKey = this.materialImageGroupKey(material);
    if (!groupKey) return this.pickMaterialImageUrl(material);
    this.materialNextImageUrlByGroup = this.materialNextImageUrlByGroup || Object.create(null);
    const lockedUrl = this.materialNextImageUrlByGroup[groupKey];
    if (lockedUrl && pool.includes(lockedUrl)) return lockedUrl;
    const nextUrl = this.pickMaterialImageUrl(material);
    this.materialNextImageUrlByGroup[groupKey] = nextUrl;
    return nextUrl;
  },

  consumeNextMaterialImageUrl(material = {}) {
    const imageUrl = this.peekNextMaterialImageUrl(material);
    if (!imageUrl) return '';
    const groupKey = this.materialImageGroupKey(material);
    if (groupKey) {
      this.materialNextImageUrlByGroup[groupKey] = this.pickMaterialImageUrl(material);
    }
    if (this.braceletCanvasState && this.data.visibleMaterials && this.data.visibleMaterials.length) {
      this.scheduleMaterialPreload(this.data.visibleMaterials);
    }
    return imageUrl;
  },

  normalizeImageUrlIdentity(url = '') {
    return String(url || '').split('?')[0];
  },

  findCurrentMaterialImageUrl(id, imageUrl) {
    if (!imageUrl) return '';
    const material = this.findMaterialById(id) || {};
    const target = this.normalizeImageUrlIdentity(imageUrl);
    return this.materialImageCandidates(material)
      .find(url => this.normalizeImageUrlIdentity(url) === target) || '';
  },

  isMaterialImageUrlCurrent(id, imageUrl) {
    return Boolean(this.findCurrentMaterialImageUrl(id, imageUrl));
  },

  hasMaterial(id) {
    return !!this.findMaterialById(id);
  },

  hasResolvableMaterialIdentifier(id) {
    const resolvedId = this.resolveMaterialId(LEGACY_ID_MAP[id] || id);
    return !!resolvedId && this.hasMaterial(resolvedId);
  },

  normalizeRecommendedRecipeToken(item) {
    if (!item || typeof item !== 'object') return String(item || '').trim();
    return String(
      item.material_id
      || item.source_material_id
      || item.materialId
      || item.sourceMaterialId
      || item.sku_id
      || item.skuId
      || item.sku
      || item.material_code
      || item.materialCode
      || item.crystal_code
      || item.code
      || item.id
      || item.name
      || ''
    ).trim();
  },

  normalizedRecommendedRecipe(recipe = []) {
    return (Array.isArray(recipe) ? recipe : [recipe])
      .map(item => this.normalizeRecommendedRecipeToken(item))
      .filter(Boolean);
  },

  resolveMaterialId(id) {
    const target = String(id || '').trim();
    if (!target) return '';
    if (this.hasMaterial(target)) return target;
    const legacyId = LEGACY_ID_MAP[id];
    if (legacyId && this.hasMaterial(legacyId)) return legacyId;
    const material = (this.materialCatalog || DEFAULT_MATERIALS).find(item => (
      [item.skuId, item.sku_id, item.material_code].map(value => String(value || '').trim()).includes(target)
    ));
    return material ? material.id : target;
  },

  sharedSequenceMaterialIdentifiers(item = {}) {
    return [
      item.id,
      item.material_id,
      item.materialId,
      item.source_material_id,
      item.sourceMaterialId,
      item.sku,
      item.skuId,
      item.sku_id,
      item.material_code,
      item.materialCode
    ].map(value => String(value || '').trim()).filter(Boolean);
  },

  sharedDesignMaterialCandidates(sharedDesign = {}) {
    const normalized = this.normalizeSharedDesignPayload(sharedDesign);
    const ids = [...(normalized.selected || [])];
    (normalized.sequence || []).filter(item => (
      !sequenceItemIsPendant(item || {}) && !sequenceItemIsBeadCap(item || {})
    )).forEach(item => {
      this.sharedSequenceMaterialIdentifiers(item).forEach(id => ids.push(id));
    });
    return Array.from(new Set(ids.map(id => String(id || '').trim()).filter(Boolean)));
  },

  resolveSharedDesignSelectedIds(normalized = {}) {
    const selected = [];
    const rawSelected = normalized.selected || [];
    const sequence = (normalized.sequence || []).filter(item => (
      !sequenceItemIsPendant(item || {}) && !sequenceItemIsBeadCap(item || {})
    ));
    const total = Math.max(rawSelected.length, sequence.length);
    for (let index = 0; index < total; index += 1) {
      const candidates = [];
      if (rawSelected[index]) candidates.push(rawSelected[index]);
      if (sequence[index]) {
        this.sharedSequenceMaterialIdentifiers(sequence[index]).forEach(id => candidates.push(id));
      }
      const resolvedId = candidates
        .map(id => this.resolveMaterialId(LEGACY_ID_MAP[id] || id))
        .find(id => this.hasMaterial(id));
      const material = resolvedId ? this.findMaterialById(resolvedId) : null;
      if (resolvedId && (!material || materialIsWorkspaceSupported(material))) selected.push(resolvedId);
    }
    return selected;
  },

  materialSearchText(material = {}) {
    if (materialSearchTextCache && material && typeof material === 'object' && materialSearchTextCache.has(material)) {
      return materialSearchTextCache.get(material);
    }
    const text = [
      material.id,
      material.material_code,
      material.name,
      material.category,
      material.series,
      material.grade,
      ...(material.effects || []),
      material.primary_element,
      ...(material.secondary_elements || []),
      ...(material.chakras || []),
      ...(material.wish_pools || [])
    ].filter(Boolean).join(' ').toLowerCase();
    if (materialSearchTextCache && material && typeof material === 'object') {
      materialSearchTextCache.set(material, text);
    }
    return text;
  },

  normalizeMaterialSearchKeyword(value) {
    return String(value || '').trim().replace(/\s+/g, ' ');
  },

  materialSearchTerms(keyword = this.data.materialSearchKeyword) {
    return this.normalizeMaterialSearchKeyword(keyword).toLowerCase().split(' ').filter(Boolean);
  },

  materialMatchesSearch(material = {}, keyword = this.data.materialSearchKeyword) {
    const terms = Array.isArray(keyword) ? keyword : this.materialSearchTerms(keyword);
    if (!terms.length) return true;
    const searchText = this.materialSearchText(material);
    return terms.every(term => searchText.includes(term));
  },

  materialFieldMatchesSearch(value, keyword = this.data.materialSearchKeyword) {
    const terms = Array.isArray(keyword) ? keyword : this.materialSearchTerms(keyword);
    if (!terms.length) return false;
    const text = String(value || '').trim().toLowerCase();
    if (!text) return false;
    return terms.every(term => text.includes(term));
  },

  resolveMaterialSearchTarget(materials = [], keyword = this.data.materialSearchKeyword) {
    const terms = Array.isArray(keyword) ? keyword : this.materialSearchTerms(keyword);
    if (!terms.length) return null;
    const matchedMaterials = (materials || []).filter(item => this.materialMatchesSearch(item, terms));
    return matchedMaterials.find(item => this.materialFieldMatchesSearch(item.category, terms))
      || matchedMaterials.find(item => this.materialFieldMatchesSearch(item.series, terms))
      || matchedMaterials.find(item => this.materialFieldMatchesSearch(item.name, terms))
      || matchedMaterials.find(item => this.materialFieldMatchesSearch(item.material_code || item.id || item.skuId, terms))
      || matchedMaterials.find(Boolean)
      || (materials || []).find(Boolean)
      || null;
  },

  materialElementCacheKey(material = {}) {
    const sku = material.sku && typeof material.sku === 'object' ? material.sku : {};
    return [
      this.materialCatalogVersion || 0,
      material.id,
      material.skuId,
      material.sku_id,
      material.material_code,
      typeof material.sku === 'string' ? material.sku : '',
      sku.id,
      sku.sku_id,
      sku.material_code,
      sku.top,
      material.top,
      material.item_type,
      material.type,
      material.element_key,
      material.primary_element,
      material.element,
      material.name,
      material.category,
      material.series,
      material.grade,
      Array.isArray(material.effects) ? material.effects.join('|') : material.effects,
      Array.isArray(material.secondary_elements) ? material.secondary_elements.join('|') : material.secondary_elements,
      Array.isArray(material.chakras) ? material.chakras.join('|') : material.chakras,
      Array.isArray(material.wish_pools) ? material.wish_pools.join('|') : material.wish_pools
    ].map(value => String(value || '').trim()).join('::');
  },

  getMaterialElementKeyCache() {
    if (!this.materialElementKeyCache) {
      this.materialElementKeyCache = {
        entries: Object.create(null),
        keys: []
      };
    }
    return this.materialElementKeyCache;
  },

  rememberMaterialElementKey(cacheKey, value) {
    const cache = this.getMaterialElementKeyCache();
    if (!Object.prototype.hasOwnProperty.call(cache.entries, cacheKey)) cache.keys.push(cacheKey);
    cache.entries[cacheKey] = value;
    if (cache.keys.length <= MATERIAL_ELEMENT_KEY_CACHE_LIMIT) return;
    const deleteCount = cache.keys.length - MATERIAL_ELEMENT_KEY_CACHE_LIMIT;
    cache.keys.splice(0, deleteCount).forEach(oldKey => {
      delete cache.entries[oldKey];
    });
  },

  materialElementKey(material = {}) {
    const cacheKey = this.materialElementCacheKey(material);
    const cache = this.materialElementKeyCache;
    if (cache && Object.prototype.hasOwnProperty.call(cache.entries, cacheKey)) {
      return cache.entries[cacheKey];
    }
    const remember = value => {
      this.rememberMaterialElementKey(cacheKey, value);
      return value;
    };
    if (!materialContributesEnergy(material)) return remember('');
    const elementKey = normalizeElementKey(material.element_key || material.primary_element || material.element);
    if (elementKey) return remember(elementKey);
    const skuKey = MATERIAL_ELEMENT_KEY[material.skuId] || MATERIAL_ELEMENT_KEY[material.material_code];
    if (skuKey) return remember(skuKey);
    const text = this.materialSearchText(material);
    if (/金|银|白|钛|发晶|铁|曜|耀/.test(text)) return remember('metal');
    if (/绿|木|松|幽灵|东陵/.test(text)) return remember('wood');
    if (/蓝|海|水|黑/.test(text)) return remember('water');
    if (/红|南红|玛瑙|石榴|火|粉|草莓/.test(text)) return remember('fire');
    if (/黄|茶|烟|土|虎眼/.test(text)) return remember('earth');
    return remember('');
  },

  chooseClosestMaterial(candidates = [], preferredSize = 8) {
    if (!candidates.length) return null;
    const targetSize = Number(preferredSize) || 8;
    return candidates.reduce((best, item) => {
      const bestSizeDiff = Math.abs(Number(best.size || targetSize) - targetSize);
      const itemSizeDiff = Math.abs(Number(item.size || targetSize) - targetSize);
      if (itemSizeDiff !== bestSizeDiff) return itemSizeDiff < bestSizeDiff ? item : best;
      return Number(item.sort_order || item.sortOrder || 0) < Number(best.sort_order || best.sortOrder || 0) ? item : best;
    }, candidates[0]);
  },

  normalizeBackendMaterialToken(value) {
    return String(value || '')
      .trim()
      .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
      .replace(/[-\s]+/g, '_')
      .replace(/[^a-z0-9_\u4e00-\u9fa5]+/gi, '_')
      .replace(/_+/g, '_')
      .replace(/^_|_$/g, '')
      .toLowerCase();
  },

  backendMaterialTokens(material = {}) {
    return [
      material.id,
      material.skuId,
      material.sku_id,
      material.material_code
    ].map(value => this.normalizeBackendMaterialToken(value)).filter(Boolean);
  },

  materialMatchesBackendCode(material = {}, code = '') {
    const target = this.normalizeBackendMaterialToken(code);
    if (!target) return false;
    return this.backendMaterialTokens(material).includes(target);
  },

  findBackendMaterialFamily(seed = {}, catalog = []) {
    const seedTokens = this.backendMaterialTokens(seed);
    if (!seedTokens.length) return [];
    return catalog.filter(item => this.backendMaterialTokens(item).some(token => seedTokens.includes(token)));
  },

  resolveBackendCrystalMaterialId(code, preferredSize = 8) {
    const catalog = filterWorkspaceMaterials(this.materialCatalog || DEFAULT_MATERIALS)
      .filter(item => item.top === 'bead');
    if (!catalog.length) return '';
    const codeMatch = this.chooseClosestMaterial(
      catalog.filter(item => this.materialMatchesBackendCode(item, code)),
      preferredSize
    );
    if (codeMatch) return codeMatch.id;

    const legacyId = BACKEND_CRYSTAL_MAP[code];
    const legacyResolved = legacyId ? this.resolveMaterialId(legacyId) : '';
    if (legacyResolved && this.hasMaterial(legacyResolved)) {
      const legacyMaterial = this.findMaterialById(legacyResolved) || {};
      const familyMatch = this.chooseClosestMaterial(
        this.findBackendMaterialFamily(legacyMaterial, catalog),
        preferredSize
      );
      return familyMatch ? familyMatch.id : legacyResolved;
    }

    const aliases = BACKEND_CRYSTAL_ALIASES[code] || [];
    const aliasCandidates = catalog.filter(item => {
      const text = this.materialSearchText(item);
      return aliases.some(alias => text.includes(String(alias).toLowerCase()));
    });
    const aliasMatch = this.chooseClosestMaterial(aliasCandidates, preferredSize);
    if (aliasMatch) return aliasMatch.id;

    const targetElement = BACKEND_CRYSTAL_ELEMENT[code];
    const elementMatch = this.chooseClosestMaterial(
      targetElement ? catalog.filter(item => this.materialElementKey(item) === targetElement) : [],
      preferredSize
    );
    if (elementMatch) return elementMatch.id;

    const availableMatch = this.chooseClosestMaterial(catalog, preferredSize);
    return availableMatch ? availableMatch.id : '';
  },

  buildBackendRecommendationSelected(payload = {}) {
    const plan = payload.bracelet_plan || {};
    const layout = Array.isArray(plan.layout) ? plan.layout : [];
    const sizeByCode = {};
    const materialByCode = {};
    (plan.items || []).forEach(item => {
      if (item && item.code) sizeByCode[item.code] = Number(item.bead_size_mm) || Number(plan.bead_size_mm) || 8;
      if (item && item.code && (item.material_id || item.source_material_id || item.id)) {
        materialByCode[item.code] = item.material_id || item.source_material_id || item.id;
      }
    });
    return layout
      .map(item => {
        const explicitIds = [
          item.material_id,
          item.source_material_id,
          item.sku_id,
          item.skuId,
          item.material_code,
          materialByCode[item.crystal_code]
        ].map(value => String(value || '').trim()).filter(Boolean);
        const resolvedExplicitId = explicitIds
          .map(id => this.resolveMaterialId(id))
          .find(id => id && this.hasMaterial(id));
        if (resolvedExplicitId) return resolvedExplicitId;
        const itemTop = String(item.top || item.kind || '').trim().toLowerCase();
        if (itemTop === 'accessory') return '';
        return this.resolveBackendCrystalMaterialId(
          item.crystal_code,
          sizeByCode[item.crystal_code] || Number(item.bead_size_mm) || Number(plan.bead_size_mm) || Number(payload.bead_size_mm) || 8
        );
      })
      .filter(id => {
        if (!id) return false;
        const material = this.findMaterialById(id);
        return !!material && materialIsWorkspaceSupported(material);
      });
  },

  onShow() {
    wx.hideTabBar({ animation: false });
    const workspacePreset = wx.getStorageSync('workspacePreset');
    if (workspacePreset === 'backend-recommended') {
      const intent = wx.getStorageSync('workspaceImportIntent') || {};
      wx.removeStorageSync('workspacePreset');
      wx.removeStorageSync('workspaceImportIntent');
      wx.removeStorageSync('workspaceOpenDesign');
      const importRevision = this.beginWorkspaceImportSession(
        intent.id || `backend-recommended:${Date.now()}`
      );
      this.pendingBackendRecommendation = true;
      this.pendingBackendRecommendationRevision = importRevision;
      if (this.materialPayloadReady) {
        this.ensurePendingMaterialDetails({
          silent: false,
          keepPendingOnEmpty: false,
          importRevision
        });
      }
      return;
    }
    if (workspacePreset === 'recommended') {
      wx.removeStorageSync('workspacePreset');
      const importRevision = this.beginWorkspaceImportSession(`recommended:${Date.now()}`);
      this.pendingRecommendedRecipe = true;
      this.pendingRecommendedRecipeRevision = importRevision;
      if (this.materialPayloadReady) {
        this.applyRecommendedRecipe({ importRevision });
      }
      return;
    }
    if (this.workspaceHasShown) {
      this.refreshMaterialCatalogInBackground();
    } else {
      this.workspaceHasShown = true;
    }
    if (this.data.workspaceCanvasVisible === false || this.data.workspaceCanvasSuppressed) {
      this.restoreWorkspaceCanvasAfterOverlay();
    } else if (this.braceletCanvasState) {
      this.scheduleMaterialPreload(this.data.visibleMaterials);
    }
    if (this.deferFirstShowProfileEnergy) {
      this.deferFirstShowProfileEnergy = false;
    } else {
      this.loadProfileEnergy();
    }
    this.scheduleCanvasRender();
    if (this.data.isLooseMode && !this.data.sharedDesignFrozen && this.physicsEngine) this.runPhysics();
    if (wx.getStorageSync('workspaceOpenDesign')) {
      wx.removeStorageSync('workspaceOpenDesign');
      this.pendingBackendRecommendation = false;
      this.pendingRecommendedRecipe = false;
      this.loadDraft();
    }
  },

  loadProfileEnergy() {
    const report = wx.getStorageSync('energyReport');
    const targetMap = {};
    if (report && report.final_energy_profile) {
      Object.keys(report.final_energy_profile).forEach(name => {
        const elementName = normalizeElementCnName(name);
        const elementKey = ELEMENT_CN_TO_EN[elementName];
        if (elementKey) {
          targetMap[elementKey] = Math.max(0, Math.min(100, Number(report.final_energy_profile[name]) * 3));
        }
      });
      const chartValues = report.chart && Array.isArray(report.chart.values) ? report.chart.values : [];
      API_ELEMENT_ORDER.forEach((name, index) => {
        const elementKey = ELEMENT_CN_TO_EN[name];
        if (elementKey && targetMap[elementKey] === undefined) {
          targetMap[elementKey] = Math.max(0, Math.min(100, Number(chartValues[index]) * 3));
        }
      });
    } else if (report && report.elements && report.elements.length) {
      report.elements.forEach(item => {
        targetMap[item.key] = Math.max(0, Math.min(100, Number(item.value) || 0));
      });
    }
    this.setData({ userEnergyTarget: targetMap });
  },

  onUnload() {
    clearTimeout(this.materialLoadTimer);
    clearTimeout(this.materialSearchTimer);
    clearTimeout(this.wristPromptTimer);
    clearTimeout(this.persistDraftTimer);
    clearTimeout(this.flightTimer);
    clearTimeout(this.flightSafetyTimer);
    clearTimeout(this.flightAnimationTimer);
    clearTimeout(this.canvasFlightRetryTimer);
    clearTimeout(this.shuffleTimer);
    clearTimeout(this.canvasResizeTimer);
    clearTimeout(this.canvasRecoveryTimer);
    clearTimeout(this.physicsFrameRetryTimer);
    clearTimeout(this.dragPhysicsSyncTimer);
    this.cancelCanvasFrame(this.pendingPhysicsLaunchFrame);
    this.pendingPhysicsLaunchFrame = null;
    this.flightAnimationTimer = null;
    this.canvasFlightRetryTimer = null;
    this.canvasRecoveryTimer = null;
    this.physicsFrameRetryTimer = null;
    this.dragPhysicsSyncTimer = null;
    clearTimeout(this.audioPrewarmTimer);
    clearTimeout(this.interactionRuntimeWarmupTimer);
    clearTimeout(this.audioRuntimeWarmupTimer);
    clearTimeout(this.canvasTextureWarmupTimer);
    this.canvasTextureWarmupTimer = null;
    this.canvasTextureWarmupByUrl = Object.create(null);
    clearTimeout(this.nonCriticalTaskTimer);
    clearTimeout(this.workspaceLoadingFallbackTimer);
    clearTimeout(this.workspaceLoadingDoneTimer);
    clearTimeout(this.workspaceLoadingHideTimer);
    clearTimeout(this.wristRulerSnapTimer);
    this.flushWorkspaceHistoryPersistence();
    this.pauseMaterialBackgroundPreload();
    this.stopCanvasRenderLoop();
    this.clearWorkspaceFlightCanvas();
    Object.values(this.audioPlayers || {}).forEach(pool => {
      const players = Array.isArray(pool) ? pool : [pool];
      players.forEach(audio => {
        try {
          audio && audio.destroy && audio.destroy();
        } catch (error) {}
      });
    });
    this.audioPlayers = {};
    this.audioPlayerCursors = {};
    this.audioPlayersReady = false;
    this.interactionRuntimeWarmed = false;
    this.stopPhysics();
    wx.showTabBar({ animation: false });
  },

  onHide() {
    clearTimeout(this.wristRulerSnapTimer);
    clearTimeout(this.physicsFrameRetryTimer);
    clearTimeout(this.dragPhysicsSyncTimer);
    clearTimeout(this.canvasFlightRetryTimer);
    clearTimeout(this.flightAnimationTimer);
    clearTimeout(this.canvasTextureWarmupTimer);
    this.canvasTextureWarmupTimer = null;
    this.physicsFrameRetryTimer = null;
    this.dragPhysicsSyncTimer = null;
    this.canvasFlightRetryTimer = null;
    this.flightAnimationTimer = null;
    this.pauseMaterialBackgroundPreload();
    this.pausePhysics();
    this.stopCanvasRenderLoop();
    wx.showTabBar({ animation: false });
  },

  loadDraft() {
    const draft = wx.getStorageSync('currentDesign');
    this.resetWorkspaceRuntime();
    if (draft && draft.selected && draft.selected.length) {
      const sourceContext = draft.sourceContext || draft.source_context || null;
      this.sourceContext = sourceContext;
      this.setData({
        selected: draft.selected.map(id => LEGACY_ID_MAP[id] || id),
        placements: this.normalizePlacements(draft.selected, draft.placements, draft.sequence),
        attachedPendants: [],
        isLooseMode: draft.isLooseMode === true,
        wristSize: this.normalizeWristValue(draft.wristSize || this.data.wristSize || 16),
        wearStyle: 'single',
        canvasFlightActive: false,
        flightBead: null,
        launchingMaterialId: '',
        isShuffling: false,
        isStringingFinishing: false,
        isReleasingString: false,
        selectedBeadIndex: -1,
        draggingBeadIndex: -1,
        dragDeleteArmed: false,
        sourceContext,
        workspacePlanLabel: this.workspaceSourceLabel(sourceContext || {})
      });
      this.recalculate();
    } else {
      this.sourceContext = null;
      this.resetInteractionData({
        selected: [],
        placements: [],
        attachedPendants: [],
        selectedItems: [],
        attachedPendantItems: [],
        selectedBeadIndex: -1,
        isLooseMode: true,
        sourceContext: null,
        workspacePlanLabel: '当前方案'
      }, () => this.recalculate());
    }
  },

  replaceCurrentDesignWithImportedDraft(options = {}) {
    const draft = buildFreshWorkspaceDraft({
      ...options,
      fallbackName: DEFAULT_DESIGN_NAME
    });
    this.lastPersistedDraftSignature = '';
    wx.setStorageSync('currentDesign', draft);
  },

  beginWorkspaceImportSession(importId = '') {
    this.workspaceDesignRevision = Number(this.workspaceDesignRevision || 0) + 1;
    this.activeWorkspaceImportId = String(importId || `workspace-import:${Date.now()}`);
    clearTimeout(this.persistDraftTimer);
    this.persistDraftTimer = null;
    this.resetWorkspaceRuntime();
    this.historyStack = [];
    this.redoStack = [];
    if (wx.setStorageSync) wx.setStorageSync('workspaceHistory', []);
    this.setData({ canUndo: false, canRedo: false });
    return this.workspaceDesignRevision;
  },

  isWorkspaceDesignRevisionCurrent(revision) {
    return Number(revision || 0) === Number(this.workspaceDesignRevision || 0);
  },

  workspaceSourceLabel(sourceContext = {}) {
    const sourceLabel = String(sourceContext.source_label || '').trim();
    const title = String(sourceContext.title || '').trim();
    if (sourceLabel && title) return `${sourceLabel} · ${title}`;
    return sourceLabel || title || '当前方案';
  },

  applyRecommendedRecipe(options = {}) {
    if (options.importRevision && !this.isWorkspaceDesignRevisionCurrent(options.importRevision)) {
      return false;
    }
    if (!this.materialPayloadReady) return false;
    const rawRecipe = wx.getStorageSync('recommendedRecipe') || ['aquamarine', 'amethyst', 'clearQuartz', 'moonstone'];
    const recipe = this.normalizedRecommendedRecipe(rawRecipe);
    const storedRecipeContext = wx.getStorageSync('recommendedRecipeContext') || {};
    const contextRecipe = this.normalizedRecommendedRecipe(storedRecipeContext.recipe || []);
    const contextMatchesRecipe = !contextRecipe.length
      || JSON.stringify(contextRecipe) === JSON.stringify(recipe);
    const sourceContext = contextMatchesRecipe && storedRecipeContext.title
      ? {
          source: storedRecipeContext.source || 'community_inspiration',
          source_label: storedRecipeContext.source_label || '灵感方案',
          post_id: storedRecipeContext.post_id || '',
          title: storedRecipeContext.title
        }
      : {
          source: 'recommended_recipe',
          source_label: '推荐方案',
          title: ''
        };
    const wristSize = Number(wx.getStorageSync('recommendedWristSize')) || this.data.wristSize || 16;
    const idMap = {
      aquamarine: 'aquamarine8',
      amethyst: 'amethyst8',
      clearQuartz: 'clearQuartz8',
      moonstone: 'moonstone8',
      citrine: 'citrine8',
      tigerEye: 'tigerEye8',
      roseQuartz: 'roseQuartz8',
      obsidian: 'obsidian10',
      silverSpacer: 'silverSpacer',
      goldSpacer: 'goldSpacer'
    };
    const materialIds = (recipe.length ? recipe : ['aquamarine', 'amethyst', 'clearQuartz', 'moonstone'])
      .map(id => this.resolveMaterialId(idMap[id] || id))
      .filter(id => this.hasMaterial(id));
    const beadMaterialIds = materialIds.filter(id => {
      const material = this.findMaterialById(id) || {};
      return materialTop(material) === 'bead' && materialIsWorkspaceSupported(material);
    });
    const recipeMaterialIds = beadMaterialIds.length
      ? beadMaterialIds
      : materialIds.filter(id => materialIsWorkspaceSupported(this.findMaterialById(id) || {}));
    const recipeItems = recipeMaterialIds
      .map(id => this.findMaterialById(id))
      .filter(Boolean);
    const targetCount = recommendedStringedBeadCount(recipeItems, wristSize);
    const selected = expandSequenceToCount(recipeMaterialIds, targetCount);
    if (!selected.length) {
      if (!options.silent) wx.showToast({ title: '暂未匹配到可用珠材', icon: 'none' });
      if (!options.keepPendingOnEmpty) {
        this.pendingRecommendedRecipe = false;
        this.pendingRecommendedRecipeRevision = 0;
      }
      return false;
    }
    if (options.importRevision && !this.isWorkspaceDesignRevisionCurrent(options.importRevision)) {
      return false;
    }
    this.pendingRecommendedRecipe = false;
    this.pendingRecommendedRecipeRevision = 0;
    this.resetWorkspaceRuntime();
    this.historyStack = [];
    this.redoStack = [];
    if (wx.setStorageSync) wx.setStorageSync('workspaceHistory', []);
    wx.removeStorageSync('recommendedRecipeContext');
    wx.setStorageSync('recommendedWristSize', wristSize);
    wx.setStorageSync('workspaceWristConfirmed', true);
    this.sourceContext = sourceContext;
    const loosePlacements = this.normalizePlacements(selected);
    const placements = this.rebuildRingPlacementsForVisualSlots(selected, loosePlacements, 0);
    this.replaceCurrentDesignWithImportedDraft({
      name: sourceContext.title,
      selected,
      placements,
      wristSize,
      sourceContext
    });
    this.setData({
      wristSize,
      selected,
      placements,
      attachedPendants: [],
      isLooseMode: false,
      selectedBeadIndex: -1,
      canvasFlightActive: false,
      flightBead: null,
      launchingMaterialId: '',
      isShuffling: false,
      isStringingFinishing: false,
      isReleasingString: false,
      draggingBeadIndex: -1,
      dragDeleteArmed: false,
      sourceContext,
      workspacePlanLabel: this.workspaceSourceLabel(sourceContext),
      canUndo: false,
      canRedo: false
    }, () => {
      if (options.importRevision && !this.isWorkspaceDesignRevisionCurrent(options.importRevision)) return;
      this.recalculate({ persist: false });
    });
    return true;
  },

  applyBackendRecommendation(options = {}) {
    if (options.importRevision && !this.isWorkspaceDesignRevisionCurrent(options.importRevision)) {
      return false;
    }
    const payload = wx.getStorageSync('diyWorkbenchPayload');
    if (!payload || !payload.bracelet_plan || !payload.bracelet_plan.layout) {
      if (!options.silent) wx.showToast({ title: '未找到推荐方案', icon: 'none' });
      if (!options.keepPendingOnEmpty) {
        this.pendingBackendRecommendation = false;
        this.pendingBackendRecommendationRevision = 0;
        this.loadDraft();
      }
      return false;
    }
    if (!this.materialPayloadReady) return false;
    const baseSelected = this.buildBackendRecommendationSelected(payload);
    const backendLayout = Array.isArray(payload.bracelet_plan.layout)
      ? payload.bracelet_plan.layout
      : [];
    if (!baseSelected.length || baseSelected.length !== backendLayout.length) {
      if (!options.silent) wx.showToast({ title: '推荐方案暂未匹配到可用珠材', icon: 'none' });
      if (!options.keepPendingOnEmpty) {
        this.pendingBackendRecommendation = false;
        this.pendingBackendRecommendationRevision = 0;
      }
      return false;
    }
    const sourceContext = payload.source_context || {
      source: payload.source || 'backend_recommendation',
      source_label: payload.source_label || '推荐方案',
      date: payload.date || '',
      keyword: payload.keyword || '',
      title: payload.bracelet_plan.title || ''
    };
    const wristSize = Number(payload.wrist_size_cm) || Number(wx.getStorageSync('recommendedWristSize')) || this.data.wristSize || 16;
    const recommendationItems = baseSelected
      .map(id => this.findMaterialById(id))
      .filter(Boolean);
    if (recommendationItems.length !== baseSelected.length
      || recommendationItems.some(item => !materialIsWorkspaceSupported(item))) {
      if (!options.silent) wx.showToast({ title: '推荐材料已更新，请重新生成方案', icon: 'none' });
      if (!options.keepPendingOnEmpty) {
        this.pendingBackendRecommendation = false;
        this.pendingBackendRecommendationRevision = 0;
      }
      return false;
    }
    const recommendedCount = recommendedStringedBeadCount(recommendationItems, wristSize);
    const backendValidation = payload.bracelet_plan.validation || {};
    const isDesignerLayout = payload.source === 'custom_design'
      || (payload.source_context || {}).source === 'custom_design';
    const backendLayoutIsTrusted = backendValidation.is_valid === true
      && baseSelected.length === backendLayout.length
      && (isDesignerLayout || baseSelected.length >= MIN_STRING_BEAD_COUNT)
      && baseSelected.length > 0
      && baseSelected.length <= MAX_RECOMMENDED_RECIPE_BEADS;
    const selected = backendLayoutIsTrusted
      ? baseSelected
      : expandSequenceToCount(baseSelected, recommendedCount);
    if (options.importRevision && !this.isWorkspaceDesignRevisionCurrent(options.importRevision)) {
      return false;
    }
    this.pendingBackendRecommendation = false;
    this.pendingBackendRecommendationRevision = 0;
    this.resetWorkspaceRuntime();
    this.historyStack = [];
    this.redoStack = [];
    if (wx.setStorageSync) wx.setStorageSync('workspaceHistory', []);
    wx.setStorageSync('recommendedWristSize', wristSize);
    wx.setStorageSync('workspaceWristConfirmed', true);
    const resolvedSourceContext = {
      ...sourceContext,
      recommendation_validation: backendValidation,
      target_bead_count: selected.length
    };
    this.sourceContext = resolvedSourceContext;
    const exactPlacements = backendLayoutIsTrusted
      ? backendLayout.map((item, index) => ({
          ...item,
          id: selected[index],
          image_url: item.selected_image_url || item.image_url || ''
        }))
      : [];
    const loosePlacements = this.normalizePlacements(
      selected,
      exactPlacements,
      backendLayoutIsTrusted ? backendLayout : []
    );
    const placements = this.rebuildRingPlacementsForVisualSlots(selected, loosePlacements, 0);
    this.replaceCurrentDesignWithImportedDraft({
      name: sourceContext.title || payload.name || payload.bracelet_plan.title,
      selected,
      placements,
      wristSize,
      sourceContext: resolvedSourceContext
    });
    this.setData({
      wristSize,
      selected,
      placements,
      isLooseMode: false,
      selectedBeadIndex: -1,
      selectedBeadInfo: null,
      showTip: false,
      canvasFlightActive: false,
      flightBead: null,
      launchingMaterialId: '',
      isShuffling: false,
      isStringingFinishing: false,
      isReleasingString: false,
      draggingBeadIndex: -1,
      dragDeleteArmed: false,
      sourceContext: resolvedSourceContext,
      workspacePlanLabel: this.workspaceSourceLabel(resolvedSourceContext),
      canUndo: false,
      canRedo: false
    }, () => {
      if (options.importRevision && !this.isWorkspaceDesignRevisionCurrent(options.importRevision)) return;
      this.recalculate({ persist: false });
      // switchTab reuses the existing workspace page. In some WeChat runtimes
      // the 2D canvas backing surface remains stale after the recommendation
      // replaces the complete design, even though draw calls succeed. Resetting
      // the canvas dimensions through initWorkspaceCanvases makes the imported
      // bracelet visible immediately.
      wx.nextTick(() => {
        if (options.importRevision && !this.isWorkspaceDesignRevisionCurrent(options.importRevision)) return;
        // recalculate() may already have queued a frame. Cancel it before
        // setupCanvasNode resets the backing bitmap, otherwise the init render
        // can be skipped because canvasFramePending is still true.
        this.stopCanvasRenderLoop();
        this.braceletCanvasDirty = true;
        this.initWorkspaceCanvases();
      });
    });
    if (!options.silent) wx.showToast({ title: '已载入专属推荐', icon: 'success' });
    return true;
  },

  normalizePlacements(selected, placements, snapshots = []) {
    const normalized = [];
    selected.forEach((id, index) => {
      const previous = placements && placements[index];
      const snapshot = snapshots && snapshots[index] || {};
      const loose = previous && Number.isFinite(previous.looseX) && Number.isFinite(previous.looseY)
        ? previous
        : this.createLoosePlacement(index, id, normalized);
      const material = this.findMaterialById(id) || {};
      const storedImageUrl = previous && previous.image_url
        || snapshot.image_url
        || firstWorkspaceImageUrl(snapshot)
        || '';
      const imageCandidates = this.materialImageCandidates(material);
      const imageUrl = imageCandidates.length
        ? (this.findCurrentMaterialImageUrl(id, storedImageUrl) || this.pickMaterialImageUrl(material))
        : storedImageUrl;
      const size = material.size
        || material.size_mm
        || previous && (previous.size || previous.diameter || previous.size_mm)
        || snapshot.size
        || snapshot.diameter
        || snapshot.size_mm
        || '';
      const currentPrice = Number(material.price);
      const price = Number.isFinite(currentPrice) && currentPrice > 0
        ? currentPrice
        : previous && (previous.price || previous.priceText || previous.amount)
        || snapshot.price
        || snapshot.priceText
        || snapshot.amount
        || '';
      const beadCaps = beadCapSlotsFromPlacement({
        bead_caps: (previous && (previous.bead_caps || previous.beadCaps))
          || (snapshot.placement && (snapshot.placement.bead_caps || snapshot.placement.beadCaps))
          || snapshot.bead_caps
          || snapshot.beadCaps
          || {}
      });
      normalized.push({
        id,
        image_url: imageUrl,
        name: material.name
          || material.series
          || previous && (previous.name || previous.material_name || previous.materialName)
          || snapshot.name
          || snapshot.material_name
          || snapshot.materialName
          || '',
        category: material.category || previous && previous.category || snapshot.category || '',
        series: material.series || previous && previous.series || snapshot.series || '',
        top: material.top || previous && previous.top || snapshot.top || 'bead',
        size,
        diameter: size,
        material_params: {
          ...(snapshot.material_params || {}),
          ...((previous && previous.material_params) || {}),
          ...(material.material_params || {})
        },
        string_axis_width_mm: material.string_axis_width_mm
          || previous && previous.string_axis_width_mm
          || snapshot.string_axis_width_mm
          || 0,
        price,
        bead_caps: beadCaps,
        dx: Number(loose.dx) || 0,
        dy: Number(loose.dy) || 0,
        looseX: loose.looseX,
        looseY: loose.looseY,
        rotation: Number(loose.rotation) || 0,
        beadSize: Number(loose.beadSize) || this.getMaterialDisplaySize(id)
      });
    });
    return normalized;
  },

  getMaterialDisplaySize(id) {
    const material = this.findMaterialById(id);
    return material ? resolveMaterialGeometry(material).displaySizeRpx : 54;
  },

  createLoosePlacement(index, id, existingPlacements = [], imageUrl = '') {
    const layout = this.getStageLayout();
    const seed = Array.from(String(id)).reduce((sum, char) => sum + char.charCodeAt(0), index * 53);
    const beadSize = this.getMaterialDisplaySize(id);
    let looseX = layout.center;
    let looseY = layout.center;
    for (let attempt = 0; attempt < 36; attempt += 1) {
      const angle = ((index * 137.5 + seed * 0.71 + attempt * 73) % 360) * Math.PI / 180;
      const radius = 48 + ((index * 47 + seed + attempt * 31) % 148);
      const candidateX = layout.center + Math.cos(angle) * radius;
      const candidateY = layout.center + Math.sin(angle) * radius;
      const collides = existingPlacements.some(existing => {
        const existingSize = Number(existing.beadSize) || this.getMaterialDisplaySize(existing.id);
        const distance = Math.sqrt(
          (candidateX - existing.looseX) ** 2 + (candidateY - existing.looseY) ** 2
        );
        return distance < (beadSize + existingSize) / 2 + 4;
      });
      looseX = candidateX;
      looseY = candidateY;
      if (!collides) break;
    }
    return {
      id,
      image_url: imageUrl || this.pickMaterialImageUrl(this.findMaterialById(id) || {}),
      dx: 0,
      dy: 0,
      looseX,
      looseY,
      rotation: (index * 83 + seed) % 360,
      beadSize
    };
  },

  createPhysicsEngine() {
    this.ensurePhysicsRuntime();
    const layout = this.getStageLayout();
    const engine = Engine.create({
      enableSleeping: true,
      positionIterations: this.isLowPerformanceDevice ? 8 : 12,
      velocityIterations: this.isLowPerformanceDevice ? 5 : 8,
      constraintIterations: 2
    });
    // 俯视水平圆盘：没有统一方向的重力，珠子只受入盘初速度、
    // 碰撞冲量、盘面滚动阻力以及成串阶段的弹簧吸附力。
    engine.gravity.x = 0;
    engine.gravity.y = 0;
    engine.gravity.scale = 0;
    if (engine.world && engine.world.gravity) {
      engine.world.gravity.x = 0;
      engine.world.gravity.y = 0;
      engine.world.gravity.scale = 0;
    }

    const wallThickness = 28;
    const wallCount = this.isLowPerformanceDevice ? 32 : 40;
    const trayRadius = this.getTrayPhysicsRadius(layout);
    const wallRadius = trayRadius - TRAY_BOUNDARY_PADDING_RPX + wallThickness * 0.5;
    const wallLength = (Math.PI * 2 * wallRadius) / wallCount + 12;
    const walls = [];
    for (let index = 0; index < wallCount; index += 1) {
      const angle = (Math.PI * 2 * index) / wallCount;
      const wall = Bodies.rectangle(
        layout.center + Math.cos(angle) * wallRadius,
        layout.center + Math.sin(angle) * wallRadius,
        wallLength,
        wallThickness,
        {
          isStatic: true,
          angle: angle + Math.PI / 2,
          restitution: BILLIARD_WALL_RESTITUTION,
          friction: BILLIARD_FRICTION,
          frictionStatic: BILLIARD_STATIC_FRICTION,
          label: 'tray-wall'
        }
      );
      walls.push(wall);
    }
    Composite.add(engine.world, walls);
    this.bindPhysicsCollisionHandlers(engine);
    this.physicsEngine = engine;
    this.physicsBodies = [];
  },

  ensurePhysicsRuntime() {
    if (Engine) return;
    const Matter = require('../../utils/vendor/matter.min');
    ({ Body, Bodies, Composite, Engine, Events, Sleeping } = Matter);
  },

  ensureAudioPlayers() {
    if (!wx.createInnerAudioContext || this.audioPlayersReady) return;
    const createPlayer = (src, name) => {
      const audio = wx.createInnerAudioContext();
      audio.obeyMuteSwitch = true;
      audio.autoplay = false;
      audio.loop = false;
      audio.startTime = 0;
      audio.volume = WORKSPACE_SOUND_VOLUME[name] || 0.18;
      audio.src = src;
      audio.__playing = false;
      if (audio.onCanplay) {
        audio.onCanplay(() => {
          audio.__ready = true;
        });
      }
      if (audio.onEnded) {
        audio.onEnded(() => {
          audio.__playing = false;
          try {
            audio.seek(0);
          } catch (error) {}
        });
      }
      if (audio.onStop) {
        audio.onStop(() => {
          audio.__playing = false;
        });
      }
      if (audio.onError) {
        audio.onError(error => {
          audio.__playing = false;
          const now = Date.now();
          if (now - Number(audio.__lastErrorLogAt || 0) > 3000) {
            audio.__lastErrorLogAt = now;
            logWorkspaceWarning('workspace sound load failed:', name, error && (error.errMsg || error.message) || error);
          }
        });
      }
      return audio;
    };
    this.audioPlayers = Object.keys(WORKSPACE_SOUND_URLS).reduce((players, name) => {
      const poolSize = WORKSPACE_SOUND_POOL_SIZE[name] || 2;
      players[name] = Array.from({ length: poolSize }, () => createPlayer(WORKSPACE_SOUND_URLS[name], name));
      return players;
    }, {});
    this.audioPlayerCursors = {};
    this.audioPlayersReady = true;
    this.preloadAudioPlayers();
  },

  preloadAudioPlayers() {
    clearTimeout(this.audioPrewarmTimer);
    this.audioPrewarmTimer = setTimeout(() => {
      Object.values(this.audioPlayers || {}).forEach(pool => {
        const players = Array.isArray(pool) ? pool : [pool];
        players.forEach(audio => {
          try {
            if (audio && audio.src) audio.src = audio.src;
          } catch (error) {}
        });
      });
    }, 80);
  },

  pickAudioPlayer(name) {
    const pool = this.audioPlayers && this.audioPlayers[name];
    if (!Array.isArray(pool) || !pool.length) return pool || null;
    const idlePlayer = pool.find(audio => audio && !audio.__playing);
    if (idlePlayer) return idlePlayer;
    const cursor = Number(this.audioPlayerCursors[name] || 0);
    this.audioPlayerCursors[name] = cursor + 1;
    return pool[cursor % pool.length];
  },

  playSoundEffect(name, throttleMs = 0, options = {}) {
    if (!this.soundEnabled) return;
    this.ensureAudioPlayers();
    const audio = this.pickAudioPlayer(name);
    if (!audio) return;
    const now = Date.now();
    const throttleKey = options.throttleKey || name;
    const lastAt = Number(this.lastSoundAt[throttleKey] || 0);
    if (throttleMs && now - lastAt < throttleMs) return;
    this.lastSoundAt[throttleKey] = now;
    try {
      if (audio.__playing && audio.stop) audio.stop();
      audio.startTime = 0;
      const requestedVolume = Number(options.volume);
      audio.volume = Number.isFinite(requestedVolume)
        ? Math.max(0, Math.min(1, requestedVolume))
        : (WORKSPACE_SOUND_VOLUME[name] || 0.18);
      audio.__playing = true;
      audio.play();
    } catch (error) {
      audio.__playing = false;
      logWorkspaceWarning('play sound failed:', name, error.message || error);
    }
  },

  playMaterialLandingSound(physicsOptions = {}) {
    const velocity = physicsOptions.velocity || {};
    const speed = Math.sqrt(
      (Number(velocity.x) || 0) ** 2 +
      (Number(velocity.y) || 0) ** 2
    );
    const speedRoom = Math.max(1, BILLIARD_LAUNCH_MAX_SPEED * BILLIARD_LAUNCH_SPEED_SCALE);
    const strength = Math.max(0, Math.min(1, speed / speedRoom));
    this.playSoundEffect('collisionSoft', 0, {
      volume: 0.15 + strength * 0.05
    });
  },

  bindPhysicsCollisionHandlers(engine) {
    if (!engine || !Events) return;
    if (this.physicsCollisionBoundEngine === engine) return;
    this.physicsCollisionBoundEngine = engine;
    Events.on(engine, 'collisionStart', event => {
      const pairs = event && event.pairs ? event.pairs : [];
      if (!pairs.length) return;
      this.handleFrozenImpactCollision(pairs);
      this.handleTrayWallCollision(pairs);
      this.containImpactCollisionBodies(pairs);
      if (this.suppressStringingSounds || this.data.isShuffling || this.data.isStringingFinishing) return;
      let maxRelSpeed = 0;
      let impactVector = null;
      pairs.forEach(pair => {
        this.applyCollisionSpin(pair);
        this.dampenNeighborBeadCollision(pair);
        const bodyA = pair.bodyA;
        const bodyB = pair.bodyB;
        if (!bodyA || !bodyB) return;
        const beadBody = this.isWorkspaceBeadBody(bodyA) && this.isTrayWallBody(bodyB)
          ? bodyA
          : (this.isWorkspaceBeadBody(bodyB) && this.isTrayWallBody(bodyA) ? bodyB : null);
        if (!beadBody) return;
        const beadVelocity = beadBody.velocity || { x: 0, y: 0 };
        const relSpeed = Math.sqrt(
          (Number(beadVelocity.x) || 0) ** 2 +
          (Number(beadVelocity.y) || 0) ** 2
        );
        if (relSpeed > maxRelSpeed) {
          maxRelSpeed = relSpeed;
          impactVector = {
            x: Number(beadVelocity.x) || 0,
            y: Number(beadVelocity.y) || 0
          };
        }
      });
      if (maxRelSpeed <= TRAY_IMPACT_FEEDBACK_MIN_SPEED) return;
      const now = Date.now();
      if (!this.lastTrayImpactAt || now - this.lastTrayImpactAt > 90) {
        this.lastTrayImpactAt = now;
        this.triggerTrayImpactFeedback(impactVector || { x: 1, y: 0 });
      }
    });
  },

  isWorkspaceBeadBody(body) {
    const plugin = (body && body.plugin) || {};
    return !!plugin.materialId && plugin.designIndex != null;
  },

  isTrayWallBody(body) {
    return !!body && body.label === 'tray-wall';
  },

  clampAngularVelocity(value, limit = MAX_BEAD_ANGULAR_VELOCITY) {
    const raw = Number(value) || 0;
    return Math.max(-limit, Math.min(limit, raw));
  },

  addBodySpin(body, delta, options = {}) {
    if (!Body || !body || body.isStatic) return;
    const maxDelta = Number(options.maxDelta || 0);
    const limitedDelta = maxDelta > 0
      ? Math.max(-maxDelta, Math.min(maxDelta, Number(delta) || 0))
      : (Number(delta) || 0);
    if (Math.abs(limitedDelta) < 0.0004) return;
    const limit = Number(options.limit || MAX_BEAD_ANGULAR_VELOCITY);
    Body.setAngularVelocity(body, this.clampAngularVelocity((Number(body.angularVelocity) || 0) + limitedDelta, limit));
    body.isSleeping = false;
    body.sleepCounter = 0;
  },

  getCollisionNormal(pair, bodyA, bodyB) {
    const normal = pair && pair.collision && pair.collision.normal;
    if (normal && Number.isFinite(normal.x) && Number.isFinite(normal.y)) {
      const length = Math.sqrt(normal.x * normal.x + normal.y * normal.y) || 1;
      return { x: normal.x / length, y: normal.y / length };
    }
    const dx = ((bodyB && bodyB.position && bodyB.position.x) || 0) - ((bodyA && bodyA.position && bodyA.position.x) || 0);
    const dy = ((bodyB && bodyB.position && bodyB.position.y) || 0) - ((bodyA && bodyA.position && bodyA.position.y) || 0);
    const distance = Math.sqrt(dx * dx + dy * dy) || 1;
    return { x: dx / distance, y: dy / distance };
  },

  applyCollisionSpin(pair) {
    if (!Body || !pair) return;
    const bodyA = pair.bodyA;
    const bodyB = pair.bodyB;
    if (!bodyA || !bodyB) return;
    const beadA = this.isWorkspaceBeadBody(bodyA);
    const beadB = this.isWorkspaceBeadBody(bodyB);
    if (!beadA && !beadB) return;
    const relX = ((bodyA.velocity && bodyA.velocity.x) || 0) - ((bodyB.velocity && bodyB.velocity.x) || 0);
    const relY = ((bodyA.velocity && bodyA.velocity.y) || 0) - ((bodyB.velocity && bodyB.velocity.y) || 0);
    const relSpeed = Math.sqrt(relX * relX + relY * relY);
    if (relSpeed < 0.16) return;
    const normal = this.getCollisionNormal(pair, bodyA, bodyB);
    const tangentX = -normal.y;
    const tangentY = normal.x;
    const tangentSpeed = relX * tangentX + relY * tangentY;
    const normalSpeed = Math.abs(relX * normal.x + relY * normal.y);
    const cross = (((bodyA.position && bodyA.position.x) || 0) - ((bodyB.position && bodyB.position.x) || 0)) * relY
      - (((bodyA.position && bodyA.position.y) || 0) - ((bodyB.position && bodyB.position.y) || 0)) * relX;
    const signSeed = Math.abs(tangentSpeed) > 0.01 ? tangentSpeed : cross;
    const sign = signSeed >= 0 ? 1 : -1;
    const spin = this.clampAngularVelocity(
      tangentSpeed * COLLISION_SPIN_FACTOR + sign * Math.min(0.065, normalSpeed * 0.0085),
      0.11
    );
    if (beadA) this.addBodySpin(bodyA, -spin);
    if (beadB) this.addBodySpin(bodyB, spin);
  },

  dampenNeighborBeadCollision(pair) {
    if (!Body || !pair) return;
    const bodyA = pair.bodyA;
    const bodyB = pair.bodyB;
    if (!bodyA || !bodyB || bodyA.isStatic || bodyB.isStatic) return;
    if (!this.isWorkspaceBeadBody(bodyA) || !this.isWorkspaceBeadBody(bodyB)) return;
    const plugA = bodyA.plugin || {};
    const plugB = bodyB.plugin || {};
    if (plugA.isLauncher || plugB.isLauncher) return;
    const normal = this.getCollisionNormal(pair, bodyA, bodyB);
    let normalX = normal.x;
    let normalY = normal.y;
    const vAX = Number(bodyA.velocity && bodyA.velocity.x) || 0;
    const vAY = Number(bodyA.velocity && bodyA.velocity.y) || 0;
    const vBX = Number(bodyB.velocity && bodyB.velocity.x) || 0;
    const vBY = Number(bodyB.velocity && bodyB.velocity.y) || 0;
    let separationSpeed = (vBX - vAX) * normalX + (vBY - vAY) * normalY;
    if (separationSpeed < -BILLIARD_NEIGHBOR_REBOUND_MIN_SPEED) {
      separationSpeed = -separationSpeed;
      normalX = -normalX;
      normalY = -normalY;
    }
    if (separationSpeed <= BILLIARD_NEIGHBOR_REBOUND_MIN_SPEED) return;
    const correction = Math.min(
      BILLIARD_NEIGHBOR_REBOUND_MAX_CORRECTION,
      separationSpeed * (1 - BILLIARD_NEIGHBOR_REBOUND_DAMPING) * 0.5
    );
    Body.setVelocity(bodyA, {
      x: vAX + normalX * correction,
      y: vAY + normalY * correction
    });
    Body.setVelocity(bodyB, {
      x: vBX - normalX * correction,
      y: vBY - normalY * correction
    });
  },

  handleFrozenImpactCollision(pairs = []) {
    if (!this.pendingFrozenImpact || !Body) return;
    for (let index = 0; index < pairs.length; index += 1) {
      const pair = pairs[index];
      const bodyA = pair.bodyA;
      const bodyB = pair.bodyB;
      const plugA = (bodyA && bodyA.plugin) || {};
      const plugB = (bodyB && bodyB.plugin) || {};
      const launcher = plugA.isLauncher ? bodyA : (plugB.isLauncher ? bodyB : null);
      const hitBody = launcher === bodyA ? bodyB : bodyA;
      const hitPlug = (hitBody && hitBody.plugin) || {};
      if (launcher && hitPlug.frozenUntilImpact) {
        this.releaseFrozenBodiesFromImpact(launcher, hitBody);
        return;
      }
    }
  },

  handleTrayWallCollision(pairs = []) {
    if (!Body || !pairs.length) return;
    let touchedWall = false;
    pairs.forEach(pair => {
      const bodyA = pair && pair.bodyA;
      const bodyB = pair && pair.bodyB;
      const beadBody = this.isTrayWallBody(bodyA) && this.isWorkspaceBeadBody(bodyB)
        ? bodyB
        : (this.isTrayWallBody(bodyB) && this.isWorkspaceBeadBody(bodyA) ? bodyA : null);
      if (!beadBody) return;
      if (beadBody.plugin) beadBody.plugin.launchAssistUntil = 0;
      this.resolveTrayBoundaryForBody(beadBody, {
        padding: TRAY_BOUNDARY_PADDING_RPX,
        guard: TRAY_BOUNDARY_GUARD_RPX + 10,
        lookaheadFrames: TRAY_BOUNDARY_MAX_LOOKAHEAD_FRAMES,
        force: true
      });
      touchedWall = true;
    });
    if (touchedWall) {
      this.extendTrayImpactContainment(520);
      this.scheduleCanvasRender(true);
    }
  },

  containImpactCollisionBodies(pairs = []) {
    if (!Body || !pairs.length) return;
    const layout = this.getStageLayout();
    let contained = false;
    let hasBeadCollision = false;
    pairs.forEach(pair => {
      [pair && pair.bodyA, pair && pair.bodyB].forEach(body => {
        if (!this.isWorkspaceBeadBody(body) || body.isStatic) return;
        hasBeadCollision = true;
        const fixed = this.resolveTrayBoundaryForBody(body, {
          layout,
          padding: TRAY_BOUNDARY_PADDING_RPX,
          guard: TRAY_IMPACT_CONTAIN_GUARD_RPX,
          lookaheadFrames: TRAY_BOUNDARY_MAX_LOOKAHEAD_FRAMES
        });
        if (fixed) contained = true;
      });
    });
    if (hasBeadCollision) this.extendTrayImpactContainment(720);
    if (contained) this.scheduleCanvasRender(true);
  },

  releaseFrozenBodiesFromImpact(launcher, hitBody) {
    if (!this.pendingFrozenImpact || !Body) return;
    this.pendingFrozenImpact = false;
    this.extendTrayImpactContainment();
    if (launcher && launcher.plugin) launcher.plugin.launchAssistUntil = 0;
    const layout = this.getStageLayout();
    const origin = (launcher && launcher.position) || { x: layout.center, y: layout.center };
    const launchVelocity = (launcher && launcher.velocity) || { x: 1, y: 0 };
    const launchSpeed = Math.sqrt(launchVelocity.x ** 2 + launchVelocity.y ** 2) || 1;
    const baseSpeed = Math.max(3.8, Math.min(8.4, launchSpeed * 0.40));
    const impactPoint = (hitBody && hitBody.position) || origin;
    const launchDirX = launchVelocity.x / launchSpeed;
    const launchDirY = launchVelocity.y / launchSpeed;
    if (launcher && this.isWorkspaceBeadBody(launcher) && !launcher.isStatic) {
      Body.setVelocity(launcher, this.shapeVelocityForTrayContainment(
        launcher,
        launcher.velocity,
        layout,
        {
          guard: TRAY_IMPACT_CONTAIN_GUARD_RPX,
          maxSpeed: this.isLowPerformanceDevice ? 10.4 : 12.2,
          inwardBias: 1.32
        }
      ));
      this.resolveTrayBoundaryForBody(launcher, {
        layout,
        padding: TRAY_BOUNDARY_PADDING_RPX,
        guard: TRAY_IMPACT_CONTAIN_GUARD_RPX,
        lookaheadFrames: TRAY_BOUNDARY_MAX_LOOKAHEAD_FRAMES
      });
    }
    (this.physicsBodies || []).forEach((body, index) => {
      if (!body || !body.plugin || !body.plugin.frozenUntilImpact) return;
      const dx = body.position.x - origin.x;
      const dy = body.position.y - origin.y;
      const distance = Math.max(1, Math.sqrt(dx * dx + dy * dy));
      const impactDx = body.position.x - impactPoint.x;
      const impactDy = body.position.y - impactPoint.y;
      const impactDistance = Math.sqrt(impactDx * impactDx + impactDy * impactDy);
      const influenceRadius = Math.max(132, Number(body.plugin.beadSize || 54) * 3.15);
      const proximity = body === hitBody
        ? 1
        : Math.max(0, 1 - impactDistance / influenceRadius);
      const localImpulse = body === hitBody ? 1.0 : proximity * proximity * 0.62;
      const tangentSign = index % 2 ? 1 : -1;
      const tangentX = -dy / distance * tangentSign;
      const tangentY = dx / distance * tangentSign;
      Body.setStatic(body, false);
      if (Sleeping) Sleeping.set(body, false);
      body.isSleeping = false;
      body.sleepCounter = 0;
      body.plugin.frozenUntilImpact = false;
      if (localImpulse <= 0.025) {
        Body.setVelocity(body, { x: 0, y: 0 });
        Body.setAngularVelocity(body, 0);
        return;
      }
      const radialSpeed = baseSpeed * (body === hitBody ? 1.0 : 0.52 * localImpulse);
      const carrySpeed = launchSpeed * (body === hitBody ? 0.24 : 0.07 * localImpulse);
      const tangentSpeed = baseSpeed * 0.14 * localImpulse;
      const releaseVelocity = {
        x: dx / distance * radialSpeed + launchDirX * carrySpeed + tangentX * tangentSpeed,
        y: dy / distance * radialSpeed + launchDirY * carrySpeed + tangentY * tangentSpeed
      };
      const maxReleaseSpeed = body === hitBody
        ? (this.isLowPerformanceDevice ? 8.8 : 10.0)
        : (this.isLowPerformanceDevice ? 5.8 : 6.8);
      Body.setVelocity(body, this.shapeVelocityForTrayContainment(
        body,
        releaseVelocity,
        layout,
        {
          guard: TRAY_IMPACT_CONTAIN_GUARD_RPX,
          maxSpeed: maxReleaseSpeed,
          inwardBias: body === hitBody ? 1.35 : 1.12
        }
      ));
      this.clampBodyVelocity(body, maxReleaseSpeed);
      this.resolveTrayBoundaryForBody(body, {
        layout,
        padding: TRAY_BOUNDARY_PADDING_RPX,
        guard: TRAY_IMPACT_CONTAIN_GUARD_RPX,
        lookaheadFrames: TRAY_BOUNDARY_MAX_LOOKAHEAD_FRAMES
      });
      Body.setAngularVelocity(body, tangentSign * 0.060 * localImpulse);
    });
    this.clampBodiesInsideTray(layout, {
      guard: TRAY_IMPACT_CONTAIN_GUARD_RPX,
      lookaheadFrames: TRAY_BOUNDARY_MAX_LOOKAHEAD_FRAMES
    });
    this.triggerTrayImpactFeedback(launchVelocity);
    if (this.pendingImpactTargets && this.pendingImpactTargets.length) {
      this.physicsTargets = this.pendingImpactTargets;
      this.pendingImpactTargets = null;
      this.stringingStartedAt = Date.now();
      this.physicsStillFrames = 0;
    }
    this.scheduleCanvasRender(true);
  },

  triggerTrayImpactFeedback(vector = { x: 1, y: 0 }) {
    const speed = Math.sqrt((vector.x || 0) ** 2 + (vector.y || 0) ** 2) || 1;
    const amplitude = this.isLowPerformanceDevice ? 1.3 : 2.1;
    this.canvasImpact = {
      startedAt: Date.now(),
      duration: 150,
      x: (vector.x || 0) / speed * amplitude,
      y: (vector.y || 0) / speed * amplitude
    };
    this.scheduleCanvasRender(true);
  },

  onResize() {
    this.initDeviceLayout({ preserveActionState: true });
    if (this.data.workspaceCanvasVisible === false) return;
    clearTimeout(this.canvasResizeTimer);
    this.canvasResizeTimer = setTimeout(() => this.initWorkspaceCanvases(), 120);
  },

  initWorkspaceCanvases() {
    if (this.data.workspaceCanvasVisible === false) return;
    const query = wx.createSelectorQuery().in(this);
    query.select('#braceletCanvas').fields({ node: true, size: true });
    query.select('#workspaceFlightCanvas').fields({ node: true, size: true });
    query.select('.bracelet-circle').boundingClientRect();
    query.select('.material-drawer').boundingClientRect();
    query.exec(res => {
      const braceletInfo = res && res[0];
      const flightInfo = res && res[1];
      const circleRect = res && res[2];
      const drawerRect = res && res[3];
      const braceletCanvasState = this.setupCanvasNode(braceletInfo, circleRect);
      if (!braceletCanvasState || !braceletCanvasState.ctx) {
        this.handleCanvasRendererFailure('bracelet canvas unavailable');
        return;
      }
      this.braceletCanvasState = braceletCanvasState;
      this.workspaceCircleRect = circleRect;
      this.materialDrawerRect = drawerRect;
      this.flightCanvasState = this.setupCanvasNode(flightInfo, {
        left: 0,
        top: 0,
        width: (this.data.deviceInfo && this.data.deviceInfo.windowWidth) || 375,
        height: (this.data.deviceInfo && this.data.deviceInfo.windowHeight) || 667
      });
      this.canvasImageCache = this.canvasImageCache || {};
      this.materialImagePreloadSet = this.materialImagePreloadSet || {};
      if (this.data.canvasRenderError) this.setData({ canvasRenderError: false });
      this.scheduleCanvasRender();
      this.scheduleMaterialPreload(this.data.visibleMaterials);
      this.scheduleWorkspaceInteractionWarmup();
      this.markWorkspaceReady('canvas');
      if (this.flightQueue && this.flightQueue.length) this.processCanvasFlightQueue();
    });
  },

  handleCanvasRendererFailure(reason = '') {
    logWorkspaceWarning('workspace canvas unavailable:', reason);
    this.stopCanvasRenderLoop();
    this.braceletCanvasState = null;
    this.flightCanvasState = null;
    this.workspaceCircleRect = null;
    this.materialDrawerRect = null;
    this.canvasImageCache = {};
    this.canvasTextureCache = {};
    this.canvasShadowCache = {};
    this.materialImagePreloadSet = {};
    this.canvasFlight = null;
    clearTimeout(this.canvasRecoveryTimer);
    const attempt = Number(this.canvasRecoveryAttempts || 0) + 1;
    this.canvasRecoveryAttempts = attempt;
    if (attempt <= 3 && this.data.workspaceCanvasVisible !== false) {
      this.setData({ canvasFlightActive: false }, () => {
        this.canvasRecoveryTimer = setTimeout(() => {
          this.canvasRecoveryTimer = null;
          wx.nextTick(() => this.initWorkspaceCanvases());
        }, attempt * 140);
      });
      return;
    }
    this.setData({
      canvasFlightActive: false,
      canvasRenderError: true
    }, () => this.markWorkspaceReady('canvas'));
  },

  retryCanvasRenderer() {
    clearTimeout(this.canvasRecoveryTimer);
    this.canvasRecoveryTimer = null;
    this.canvasRecoveryAttempts = 0;
    this.setData({
      canvasRenderError: false,
      workspaceLoading: true,
      workspaceLoadingClass: '',
      workspaceLoadingText: '正在重新加载工作台',
      workspaceLoadingSubtext: '恢复盘面与珠材...'
    }, () => {
      this.workspaceBootStartedAt = Date.now();
      this.armWorkspaceLoadingFallback();
      wx.nextTick(() => this.initWorkspaceCanvases());
    });
  },

  setupCanvasNode(info, rect = {}) {
    if (!info || !info.node) return null;
    const canvas = info.node;
    const dpr = (wx.getWindowInfo && wx.getWindowInfo().pixelRatio)
      || (wx.getSystemInfoSync && wx.getSystemInfoSync().pixelRatio)
      || 1;
    const width = Math.max(1, Number(info.width || rect.width || 1));
    const height = Math.max(1, Number(info.height || rect.height || 1));
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;
    if (ctx.setTransform) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    else ctx.scale(dpr, dpr);
    return {
      canvas,
      ctx,
      dpr,
      width,
      height,
      rect: {
        left: Number(rect.left || 0),
        top: Number(rect.top || 0),
        width,
        height
      }
    };
  },

  requestCanvasFrame(callback) {
    const canvas = (this.braceletCanvasState && this.braceletCanvasState.canvas)
      || (this.flightCanvasState && this.flightCanvasState.canvas);
    if (canvas && canvas.requestAnimationFrame) {
      return { type: 'canvas', id: canvas.requestAnimationFrame(callback), canvas };
    }
    return { type: 'timer', id: setTimeout(callback, 16) };
  },

  cancelCanvasFrame(frame) {
    if (!frame) return;
    if (frame.type === 'canvas' && frame.canvas && frame.canvas.cancelAnimationFrame) {
      frame.canvas.cancelAnimationFrame(frame.id);
      return;
    }
    clearTimeout(frame.id);
  },

  hasActiveBraceletCanvasMotion() {
    return !!(
      this.physicsTimer
      || this.dragState
      || this.ringDragState
      || this.ringSlideState
      || this.canvasImpact
      || this.data.isShuffling
      || this.data.isStringingFinishing
      || this.data.isReleasingString
    );
  },

  hasActiveCanvasMotion() {
    return !!(
      this.hasActiveBraceletCanvasMotion()
      || this.canvasFlight
      || this.data.canvasFlightActive
    );
  },

  scheduleCanvasRender(keepLoop = false, options = {}) {
    if (this.data.workspaceCanvasVisible === false || this.data.canvasRenderError) return;
    if (options.markDirty !== false) this.braceletCanvasDirty = true;
    this.canvasKeepLoop = this.canvasKeepLoop || keepLoop;
    if (this.canvasFramePending) return;
    this.canvasFramePending = true;
    this.canvasFrame = this.requestCanvasFrame(() => {
      this.canvasFramePending = false;
      if (this.data.workspaceCanvasVisible === false) return;
      const keepLoopRequested = !!this.canvasKeepLoop;
      this.canvasKeepLoop = false;
      const hasFlightMotion = !!(this.canvasFlight || this.data.canvasFlightActive);
      const hasBraceletMotion = this.hasActiveBraceletCanvasMotion();
      const shouldCheckSignature = !this.braceletCanvasDirty
        && !this.canvasImpact
        && (hasBraceletMotion || (keepLoopRequested && !hasFlightMotion));
      const nextBraceletContext = shouldCheckSignature
        ? this.getCanvasBeadSpriteContext()
        : null;
      const nextBraceletSnapshot = shouldCheckSignature
        ? this.buildCanvasRenderSceneSnapshot(nextBraceletContext)
        : null;
      const nextBraceletSignature = shouldCheckSignature
        ? nextBraceletSnapshot.signature
        : '';
      const braceletSceneChanged = shouldCheckSignature
        ? nextBraceletSignature !== this.lastBraceletCanvasRenderSignature
        : true;
      const needsBraceletRender = this.braceletCanvasDirty
        || !!this.canvasImpact
        || (hasBraceletMotion && braceletSceneChanged)
        || (keepLoopRequested && !hasFlightMotion && braceletSceneChanged);
      if (needsBraceletRender) {
        this.renderBraceletCanvas(nextBraceletSignature, nextBraceletContext, nextBraceletSnapshot);
        this.braceletCanvasDirty = false;
      }
      if (this.canvasFlight || this.data.canvasFlightActive) {
        this.renderWorkspaceFlightCanvas();
      }
      const shouldContinue = this.canvasKeepLoop || this.hasActiveCanvasMotion();
      if (shouldContinue) this.scheduleCanvasRender(true, { markDirty: false });
    });
  },

  stopCanvasRenderLoop() {
    this.canvasKeepLoop = false;
    this.canvasFramePending = false;
    this.cancelCanvasFrame(this.canvasFrame);
    this.canvasFrame = null;
  },

  hideWorkspaceCanvasForOverlay() {
    this.stopCanvasRenderLoop();
    this.clearWorkspaceFlightCanvas();
    this.setData({
      // 原生 canvas 在小程序中可能脱离普通 z-index/visibility 层级，
      // 详情弹窗期间直接卸载节点，避免画布内容穿透到弹窗内部。
      workspaceCanvasVisible: false,
      workspaceCanvasSuppressed: true,
      canvasFlightActive: false
    });
  },

  restoreWorkspaceCanvasAfterOverlay() {
    const canvasNodeMissing = this.data.workspaceCanvasVisible === false || !this.braceletCanvasState;
    if (!this.data.workspaceCanvasSuppressed && !canvasNodeMissing) return;
    this.setData({
      workspaceCanvasVisible: true,
      workspaceCanvasSuppressed: false
    }, () => {
      if (canvasNodeMissing) {
        wx.nextTick(() => this.initWorkspaceCanvases());
        return;
      }
      this.scheduleCanvasRender();
    });
  },

  clearWorkspaceFlightCanvas() {
    const state = this.flightCanvasState;
    if (!state || !state.ctx) return;
    state.ctx.clearRect(0, 0, state.width, state.height);
  },

  renderWorkspaceFlightCanvas() {
    const state = this.flightCanvasState;
    if (!state || !state.ctx) return;
    const ctx = state.ctx;
    ctx.clearRect(0, 0, state.width, state.height);
    const flight = this.canvasFlight;
    if (!flight) return;
    const elapsed = Date.now() - flight.startedAt;
    const raw = Math.max(0, Math.min(1, elapsed / flight.duration));
    if (flight.trail && raw > 0.08) {
      [0.26, 0.16, 0.08].forEach((lag, trailIndex) => {
        const frame = this.resolveFlightFrame(flight, raw - lag);
        if (!frame) return;
        this.drawCanvasBead(ctx, {
          item: flight.material,
          x: frame.point.x,
          y: frame.point.y,
          size: frame.size * (0.90 + trailIndex * 0.025),
          rotation: frame.rotation,
          active: false,
          deleteReady: false,
          screenSpace: true,
          opacity: 0.10 + trailIndex * 0.07
        });
      });
    }
    const frame = this.resolveFlightFrame(flight, raw);
    if (!frame) return;
    this.drawCanvasBead(ctx, {
      item: flight.material,
      x: frame.point.x,
      y: frame.point.y,
      size: frame.size,
      rotation: frame.rotation,
      active: false,
      deleteReady: false,
      screenSpace: true,
      opacity: 1
    });
    this.clearEnergyPanelCanvasOverlap(ctx, state);
  },

  resolveFlightFrame(flight, rawValue) {
    if (!flight) return null;
    const raw = Math.max(0, Math.min(1, Number(rawValue) || 0));
    const progress = flight.easing === 'linear'
      ? raw
      : (flight.easing === 'swish' ? this.easeOutQuart(raw) : this.easeOutCubic(raw));
    const point = flight.path === 'line'
      ? {
        x: flight.start.x + (flight.end.x - flight.start.x) * progress,
        y: flight.start.y + (flight.end.y - flight.start.y) * progress
      }
      : this.quadraticBezier(flight.start, flight.control, flight.end, progress);
    const sizeProgress = flight.easing === 'linear' ? raw : this.easeOutCubic(raw);
    return {
      point,
      size: flight.sourceSize + (flight.targetSize - flight.sourceSize) * sizeProgress,
      rotation: flight.rotation + flight.rotationDelta * progress
    };
  },

  renderBraceletCanvas(sceneSignature = '', spriteContext = null, sceneSnapshot = null) {
    const state = this.braceletCanvasState;
    if (!state || !state.ctx) return;
    const ctx = state.ctx;
    ctx.clearRect(0, 0, state.width, state.height);
    const impactOffset = this.getCanvasImpactOffset();
    ctx.save();
    let restored = false;
    try {
      ctx.translate(impactOffset.x, impactOffset.y);
      const renderedSignature = this.drawCanvasBeadSprites(ctx, spriteContext, sceneSnapshot);
      ctx.restore();
      restored = true;
      const renderedSnapshot = this.latestCanvasDrawSnapshot || sceneSnapshot || null;
      const renderedSpriteCount = renderedSnapshot
        ? (renderedSnapshot.normalSprites || []).length + (renderedSnapshot.overlaySprites || []).length
        : 0;
      if (this.materialPayloadReady && this.data.selected.length && !renderedSpriteCount) {
        throw new Error('canvas bead sprites unavailable');
      }
      this.clearEnergyPanelCanvasOverlap(ctx, state);
      if (!this.canvasImpact) {
        this.lastBraceletCanvasRenderSignature = sceneSignature || renderedSignature || this.buildCanvasEmptySceneSignature();
        this.lastBraceletCanvasRenderSnapshot = renderedSnapshot;
      }
      this.canvasRecoveryAttempts = 0;
      if (this.data.canvasRenderError) this.setData({ canvasRenderError: false });
    } catch (error) {
      if (!restored) {
        try {
          ctx.restore();
        } catch (restoreError) {}
      }
      logWorkspaceWarning('workspace canvas render failed:', error);
      this.handleCanvasRendererFailure('bracelet canvas render failed');
    }
  },

  clearEnergyPanelCanvasOverlap(ctx, state) {
    if (!this.data.showEnergyPanel || !ctx || !state || !state.rect || !this.energyPanelRect) return;
    const deviceInfo = this.data.deviceInfo || {};
    const rpxToPx = (Number(deviceInfo.windowWidth) || 375) / 750;
    const paddingRpx = 10;
    const panel = this.energyPanelRect;
    const left = (panel.left - paddingRpx) * rpxToPx - Number(state.rect.left || 0);
    const top = (panel.top - paddingRpx) * rpxToPx - Number(state.rect.top || 0);
    const width = (panel.width + paddingRpx * 2) * rpxToPx;
    const height = (panel.height + paddingRpx * 2) * rpxToPx;
    const x = Math.max(0, left);
    const y = Math.max(0, top);
    const right = Math.min(Number(state.width || 0), left + width);
    const bottom = Math.min(Number(state.height || 0), top + height);
    if (right <= x || bottom <= y) return;
    ctx.clearRect(x, y, right - x, bottom - y);
  },

  getCanvasImpactOffset() {
    const impact = this.canvasImpact;
    if (!impact) return { x: 0, y: 0 };
    const elapsed = Date.now() - impact.startedAt;
    const duration = impact.duration || 150;
    if (elapsed >= duration) {
      this.canvasImpact = null;
      return { x: 0, y: 0 };
    }
    const progress = elapsed / duration;
    const wave = Math.sin(progress * Math.PI * 3.2) * Math.pow(1 - progress, 2);
    return {
      x: (impact.x || 0) * wave,
      y: (impact.y || 0) * wave
    };
  },

  getCachedBraceletGeometry(items) {
    const layout = this.getStageLayout();
    const key = [
      layout.center,
      layout.radius,
      (items || []).map(item => {
        const physical = resolveMaterialGeometry(item);
        return `${item.id}:${physical.displaySizeRpx}:${physical.spacingSizeRpx}:${physical.shape}:${physical.placementMode}:${physical.imageStringAxisDeg}`;
      }).join('|')
    ].join('::');
    if (this.braceletGeometryCache && this.braceletGeometryCache.key === key) {
      return this.braceletGeometryCache.geometry;
    }
    const geometry = this.calculateBraceletGeometry(items || []);
    this.braceletGeometryCache = { key, geometry };
    return geometry;
  },

  getCachedCanvasBeadItems(selected = [], placements = []) {
    const imageKey = this.canvasPlacementImageKey(selected, placements);
    const key = [
      this.materialCatalogDesignVersion || 0,
      selected.join('|'),
      imageKey
    ].join('::');
    if (this.canvasSelectedItemsCache && this.canvasSelectedItemsCache.key === key) {
      return this.canvasSelectedItemsCache.items;
    }
    const materials = this.getCachedSelectedMaterials(selected);
    const items = selected.map((id, index) => {
      const material = materials[index];
      if (!material) return null;
      const placement = placements[index] || {};
      return {
        ...material,
        image_url: placement.image_url || material.image_url || ''
      };
    }).filter(Boolean);
    this.canvasSelectedItemsCache = { key, items };
    return items;
  },

  canvasPlacementImageKey(selected = [], placements = []) {
    return (placements || [])
      .slice(0, selected.length)
      .map(placement => (placement && placement.image_url) || '')
      .join('|');
  },

  getCanvasSpriteStaticContext(selected = [], placements = []) {
    const layout = this.getStageLayout();
    const state = this.braceletCanvasState;
    const key = [
      this.materialCatalogDesignVersion || 0,
      selected.join('|'),
      this.canvasPlacementImageKey(selected, placements),
      layout.center,
      layout.radius,
      state && state.width || 0
    ].join('::');
    if (this.canvasSpriteContextCache && this.canvasSpriteContextCache.key === key) {
      return this.canvasSpriteContextCache.context;
    }
    const items = this.getCachedCanvasBeadItems(selected, placements);
    const geometry = this.getCachedBraceletGeometry(items);
    const logicalSize = layout.center * 2;
    const scale = state && state.width ? state.width / logicalSize : 1;
    const context = { items, geometry, layout, scale };
    this.canvasSpriteContextCache = { key, context };
    return context;
  },

  setLivePlacements(placements = []) {
    this.livePlacements = placements;
    this.livePlacementsSelectedKey = (this.data.selected || []).join('|');
    this.livePlacementsDesignVersion = this.materialCatalogDesignVersion || 0;
  },

  clearLivePlacements() {
    this.livePlacements = null;
    this.livePlacementsSelectedKey = '';
    this.livePlacementsDesignVersion = -1;
    this.lastPhysicsPlacementSyncSignature = '';
    this.selectedItemStylePatchCache = null;
  },

  physicsPlacementSyncSignature(placements = []) {
    const selectedKey = (this.data.selected || []).join('|');
    return [
      selectedKey,
      (placements || []).map((placement, index) => {
        const x = Math.round((Number(placement && placement.looseX) || 0) * 2);
        const y = Math.round((Number(placement && placement.looseY) || 0) * 2);
        const rotation = Math.round((Number(placement && placement.rotation) || 0) * 2);
        const size = Math.round((Number(placement && placement.beadSize) || 0) * 2);
        return `${index}:${x},${y},${rotation},${size}`;
      }).join('|')
    ].join('::');
  },

  shouldSyncPhysicsPlacements(placements = [], force = false) {
    const signature = this.physicsPlacementSyncSignature(placements);
    if (!force && signature && signature === this.lastPhysicsPlacementSyncSignature) return false;
    this.lastPhysicsPlacementSyncSignature = signature;
    return true;
  },

  buildPhysicsPlacementsSnapshot(basePlacements = null) {
    const selected = this.data.selected || [];
    const source = basePlacements || this.getCachedCanvasPlacements(selected, this.data.placements);
    const placements = source.slice();
    this.sanitizePhysicsBodies(this.getStageLayout());
    (this.physicsBodies || []).forEach(body => {
      const index = body && body.plugin && body.plugin.designIndex;
      if (index == null || !placements[index] || !body.position) return;
      placements[index] = {
        ...placements[index],
        looseX: body.position.x,
        looseY: body.position.y,
        rotation: body.angle * 180 / Math.PI,
        beadSize: body.plugin.beadSize
      };
    });
    return placements;
  },

  buildPhysicsBodyCluster(limit = 0) {
    const activeCount = Math.max(0, Number(limit) || 0);
    if (!activeCount) return null;
    const cluster = { x: 0, y: 0, count: 0 };
    (this.physicsBodies || []).forEach(body => {
      const index = body && body.plugin && body.plugin.designIndex;
      if (index == null || index < 0 || index >= activeCount || !body.position) return;
      const x = Number(body.position.x);
      const y = Number(body.position.y);
      if (!Number.isFinite(x) || !Number.isFinite(y)) return;
      cluster.x += x;
      cluster.y += y;
      cluster.count += 1;
    });
    return cluster.count ? cluster : null;
  },

  scheduleDragPhysicsFrame(force = false, onSynced) {
    if (force) {
      clearTimeout(this.dragPhysicsSyncTimer);
      this.dragPhysicsSyncTimer = null;
      this.lastDragPhysicsSyncAt = Date.now();
      this.syncPhysicsFrame(onSynced);
      return;
    }
    this.scheduleCanvasRender(true);
    const now = Date.now();
    const minInterval = Math.max(24, Number(this.physicsRenderInterval || 50));
    const elapsed = now - Number(this.lastDragPhysicsSyncAt || 0);
    if (elapsed >= minInterval) {
      this.lastDragPhysicsSyncAt = now;
      this.syncPhysicsFrame(onSynced);
      return;
    }
    clearTimeout(this.dragPhysicsSyncTimer);
    this.dragPhysicsSyncTimer = setTimeout(() => {
      this.dragPhysicsSyncTimer = null;
      this.lastDragPhysicsSyncAt = Date.now();
      this.syncPhysicsFrame(onSynced);
    }, Math.max(16, minInterval - elapsed));
  },

  getCanvasRenderPlacements(selected = [], sourcePlacements = []) {
    const selectedKey = (selected || []).join('|');
    if (
      sourcePlacements
      && sourcePlacements === this.livePlacements
      && this.livePlacementsSelectedKey === selectedKey
      && this.livePlacementsDesignVersion === (this.materialCatalogDesignVersion || 0)
    ) {
      return sourcePlacements;
    }
    return this.getCachedCanvasPlacements(selected, sourcePlacements);
  },

  getCachedCanvasPlacements(selected = [], placements = []) {
    const selectedKey = (selected || []).join('|');
    const cache = this.canvasPlacementsCache;
    if (
      cache
      && cache.selectedRef === selected
      && cache.placementsRef === placements
      && cache.selectedKey === selectedKey
      && cache.materialCatalogDesignVersion === (this.materialCatalogDesignVersion || 0)
    ) {
      return cache.placements;
    }
    const normalized = this.normalizePlacements(selected, placements);
    this.canvasPlacementsCache = {
      selectedRef: selected,
      placementsRef: placements,
      selectedKey,
      materialCatalogDesignVersion: this.materialCatalogDesignVersion || 0,
      placements: normalized
    };
    return normalized;
  },

  trimCanvasImageCache() {
    const cache = this.canvasImageCache || {};
    const keys = Object.keys(cache);
    if (keys.length <= CANVAS_IMAGE_CACHE_LIMIT) return;
    keys
      .map(key => ({ key, entry: cache[key] || {} }))
      .filter(item => !item.entry.loading)
      .sort((a, b) => Number(a.entry.lastUsedAt || 0) - Number(b.entry.lastUsedAt || 0))
      .slice(0, Math.max(0, keys.length - CANVAS_IMAGE_CACHE_LIMIT))
      .forEach(item => {
        delete cache[item.key];
      });
  },

  trimCanvasTextureCache() {
    const cache = this.canvasTextureCache || {};
    const keys = Object.keys(cache);
    if (keys.length <= CANVAS_TEXTURE_CACHE_LIMIT) return;
    keys
      .map(key => ({ key, entry: cache[key] || {} }))
      .sort((a, b) => Number(a.entry.lastUsedAt || 0) - Number(b.entry.lastUsedAt || 0))
      .slice(0, Math.max(0, keys.length - CANVAS_TEXTURE_CACHE_LIMIT))
      .forEach(item => {
        delete cache[item.key];
      });
  },

  trimCanvasShadowCache() {
    const cache = this.canvasShadowCache || {};
    const keys = Object.keys(cache);
    if (keys.length <= CANVAS_SHADOW_CACHE_LIMIT) return;
    keys
      .map(key => ({ key, entry: cache[key] || {} }))
      .sort((a, b) => Number(a.entry.lastUsedAt || 0) - Number(b.entry.lastUsedAt || 0))
      .slice(0, Math.max(0, keys.length - CANVAS_SHADOW_CACHE_LIMIT))
      .forEach(item => {
        delete cache[item.key];
      });
  },

  activeCanvasImageUsageKey(selected = this.data.selected || [], placements = this.livePlacements || this.data.placements || []) {
    const flightUrl = this.canvasFlight && this.canvasFlight.material && this.canvasFlight.material.image_url || '';
    return [
      this.materialCatalogVersion || 0,
      this.materialCatalogDesignVersion || 0,
      (selected || []).join('|'),
      this.canvasPlacementImageKey(selected, placements),
      flightUrl
    ].join('::');
  },

  getActiveCanvasImageUsageMap() {
    const selected = this.data.selected || [];
    const placements = this.livePlacements || this.data.placements || [];
    const key = this.activeCanvasImageUsageKey(selected, placements);
    if (this.activeCanvasImageUsageCache && this.activeCanvasImageUsageCache.key === key) {
      return this.activeCanvasImageUsageCache.map;
    }
    const map = Object.create(null);
    const flightUrl = this.canvasFlight && this.canvasFlight.material && this.canvasFlight.material.image_url || '';
    if (flightUrl) map[flightUrl] = true;
    const materials = this.getCachedSelectedMaterials(selected);
    for (let index = 0; index < selected.length; index += 1) {
      const placement = placements[index] || {};
      if (placement.image_url) map[placement.image_url] = true;
      const material = materials[index];
      if (material && material.image_url) map[material.image_url] = true;
    }
    this.activeCanvasImageUsageCache = { key, map };
    return map;
  },

  isCanvasImageUsedByActiveScene(url) {
    if (!url) return false;
    const usageMap = this.getActiveCanvasImageUsageMap();
    return !!(usageMap && usageMap[url]);
  },

  scheduleCanvasImageReadyRender(url) {
    if (this.data.workspaceCanvasVisible === false) return;
    if (this.isCanvasImageUsedByActiveScene(url)) {
      this.scheduleCanvasRender();
    }
  },

  getCanvasImage(url) {
    if (!url || !this.braceletCanvasState || !this.braceletCanvasState.canvas) return null;
    this.canvasImageCache = this.canvasImageCache || {};
    const cached = this.canvasImageCache[url];
    if (cached && cached.loaded) {
      cached.lastUsedAt = Date.now();
      return cached.image;
    }
    if (cached && cached.loading) {
      cached.lastUsedAt = Date.now();
      return null;
    }
    const image = this.braceletCanvasState.canvas.createImage();
    const entry = { image, loading: true, loaded: false, failed: false, lastUsedAt: Date.now() };
    this.canvasImageCache[url] = entry;
    this.trimCanvasImageCache();
    image.onload = () => {
      entry.loading = false;
      entry.loaded = true;
      entry.lastUsedAt = Date.now();
      this.scheduleCanvasTextureWarmup();
      this.scheduleCanvasImageReadyRender(url);
    };
    image.onerror = () => {
      entry.loading = false;
      entry.failed = true;
      entry.lastUsedAt = Date.now();
      this.scheduleCanvasImageReadyRender(url);
    };
    image.src = url;
    return null;
  },

  warmCanvasMaterialTextures(material = {}, imageUrl = '') {
    const url = String(imageUrl || material.image_url || '').trim();
    if (!url) return false;
    const item = { ...material, image_url: url };
    const image = this.getCanvasImage(url);
    if (!image) {
      this.canvasTextureWarmupByUrl = this.canvasTextureWarmupByUrl || Object.create(null);
      const key = `${item.id || item.skuId || item.sku_id || item.material_code || item.name || ''}::${url}`;
      const entries = this.canvasTextureWarmupByUrl[url] || [];
      if (!entries.some(entry => entry.key === key)) entries.push({ key, item });
      this.canvasTextureWarmupByUrl[url] = entries;
      return false;
    }
    const textureSize = resolveMaterialGeometry(item, { maxDisplayRpx: 72 }).displaySizeRpx;
    this.getCanvasBeadTexture(item, textureSize);
    return true;
  },

  scheduleCanvasTextureWarmup() {
    clearTimeout(this.canvasTextureWarmupTimer);
    this.canvasTextureWarmupTimer = setTimeout(() => {
      this.canvasTextureWarmupTimer = null;
      if (this.isMaterialPreloadBusy()) {
        this.scheduleCanvasTextureWarmup();
        return;
      }
      const pending = this.canvasTextureWarmupByUrl || {};
      const url = Object.keys(pending)[0];
      if (!url) return;
      const entries = pending[url] || [];
      delete pending[url];
      entries.forEach(entry => this.warmCanvasMaterialTextures(entry.item, url));
      if (Object.keys(pending).length) this.scheduleCanvasTextureWarmup();
    }, this.isLowPerformanceDevice ? 90 : 32);
  },

  hasCanvasImagePreloadRecord(url) {
    if (!url || !this.canvasImageCache) return false;
    const cached = this.canvasImageCache[url];
    if (!cached) return false;
    cached.lastUsedAt = Date.now();
    return !!(cached.loaded || cached.loading || cached.failed);
  },

  hasMaterialImagePreloadRecord(url) {
    if (!url || !this.materialImagePreloadSet) return false;
    const record = this.materialImagePreloadSet[url];
    if (!record) return false;
    if (record && typeof record === 'object') record.lastUsedAt = Date.now();
    return true;
  },

  materialPreloadSignature(materials = []) {
    return (materials || [])
      .map(item => {
        if (!item) return '';
        const url = this.peekNextMaterialImageUrl(item);
        return url ? `${this.materialImageGroupKey(item)}::${url}` : '';
      })
      .filter(Boolean)
      .join('|');
  },

  rememberMaterialImagePreload(url, status = 'loaded') {
    if (!url) return;
    this.materialImagePreloadSet = this.materialImagePreloadSet || {};
    this.materialImagePreloadSet[url] = {
      status,
      lastUsedAt: Date.now()
    };
    this.trimMaterialImagePreloadRecords();
  },

  trimMaterialImagePreloadRecords() {
    const records = this.materialImagePreloadSet || {};
    const keys = Object.keys(records);
    if (keys.length <= MATERIAL_PRELOAD_RECORD_LIMIT) return;
    keys
      .map(key => {
        const entry = records[key];
        return {
          key,
          lastUsedAt: entry && typeof entry === 'object' ? Number(entry.lastUsedAt || 0) : 0
        };
      })
      .sort((a, b) => a.lastUsedAt - b.lastUsedAt)
      .slice(0, Math.max(0, keys.length - MATERIAL_PRELOAD_RECORD_LIMIT))
      .forEach(item => {
        delete records[item.key];
      });
  },

  scheduleMaterialPreload(materials = []) {
    const signature = this.materialPreloadSignature(materials);
    if (
      signature
      && signature === this.materialPreloadActiveSignature
      && (this.materialPreloadTimer || (this.materialPreloadQueue && this.materialPreloadQueue.length))
    ) {
      return;
    }
    if (
      signature
      && signature === this.materialPreloadCompletedSignature
      && !this.materialPreloadTimer
      && !(this.materialPreloadQueue && this.materialPreloadQueue.length)
    ) {
      return;
    }
    clearTimeout(this.materialPreloadTimer);
    this.materialPreloadToken = Number(this.materialPreloadToken || 0) + 1;
    const token = this.materialPreloadToken;
    this.materialPreloadActiveSignature = signature;
    this.materialPreloadDeferStartedAt = 0;
    const delay = this.isLowPerformanceDevice ? 420 : 180;
    this.materialPreloadTimer = setTimeout(() => {
      this.materialPreloadTimer = null;
      this.materialPreloadQueue = this.buildMaterialPreloadQueue(materials);
      this.runMaterialPreloadBatch(token);
    }, delay);
  },

  buildMaterialPreloadQueue(materials = []) {
    const preloadCount = this.isLowPerformanceDevice ? 4 : 10;
    const canvasPreloadCount = this.isLowPerformanceDevice ? 4 : 8;
    const seen = {};
    const queue = [];
    let infoQueued = 0;
    let canvasQueued = 0;
    (materials || []).some(item => {
      const url = item && this.peekNextMaterialImageUrl(item);
      if (!url || seen[url]) return false;
      seen[url] = true;
      const preloadInfo = infoQueued < preloadCount && !this.hasMaterialImagePreloadRecord(url);
      const preloadCanvas = canvasQueued < canvasPreloadCount && !this.hasCanvasImagePreloadRecord(url);
      if (!preloadInfo && !preloadCanvas) return false;
      queue.push({ url, preloadInfo, preloadCanvas, material: item });
      if (preloadInfo) infoQueued += 1;
      if (preloadCanvas) canvasQueued += 1;
      return infoQueued >= preloadCount && canvasQueued >= canvasPreloadCount;
    });
    return queue;
  },

  isMaterialPreloadBusy() {
    return !!(
      this.flightActive
      || (this.flightQueue && this.flightQueue.length)
      || this.canvasFlight
      || this.data.canvasFlightActive
      || this.physicsTimer
      || this.dragState
      || this.ringDragState
      || this.ringSlideState
      || this.data.isShuffling
      || this.data.isStringingFinishing
      || this.data.isReleasingString
    );
  },

  shouldDeferMaterialPreloadForMotion() {
    if (!this.isMaterialPreloadBusy()) {
      this.materialPreloadDeferStartedAt = 0;
      return false;
    }
    const now = Date.now();
    if (!this.materialPreloadDeferStartedAt) this.materialPreloadDeferStartedAt = now;
    const maxDefer = this.isLowPerformanceDevice
      ? MATERIAL_PRELOAD_MAX_DEFER_MS * 1.35
      : MATERIAL_PRELOAD_MAX_DEFER_MS;
    return now - this.materialPreloadDeferStartedAt < maxDefer;
  },

  scheduleMaterialPreloadRetry(token, delay) {
    clearTimeout(this.materialPreloadTimer);
    this.materialPreloadTimer = setTimeout(() => {
      this.materialPreloadTimer = null;
      this.runMaterialPreloadBatch(token);
    }, delay);
  },

  runMaterialPreloadBatch(token = this.materialPreloadToken) {
    if (token !== this.materialPreloadToken) return;
    const queue = this.materialPreloadQueue || [];
    if (!queue.length) {
      this.materialPreloadCompletedSignature = this.materialPreloadActiveSignature || '';
      this.materialPreloadDeferStartedAt = 0;
      return;
    }
    if (this.shouldDeferMaterialPreloadForMotion()) {
      const retryDelay = this.isLowPerformanceDevice
        ? MATERIAL_PRELOAD_IDLE_RETRY_MS * 1.5
        : MATERIAL_PRELOAD_IDLE_RETRY_MS;
      this.scheduleMaterialPreloadRetry(token, retryDelay);
      return;
    }
    const busy = this.isMaterialPreloadBusy();
    const batchSize = busy ? 1 : (this.isLowPerformanceDevice ? 2 : MATERIAL_PRELOAD_BATCH_SIZE);
    queue.splice(0, batchSize).forEach(task => {
      if (!task || !task.url) return;
      if (task.preloadCanvas && this.braceletCanvasState && this.braceletCanvasState.canvas) {
        this.warmCanvasMaterialTextures(task.material || {}, task.url);
      }
      if (task.preloadInfo && wx.getImageInfo) {
        if (!this.hasMaterialImagePreloadRecord(task.url)) {
          this.rememberMaterialImagePreload(task.url, 'loading');
          wx.getImageInfo({
            src: task.url,
            success: () => this.rememberMaterialImagePreload(task.url, 'loaded'),
            fail: () => this.rememberMaterialImagePreload(task.url, 'failed')
          });
        }
      }
    });
    if (!queue.length || token !== this.materialPreloadToken) {
      if (!queue.length && token === this.materialPreloadToken) {
        this.materialPreloadCompletedSignature = this.materialPreloadActiveSignature || '';
        this.materialPreloadDeferStartedAt = 0;
      }
      return;
    }
    if (busy) this.materialPreloadDeferStartedAt = Date.now();
    const delay = busy
      ? (this.isLowPerformanceDevice ? MATERIAL_PRELOAD_IDLE_RETRY_MS * 1.5 : MATERIAL_PRELOAD_IDLE_RETRY_MS)
      : (this.isLowPerformanceDevice ? MATERIAL_PRELOAD_BATCH_DELAY_MS * 2 : MATERIAL_PRELOAD_BATCH_DELAY_MS);
    this.scheduleMaterialPreloadRetry(token, delay);
  },

  pauseMaterialBackgroundPreload() {
    clearTimeout(this.materialPreloadTimer);
    this.materialPreloadTimer = null;
    this.materialPreloadToken = Number(this.materialPreloadToken || 0) + 1;
    this.materialPreloadQueue = [];
    this.materialPreloadActiveSignature = '';
    this.materialPreloadCompletedSignature = '';
    this.materialPreloadDeferStartedAt = 0;
    Object.values(this.materialImagePoolWarmTimers || {}).forEach(timer => clearTimeout(timer));
    this.materialImagePoolWarmTimers = {};
  },

  canvasRenderBucket(value, min = 1, max = Infinity, step = 8) {
    const raw = Number(value);
    const safeMin = Number.isFinite(Number(min)) ? Number(min) : 1;
    const safeMax = Number.isFinite(Number(max)) ? Number(max) : Infinity;
    const safeStep = Math.max(1, Number(step) || 1);
    if (!Number.isFinite(raw)) return safeMin;
    const bucket = Math.round(raw / safeStep) * safeStep;
    return Math.max(safeMin, Math.min(safeMax, bucket));
  },

  getCanvasBeadTexture(item = {}, size = 64, options = {}) {
    const dpr = (this.braceletCanvasState && this.braceletCanvasState.dpr) || 1;
    const baseSize = Math.round(Number(size) || 64);
    const bucket = this.canvasRenderBucket(
      baseSize * dpr,
      64,
      item.image_url ? 256 : 160,
      CANVAS_TEXTURE_BUCKET_STEP
    );
    const key = `${item.id || item.skuId || item.image_url || item.name || 'bead'}::${item.image_url || item.color || ''}::${bucket}`;
    this.canvasTextureCache = this.canvasTextureCache || {};
    const cached = this.canvasTextureCache[key];
    if (cached && cached.ready) {
      cached.lastUsedAt = Date.now();
      return cached.canvas;
    }
    if (cached && cached.failed) return null;
    if (options.allowCreate === false) return null;
    if (!wx.createOffscreenCanvas) return null;
    const sourceImage = item.image_url ? this.getCanvasImage(item.image_url) : null;
    if (item.image_url && !sourceImage) return null;
    try {
      const canvas = wx.createOffscreenCanvas({ type: '2d', width: bucket, height: bucket });
      const ctx = canvas.getContext('2d');
      const radius = bucket / 2;
      if (sourceImage) {
        ctx.clearRect(0, 0, bucket, bucket);
        ctx.drawImage(sourceImage, 0, 0, bucket, bucket);
        this.canvasTextureCache[key] = { ready: true, canvas, lastUsedAt: Date.now() };
        this.trimCanvasTextureCache();
        return canvas;
      }
      ctx.save();
      ctx.beginPath();
      ctx.arc(radius, radius, radius, 0, Math.PI * 2);
      ctx.clip();
      const gradient = ctx.createRadialGradient(bucket * 0.36, bucket * 0.32, bucket * 0.06, radius, radius, radius);
      gradient.addColorStop(0, item.shine || '#ffffff');
      gradient.addColorStop(0.18, item.color || '#d8d2c8');
      gradient.addColorStop(0.72, item.color || '#d8d2c8');
      gradient.addColorStop(1, 'rgba(32,24,18,0.28)');
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, bucket, bucket);
      ctx.fillStyle = 'rgba(255,255,255,0.52)';
      ctx.beginPath();
      ctx.arc(bucket * 0.38, bucket * 0.34, bucket * 0.11, 0, Math.PI * 2);
      ctx.fill();
      const shade = ctx.createRadialGradient(bucket * 0.36, bucket * 0.32, bucket * 0.08, radius, radius, radius);
      shade.addColorStop(0, 'rgba(255,255,255,0.03)');
      shade.addColorStop(0.62, 'rgba(255,255,255,0)');
      shade.addColorStop(1, 'rgba(0,0,0,0.20)');
      ctx.fillStyle = shade;
      ctx.fillRect(0, 0, bucket, bucket);
      ctx.restore();
      ctx.beginPath();
      ctx.arc(radius, radius, radius - 0.8, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(255,255,255,0.16)';
      ctx.lineWidth = 0.8;
      ctx.stroke();
      this.canvasTextureCache[key] = { ready: true, canvas, lastUsedAt: Date.now() };
      this.trimCanvasTextureCache();
      return canvas;
    } catch (error) {
      this.canvasTextureCache[key] = { ready: false, failed: true, lastUsedAt: Date.now() };
      this.trimCanvasTextureCache();
      return null;
    }
  },

  drawCanvasBeadShadowFallback(ctx, radius, hasImage) {
    const shadowStrength = hasImage ? 1 : 0.82;
    ctx.save();
    ctx.translate(0, radius * 0.18);
    ctx.scale(1.08, 0.56);
    const softShadow = ctx.createRadialGradient(0, 0, radius * 0.10, 0, 0, radius * 0.96);
    softShadow.addColorStop(0, `rgba(42, 33, 24, ${0.22 * shadowStrength})`);
    softShadow.addColorStop(0.40, `rgba(42, 33, 24, ${0.11 * shadowStrength})`);
    softShadow.addColorStop(0.72, `rgba(42, 33, 24, ${0.035 * shadowStrength})`);
    softShadow.addColorStop(1, 'rgba(44, 36, 26, 0)');
    ctx.fillStyle = softShadow;
    ctx.beginPath();
    ctx.arc(0, 0, radius * 0.96, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    ctx.save();
    ctx.translate(0, radius * 0.28);
    ctx.scale(0.80, 0.26);
    const contactShadow = ctx.createRadialGradient(0, 0, radius * 0.02, 0, 0, radius * 0.76);
    contactShadow.addColorStop(0, `rgba(30, 24, 18, ${0.28 * shadowStrength})`);
    contactShadow.addColorStop(0.42, `rgba(30, 24, 18, ${0.14 * shadowStrength})`);
    contactShadow.addColorStop(0.72, `rgba(30, 24, 18, ${0.045 * shadowStrength})`);
    contactShadow.addColorStop(1, 'rgba(34, 27, 20, 0)');
    ctx.fillStyle = contactShadow;
    ctx.beginPath();
    ctx.arc(0, 0, radius * 0.76, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  },

  getCanvasBeadShadowTexture(radius = 24, hasImage = true) {
    if (!wx.createOffscreenCanvas) return null;
    const dpr = (this.braceletCanvasState && this.braceletCanvasState.dpr) || 1;
    const bucket = this.canvasRenderBucket(radius * 2 * dpr, 20, Infinity, CANVAS_SHADOW_BUCKET_STEP);
    const key = `vertical-v2::${hasImage ? 'image' : 'fallback'}::${bucket}`;
    this.canvasShadowCache = this.canvasShadowCache || {};
    const cached = this.canvasShadowCache[key];
    if (cached && cached.ready) {
      cached.lastUsedAt = Date.now();
      return cached;
    }
    if (cached && cached.failed) return null;
    const logicalRadius = bucket / (2 * dpr);
    const left = -logicalRadius * 1.05;
    const top = logicalRadius * 0.38;
    const width = logicalRadius * 2.62;
    const height = logicalRadius * 1.08;
    try {
      const canvas = wx.createOffscreenCanvas({
        type: '2d',
        width: Math.ceil(width * dpr),
        height: Math.ceil(height * dpr)
      });
      const ctx = canvas.getContext('2d');
      if (!ctx) return null;
      if (ctx.setTransform) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      else ctx.scale(dpr, dpr);
      ctx.translate(-left, -top);
      this.drawCanvasBeadShadowFallback(ctx, logicalRadius, hasImage);
      const entry = { ready: true, canvas, left, top, width, height, lastUsedAt: Date.now() };
      this.canvasShadowCache[key] = entry;
      this.trimCanvasShadowCache();
      return entry;
    } catch (error) {
      this.canvasShadowCache[key] = { ready: false, failed: true, lastUsedAt: Date.now() };
      this.trimCanvasShadowCache();
      return null;
    }
  },

  drawCanvasBeadShadow(ctx, radius, hasImage) {
    const texture = this.getCanvasBeadShadowTexture(radius, hasImage);
    if (texture && texture.canvas) {
      ctx.drawImage(texture.canvas, texture.left, texture.top, texture.width, texture.height);
      return;
    }
    this.drawCanvasBeadShadowFallback(ctx, radius, hasImage);
  },

  drawCanvasNonRoundShadow(ctx, width, height) {
    const radiusX = Math.max(6, width * 0.48);
    const radiusY = Math.max(3, height * 0.22);
    ctx.save();
    ctx.translate(0, height * 0.10);
    ctx.scale(radiusX, radiusY);
    const shadow = ctx.createRadialGradient(0, 0, 0.08, 0, 0, 1);
    shadow.addColorStop(0, 'rgba(35,29,23,.26)');
    shadow.addColorStop(0.58, 'rgba(35,29,23,.10)');
    shadow.addColorStop(1, 'rgba(35,29,23,0)');
    ctx.fillStyle = shadow;
    ctx.beginPath();
    ctx.arc(0, 0, 1, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  },

  drawCanvasBead(ctx, sprite) {
    if (!ctx || !sprite || !sprite.item) return;
    const size = Math.max(8, Number(sprite.size) || 48);
    const drawWidth = Math.max(8, Number(sprite.drawWidth) || size);
    const drawHeight = Math.max(8, Number(sprite.drawHeight) || size);
    const radius = size / 2;
    const physical = resolveMaterialGeometry(sprite.item);
    const displayScale = size / Math.max(1, physical.displaySizeRpx);
    const collisionWidth = Math.max(8, physical.collisionWidthRpx * displayScale);
    const collisionHeight = Math.max(8, physical.collisionHeightRpx * displayScale);
    ctx.save();
    const opacity = Number.isFinite(Number(sprite.opacity)) ? Math.max(0, Math.min(1, Number(sprite.opacity))) : 1;
    ctx.globalAlpha = (sprite.deleteReady ? 0.58 : 1) * opacity;
    ctx.translate(sprite.x, sprite.y);
    const hasImage = Boolean(sprite.item.image_url);
    if (!sprite.screenSpace && !sprite.noShadow) {
      if (physical.isRound) this.drawCanvasBeadShadow(ctx, radius, hasImage);
      else this.drawCanvasNonRoundShadow(ctx, collisionWidth, collisionHeight);
    }
    ctx.rotate((Number(sprite.rotation) || 0) * Math.PI / 180);
    if (sprite.mirrorX) ctx.scale(-1, 1);
    if (sprite.active || sprite.deleteReady) {
      ctx.save();
      ctx.beginPath();
      if (physical.isRound) {
        ctx.arc(0, 0, radius + (sprite.deleteReady ? 5 : 4), 0, Math.PI * 2);
      } else {
        const padding = sprite.deleteReady ? 5 : 4;
        ctx.rect(
          -collisionWidth / 2 - padding,
          -collisionHeight / 2 - padding,
          collisionWidth + padding * 2,
          collisionHeight + padding * 2
        );
      }
      ctx.strokeStyle = sprite.deleteReady
        ? 'rgba(188, 62, 55, 0.86)'
        : (hasImage ? 'rgba(196, 151, 78, 0.88)' : 'rgba(18, 18, 18, 0.82)');
      ctx.lineWidth = sprite.deleteReady ? 3 : 2.5;
      ctx.stroke();
      ctx.restore();
    }
    ctx.save();
    if (!hasImage && physical.isRound) {
      ctx.beginPath();
      ctx.arc(0, 0, radius, 0, Math.PI * 2);
      ctx.clip();
    } else if (!hasImage) {
      ctx.beginPath();
      ctx.rect(-collisionWidth / 2, -collisionHeight / 2, collisionWidth, collisionHeight);
      ctx.clip();
    }
    const textureSize = Math.max(drawWidth, drawHeight);
    const texture = this.getCanvasBeadTexture(sprite.item, textureSize, {
      allowCreate: !sprite.screenSpace
    });
    const image = texture ? null : this.getCanvasImage(sprite.item.image_url);
    if (texture) {
      ctx.drawImage(texture, -drawWidth / 2, -drawHeight / 2, drawWidth, drawHeight);
    } else if (image) {
      ctx.drawImage(image, -drawWidth / 2, -drawHeight / 2, drawWidth, drawHeight);
    } else {
      const gradient = ctx.createRadialGradient(-radius * 0.28, -radius * 0.34, radius * 0.06, 0, 0, radius);
      gradient.addColorStop(0, sprite.item.shine || '#ffffff');
      gradient.addColorStop(0.18, sprite.item.color || '#d8d2c8');
      gradient.addColorStop(0.72, sprite.item.color || '#d8d2c8');
      gradient.addColorStop(1, 'rgba(32,24,18,0.34)');
      ctx.fillStyle = gradient;
      ctx.fillRect(-drawWidth / 2, -drawHeight / 2, drawWidth, drawHeight);
      ctx.fillStyle = 'rgba(255,255,255,0.52)';
      ctx.beginPath();
      ctx.arc(-radius * 0.24, -radius * 0.30, radius * 0.20, 0, Math.PI * 2);
      ctx.fill();
    }
    if (!hasImage) {
      const shade = ctx.createRadialGradient(-radius * 0.24, -radius * 0.28, radius * 0.08, 0, 0, radius);
      shade.addColorStop(0, 'rgba(255,255,255,0.04)');
      shade.addColorStop(0.64, 'rgba(255,255,255,0)');
      shade.addColorStop(1, 'rgba(0,0,0,0.20)');
      ctx.fillStyle = shade;
      ctx.fillRect(-drawWidth / 2, -drawHeight / 2, drawWidth, drawHeight);
    }
    ctx.restore();
    if (!hasImage) {
      ctx.beginPath();
      ctx.arc(0, 0, radius - 1, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(255,255,255,0.16)';
      ctx.lineWidth = 0.8;
      ctx.stroke();
    }
    ctx.restore();
  },

  getPhysicsBodyByDesignIndex() {
    const bodies = this.physicsBodies || [];
    if (!bodies.length) return [];
    const cache = this.physicsBodyByDesignIndexCache;
    if (cache && cache.bodiesRef === bodies && cache.length === bodies.length) {
      return cache.bodyByIndex;
    }
    const bodyByIndex = [];
    bodies.forEach(body => {
      if (body && body.plugin && body.plugin.designIndex != null) {
        bodyByIndex[body.plugin.designIndex] = body;
      }
    });
    this.physicsBodyByDesignIndexCache = {
      bodiesRef: bodies,
      length: bodies.length,
      bodyByIndex
    };
    return bodyByIndex;
  },

  getCanvasBeadSpriteContext() {
    const selected = this.data.selected || [];
    if (!selected.length) return null;
    const sourcePlacements = this.livePlacements || this.data.placements;
    const placements = this.getCanvasRenderPlacements(selected, sourcePlacements);
    const isLooseMode = this.data.isLooseMode;
    const bodyByIndex = isLooseMode && this.physicsBodies && this.physicsBodies.length
      ? this.getPhysicsBodyByDesignIndex()
      : null;
    return {
      ...this.getCanvasSpriteStaticContext(selected, placements),
      placements,
      isLooseMode,
      bodyByIndex,
      selectedBeadIndex: this.data.selectedBeadIndex,
      dragDeleteArmed: this.data.dragDeleteArmed
    };
  },

  fillCanvasBeadSprite(target, context, index) {
    if (!target || !context || !context.items) return null;
    const { items, placements, geometry, layout, scale, isLooseMode, bodyByIndex } = context;
    const item = items[index];
    if (!item) return null;
    const placement = placements[index] || {};
    const angle = geometry.angles[index] || 0;
    const body = bodyByIndex ? bodyByIndex[index] : null;
    const beadSize = geometry.beadSizes[index] || this.getMaterialDisplaySize(item.id);
    const physical = (geometry.materialGeometries || [])[index] || resolveMaterialGeometry(item);
    const displayScale = beadSize / Math.max(1, physical.displaySizeRpx);
    const stringedOffset = stringedMaterialOffset(physical, displayScale);
    let x;
    let y;
    let rotation;
    if (isLooseMode) {
      x = body && body.position ? body.position.x : Number(placement.looseX || layout.center);
      y = body && body.position ? body.position.y : Number(placement.looseY || layout.center);
      rotation = body && body.angle != null ? body.angle * 180 / Math.PI : Number(placement.rotation || 0);
    } else {
      x = layout.center + Math.cos(angle) * geometry.radius + stringedOffset.x;
      y = layout.center + Math.sin(angle) * geometry.radius + stringedOffset.y;
      rotation = stringedMaterialRotationDeg(angle, physical);
    }
    x += Number(placement.dx || 0);
    y += Number(placement.dy || 0);
    if (!isLooseMode) {
      rotation = stringedMaterialRotationDeg(
        Math.atan2(y - stringedOffset.y - layout.center, x - stringedOffset.x - layout.center),
        physical
      );
    }
    let dragging = false;
    let deleteReady = false;
    if (isLooseMode && this.dragState && this.dragState.index === index && this.dragState.body && this.dragState.body.position) {
      x = this.dragState.body.position.x;
      y = this.dragState.body.position.y;
      rotation = this.dragState.body.angle * 180 / Math.PI;
      dragging = true;
      deleteReady = !!context.dragDeleteArmed;
    }
    if (this.ringDragState && this.ringDragState.currentIndex === index && this.ringDragState.draggingX != null) {
      x = this.ringDragState.draggingX;
      y = this.ringDragState.draggingY;
      rotation = stringedMaterialRotationDeg(Math.atan2(y - layout.center, x - layout.center), physical);
      dragging = true;
      deleteReady = !!context.dragDeleteArmed;
    }
    target.item = item;
    target.index = index;
    target.x = x * scale;
    target.y = y * scale;
    target.size = beadSize * scale;
    target.logicalX = x;
    target.logicalY = y;
    target.logicalSize = beadSize;
    target.rotation = rotation;
    target.attachmentAxisRotation = isLooseMode
      ? rotation
      : (Number(angle || 0) * 180 / Math.PI + 90);
    target.beadCaps = beadCapSlotsFromPlacement(placement);
    target.active = index === context.selectedBeadIndex;
    target.dragging = dragging;
    target.deleteReady = deleteReady;
    target.opacity = 1;
    target.screenSpace = false;
    return target;
  },

  buildCanvasEmptySceneSignature() {
    const state = this.braceletCanvasState || {};
    const panel = this.energyPanelRect || {};
    return [
      'empty',
      Number(state.width || 0),
      Number(state.height || 0),
      this.data.showEnergyPanel ? 1 : 0,
      Math.round(Number(panel.left || 0)),
      Math.round(Number(panel.top || 0)),
      Math.round(Number(panel.width || 0)),
      Math.round(Number(panel.height || 0))
    ].join(':');
  },

  canvasSpriteSignaturePart(sprite = {}) {
    const item = sprite.item || {};
    return [
      sprite.index,
      item.id || '',
      item.image_url || '',
      Math.round((Number(sprite.x) || 0) * 2),
      Math.round((Number(sprite.y) || 0) * 2),
      Math.round((Number(sprite.size) || 0) * 2),
      Math.round((Number(sprite.rotation) || 0) * 2),
      sprite.active ? 1 : 0,
      sprite.dragging ? 1 : 0,
      sprite.deleteReady ? 1 : 0,
      sprite.attachedAccessory ? 1 : 0,
      sprite.attachmentSide || ''
    ].join(',');
  },

  buildCanvasRenderSceneSignatureParts(context = {}) {
    const state = this.braceletCanvasState || {};
    const panel = this.energyPanelRect || {};
    return [
      'scene',
      Number(state.width || 0),
      Number(state.height || 0),
      context.isLooseMode ? 1 : 0,
      context.selectedBeadIndex,
      context.dragDeleteArmed ? 1 : 0,
      this.data.showEnergyPanel ? 1 : 0,
      Math.round(Number(panel.left || 0)),
      Math.round(Number(panel.top || 0)),
      Math.round(Number(panel.width || 0)),
      Math.round(Number(panel.height || 0))
    ];
  },

  buildCanvasRenderSceneSnapshot(context = this.getCanvasBeadSpriteContext()) {
    if (!context || !context.items || !context.items.length) {
      return {
        signature: this.buildCanvasEmptySceneSignature(),
        normalSprites: [],
        overlaySprites: []
      };
    }
    const parts = this.buildCanvasRenderSceneSignatureParts(context);
    const normalSprites = [];
    const overlaySprites = [];
    const sprite = {};
    const hostSprites = [];
    for (let index = 0; index < context.items.length; index += 1) {
      const nextSprite = this.fillCanvasBeadSprite(sprite, context, index);
      if (!nextSprite) continue;
      parts.push(this.canvasSpriteSignaturePart(nextSprite));
      const snapshotSprite = { ...nextSprite };
      hostSprites.push(snapshotSprite);
      if (nextSprite.dragging || nextSprite.deleteReady) {
        overlaySprites.push(snapshotSprite);
      } else {
        normalSprites.push(snapshotSprite);
      }
    }
    hostSprites.forEach(hostSprite => {
      const slots = hostSprite.beadCaps || {};
      ['left', 'right'].forEach(side => {
        const capSprite = beadCapSprite(hostSprite, slots[side], side);
        if (!capSprite) return;
        parts.push(this.canvasSpriteSignaturePart(capSprite));
        overlaySprites.push(capSprite);
      });
    });
    return {
      signature: parts.join('|'),
      normalSprites,
      overlaySprites
    };
  },

  buildCanvasRenderSceneSignature(context = this.getCanvasBeadSpriteContext()) {
    return this.buildCanvasRenderSceneSnapshot(context).signature;
  },

  drawCanvasBeadSprites(ctx, contextOverride = null, sceneSnapshot = null) {
    const snapshot = sceneSnapshot || this.buildCanvasRenderSceneSnapshot(contextOverride || this.getCanvasBeadSpriteContext());
    this.latestCanvasDrawSnapshot = snapshot;
    (snapshot.normalSprites || []).forEach(item => this.drawCanvasBead(ctx, item));
    (snapshot.overlaySprites || []).forEach(item => this.drawCanvasBead(ctx, item));
    return snapshot.signature || this.buildCanvasEmptySceneSignature();
  },

  getReusableCanvasSpriteSnapshot() {
    const snapshot = this.lastBraceletCanvasRenderSnapshot;
    if (!snapshot || !snapshot.signature) return null;
    if (this.braceletCanvasDirty || this.canvasImpact || this.hasActiveBraceletCanvasMotion()) return null;
    if (snapshot.signature !== this.lastBraceletCanvasRenderSignature) return null;
    return snapshot;
  },

  getReusableCanvasHitTestSprites() {
    const snapshot = this.getReusableCanvasSpriteSnapshot();
    if (!snapshot) return null;
    const signature = snapshot.signature || '';
    const cache = this.canvasHitTestSpritesCache;
    if (cache && cache.signature === signature) return cache.sprites;
    const sprites = [
      ...(snapshot.normalSprites || []),
      ...(snapshot.overlaySprites || [])
    ];
    this.canvasHitTestSpritesCache = { signature, sprites };
    return sprites;
  },

  getCanvasBeadSprites() {
    const reusable = this.getReusableCanvasHitTestSprites();
    if (reusable) return reusable.map(sprite => ({ ...sprite }));
    const context = this.getCanvasBeadSpriteContext();
    if (!context || !context.items.length) return [];
    const sprite = {};
    return context.items.map((item, index) => {
      const nextSprite = this.fillCanvasBeadSprite(sprite, context, index);
      return nextSprite ? { ...nextSprite } : null;
    }).filter(Boolean);
  },

  hitTestCanvasBead(touch) {
    const hit = this.hitTestCanvasBeadInfo(touch);
    return hit ? hit.index : -1;
  },

  hitTestCanvasBeadInfo(touch) {
    const point = this.touchToCanvasTrayPoint(touch);
    if (!point) return null;
    const hitPoint = { x: point.x, y: point.y };
    const reusableSprites = this.getReusableCanvasHitTestSprites();
    if (reusableSprites) {
      const layout = point.layout || this.getStageLayout();
      return this.hitTestCanvasSpriteList(point, hitPoint, reusableSprites, layout);
    }
    const context = this.getCanvasBeadSpriteContext();
    if (!context || !context.items.length) {
      return { index: -1, point: hitPoint, sprite: null, outwardProjection: 0, isOuterEdge: false };
    }
    const layout = point.layout || this.getStageLayout();
    const sprite = {};
    for (let index = context.items.length - 1; index >= 0; index -= 1) {
      const current = this.fillCanvasBeadSprite(sprite, context, index);
      if (!current) continue;
      const dx = point.x - current.logicalX;
      const dy = point.y - current.logicalY;
      const radius = Math.max(24, current.logicalSize / 2 + 8);
      if (dx * dx + dy * dy <= radius * radius) {
        const beadDx = current.logicalX - layout.center;
        const beadDy = current.logicalY - layout.center;
        const beadDistance = Math.max(1, Math.sqrt(beadDx * beadDx + beadDy * beadDy));
        const outwardX = beadDx / beadDistance;
        const outwardY = beadDy / beadDistance;
        const outwardProjection = dx * outwardX + dy * outwardY;
        const coreRadius = Math.max(12, current.logicalSize * RING_SLIDE_EDGE_RATIO);
        return {
          index: current.index,
          point: hitPoint,
          sprite: { ...current },
          outwardProjection,
          isOuterEdge: outwardProjection > coreRadius
        };
      }
    }
    return { index: -1, point: hitPoint, sprite: null, outwardProjection: 0, isOuterEdge: false };
  },

  hitTestCanvasSpriteList(point, hitPoint, sprites = [], layout = this.getStageLayout()) {
    if (!sprites || !sprites.length) {
      return { index: -1, point: hitPoint, sprite: null, outwardProjection: 0, isOuterEdge: false };
    }
    for (let index = sprites.length - 1; index >= 0; index -= 1) {
      const current = sprites[index];
      if (!current) continue;
      const dx = point.x - current.logicalX;
      const dy = point.y - current.logicalY;
      const radius = Math.max(24, current.logicalSize / 2 + 8);
      if (dx * dx + dy * dy <= radius * radius) {
        const beadDx = current.logicalX - layout.center;
        const beadDy = current.logicalY - layout.center;
        const beadDistance = Math.max(1, Math.sqrt(beadDx * beadDx + beadDy * beadDy));
        const outwardX = beadDx / beadDistance;
        const outwardY = beadDy / beadDistance;
        const outwardProjection = dx * outwardX + dy * outwardY;
        const coreRadius = Math.max(12, current.logicalSize * RING_SLIDE_EDGE_RATIO);
        return {
          index: current.index,
          point: hitPoint,
          sprite: { ...current },
          outwardProjection,
          isOuterEdge: outwardProjection > coreRadius
        };
      }
    }
    return { index: -1, point: hitPoint, sprite: null, outwardProjection: 0, isOuterEdge: false };
  },

  touchToCanvasTrayPoint(touch) {
    const state = this.braceletCanvasState;
    if (!touch || !state || !state.rect) return null;
    const layout = this.getStageLayout();
    const clientX = Number(touch.clientX == null ? touch.pageX : touch.clientX);
    const clientY = Number(touch.clientY == null ? touch.pageY : touch.clientY);
    const scale = state.rect.width / (layout.center * 2);
    return {
      x: (clientX - state.rect.left) / scale,
      y: (clientY - state.rect.top) / scale,
      layout
    };
  },

  refreshBraceletCanvasRect(callback) {
    const query = wx.createSelectorQuery().in(this);
    query.select('.bracelet-circle').boundingClientRect();
    query.exec(res => {
      const rect = res && res[0];
      if (rect && this.braceletCanvasState) {
        this.braceletCanvasState.rect = {
          left: Number(rect.left || 0),
          top: Number(rect.top || 0),
          width: Number(rect.width || this.braceletCanvasState.width || 1),
          height: Number(rect.height || this.braceletCanvasState.height || 1)
        };
      } else if (rect) {
        this.braceletCanvasState = {
          rect: {
            left: Number(rect.left || 0),
            top: Number(rect.top || 0),
            width: Number(rect.width || 1),
            height: Number(rect.height || 1)
          },
          width: Number(rect.width || 1),
          height: Number(rect.height || 1)
        };
      }
      if (typeof callback === 'function') callback(rect || null);
    });
  },

  onBraceletCanvasTouchStart(e) {
    if (this.data.isShuffling || this.data.isStringingFinishing || this.data.isReleasingString) return;
    const touch = e.touches && e.touches[0];
    if (!touch) return;
    this.refreshBraceletCanvasRect(rect => {
      const hit = this.hitTestCanvasBeadInfo(touch);
      const index = hit && Number.isInteger(hit.index) ? hit.index : -1;
      if (!this.data.isLooseMode && this.shouldStartRingSlide(hit)) {
        this.pushHistory();
        this.beginRingSlide(touch, rect, { originIndex: index });
        return;
      }
      if (index < 0) return;
      this.pushHistory();
      if (this.data.isLooseMode && (!this.physicsBodies || !this.physicsBodies.length)) {
        if (this.data.sharedDesignFrozen) this.setData({ sharedDesignFrozen: false });
        this.startPhysicsFromCurrentDesign();
      }
      if (this.data.isLooseMode) {
        this.beginBeadDrag(index, touch, rect);
      } else {
        this.beginRingReorder(index, touch, rect);
      }
    });
  },

  onBraceletCanvasTouchMove(e) {
    this.onBeadTouchMove(e);
  },

  onBraceletCanvasTouchEnd(e) {
    this.onBeadTouchEnd(e);
  },

  easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
  },

  easeOutQuart(t) {
    return 1 - Math.pow(1 - t, 4);
  },

  easeOutBack(t) {
    const c1 = 1.12;
    const c3 = c1 + 1;
    return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
  },

  quadraticBezier(start, control, end, t) {
    const inv = 1 - t;
    return {
      x: inv * inv * start.x + 2 * inv * t * control.x + t * t * end.x,
      y: inv * inv * start.y + 2 * inv * t * control.y + t * t * end.y
    };
  },

  createPhysicsBody(id, placement, index, options = {}) {
    if (!this.physicsEngine) this.createPhysicsEngine();
    const beadSize = Number(placement.beadSize) || this.getMaterialDisplaySize(id);
    const material = this.findMaterialById(id) || {};
    const physical = resolveMaterialGeometry(material);
    const displayScale = beadSize / Math.max(1, physical.displaySizeRpx);
    const bodyWidth = Math.max(10, physical.collisionWidthRpx * displayScale - 0.4);
    const bodyHeight = Math.max(10, physical.collisionHeightRpx * displayScale - 0.4);
    const bodyRadius = Math.max(bodyWidth, bodyHeight) * 0.5;
    const initialPoint = this.constrainPointInsideTray({
      x: options.x == null ? placement.looseX : options.x,
      y: options.y == null ? placement.looseY : options.y
    }, beadSize, this.getStageLayout(), 12);
    const bodyOptions = {
        isStatic: !!options.isStatic,
        restitution: options.restitution == null ? BILLIARD_BEAD_RESTITUTION : options.restitution,
        friction: options.friction == null ? BILLIARD_FRICTION : options.friction,
        frictionStatic: options.frictionStatic == null ? BILLIARD_STATIC_FRICTION : options.frictionStatic,
        frictionAir: options.frictionAir == null ? BILLIARD_FRICTION_AIR : options.frictionAir,
        density: options.density == null ? 0.0018 : options.density,
        slop: options.slop == null ? 0.006 : options.slop,
        sleepThreshold: 44,
        label: `bead-${index}`
      };
    const body = physical.collisionShape === 'rectangle'
      ? Bodies.rectangle(initialPoint.x, initialPoint.y, bodyWidth, bodyHeight, {
        ...bodyOptions,
        chamfer: { radius: Math.min(6, bodyWidth * 0.18, bodyHeight * 0.18) }
      })
      : Bodies.circle(initialPoint.x, initialPoint.y, bodyRadius, bodyOptions);
    body.plugin = {
      designIndex: index,
      materialId: id,
      beadSize,
      bodyRadius,
      bodyWidth,
      bodyHeight,
      collisionShape: physical.collisionShape,
      isLauncher: !!options.isLauncher,
      frozenUntilImpact: !!options.frozenUntilImpact,
      billiardDamping: options.billiardDamping,
      angularDamping: options.angularDamping,
      launchAimX: Number(options.launchAimX),
      launchAimY: Number(options.launchAimY),
      launchSpeed: Number(options.launchSpeed),
      launchAssistUntil: Number(options.launchAssistMs) > 0 ? Date.now() + Number(options.launchAssistMs) : 0
    };
    Body.setAngle(body, (Number(placement.rotation) || 0) * Math.PI / 180);
    if (options.velocity) {
      if (Sleeping) Sleeping.set(body, false);
      body.isSleeping = false;
      body.sleepCounter = 0;
      Body.setVelocity(body, options.velocity);
    }
    if (options.angularVelocity) {
      if (Sleeping) Sleeping.set(body, false);
      body.isSleeping = false;
      body.sleepCounter = 0;
      Body.setAngularVelocity(body, options.angularVelocity);
    }
    Composite.add(this.physicsEngine.world, body);
    this.physicsBodies.push(body);
    return body;
  },

  startPhysicsFromCurrentDesign() {
    this.stopPhysics();
    if (!this.data.isLooseMode || !this.data.selected.length) return;
    this.createPhysicsEngine();
    const placements = this.normalizePlacements(this.data.selected, this.data.placements);
    this.data.selected.forEach((id, index) => {
      this.createPhysicsBody(id, placements[index], index);
    });
    this.runPhysics();
  },

  applyLauncherTrajectoryAssist(now = Date.now(), layout = this.getStageLayout()) {
    if (!Body) return;
    (this.physicsBodies || []).forEach(body => {
      const plugin = body && body.plugin;
      if (!body || !plugin || !plugin.isLauncher || !plugin.launchAssistUntil) return;
      if (now > plugin.launchAssistUntil) {
        plugin.launchAssistUntil = 0;
        return;
      }
      const rawAimX = Number(plugin.launchAimX);
      const rawAimY = Number(plugin.launchAimY);
      if (!Number.isFinite(rawAimX) || !Number.isFinite(rawAimY) || !body.position) {
        plugin.launchAssistUntil = 0;
        return;
      }
      const safeAim = this.constrainPointInsideTray(
        { x: rawAimX, y: rawAimY },
        plugin.beadSize,
        layout,
        14
      );
      const aimX = safeAim.x;
      const aimY = safeAim.y;
      const dx = aimX - body.position.x;
      const dy = aimY - body.position.y;
      const distance = Math.sqrt(dx * dx + dy * dy);
      const radius = Number(plugin.bodyRadius || plugin.beadSize * 0.5) || 24;
      if (!Number.isFinite(distance) || distance < Math.max(10, radius * 0.35)) {
        plugin.launchAssistUntil = 0;
        return;
      }
      const speed = Math.max(9.8, Math.min(this.getBodySpeedLimit(body), Number(plugin.launchSpeed) || 13.8));
      if (Sleeping) Sleeping.set(body, false);
      body.isSleeping = false;
      body.sleepCounter = 0;
      Body.setVelocity(body, {
        x: dx / distance * speed,
        y: dy / distance * speed
      });
    });
  },

  getTrayPhysicsRadius(layout = this.getStageLayout()) {
    const center = Number(layout && layout.center) || 300;
    const radius = Number(layout && layout.radius);
    const fallback = center * 0.78;
    return Math.max(80, Math.min(center - 8, Number.isFinite(radius) && radius > 0 ? radius : fallback));
  },

  getTraySafeDistance(beadSize = 0, layout = this.getStageLayout(), padding = 12) {
    const visualSize = Number(beadSize);
    const bodyRadius = Math.max(19, Number.isFinite(visualSize) && visualSize > 0 ? visualSize * 0.5 - 0.2 : 24);
    const trayRadius = this.getTrayPhysicsRadius(layout);
    return Math.max(8, trayRadius - bodyRadius - padding);
  },

  constrainPointInsideTray(point = {}, beadSize = 0, layout = this.getStageLayout(), padding = 12) {
    const center = Number(layout && layout.center) || 300;
    const x = Number(point.x);
    const y = Number(point.y);
    if (!Number.isFinite(x) || !Number.isFinite(y)) return { x: center, y: center };
    const maxDistance = this.getTraySafeDistance(beadSize, layout, padding);
    let dx = x - center;
    let dy = y - center;
    let distance = Math.sqrt(dx * dx + dy * dy);
    if (!Number.isFinite(distance)) return { x: center, y: center };
    if (distance <= maxDistance) return { x, y };
    if (distance <= 0.0001) {
      dx = 1;
      dy = 0;
      distance = 1;
    }
    return {
      x: center + dx / distance * maxDistance,
      y: center + dy / distance * maxDistance
    };
  },

  constrainPhysicsTarget(target = {}, layout = this.getStageLayout(), padding = 12) {
    const beadSize = Number(target.beadSize || target.size || 0);
    return {
      ...target,
      ...this.constrainPointInsideTray(target, beadSize, layout, padding)
    };
  },

  getBodyRadius(body) {
    return Number(body && body.plugin && (body.plugin.bodyRadius || body.plugin.beadSize * 0.5)) || 24;
  },

  getTrayBoundaryState(body, layout = this.getStageLayout(), padding = TRAY_BOUNDARY_PADDING_RPX) {
    const center = Number(layout && layout.center) || 300;
    const radius = this.getBodyRadius(body);
    const trayRadius = this.getTrayPhysicsRadius(layout);
    const maxDistance = Math.max(8, trayRadius - radius - (Number(padding) || 0));
    const x = Number(body && body.position && body.position.x);
    const y = Number(body && body.position && body.position.y);
    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      return {
        valid: false,
        center,
        radius,
        maxDistance,
        normalX: 1,
        normalY: 0,
        distance: 0,
        overflow: 0
      };
    }
    let dx = x - center;
    let dy = y - center;
    let distance = Math.sqrt(dx * dx + dy * dy);
    if (!Number.isFinite(distance)) {
      return {
        valid: false,
        center,
        radius,
        maxDistance,
        normalX: 1,
        normalY: 0,
        distance: 0,
        overflow: 0
      };
    }
    if (distance <= 0.0001) {
      dx = 1;
      dy = 0;
      distance = 0;
    }
    const normalDistance = Math.max(distance, 1);
    return {
      valid: true,
      center,
      radius,
      maxDistance,
      normalX: dx / normalDistance,
      normalY: dy / normalDistance,
      distance,
      overflow: distance - maxDistance
    };
  },

  extendTrayImpactContainment(duration = TRAY_IMPACT_CONTAIN_MS) {
    const nextUntil = Date.now() + Math.max(120, Number(duration) || TRAY_IMPACT_CONTAIN_MS);
    this.trayImpactContainUntil = Math.max(Number(this.trayImpactContainUntil) || 0, nextUntil);
  },

  isTrayImpactContainmentActive(now = Date.now()) {
    return !!this.pendingFrozenImpact || now < (Number(this.trayImpactContainUntil) || 0);
  },

  refreshTrayImpactContainmentFromMotion(now = Date.now(), layout = this.getStageLayout(), profile = null) {
    const bodies = this.physicsBodies || [];
    if (!bodies.length) return;
    const motionProfile = profile || this.getPhysicsMotionProfile(now, layout, { includeBoundaryRisk: false });
    const active = this.isTrayImpactContainmentActive(now);
    if (motionProfile.keepAlive) {
      this.extendTrayImpactContainment(active ? TRAY_IMPACT_KEEPALIVE_MS : TRAY_IMPACT_KEEPALIVE_MS + 180);
    }
  },

  getPhysicsMotionProfile(now = Date.now(), layout = this.getStageLayout(), options = {}) {
    const bodies = this.physicsBodies || [];
    const profile = {
      maxSpeed: 0,
      hasLauncherAssist: false,
      hasBoundaryRisk: false,
      keepAlive: false
    };
    if (!bodies.length) return profile;
    const activeContainment = this.isTrayImpactContainmentActive(now);
    const speedThreshold = activeContainment ? TRAY_IMPACT_KEEPALIVE_SPEED_RPX : TRAY_IMPACT_REARM_SPEED_RPX;
    const includeBoundaryRisk = options.includeBoundaryRisk !== false;
    const padding = activeContainment ? TRAY_IMPACT_CONTAIN_PADDING_RPX : TRAY_BOUNDARY_PADDING_RPX;
    bodies.forEach(body => {
      if (!this.isWorkspaceBeadBody(body) || body.isStatic) return;
      const plugin = body.plugin || {};
      const vx = Number(body.velocity && body.velocity.x);
      const vy = Number(body.velocity && body.velocity.y);
      const speed = Number.isFinite(vx) && Number.isFinite(vy)
        ? Math.sqrt(vx * vx + vy * vy)
        : Number(body.speed || 0);
      if (Number.isFinite(speed)) profile.maxSpeed = Math.max(profile.maxSpeed, speed);
      if (plugin.launchAssistUntil && now < plugin.launchAssistUntil) {
        profile.hasLauncherAssist = true;
        profile.keepAlive = true;
      }
      if (plugin.isLauncher && speed > 0.55) profile.keepAlive = true;
      if (speed > speedThreshold) profile.keepAlive = true;
      if (!includeBoundaryRisk) return;
      const state = this.getTrayBoundaryState(body, layout, padding);
      if (!state.valid || !Number.isFinite(vx) || !Number.isFinite(vy)) return;
      const outwardSpeed = vx * state.normalX + vy * state.normalY;
      if (outwardSpeed <= 0.02) return;
      const projectedDistance = state.distance + outwardSpeed * TRAY_BOUNDARY_MAX_LOOKAHEAD_FRAMES;
      if (projectedDistance >= state.maxDistance - TRAY_IMPACT_CONTAIN_GUARD_RPX) {
        profile.hasBoundaryRisk = true;
      }
    });
    return profile;
  },

  shouldUsePhysicsSubsteps(now = Date.now(), layout = this.getStageLayout(), profile = null) {
    if (this.physicsTargets || this.pendingFrozenImpact) return true;
    if (!this.isTrayImpactContainmentActive(now)) return false;
    const motionProfile = profile || this.getPhysicsMotionProfile(now, layout);
    return motionProfile.hasLauncherAssist
      || motionProfile.hasBoundaryRisk
      || motionProfile.maxSpeed > TRAY_IMPACT_KEEPALIVE_SPEED_RPX;
  },

  normalizeTrayContainmentOptions(options = {}) {
    const active = this.isTrayImpactContainmentActive();
    const rawPadding = options.padding == null ? TRAY_BOUNDARY_PADDING_RPX : Number(options.padding);
    const rawGuard = options.guard == null ? TRAY_BOUNDARY_GUARD_RPX : Number(options.guard);
    const rawTouchGuard = options.touchGuard == null
      ? (active ? TRAY_IMPACT_TOUCH_GUARD_RPX : TRAY_BOUNDARY_TOUCH_GUARD_RPX)
      : Number(options.touchGuard);
    const rawLookahead = options.lookaheadFrames == null
      ? TRAY_BOUNDARY_LOOKAHEAD_FRAMES
      : Number(options.lookaheadFrames);
    const padding = Number.isFinite(rawPadding) ? rawPadding : TRAY_BOUNDARY_PADDING_RPX;
    const guard = Number.isFinite(rawGuard) ? rawGuard : TRAY_BOUNDARY_GUARD_RPX;
    const touchGuard = Number.isFinite(rawTouchGuard) ? rawTouchGuard : TRAY_BOUNDARY_TOUCH_GUARD_RPX;
    const lookaheadFrames = Number.isFinite(rawLookahead) ? rawLookahead : TRAY_BOUNDARY_LOOKAHEAD_FRAMES;
    if (!active) {
      return {
        ...options,
        padding,
        guard,
        touchGuard,
        lookaheadFrames
      };
    }
    const activeMaxSpeed = this.isLowPerformanceDevice ? 76.0 : 96.0;
    const rawMaxSpeed = Number(options.maxSpeed);
    return {
      ...options,
      padding: Math.max(padding, TRAY_IMPACT_CONTAIN_PADDING_RPX),
      guard: Math.max(guard, TRAY_IMPACT_CONTAIN_GUARD_RPX),
      touchGuard: Math.max(touchGuard, TRAY_IMPACT_TOUCH_GUARD_RPX),
      lookaheadFrames: Math.max(lookaheadFrames, TRAY_BOUNDARY_MAX_LOOKAHEAD_FRAMES),
      maxSpeed: Number.isFinite(rawMaxSpeed) && rawMaxSpeed > 0
        ? Math.min(rawMaxSpeed, activeMaxSpeed)
        : activeMaxSpeed,
      inwardBias: Math.max(Number(options.inwardBias) || 0, 1.85),
      reserveRatio: Math.max(Number(options.reserveRatio) || 0, 0.46)
    };
  },

  shapeVelocityForTrayContainment(body, velocity = {}, layout = this.getStageLayout(), options = {}) {
    const vx = Number(velocity && velocity.x);
    const vy = Number(velocity && velocity.y);
    if (!Number.isFinite(vx) || !Number.isFinite(vy)) return { x: 0, y: 0 };
    const containmentOptions = this.normalizeTrayContainmentOptions(options);
    const state = this.getTrayBoundaryState(
      body,
      layout,
      containmentOptions.padding
    );
    if (!state.valid) return { x: 0, y: 0 };
    const guard = Math.max(0, Number(containmentOptions.guard));
    const tangentX = -state.normalY;
    const tangentY = state.normalX;
    let outwardSpeed = vx * state.normalX + vy * state.normalY;
    let tangentSpeed = vx * tangentX + vy * tangentY;
    const touchGuard = Math.max(0, Number(containmentOptions.touchGuard || 0));
    const nearWall = state.distance >= state.maxDistance - touchGuard;
    if (outwardSpeed > 0 && nearWall) {
      const wallPressure = Math.max(0, Math.min(1, (state.distance - (state.maxDistance - guard)) / Math.max(guard, 1)));
      const bounce = Math.max(BILLIARD_WALL_RESTITUTION, Number(containmentOptions.wallRestitution || 0));
      outwardSpeed = -Math.max(3.2, Math.min(outwardSpeed * bounce, this.isLowPerformanceDevice ? 22.0 : 30.0));
      tangentSpeed *= Math.max(0.64, 0.90 - wallPressure * 0.16);
    }
    const shaped = {
      x: state.normalX * outwardSpeed + tangentX * tangentSpeed,
      y: state.normalY * outwardSpeed + tangentY * tangentSpeed
    };
    const maxSpeed = Number(containmentOptions.maxSpeed || this.getBodySpeedLimit(body));
    const speed = Math.sqrt(shaped.x * shaped.x + shaped.y * shaped.y);
    if (!Number.isFinite(speed) || speed <= maxSpeed) return shaped;
    const scale = maxSpeed / Math.max(speed, 0.0001);
    return {
      x: shaped.x * scale,
      y: shaped.y * scale
    };
  },

  resolveTrayBoundaryForBody(body, options = {}) {
    if (!Body || !body || !body.position) return false;
    if (body.isStatic && !options.includeStatic) return false;
    const containmentOptions = this.normalizeTrayContainmentOptions(options);
    const layout = options.layout || this.getStageLayout();
    const padding = containmentOptions.padding;
    const state = this.getTrayBoundaryState(body, layout, padding);
    if (!state.valid) {
      Body.setPosition(body, { x: state.center, y: state.center });
      Body.setVelocity(body, { x: 0, y: 0 });
      Body.setAngularVelocity(body, 0);
      return true;
    }
    const velocityX = Number(body.velocity && body.velocity.x);
    const velocityY = Number(body.velocity && body.velocity.y);
    if (!Number.isFinite(velocityX) || !Number.isFinite(velocityY)) {
      Body.setVelocity(body, { x: 0, y: 0 });
      Body.setAngularVelocity(body, 0);
      return true;
    }
    const speed = Math.sqrt(velocityX * velocityX + velocityY * velocityY);
    const outwardSpeed = velocityX * state.normalX + velocityY * state.normalY;
    const needsPositionClamp = state.overflow > 0.001;
    const touchGuard = Math.max(0, Number(containmentOptions.touchGuard || 0));
    const nearWall = state.distance >= state.maxDistance - touchGuard;
    const needsVelocityGuard = containmentOptions.force || needsPositionClamp || (nearWall && outwardSpeed > 0.02);
    if (!needsPositionClamp && !needsVelocityGuard) return false;
    const shouldPreLimitOutwardSpeed = false;

    if (needsPositionClamp) {
      Body.setPosition(body, {
        x: state.center + state.normalX * state.maxDistance,
        y: state.center + state.normalY * state.maxDistance
      });
    }

    if (!shouldPreLimitOutwardSpeed || projectedOverflow > 0) {
      this.applyTrayWallSpin(body, state.normalX, state.normalY, outwardSpeed);
    }
    const tangentX = -state.normalY;
    const tangentY = state.normalX;
    const tangentSpeed = velocityX * tangentX + velocityY * tangentY;
    const penetration = Math.max(0, state.overflow);
    let nextOutwardSpeed;
    let tangentDamping;
    const inwardBias = Math.max(0.1, Number(containmentOptions.inwardBias || 1));
    if (shouldPreLimitOutwardSpeed) {
      const reserve = Math.max(10, dynamicGuard * Math.max(0.18, Number(containmentOptions.reserveRatio || 0.34)));
      const allowedOutwardSpeed = (state.maxDistance - state.distance - reserve) / Math.max(lookaheadFrames, 1);
      nextOutwardSpeed = Math.min(outwardSpeed, Math.max(-0.52 * inwardBias, allowedOutwardSpeed));
      if (projectedOverflow > 0) {
        nextOutwardSpeed = Math.min(nextOutwardSpeed, Math.max(-0.72 * inwardBias, outwardSpeed * 0.48));
      }
      tangentDamping = Math.max(0.70, 0.93 - Math.max(0, projectedOverflow) / 160);
    } else {
      const bounce = Math.max(BILLIARD_WALL_RESTITUTION, Number(containmentOptions.wallRestitution || 0));
      const maxBounceSpeed = this.isLowPerformanceDevice ? 24.0 : 32.0;
      nextOutwardSpeed = outwardSpeed > 0.02
        ? -Math.max(
          1.45 * inwardBias,
          Math.min(maxBounceSpeed, outwardSpeed * bounce + Math.max(0, penetration) * 0.018)
        )
        : Math.max(-maxBounceSpeed, outwardSpeed * 0.82);
      tangentDamping = penetration > 0
        ? Math.max(0.58, 0.84 - penetration / 130)
        : 0.86;
    }
    Body.setVelocity(body, {
      x: state.normalX * nextOutwardSpeed + tangentX * tangentSpeed * tangentDamping,
      y: state.normalY * nextOutwardSpeed + tangentY * tangentSpeed * tangentDamping
    });
    if (penetration > 10) {
      Body.setAngularVelocity(body, (Number(body.angularVelocity) || 0) * 0.62);
    }
    const maxSpeed = Number(containmentOptions.maxSpeed || Math.min(this.getBodySpeedLimit(body), this.isLowPerformanceDevice ? 7.4 : 8.4));
    this.clampBodyVelocity(body, Math.min(this.getBodySpeedLimit(body), maxSpeed));
    return true;
  },

  getBodySpeedLimit(body) {
    const plugin = (body && body.plugin) || {};
    if (plugin.isLauncher) return this.isLowPerformanceDevice ? 84.0 : 108.0;
    return this.isLowPerformanceDevice ? 22.0 : 30.0;
  },

  clampBodyVelocity(body, maxSpeed = this.getBodySpeedLimit(body)) {
    if (!Body || !body || !body.velocity) return;
    const vx = Number(body.velocity.x);
    const vy = Number(body.velocity.y);
    if (!Number.isFinite(vx) || !Number.isFinite(vy)) {
      Body.setVelocity(body, { x: 0, y: 0 });
      return;
    }
    const speed = Math.sqrt(vx * vx + vy * vy);
    if (!Number.isFinite(speed) || speed <= maxSpeed) return;
    const scale = maxSpeed / Math.max(speed, 0.0001);
    Body.setVelocity(body, { x: vx * scale, y: vy * scale });
  },

  recoverInvalidPhysicsBody(body, layout = this.getStageLayout()) {
    if (!Body || !body || !this.isWorkspaceBeadBody(body)) return false;
    const plugin = body.plugin || {};
    const designIndex = Number(plugin.designIndex);
    const placements = this.livePlacements || this.data.placements || [];
    const placement = Number.isInteger(designIndex) && designIndex >= 0 ? (placements[designIndex] || {}) : {};
    const beadSize = Number(plugin.beadSize || placement.beadSize || placement.size || placement.diameter || 54);
    let recovered = false;
    const positionX = Number(body.position && body.position.x);
    const positionY = Number(body.position && body.position.y);
    if (!Number.isFinite(positionX) || !Number.isFinite(positionY)) {
      const fallbackPoint = this.constrainPointInsideTray({
        x: Number(placement.looseX),
        y: Number(placement.looseY)
      }, beadSize, layout, TRAY_BOUNDARY_GUARD_RPX + 24);
      Body.setPosition(body, fallbackPoint);
      recovered = true;
    } else {
      const escapePadding = this.isTrayImpactContainmentActive()
        ? TRAY_IMPACT_CONTAIN_PADDING_RPX
        : TRAY_BOUNDARY_PADDING_RPX;
      const escapeGuard = this.isTrayImpactContainmentActive()
        ? TRAY_IMPACT_ESCAPE_RESET_GUARD_RPX
        : TRAY_ESCAPE_RESET_GUARD_RPX;
      const state = this.getTrayBoundaryState(body, layout, escapePadding);
      if (state.valid && state.distance > state.maxDistance + escapeGuard) {
        const fallbackPoint = this.constrainPointInsideTray(
          { x: positionX, y: positionY },
          beadSize,
          layout,
          escapePadding + 12
        );
        Body.setPosition(body, fallbackPoint);
        Body.setVelocity(body, { x: 0, y: 0 });
        Body.setAngularVelocity(body, 0);
        recovered = true;
      }
    }
    const velocityX = Number(body.velocity && body.velocity.x);
    const velocityY = Number(body.velocity && body.velocity.y);
    const rawSpeed = body.speed;
    const speedInvalid = rawSpeed != null && !Number.isFinite(Number(rawSpeed));
    if (!Number.isFinite(velocityX) || !Number.isFinite(velocityY) || speedInvalid) {
      Body.setVelocity(body, { x: 0, y: 0 });
      recovered = true;
    }
    if (!Number.isFinite(Number(body.angle))) {
      Body.setAngle(body, (Number(placement.rotation) || 0) * Math.PI / 180);
      recovered = true;
    }
    if (!Number.isFinite(Number(body.angularVelocity))) {
      Body.setAngularVelocity(body, 0);
      recovered = true;
    }
    if (recovered) {
      if (Sleeping) Sleeping.set(body, false);
      body.isSleeping = false;
      body.sleepCounter = 0;
    }
    return recovered;
  },

  sanitizePhysicsBodies(layout = this.getStageLayout()) {
    const bodies = this.physicsBodies || [];
    if (!bodies.length || !Body) return false;
    let recovered = false;
    bodies.forEach(body => {
      if (this.recoverInvalidPhysicsBody(body, layout)) recovered = true;
    });
    return recovered;
  },

  clampPhysicsVelocities() {
    (this.physicsBodies || []).forEach(body => {
      if (!body || body.isStatic) return;
      this.clampBodyVelocity(body);
    });
  },

  getAdaptivePhysicsInterval(now = Date.now()) {
    const baseInterval = Number(this.physicsTimerInterval) || 33;
    const bodies = this.physicsBodies || [];
    const data = this.data || {};
    const hasActiveMotion = bodies.some(body => {
      if (!body || body.isStatic) return false;
      const plugin = body.plugin || {};
      if (Number(plugin.launchAssistUntil) > now) return true;
      const velocity = body.velocity || {};
      return Math.hypot(
        Number(velocity.x) || 0,
        Number(velocity.y) || 0
      ) > 12;
    });
    const needsResponsivePhysics = !!(
      this.physicsTargets
      || this.pendingFrozenImpact
      || this.dragState
      || this.ringDragState
      || this.ringSlideState
      || data.isShuffling
      || data.isStringingFinishing
      || data.isReleasingString
      || hasActiveMotion
    );
    if (needsResponsivePhysics || bodies.length <= 18) return baseInterval;
    if (bodies.length <= 28) {
      return Math.max(baseInterval, this.isLowPerformanceDevice ? 38 : (this.isRealDevice ? 28 : 24));
    }
    return Math.max(baseInterval, this.isLowPerformanceDevice ? 42 : (this.isRealDevice ? 34 : 30));
  },

  runPhysics() {
    if (!this.physicsEngine || this.physicsTimer) return;
    this.physicsLastTime = Date.now();
    this.physicsLoopLastAt = this.physicsLastTime;
    this.physicsAccumulatorMs = 0;
    this.physicsLastRender = 0;
    this.physicsStillFrames = 0;
    this.scheduleCanvasRender(true);
    this.physicsTimer = setInterval(() => {
      try {
        const now = Date.now();
        const adaptiveInterval = this.getAdaptivePhysicsInterval(now);
        const elapsed = Math.max(0, now - Number(this.physicsLoopLastAt || now));
        this.physicsLoopLastAt = now;
        this.physicsAccumulatorMs = Math.min(
          adaptiveInterval * 2,
          Number(this.physicsAccumulatorMs || 0) + elapsed
        );
        if (this.physicsAccumulatorMs + 0.5 < adaptiveInterval) return;
        this.physicsAccumulatorMs = Math.max(0, this.physicsAccumulatorMs - adaptiveInterval);
        const layout = this.getStageLayout();
        this.physicsLastTime = now;
        this.sanitizePhysicsBodies(layout);
        const motionProfile = this.getPhysicsMotionProfile(now, layout);
        this.refreshTrayImpactContainmentFromMotion(now, layout, motionProfile);
        const boundaryOptions = {
          guard: TRAY_BOUNDARY_GUARD_RPX + 24,
          lookaheadFrames: TRAY_BOUNDARY_MAX_LOOKAHEAD_FRAMES
        };
        const useSubsteps = this.shouldUsePhysicsSubsteps(now, layout, motionProfile);
        const substepCount = useSubsteps ? (this.isLowPerformanceDevice ? 2 : 3) : 1;
        const substepMs = adaptiveInterval / substepCount;
        for (let substepIndex = 0; substepIndex < substepCount; substepIndex += 1) {
          const substepNow = now + substepIndex * substepMs;
          if (this.physicsTargets) this.applyStringingForces(layout);
          this.applyLauncherTrajectoryAssist(substepNow, layout);
          this.clampPhysicsVelocities();
          this.clampBodiesInsideTray(layout, boundaryOptions);
          Engine.update(this.physicsEngine, substepMs);
          this.sanitizePhysicsBodies(layout);
          this.refreshTrayImpactContainmentFromMotion(substepNow, layout);
          this.clampPhysicsVelocities();
          this.clampBodiesInsideTray(layout, boundaryOptions);
        }
        if (!this.physicsTargets && !this.data.isShuffling && !this.data.isStringingFinishing) {
          this.applyRollingSpinFromVelocity(layout);
        }
        const dampingSettled = !this.physicsTargets ? this.applyBilliardDamping() : false;
        const overlapsCorrected = this.resolveBeadOverlaps(layout);
        this.clampBodiesInsideTray(layout, {
          guard: TRAY_BOUNDARY_GUARD_RPX + 24,
          lookaheadFrames: TRAY_BOUNDARY_MAX_LOOKAHEAD_FRAMES
        });
        if (this.pendingFrozenImpact && now - (this.pendingFrozenImpactAt || now) > 760) {
          const launcher = (this.physicsBodies || []).find(body => body && body.plugin && body.plugin.isLauncher);
          this.releaseFrozenBodiesFromImpact(launcher, null);
        }
        if (this.physicsTargets && this.isStringingSettled(layout)) {
          this.physicsStillFrames += 1;
          if (this.physicsStillFrames > 6) {
            if (this.data.isShuffling) this.finishStringing();
            else this.finishImpactTargeting();
            return;
          }
        } else if (this.physicsTargets) {
          this.physicsStillFrames = 0;
        }
        if (this.physicsTargets && now - this.stringingStartedAt > 1700) {
          if (this.data.isShuffling) this.finishStringing();
          else this.finishImpactTargeting();
          return;
        }
        if (!this.physicsTargets) {
          this.physicsStillFrames = dampingSettled && !overlapsCorrected ? this.physicsStillFrames + 1 : 0;
        }
        if (now - this.physicsLastRender >= (this.physicsRenderInterval || 50)) {
          this.physicsLastRender = now;
          this.syncPhysicsFrame();
        }
        if (!this.physicsTargets && this.physicsStillFrames > 12) {
          this.syncPhysicsFrame();
          this.pausePhysics();
        }
      } catch (error) {
        this.recoverPhysicsRuntime();
      }
    }, this.physicsTimerInterval || 33);
  },

  resolveBeadOverlaps(layout = this.getStageLayout()) {
    const bodies = this.physicsBodies || [];
    if (bodies.length < 2 || !Body) return false;
    let correctedAny = false;
    const maxCorrectionPerPass = this.isLowPerformanceDevice ? 16 : 26;
    const passes = this.isLowPerformanceDevice ? 2 : 3;
    const boundaryOptions = {
      layout,
      guard: this.isTrayImpactContainmentActive() ? TRAY_IMPACT_CONTAIN_GUARD_RPX : TRAY_BOUNDARY_GUARD_RPX + 24,
      lookaheadFrames: TRAY_BOUNDARY_MAX_LOOKAHEAD_FRAMES
    };
    const bodyEntries = bodies.map(body => {
      const plugin = body && body.plugin || {};
      return {
        body,
        radius: Number(plugin.bodyRadius || plugin.beadSize * 0.5) || 24,
        isStatic: !!(body && body.isStatic)
      };
    });
    for (let pass = 0; pass < passes; pass += 1) {
      let passCorrected = false;
      for (let i = 0; i < bodyEntries.length - 1; i += 1) {
        const entryA = bodyEntries[i];
        const bodyA = entryA && entryA.body;
        if (!bodyA || !bodyA.position) continue;
        for (let j = i + 1; j < bodyEntries.length; j += 1) {
          const entryB = bodyEntries[j];
          const bodyB = entryB && entryB.body;
          if (!bodyB || !bodyB.position) continue;
          if (entryA.isStatic && entryB.isStatic) continue;
          const minDistance = entryA.radius + entryB.radius + 3.2;
          let dx = bodyB.position.x - bodyA.position.x;
          let dy = bodyB.position.y - bodyA.position.y;
          if (Math.abs(dx) >= minDistance || Math.abs(dy) >= minDistance) continue;
          let distanceSq = dx * dx + dy * dy;
          if (distanceSq <= 0.0001) {
            const seed = (i + 1) * 17 + (j + 1) * 31 + pass * 13;
            dx = Math.cos(seed);
            dy = Math.sin(seed);
            distanceSq = 1;
          } else if (distanceSq >= minDistance * minDistance) {
            continue;
          }
          const distance = Math.sqrt(distanceSq);
          const overlap = minDistance - distance;
          if (overlap <= 0) continue;
          const normalX = dx / distance;
          const normalY = dy / distance;
          const correction = Math.min(overlap, maxCorrectionPerPass) * 0.82;
          passCorrected = true;
          if (bodyA.isStatic) {
            Body.setPosition(bodyB, {
              x: bodyB.position.x + normalX * correction,
              y: bodyB.position.y + normalY * correction
            });
            Body.setVelocity(bodyB, { x: bodyB.velocity.x * 0.84, y: bodyB.velocity.y * 0.84 });
            this.applyOverlapSeparationSpin(bodyA, bodyB, normalX, normalY, correction);
          } else if (bodyB.isStatic) {
            Body.setPosition(bodyA, {
              x: bodyA.position.x - normalX * correction,
              y: bodyA.position.y - normalY * correction
            });
            Body.setVelocity(bodyA, { x: bodyA.velocity.x * 0.84, y: bodyA.velocity.y * 0.84 });
            this.applyOverlapSeparationSpin(bodyA, bodyB, normalX, normalY, correction);
          } else {
            const half = correction * 0.5;
            Body.setPosition(bodyA, {
              x: bodyA.position.x - normalX * half,
              y: bodyA.position.y - normalY * half
            });
            Body.setPosition(bodyB, {
              x: bodyB.position.x + normalX * half,
              y: bodyB.position.y + normalY * half
            });
            this.applyOverlapSeparationSpin(bodyA, bodyB, normalX, normalY, correction);
          }
          this.resolveTrayBoundaryForBody(bodyA, boundaryOptions);
          this.resolveTrayBoundaryForBody(bodyB, boundaryOptions);
        }
      }
      if (passCorrected) {
        correctedAny = true;
        this.clampBodiesInsideTray(layout, boundaryOptions);
      }
    }
    return correctedAny;
  },

  applyOverlapSeparationSpin(bodyA, bodyB, normalX, normalY, correction) {
    if (!Body) return;
    const beadA = this.isWorkspaceBeadBody(bodyA);
    const beadB = this.isWorkspaceBeadBody(bodyB);
    if (!beadA && !beadB) return;
    const relX = ((bodyA.velocity && bodyA.velocity.x) || 0) - ((bodyB.velocity && bodyB.velocity.x) || 0);
    const relY = ((bodyA.velocity && bodyA.velocity.y) || 0) - ((bodyB.velocity && bodyB.velocity.y) || 0);
    const tangentSpeed = relX * -normalY + relY * normalX;
    const sign = Math.abs(tangentSpeed) > 0.01 ? (tangentSpeed >= 0 ? 1 : -1) : ((bodyA.plugin && bodyA.plugin.designIndex || 0) % 2 ? 1 : -1);
    const pressureSpin = Math.min(0.026, Math.max(0, correction) * 0.0016) * sign;
    const spin = this.clampAngularVelocity(tangentSpeed * 0.008 + pressureSpin, 0.045);
    if (beadA) this.addBodySpin(bodyA, -spin, { maxDelta: 0.035 });
    if (beadB) this.addBodySpin(bodyB, spin, { maxDelta: 0.035 });
  },

  applyRollingSpinFromVelocity(layout = this.getStageLayout()) {
    const bodies = this.physicsBodies || [];
    if (!bodies.length || !Body) return;
    const center = layout.center;
    bodies.forEach(body => {
      if (!this.isWorkspaceBeadBody(body) || body.isStatic || !body.position) return;
      const speed = Number(body.speed) || 0;
      if (speed < 0.09) return;
      const radius = Number(body.plugin && (body.plugin.bodyRadius || body.plugin.beadSize * 0.5)) || 24;
      const dx = body.position.x - center;
      const dy = body.position.y - center;
      const distance = Math.sqrt(dx * dx + dy * dy) || 1;
      const tangentX = -dy / distance;
      const tangentY = dx / distance;
      const tangentSpeed = ((body.velocity && body.velocity.x) || 0) * tangentX
        + ((body.velocity && body.velocity.y) || 0) * tangentY;
      const travelSpin = tangentSpeed / Math.max(14, radius) * ROLLING_SPIN_FACTOR;
      this.addBodySpin(body, travelSpin, { maxDelta: 0.010, limit: 0.11 });
    });
  },

  applyBilliardDamping() {
    const bodies = this.physicsBodies || [];
    if (!bodies.length || !Body) return false;
    const defaultMu = BILLIARD_LINEAR_DAMPING;
    let allSettled = true;
    bodies.forEach(body => {
      if (!body || !body.position) {
        allSettled = false;
        return;
      }
      if (body.isStatic || body.isSleeping) return;
      const plugin = body.plugin || {};
      const mu = Number(plugin.billiardDamping || defaultMu);
      const angularMu = Number(plugin.angularDamping || BILLIARD_ANGULAR_DAMPING);
      if (body.speed < 0.055) {
        Body.setVelocity(body, { x: 0, y: 0 });
        const angularVelocity = Number(body.angularVelocity) || 0;
        if (Math.abs(angularVelocity) < 0.005) {
          Body.setAngularVelocity(body, 0);
        } else {
          Body.setAngularVelocity(body, angularVelocity * angularMu);
          body.isSleeping = false;
          body.sleepCounter = 0;
          allSettled = false;
        }
        return;
      }
      allSettled = false;
      Body.setVelocity(body, {
        x: body.velocity.x * mu,
        y: body.velocity.y * mu
      });
      Body.setAngularVelocity(body, body.angularVelocity * angularMu);
    });
    return allSettled;
  },

  clampBodiesInsideTray(layout = this.getStageLayout(), options = {}) {
    const bodies = this.physicsBodies || [];
    if (!bodies.length || !Body) return;
    const activeContainment = this.isTrayImpactContainmentActive();
    bodies.forEach(body => {
      const clampOptions = {
        layout,
        padding: options.padding == null ? TRAY_BOUNDARY_PADDING_RPX : options.padding,
        guard: options.guard == null ? TRAY_BOUNDARY_GUARD_RPX : options.guard,
        lookaheadFrames: options.lookaheadFrames,
        force: options.force
      };
      if (activeContainment && this.isWorkspaceBeadBody(body) && !body.isStatic && body.velocity) {
        const shapedVelocity = this.shapeVelocityForTrayContainment(
          body,
          body.velocity,
          layout,
          clampOptions
        );
        const vx = Number(body.velocity.x);
        const vy = Number(body.velocity.y);
        if (Number.isFinite(shapedVelocity.x)
          && Number.isFinite(shapedVelocity.y)
          && (Math.abs(shapedVelocity.x - vx) > 0.001 || Math.abs(shapedVelocity.y - vy) > 0.001)) {
          Body.setVelocity(body, shapedVelocity);
        }
      }
      this.resolveTrayBoundaryForBody(body, {
        ...clampOptions
      });
    });
  },

  applyTrayWallSpin(body, normalX, normalY, outwardSpeed = 0) {
    if (!this.isWorkspaceBeadBody(body) || body.isStatic) return;
    const radius = Number(body.plugin && (body.plugin.bodyRadius || body.plugin.beadSize * 0.5)) || 24;
    const tangentSpeed = ((body.velocity && body.velocity.x) || 0) * -normalY
      + ((body.velocity && body.velocity.y) || 0) * normalX;
    const sign = Math.abs(tangentSpeed) > 0.01 ? (tangentSpeed >= 0 ? 1 : -1) : (outwardSpeed >= 0 ? 1 : -1);
    const spin = tangentSpeed / Math.max(14, radius) * 0.42 + sign * Math.min(0.035, Math.abs(outwardSpeed) * 0.006);
    this.addBodySpin(body, spin, { maxDelta: 0.065, limit: 0.13 });
  },

  syncPhysicsFrame(onSynced) {
    const hasSyncedCallback = typeof onSynced === 'function';
    if (this.physicsFramePending) {
      if (hasSyncedCallback) {
        clearTimeout(this.physicsFrameRetryTimer);
        this.physicsFrameRetryTimer = setTimeout(() => {
          this.physicsFrameRetryTimer = null;
          this.syncPhysicsFrame(onSynced);
        }, this.physicsRenderInterval || 50);
      }
      return;
    }
    if (!this.data.isLooseMode || !this.physicsBodies.length) {
      if (hasSyncedCallback) onSynced();
      return;
    }
    this.physicsFramePending = true;
    this.physicsFrameSequence = (this.physicsFrameSequence || 0) + 1;
    this.scheduleCanvasRender(true);
    const shouldPersistFrame = hasSyncedCallback || this.physicsFrameSequence % 10 === 0;
    if (!shouldPersistFrame) {
      this.physicsFramePending = false;
      return;
    }
    const placements = this.buildPhysicsPlacementsSnapshot();
    this.setLivePlacements(placements);
    const shouldSyncPlacements = this.shouldSyncPhysicsPlacements(placements, hasSyncedCallback);
    if (shouldSyncPlacements) {
      this.setData({ placements }, () => {
        this.physicsFramePending = false;
        if (hasSyncedCallback) onSynced();
      });
    } else {
      this.physicsFramePending = false;
      if (hasSyncedCallback) onSynced();
    }
  },

  applyStringingForces(layout = this.getStageLayout()) {
    this.physicsBodies.forEach((body, index) => {
      const rawTarget = this.physicsTargets[index];
      if (!rawTarget) return;
      const target = this.constrainPhysicsTarget(rawTarget, layout, 12);
      const dx = target.x - body.position.x;
      const dy = target.y - body.position.y;
      const distance = Math.sqrt(dx ** 2 + dy ** 2);
      const nearTarget = distance < 24;
      const spring = (nearTarget ? 0.00072 : 0.00095) * body.mass;
      const damping = (nearTarget ? 0.00205 : 0.00142) * body.mass;
      Body.applyForce(body, body.position, {
        x: dx * spring - body.velocity.x * damping,
        y: dy * spring - body.velocity.y * damping
      });
      if (nearTarget && body.speed < 1.8) {
        Body.setVelocity(body, {
          x: body.velocity.x * 0.64,
          y: body.velocity.y * 0.64
        });
      }
      if (distance < 4.2 && body.speed < 0.95) {
        Body.setPosition(body, target);
        Body.setVelocity(body, { x: 0, y: 0 });
      }
    });
  },

  isStringingSettled(layout = this.getStageLayout()) {
    return this.physicsBodies.every((body, index) => {
      const rawTarget = this.physicsTargets[index];
      if (!rawTarget) return true;
      const target = this.constrainPhysicsTarget(rawTarget, layout, 12);
      const distance = Math.sqrt(
        (target.x - body.position.x) ** 2 + (target.y - body.position.y) ** 2
      );
      return distance < 5.5 && body.speed < 0.8;
    });
  },

  finishStringing() {
    if (!this.data.isShuffling || this.data.isStringingFinishing) return;
    this.pausePhysics();
    clearTimeout(this.stringingGuardTimer);
    this.stringingGuardTimer = null;
    const targets = this.physicsTargets;
    if (!targets || !this.physicsBodies.length) {
      this.completeStringing();
      return;
    }
    const layout = this.getStageLayout();
    const safeTargets = targets.map(target => (
      target ? this.constrainPhysicsTarget(target, layout, 12) : target
    ));
    const starts = this.physicsBodies.map(body => ({
      x: body.position.x,
      y: body.position.y,
      angle: body.angle
    }));
    const totalFrames = this.isLowPerformanceDevice ? 8 : (this.isRealDevice ? 12 : 10);
    let frame = 0;
    this.setData({ isStringingFinishing: true });
    clearInterval(this.stringingFinishTimer);
    this.stringingFinishTimer = setInterval(() => {
      try {
        frame += 1;
        const progress = Math.min(1, frame / totalFrames);
        const c1 = 1.18;
        const c3 = c1 + 1;
        const shifted = progress - 1;
        const eased = 1 + c3 * shifted ** 3 + c1 * shifted ** 2;
        this.physicsBodies.forEach((body, index) => {
          const target = safeTargets[index];
          const start = starts[index];
          if (!target || !start) return;
          Body.setPosition(body, {
            x: start.x + (target.x - start.x) * eased,
            y: start.y + (target.y - start.y) * eased
          });
          const targetAngle = target.rotation == null
            ? start.angle
            : Number(target.rotation) * Math.PI / 180;
          Body.setAngle(body, start.angle + (targetAngle - start.angle) * progress);
          Body.setVelocity(body, { x: 0, y: 0 });
          Body.setAngularVelocity(body, 0);
        });
        this.syncPhysicsFrame();
        if (progress >= 1) {
          clearInterval(this.stringingFinishTimer);
          this.stringingFinishTimer = null;
          clearTimeout(this.stringingCompleteTimer);
          this.stringingCompleteTimer = setTimeout(() => {
            this.stringingCompleteTimer = null;
            this.completeStringing();
          }, 45);
        }
      } catch (error) {
        this.recoverStringingRuntime();
      }
    }, this.isLowPerformanceDevice ? 28 : (this.isRealDevice ? 20 : 18));
  },

  finishImpactTargeting() {
    this.physicsTargets = null;
    this.pendingImpactTargets = null;
    this.pendingFrozenImpact = false;
    this.syncPhysicsFrame(() => {
      if (!this.data.isShuffling) this.pausePhysics();
      this.scheduleDraftPersistence();
    });
  },

  completeStringing() {
    this.physicsTargets = null;
    this.suppressStringingSounds = false;
    this.setData({
      isLooseMode: false,
      isShuffling: false,
      isStringingFinishing: false,
      isReleasingString: false,
      draggingBeadIndex: -1,
      dragDeleteArmed: false
    }, () => {
      this.recalculate();
      this.stopPhysics();
      this.refreshWorkspaceCanvasAfterDesignTransition();
    });
  },

  pausePhysics() {
    if (this.physicsTimer) {
      clearInterval(this.physicsTimer);
      this.physicsTimer = null;
    }
    this.physicsLoopLastAt = 0;
    this.physicsAccumulatorMs = 0;
    if (this.data.isLooseMode && this.physicsBodies && this.physicsBodies.length) {
      this.setLivePlacements(this.buildPhysicsPlacementsSnapshot());
    }
    if (this.data.isLooseMode && this.livePlacements) {
      this.setData({ placements: this.livePlacements });
    }
  },

  stopPhysics() {
    this.pausePhysics();
    clearTimeout(this.physicsFrameRetryTimer);
    this.physicsFrameRetryTimer = null;
    clearInterval(this.stringingFinishTimer);
    this.stringingFinishTimer = null;
    clearInterval(this.releaseStringTimer);
    this.releaseStringTimer = null;
    clearTimeout(this.stringingCompleteTimer);
    this.stringingCompleteTimer = null;
    clearTimeout(this.stringingGuardTimer);
    this.stringingGuardTimer = null;
    if (this.physicsEngine) Engine.clear(this.physicsEngine);
    this.physicsEngine = null;
    this.physicsBodies = [];
    this.physicsBodyByDesignIndexCache = null;
    this.physicsTargets = null;
    this.pendingImpactTargets = null;
    this.pendingFrozenImpact = false;
    this.pendingFrozenImpactAt = 0;
    this.physicsFramePending = false;
    this.suppressStringingSounds = false;
    this.stringingStartQueued = false;
    this.clearLivePlacements();
  },

  clearFlightRuntime() {
    this.cancelCanvasFrame(this.pendingPhysicsLaunchFrame);
    this.pendingPhysicsLaunchFrame = null;
    clearTimeout(this.flightTimer);
    this.flightTimer = null;
    clearTimeout(this.flightSafetyTimer);
    this.flightSafetyTimer = null;
    clearTimeout(this.flightAnimationTimer);
    this.flightAnimationTimer = null;
    clearTimeout(this.canvasFlightRetryTimer);
    this.canvasFlightRetryTimer = null;
    this.flightQueue = [];
    this.flightActive = false;
    this.canvasFlightReadyRetries = 0;
    this.canvasFlight = null;
    this.clearWorkspaceFlightCanvas();
  },

  resetWorkspaceRuntime() {
    this.clearFlightRuntime();
    this.clearLivePlacements();
    this.stopPhysics();
    this.invalidateCanvasInteractionSnapshot();
    this.dragState = null;
    this.ringDragState = null;
    this.ringSlideState = null;
    this.braceletGeometryCache = null;
    this.canvasSpriteContextCache = null;
    this.scaleTicksCache = null;
    this.wristOptionItemsCache = null;
    this.workspaceSummaryCache = null;
    this.suppressBeadTapUntil = 0;
    this.lastPersistedDraftSignature = '';
  },

  invalidateCanvasInteractionSnapshot() {
    // 推荐方案会一次替换整条手串。触摸命中必须等待新方案完成绘制，
    // 不能继续复用上一条手串的画布精灵快照。
    this.lastBraceletCanvasRenderSignature = '';
    this.lastBraceletCanvasRenderSnapshot = null;
    this.latestCanvasDrawSnapshot = null;
    this.canvasHitTestSpritesCache = null;
    this.braceletCanvasDirty = true;
  },

  refreshWorkspaceCanvasAfterDesignTransition() {
    wx.nextTick(() => {
      this.stopCanvasRenderLoop();
      this.braceletCanvasDirty = true;
      this.initWorkspaceCanvases();
    });
  },

  resetInteractionData(extra = {}, callback) {
    const nextData = {
      canvasFlightActive: false,
      flightBead: null,
      launchingMaterialId: '',
      isShuffling: false,
      isStringingFinishing: false,
      isReleasingString: false,
      draggingBeadIndex: -1,
      dragDeleteArmed: false,
      ...extra
    };
    if (nextData.selectedBeadIndex === -1) {
      nextData.selectedBeadInfo = null;
    }
    this.setData(nextData, callback);
  },

  hasBusyWorkspaceRuntime() {
    return !!(
      this.data.isShuffling
      || this.data.isStringingFinishing
      || this.data.isReleasingString
      || this.data.canvasFlightActive
      || this.flightActive
      || (this.flightQueue && this.flightQueue.length)
      || this.canvasFlight
      || this.physicsTimer
      || this.stringingFinishTimer
      || this.ringSlideState
      || this.releaseStringTimer
      || this.stringingCompleteTimer
      || this.stringingGuardTimer
    );
  },

  recoverFlightRuntime() {
    this.clearFlightRuntime();
    this.resetInteractionData({}, () => {
      this.scheduleCanvasRender();
    });
  },

  armFlightSafetyTimer(duration = 1800) {
    clearTimeout(this.flightSafetyTimer);
    this.flightSafetyTimer = setTimeout(() => {
      if (!this.flightActive && !this.canvasFlight && !this.data.canvasFlightActive) return;
      this.recoverFlightRuntime();
    }, duration);
  },

  recoverStringingRuntime() {
    const selected = this.data.selected || [];
    const placements = this.normalizePlacements(selected, this.data.placements);
    this.stopPhysics();
    this.resetInteractionData({
      placements,
      isLooseMode: selected.length ? false : true,
      selectedBeadIndex: -1
    }, () => {
      this.recalculate();
      this.scheduleCanvasRender();
    });
  },

  recoverPhysicsRuntime() {
    if (this.data.isShuffling || this.data.isStringingFinishing || this.physicsTargets) {
      this.recoverStringingRuntime();
      return;
    }
    const selected = this.data.selected || [];
    const placements = this.normalizePlacements(selected, this.data.placements);
    this.stopPhysics();
    this.resetInteractionData({
      placements,
      isLooseMode: true,
      selectedBeadIndex: -1
    }, () => {
      this.recalculate();
      this.scheduleCanvasRender();
    });
  },

  pushHistory() {
    const history = this.historyStack || [];
    history.push({
      selected: [...this.data.selected],
      placements: this.data.placements.map(item => ({ ...item })),
      attachedPendants: [],
      wristSize: this.data.wristSize,
      wearStyle: 'single',
      isLooseMode: this.data.isLooseMode
    });
    this.historyStack = history.slice(-30);
    this.redoStack = [];
    this.scheduleWorkspaceHistoryPersistence();
    this.setData({ canUndo: true, canRedo: false });
  },

  persistWorkspaceHistory() {
    try {
      wx.setStorage({ key: 'workspaceHistory', data: this.historyStack || [] });
    } catch (error) {
      logWorkspaceWarning('persist workspace history failed:', error && (error.message || error));
    }
  },

  scheduleWorkspaceHistoryPersistence() {
    clearTimeout(this.historyPersistTimer);
    const delay = Number(this.historyPersistDelayMs) || 650;
    this.historyPersistTimer = setTimeout(() => {
      this.historyPersistTimer = null;
      this.persistWorkspaceHistory();
    }, delay);
  },

  flushWorkspaceHistoryPersistence() {
    if (!this.historyPersistTimer) return;
    clearTimeout(this.historyPersistTimer);
    this.historyPersistTimer = null;
    this.persistWorkspaceHistory();
  },

  currentDesignSnapshot() {
    return {
      selected: [...this.data.selected],
      placements: this.data.placements.map(item => ({ ...item })),
      attachedPendants: [],
      wristSize: this.data.wristSize,
      wearStyle: 'single',
      isLooseMode: this.data.isLooseMode
    };
  },

  restoreDesignSnapshot(snapshot) {
    if (!snapshot) return;
    this.resetWorkspaceRuntime();
    this.setData({
      selected: snapshot.selected || [],
      placements: snapshot.placements || [],
      attachedPendants: [],
      wristSize: snapshot.wristSize || 16,
      wearStyle: 'single',
      isLooseMode: snapshot.isLooseMode === true,
      selectedBeadIndex: -1,
      selectedBeadInfo: null,
      canvasFlightActive: false,
      flightBead: null,
      launchingMaterialId: '',
      isShuffling: false,
      isStringingFinishing: false,
      isReleasingString: false,
      draggingBeadIndex: -1,
      dragDeleteArmed: false,
      canUndo: (this.historyStack || []).length > 0,
      canRedo: (this.redoStack || []).length > 0
    });
    this.recalculate();
    if (snapshot.isLooseMode === true) {
      wx.nextTick(() => this.startPhysicsFromCurrentDesign());
    } else {
      this.stopPhysics();
    }
  },

  undo() {
    const history = this.historyStack || [];
    const previous = history.pop();
    if (!previous) {
      wx.showToast({ title: '没有可撤回的操作', icon: 'none' });
      this.setData({ canUndo: false });
      return;
    }
    this.historyStack = history;
    this.redoStack = [...(this.redoStack || []), this.currentDesignSnapshot()].slice(-30);
    this.scheduleWorkspaceHistoryPersistence();
    this.restoreDesignSnapshot(previous);
  },

  redo() {
    const redo = this.redoStack || [];
    const next = redo.pop();
    if (!next) {
      wx.showToast({ title: '没有可还原的排列', icon: 'none' });
      this.setData({ canRedo: false });
      return;
    }
    this.redoStack = redo;
    this.historyStack = [...(this.historyStack || []), this.currentDesignSnapshot()].slice(-30);
    this.scheduleWorkspaceHistoryPersistence();
    this.restoreDesignSnapshot(next);
  },

  refreshFilters(options = {}) {
    const pool = (this.materialCatalog || DEFAULT_MATERIALS).filter(item => item.top === this.data.activeTop);
    const backendCategories = (this.categoriesByTop || {})[this.data.activeTop] || [];
    const keyword = this.normalizeMaterialSearchKeyword(this.data.materialSearchKeyword);
    const searchTerms = this.materialSearchTerms(keyword);
    const searchPool = searchTerms.length ? pool.filter(item => this.materialMatchesSearch(item, searchTerms)) : [];
    const shouldAutoTargetSearch = searchTerms.length && options.autoTargetSearch !== false;
    const searchTarget = shouldAutoTargetSearch ? this.resolveMaterialSearchTarget(searchPool, searchTerms) : null;
    let categoryNames = backendCategories.length ? backendCategories : [ALL_OPTION_LABEL, ...Array.from(new Set(pool.map(item => item.category)))];
    if (searchTarget && searchTarget.category && !categoryNames.includes(searchTarget.category)) {
      categoryNames = [...categoryNames, searchTarget.category];
    }
    const targetCategory = searchTarget && searchTarget.category;
    const activeCategory = targetCategory && categoryNames.includes(targetCategory)
      ? targetCategory
      : (categoryNames.includes(this.data.activeCategory) ? this.data.activeCategory : ALL_OPTION_LABEL);
    const categoryPool = pool.filter(item => this.isAllFilterValue(activeCategory) || item.category === activeCategory);
    const seriesKey = `${this.data.activeTop}::${activeCategory}`;
    const backendSeries = (this.seriesByCategory || {})[seriesKey] || [];
    const localSeries = [ALL_OPTION_LABEL, ...Array.from(new Set(categoryPool.map(item => item.series || item.name).filter(Boolean)))];
    let seriesOptions = this.isAllFilterValue(activeCategory) ? [ALL_OPTION_LABEL] : (backendSeries.length ? backendSeries : localSeries);
    const targetSeries = searchTarget && searchTarget.category === activeCategory
      ? (searchTarget.series || searchTarget.name || '')
      : '';
    if (targetSeries && !seriesOptions.includes(targetSeries)) {
      seriesOptions = [...seriesOptions, targetSeries];
    }
    const activeSeries = targetSeries && seriesOptions.includes(targetSeries)
      ? targetSeries
      : (seriesOptions.includes(this.data.activeSeries) ? this.data.activeSeries : ALL_OPTION_LABEL);
    const decoratedCategories = this.decorateOptionList(categoryNames, activeCategory, '', 'category-filter');
    const decoratedSeriesOptions = this.decorateOptionList(seriesOptions, activeSeries, '', 'series-filter');
    const activeCategoryAnchor = this.getActiveOptionAnchor(decoratedCategories);
    const activeSeriesAnchor = this.getActiveOptionAnchor(decoratedSeriesOptions);
    const filteredMaterials = categoryPool.filter(item => {
      const series = item.series || item.name || '';
      const matchesSeries = this.isAllFilterValue(activeSeries) || series === activeSeries;
      return matchesSeries && this.materialMatchesSearch(item, searchTerms);
    });
    this.filteredMaterialCatalog = filteredMaterials;
    const requestedLimit = Number(options.limit) || this.materialPageSize || MATERIAL_PAGE_SIZE;
    const visibleMaterials = this.decorateVisibleMaterials(filteredMaterials.slice(0, requestedLimit));
    const filterSummary = `${activeCategory} · ${activeSeries} · ${filteredMaterials.length} 款`;
    this.setData({
      topTabs: this.decorateOptionList(this.data.topTabs, this.data.activeTop, 'key'),
      categories: decoratedCategories,
      activeCategory,
      activeCategoryAnchor,
      seriesOptions: decoratedSeriesOptions,
      activeSeries,
      activeSeriesAnchor,
      visibleMaterials,
      hasMoreMaterials: visibleMaterials.length < filteredMaterials.length,
      filterSummary
    }, () => {
      this.scheduleMaterialPreload(visibleMaterials);
    });
  },

  loadMoreMaterials() {
    if (this.useServerMaterialPagination) {
      if (this.data.materialsLoading || this.data.materialsLoadingMore || !this.data.hasMoreMaterials) return;
      const nextPage = Number((this.materialPageState && this.materialPageState.page) || 1) + 1;
      this.loadMaterialPage(nextPage, { reset: false });
      return;
    }
    const filteredMaterials = this.filteredMaterialCatalog || [];
    const currentCount = (this.data.visibleMaterials || []).length;
    if (currentCount >= filteredMaterials.length) return;
    const nextMaterials = this.decorateVisibleMaterials(
      filteredMaterials.slice(currentCount, currentCount + (this.materialPageSize || MATERIAL_PAGE_SIZE)),
      currentCount
    );
    const nextCount = currentCount + nextMaterials.length;
    this.setData({
      ...this.buildVisibleMaterialAppendUpdates(nextMaterials, currentCount),
      hasMoreMaterials: nextCount < filteredMaterials.length
    }, () => {
      this.scheduleMaterialPreload(nextMaterials);
    });
  },

  decorateOptionList(list, activeValue, key = '', anchorPrefix = '') {
    return (list || []).map((item, index) => {
      const anchorId = anchorPrefix ? `${anchorPrefix}-${index}` : '';
      if (typeof item === 'string') {
        return { label: item, value: item, className: item === activeValue ? 'active' : '', anchorId };
      }
      const value = key ? item[key] : item.value;
      return {
        ...item,
        value,
        className: value === activeValue ? 'active' : '',
        anchorId
      };
    });
  },

  getActiveOptionAnchor(list = []) {
    const active = (list || []).find(item => item && item.className === 'active' && item.anchorId);
    return active ? active.anchorId : '';
  },

  buildVisibleMaterialAppendUpdates(materials = [], startIndex = 0) {
    return (materials || []).reduce((updates, item, index) => {
      updates[`visibleMaterials[${startIndex + index}]`] = item;
      return updates;
    }, {});
  },

  materialCardClass(item = {}, displayIndex = 0, launchingMaterialId = this.data.launchingMaterialId || '') {
    const baseClass = item.baseCardClass || `material-card-${displayIndex}`;
    const itemId = String(item.id || '');
    const launchingId = String(launchingMaterialId || '');
    return `${baseClass}${launchingId && itemId === launchingId ? ' launching' : ''}`;
  },

  buildLaunchingMaterialUpdates(nextLaunchingMaterialId = '', extraUpdates = {}) {
    const nextId = String(nextLaunchingMaterialId || '');
    const previousId = this.data.launchingMaterialId || '';
    const updates = {
      ...extraUpdates,
      launchingMaterialId: nextId
    };
    const visibleMaterials = this.data.visibleMaterials || [];
    if (!previousId && !nextId) return updates;
    visibleMaterials.forEach((item, index) => {
      const itemId = String(item && item.id || '');
      if (!item || (itemId !== previousId && itemId !== nextId)) return;
      const cardClass = this.materialCardClass(item, index, nextId);
      if (item.cardClass !== cardClass) {
        updates[`visibleMaterials[${index}].cardClass`] = cardClass;
      }
    });
    return updates;
  },

  setLaunchingMaterialState(nextLaunchingMaterialId = '', extraUpdates = {}, callback) {
    this.setData(this.buildLaunchingMaterialUpdates(nextLaunchingMaterialId, extraUpdates), callback);
  },

  decoratedMaterialCacheKey(item = {}, displayIndex = 0) {
    return [
      this.materialCatalogVersion || 0,
      displayIndex,
      item.id || item.skuId || item.sku_id || item.material_code || '',
      item.image_url || '',
      item.name || '',
      item.series || '',
      item.grade || '',
      (item.effects || []).join('|'),
      item.price || '',
      item.size || ''
    ].join('::');
  },

  getDecoratedMaterialCache() {
    if (!this.decoratedMaterialCache) {
      this.decoratedMaterialCache = {
        entries: Object.create(null),
        keys: []
      };
    }
    return this.decoratedMaterialCache;
  },

  rememberDecoratedMaterial(key, value) {
    const cache = this.getDecoratedMaterialCache();
    if (!cache.entries[key]) cache.keys.push(key);
    cache.entries[key] = value;
    if (cache.keys.length <= DECORATED_MATERIAL_CACHE_LIMIT) return;
    const deleteCount = cache.keys.length - DECORATED_MATERIAL_CACHE_LIMIT;
    cache.keys.splice(0, deleteCount).forEach(oldKey => {
      delete cache.entries[oldKey];
    });
  },

  decorateVisibleMaterials(materials, startIndex = 0) {
    const launchingMaterialId = this.data.launchingMaterialId || '';
    return (materials || []).map((item, index) => {
      const displayIndex = startIndex + index;
      const cacheKey = this.decoratedMaterialCacheKey(item, displayIndex);
      const cached = this.decoratedMaterialCache && this.decoratedMaterialCache.entries
        ? this.decoratedMaterialCache.entries[cacheKey]
        : null;
      if (cached) {
        const cardClass = this.materialCardClass(cached, displayIndex, launchingMaterialId);
        return cached.cardClass === cardClass ? cached : { ...cached, cardClass };
      }
      const decorated = {
        ...item,
        baseCardClass: `material-card-${displayIndex}`,
        cardClass: this.materialCardClass(item, displayIndex, launchingMaterialId)
      };
      this.rememberDecoratedMaterial(cacheKey, decorated);
      return decorated;
    });
  },

  selectTop(e) {
    this.setData({ activeTop: e.currentTarget.dataset.top, activeCategory: ALL_OPTION_LABEL, activeSeries: ALL_OPTION_LABEL }, () => {
      if (this.useServerMaterialPagination) this.loadMaterials();
      else this.refreshFilters();
    });
  },

  selectCategory(e) {
    this.setData({ activeCategory: e.currentTarget.dataset.category, activeSeries: ALL_OPTION_LABEL }, () => {
      if (this.useServerMaterialPagination) this.loadMaterials({ autoTargetSearch: false });
      else this.refreshFilters({ autoTargetSearch: false });
    });
  },

  selectSeries(e) {
    this.setData({ activeSeries: e.currentTarget.dataset.series }, () => {
      if (this.useServerMaterialPagination) this.loadMaterials({ autoTargetSearch: false });
      else this.refreshFilters({ autoTargetSearch: false });
    });
  },

  reloadMaterialsForSearch(options = {}) {
    const keyword = this.normalizeMaterialSearchKeyword(this.data.materialSearchKeyword);
    if (!options.force && keyword === this.appliedMaterialSearchKeyword) return;
    this.appliedMaterialSearchKeyword = keyword;
    const autoTargetSearch = options.autoTargetSearch !== false;
    const reload = () => {
      if (this.useServerMaterialPagination) this.loadMaterials({ autoTargetSearch });
      else this.refreshFilters({ autoTargetSearch });
    };
    if (keyword && autoTargetSearch && (!this.isAllFilterValue(this.data.activeCategory) || !this.isAllFilterValue(this.data.activeSeries))) {
      this.setData({
        activeCategory: ALL_OPTION_LABEL,
        activeSeries: ALL_OPTION_LABEL
      }, reload);
      return;
    }
    reload();
  },

  onMaterialSearchInput(e) {
    const keyword = (e.detail && e.detail.value) || '';
    if (keyword === this.data.materialSearchKeyword) return;
    this.setData({ materialSearchKeyword: keyword });
    clearTimeout(this.materialSearchTimer);
    this.materialSearchTimer = setTimeout(() => {
      this.reloadMaterialsForSearch();
    }, MATERIAL_SEARCH_DEBOUNCE_MS);
  },

  submitMaterialSearch(e) {
    const keyword = (e.detail && e.detail.value) || this.data.materialSearchKeyword || '';
    clearTimeout(this.materialSearchTimer);
    this.setData({ materialSearchKeyword: keyword }, () => this.reloadMaterialsForSearch({ force: true }));
  },

  clearMaterialSearch() {
    if (!this.data.materialSearchKeyword) return;
    clearTimeout(this.materialSearchTimer);
    this.setData({ materialSearchKeyword: '' }, () => this.reloadMaterialsForSearch({ force: true }));
  },

  onMaterialImageError(e) {
    const id = e.currentTarget.dataset.id;
    if (!id) return;
    this.materialCatalog = (this.materialCatalog || DEFAULT_MATERIALS).map(item => (
      item.id === id ? { ...item, image_url: '' } : item
    ));
    this.rebuildMaterialLookup();
    if (this.useServerMaterialPagination) {
      this.setData({
        visibleMaterials: (this.data.visibleMaterials || []).map(item => (
          item.id === id ? { ...item, image_url: '' } : item
        ))
      });
      this.recalculate();
      return;
    }
    this.refreshFilters({
      limit: Math.max(this.materialPageSize || MATERIAL_PAGE_SIZE, (this.data.visibleMaterials || []).length)
    });
    this.recalculate();
  },

  onTrayImageError() {
    this.setData({ trayImageFailed: true });
    logWorkspaceWarning('workspace tray image failed, fallback background is active:', this.data.trayImageUrl);
  },

  closeTip() {
    this.setData({ showTip: false });
  },

  initWorkspaceGuide() {
    this.workspaceGuideDismissed = !!wx.getStorageSync(WORKSPACE_GUIDE_STORAGE_KEY);
    this.workspaceGuideStarted = false;
  },

  maybeShowWorkspaceGuide() {
    if (this.workspaceGuideDismissed || this.workspaceGuideStarted || this.data.sharedDesignLoading) return;
    this.workspaceGuideStarted = true;
    this.showWorkspaceGuideStep(0);
  },

  showWorkspaceGuideStep(step) {
    const safeStep = Math.max(0, Math.min(WORKSPACE_GUIDE_STEPS.length - 1, Number(step) || 0));
    this.setData({
      showWorkspaceGuide: true,
      workspaceGuideStep: safeStep,
      activeWorkspaceGuide: WORKSPACE_GUIDE_STEPS[safeStep],
      workspaceGuideFocusStyle: ''
    }, () => this.measureWorkspaceGuideFocus());
  },

  measureWorkspaceGuideFocus() {
    const target = this.data.activeWorkspaceGuide && this.data.activeWorkspaceGuide.target;
    if (!target || !this.data.showWorkspaceGuide) return;
    wx.nextTick(() => {
      wx.createSelectorQuery().in(this).select(`.workspace-guide-anchor-${target}`).boundingClientRect(rect => {
        if (!rect || !this.data.showWorkspaceGuide || this.data.activeWorkspaceGuide.target !== target) return;
        const padding = target === 'tray' ? 5 : 7;
        this.setData({
          workspaceGuideFocusStyle: [
            `left:${Math.max(0, rect.left - padding)}px`,
            `top:${Math.max(0, rect.top - padding)}px`,
            `width:${rect.width + padding * 2}px`,
            `height:${rect.height + padding * 2}px`
          ].join(';')
        });
      }).exec();
    });
  },

  dismissWorkspaceGuide(e) {
    const dataset = (e && e.currentTarget && e.currentTarget.dataset) || {};
    if (dataset.forever) {
      wx.setStorageSync(WORKSPACE_GUIDE_STORAGE_KEY, true);
      this.workspaceGuideDismissed = true;
    }
    this.setData({ showWorkspaceGuide: false });
  },

  advanceWorkspaceGuide() {
    const nextStep = Number(this.data.workspaceGuideStep || 0) + 1;
    if (nextStep >= WORKSPACE_GUIDE_STEPS.length) {
      this.dismissWorkspaceGuide({ currentTarget: { dataset: { forever: true } } });
      return;
    }
    this.showWorkspaceGuideStep(nextStep);
  },

  resumeWristGuideIfNeeded(confirmed = false) {
    if (!this.workspaceGuideWaitingForWrist) return;
    this.workspaceGuideWaitingForWrist = false;
    this.showWorkspaceGuideStep(confirmed ? 1 : 0);
  },

  restartWorkspaceGuide() {
    this.workspaceGuideStarted = true;
    this.setData({ showWristGuideModal: false }, () => {
      this.restoreWorkspaceCanvasAfterOverlay();
      this.showWorkspaceGuideStep(0);
    });
  },

  openWristSetting() {
    const guidingWrist = this.data.showWorkspaceGuide && this.data.activeWorkspaceGuide.target === 'wrist';
    if (guidingWrist) {
      this.workspaceGuideWaitingForWrist = true;
      this.setData({ showWorkspaceGuide: false, workspaceGuideFocusStyle: '' });
    }
    this.hideWorkspaceCanvasForOverlay();
    this.setData({ showWristPicker: true });
  },

  closeWristSetting() {
    this.setData({ showWristPicker: false }, () => {
      this.restoreWorkspaceCanvasAfterOverlay();
      this.resumeWristGuideIfNeeded();
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

  confirmWristRuler() {
    const wristSize = this.normalizeWristValue(Number(this.data.wristRulerValue));
    const isSameWristSize = wristSize === Number(this.data.wristSize);
    const rememberedWristSize = this.rememberWristSize(wristSize);
    if (isSameWristSize) {
      this.setData({ wristSize: rememberedWristSize, showWristPicker: false }, () => {
        this.restoreWorkspaceCanvasAfterOverlay();
        this.resumeWristGuideIfNeeded(true);
      });
      wx.showToast({ title: `已是 ${this.formatWristValue(wristSize)}cm`, icon: 'none' });
      return;
    }
    try {
      this.pushHistory();
    } catch (error) {
      logWorkspaceWarning('push wrist history failed:', error);
    }
    this.setData({ wristSize: rememberedWristSize, showWristPicker: false }, () => {
      this.recalculate();
      this.restoreWorkspaceCanvasAfterOverlay();
      this.resumeWristGuideIfNeeded(true);
    });
    wx.showToast({ title: `${this.formatWristValue(rememberedWristSize)}cm 手围`, icon: 'success' });
  },

  confirmWristPickerComponent(event) {
    const value = Number(event && event.detail && event.detail.value);
    this.setData({ wristRulerValue: this.formatWristValue(value) });
    this.confirmWristRuler();
  },

  chooseWristSize(e) {
    const wristSize = this.normalizeWristValue(Number(e.currentTarget.dataset.size));
    if (!wristSize) return;
    const isSameWristSize = wristSize === Number(this.data.wristSize);
    const rememberedWristSize = this.rememberWristSize(wristSize);
    if (isSameWristSize) {
      this.setData({ wristSize: rememberedWristSize, showWristPicker: false }, () => {
        this.restoreWorkspaceCanvasAfterOverlay();
        this.resumeWristGuideIfNeeded(true);
      });
      wx.showToast({ title: `已是 ${this.formatWristValue(wristSize)}cm`, icon: 'none' });
      return;
    }
    try {
      this.pushHistory();
    } catch (error) {
      logWorkspaceWarning('push wrist history failed:', error);
    }
    this.setData({ wristSize: rememberedWristSize, showWristPicker: false }, () => {
      this.recalculate();
      this.restoreWorkspaceCanvasAfterOverlay();
      this.resumeWristGuideIfNeeded(true);
    });
    wx.showToast({ title: `${this.formatWristValue(rememberedWristSize)}cm 手围`, icon: 'success' });
  },

  promptInitialWristSize() {
    if (!this.workspaceGuideDismissed) return;
    if (wx.getStorageSync('workspaceWristConfirmed')) return;
    if (this.pendingSharedDesign || this.pendingShareToken || this.pendingBackendRecommendation || this.pendingRecommendedRecipe) return;
    const workspacePreset = wx.getStorageSync('workspacePreset');
    if (workspacePreset === 'backend-recommended' || workspacePreset === 'recommended') return;
    this.openWristSetting();
  },

  releaseString() {
    if (
      this.data.isLooseMode
      || !this.data.selected.length
      || this.data.isShuffling
      || this.data.isStringingFinishing
      || this.data.isReleasingString
    ) return;
    this.pushHistory();
    this.stopPhysics();
    const selected = this.data.selected || [];
    const currentPlacements = this.normalizePlacements(selected, this.data.placements);
    const items = selected.map((id, index) => {
      const material = this.findMaterialById(id) || {};
      const placement = currentPlacements[index] || {};
      return {
        ...placement,
        ...material,
        id,
        image_url: placement.image_url || material.image_url || ''
      };
    });
    const geometry = this.getCachedBraceletGeometry(items);
    const targetPlacements = [];
    selected.forEach((id, index) => {
      const previous = currentPlacements[index] || {};
      const loosePlacement = this.createLoosePlacement(index, id, targetPlacements);
      targetPlacements.push({
        ...previous,
        ...loosePlacement,
        image_url: previous.image_url || loosePlacement.image_url || '',
        name: previous.name || loosePlacement.name || '',
        category: previous.category || loosePlacement.category || '',
        series: previous.series || loosePlacement.series || '',
        size: previous.size || previous.diameter || loosePlacement.size || '',
        diameter: previous.diameter || previous.size || loosePlacement.diameter || '',
        price: previous.price || loosePlacement.price || ''
      });
    });
    const startPlacements = currentPlacements.map((placement, index) => {
      const angle = geometry.angles[index] || 0;
      const beadSize = geometry.beadSizes[index] || Number(placement.beadSize) || this.getMaterialDisplaySize(selected[index]);
      return {
        ...placement,
        looseX: geometry.center + Math.cos(angle) * geometry.radius,
        looseY: geometry.center + Math.sin(angle) * geometry.radius,
        rotation: Number(placement.rotation || 0),
        beadSize
      };
    });
    this.setData({
      placements: startPlacements,
      isLooseMode: true,
      isReleasingString: true,
      selectedBeadIndex: -1,
      selectedBeadInfo: null,
      draggingBeadIndex: -1,
      dragDeleteArmed: false
    }, () => {
      this.recalculate({ persist: false });
      this.animateReleaseString(startPlacements, targetPlacements, items, geometry);
    });
  },

  animateReleaseString(startPlacements, targetPlacements, items, geometry) {
    clearInterval(this.releaseStringTimer);
    this.releaseStringTimer = null;
    const duration = this.isLowPerformanceDevice ? RELEASE_STRING_LOW_PERF_DURATION : RELEASE_STRING_FLIGHT_DURATION;
    const stagger = this.isLowPerformanceDevice ? RELEASE_STRING_LOW_PERF_STAGGER_MS : RELEASE_STRING_STAGGER_MS;
    const interval = this.isLowPerformanceDevice ? 28 : (this.isRealDevice ? 20 : 16);
    const startedAt = Date.now();
    const totalDuration = duration + Math.max(0, (startPlacements.length - 1) * stagger);
    const center = geometry.center || this.getStageLayout().center;
    this.releaseStringTimer = setInterval(() => {
      const elapsed = Date.now() - startedAt;
      const nextPlacements = startPlacements.map((start, index) => {
        const target = targetPlacements[index] || start;
        const progress = Math.max(0, Math.min(1, (elapsed - index * stagger) / duration));
        const eased = progress;
        const startX = Number(start.looseX || center);
        const startY = Number(start.looseY || center);
        const x = startX + (Number(target.looseX || center) - startX) * eased;
        const y = startY + (Number(target.looseY || center) - startY) * eased;
        const fromRotation = Number(start.rotation || 0);
        const toRotation = Number(target.rotation || 0);
        return {
          ...target,
          looseX: x,
          looseY: y,
          rotation: fromRotation + (toRotation - fromRotation) * eased,
          beadSize: Number(start.beadSize || target.beadSize || 54)
            + (Number(target.beadSize || start.beadSize || 54) - Number(start.beadSize || target.beadSize || 54)) * eased
        };
      });
      this.setLivePlacements(nextPlacements);
      const isComplete = elapsed >= totalDuration;
      if (isComplete) {
        clearInterval(this.releaseStringTimer);
        this.releaseStringTimer = null;
      }
      this.scheduleCanvasRender(true);
      if (isComplete) this.completeReleaseString(targetPlacements);
    }, interval);
  },

  completeReleaseString(targetPlacements) {
    this.setLivePlacements(targetPlacements);
    this.setData({
      placements: targetPlacements,
      isLooseMode: true,
      isReleasingString: false,
      selectedBeadIndex: -1,
      selectedBeadInfo: null,
      draggingBeadIndex: -1,
      dragDeleteArmed: false
    }, () => {
      this.recalculate({ persistDelay: 260 });
      wx.nextTick(() => {
        this.startPhysicsFromCurrentDesign();
        this.refreshWorkspaceCanvasAfterDesignTransition();
      });
    });
  },

  toggleStringMode() {
    if (this.hasActiveStringModeTransition()) {
      wx.showToast({ title: this.data.isReleasingString ? '正在散开，请稍候' : '正在成串，请稍候', icon: 'none' });
      return;
    }
    if (this.hasStaleStringModeTransition()) {
      const keepLooseMode = !!this.data.isLooseMode;
      this.stopPhysics();
      this.resetInteractionData({ isLooseMode: keepLooseMode }, () => {
        this.recalculate({ persist: false });
        this.toggleStringMode();
      });
      return;
    }
    if (this.data.sharedDesignFrozen) this.setData({ sharedDesignFrozen: false });
    if (this.data.isLooseMode) {
      if (this.isRecommendationWorkspaceSource()) {
        this.stringCurrentDesign();
        return;
      }
      this.shuffleDesign();
      return;
    }
    this.releaseString();
  },

  hasActiveStringModeTransition() {
    if (this.data.isReleasingString) return !!this.releaseStringTimer;
    if (!this.data.isShuffling && !this.data.isStringingFinishing) return false;
    return !!(
      this.stringingStartQueued
      || this.stringingFinishTimer
      || this.stringingCompleteTimer
      || this.physicsTargets
      || this.physicsTimer
    );
  },

  hasStaleStringModeTransition() {
    return !!(
      (this.data.isShuffling || this.data.isStringingFinishing || this.data.isReleasingString)
      && !this.hasActiveStringModeTransition()
    );
  },

  isRecommendationWorkspaceSource() {
    const context = this.data.sourceContext || this.sourceContext || {};
    const source = String(context.source || '').trim().toLowerCase();
    const sourceLabel = String(context.source_label || '').trim();
    return source === 'backend_recommendation'
      || source === 'recommended_recipe'
      || sourceLabel === '推荐方案';
  },

  stringCurrentDesign() {
    if (this.data.selected.length < MIN_STRING_BEAD_COUNT) {
      wx.showToast({ title: `至少选择${MIN_STRING_BEAD_COUNT}颗珠子成串`, icon: 'none' });
      return;
    }
    this.pushHistory();
    this.stopPhysics();
    this.setData({
      isLooseMode: true,
      isShuffling: true,
      isStringingFinishing: false,
      isReleasingString: false,
      selectedBeadIndex: -1,
      selectedBeadInfo: null,
      draggingBeadIndex: -1,
      dragDeleteArmed: false
    }, () => {
      this.recalculate({ persist: false });
      this.stringingStartQueued = true;
      wx.nextTick(() => {
        this.stringingStartQueued = false;
        this.startStringingPhysics();
      });
    });
  },

  buildCurrentPersistedPlacements() {
    const selected = this.data.selected || [];
    const sourcePlacements = this.data.isLooseMode && this.livePlacements && this.livePlacements.length === selected.length
      ? this.livePlacements
      : this.data.placements;
    const placements = this.normalizePlacements(selected, sourcePlacements);
    if (this.data.isLooseMode) return placements.map(item => ({ ...item }));
    const context = this.getStringedRingContext();
    const geometry = context.geometry || {};
    const center = Number(geometry.center) || this.getStageLayout().center;
    return context.placements.map((placement, index) => {
      const angle = Number((geometry.angles || [])[index]) || 0;
      const x = center + Math.cos(angle) * Number(geometry.radius || 0);
      const y = center + Math.sin(angle) * Number(geometry.radius || 0);
      const physical = (geometry.materialGeometries || [])[index]
        || resolveMaterialGeometry((context.items || [])[index] || {});
      return {
        ...placement,
        x,
        y,
        rotation: stringedMaterialRotationDeg(angle, physical),
        beadSize: Number((geometry.beadSizes || [])[index])
          || Number(placement.beadSize)
          || this.getMaterialDisplaySize(selected[index])
      };
    });
  },

  buildCurrentSequence(persistedPlacements = this.buildCurrentPersistedPlacements()) {
    const timestamp = new Date().toISOString();
    const beadSequence = (this.data.selected || []).map((id, index) => {
      const material = this.findMaterialById(id) || {};
      const placement = (persistedPlacements || [])[index] || {};
      const imageUrls = this.materialOwnImageUrls(material);
      const size = material.size || material.diameter || placement.diameter || '';
      const price = Number(material.price ?? material.priceText ?? material.amount ?? material.sale_price ?? 0);
      const materialParams = {
        ...(placement.material_params || {}),
        ...(material.material_params || {})
      };
      const contributesEnergy = materialContributesEnergy(material);
      const primaryElement = contributesEnergy ? (material.primary_element || material.element || '') : '';
      const elementKey = contributesEnergy ? this.materialElementKey(material) : '';
      return {
        index: index + 1,
        id,
        material_id: material.id || id,
        sku: material.skuId || material.sku || id,
        top: material.top || 'bead',
        item_type: material.top || 'bead',
        name: this.displayMaterialName(material, id),
        category: repairMaybeMojibakeText(material.category) || '',
        series: repairMaybeMojibakeText(material.series) || '',
        grade: repairMaybeMojibakeText(material.grade) || '',
        effect: material.effect || '',
        element: primaryElement,
        primary_element: primaryElement,
        element_key: elementKey,
        secondary_elements: contributesEnergy ? (material.secondary_elements || []) : [],
        color: material.color || '',
        size,
        diameter: size,
        bead_shape: material.bead_shape || materialParams.bead_shape || '',
        placement_mode: material.placement_mode || materialParams.placement_mode || 'threaded',
        material_params: materialParams,
        string_axis_width_mm: material.string_axis_width_mm || materialParams.string_axis_width_mm || 0,
        price: Number.isFinite(price) ? price : 0,
        weight: Number(material.weight || 0),
        image_url: placement.image_url || imageUrls[0] || '',
        image_urls: imageUrls,
        placement: {
          x: placement.x,
          y: placement.y,
          dx: placement.dx,
          dy: placement.dy,
          looseX: placement.looseX,
          looseY: placement.looseY,
          rotation: placement.rotation,
          beadSize: placement.beadSize,
          angle: placement.angle,
          diameter: placement.diameter,
          image_url: placement.image_url || '',
          bead_caps: beadCapSlotsFromPlacement(placement)
        },
        snapshot_at: timestamp
      };
    });
    const capSequence = [];
    (persistedPlacements || []).forEach((placement, hostIndex) => {
      const slots = beadCapSlotsFromPlacement(placement);
      ['left', 'right'].forEach(side => {
        const cap = slots[side];
        if (!cap) return;
        const materialParams = cap.material_params || {};
        const id = cap.id || cap.material_id || cap.skuId || '';
        capSequence.push({
          index: beadSequence.length + capSequence.length + 1,
          id,
          material_id: cap.material_id || id,
          sku: cap.skuId || id,
          top: cap.top || 'accessory',
          item_type: cap.top || 'accessory',
          name: this.displayMaterialName(cap, '包珠隔片'),
          category: repairMaybeMojibakeText(cap.category) || '',
          series: repairMaybeMojibakeText(cap.series) || '',
          size: cap.size || '',
          diameter: cap.size || '',
          bead_shape: materialParams.bead_shape || 'bead_cap',
          placement_mode: 'attached_side',
          attachment_mode: 'bead_cap',
          attachment: {
            mode: 'bead_cap',
            host_index: hostIndex + 1,
            side
          },
          material_params: materialParams,
          price: Number(cap.price || 0),
          weight: Number(cap.weight || 0),
          image_url: cap.image_url || '',
          image_urls: cap.image_urls || [],
          placement: {
            host_index: hostIndex + 1,
            side,
            x: placement.x,
            y: placement.y,
            looseX: placement.looseX,
            looseY: placement.looseY,
            rotation: placement.rotation
          },
          snapshot_at: timestamp
        });
      });
    });
    return [...beadSequence, ...capSequence];
  },

  validateStringedDesignForCheckout() {
    if (!this.data.selected.length) {
      wx.showToast({ title: '请先选择珠子', icon: 'none' });
      return false;
    }
    if (this.data.selected.length < MIN_STRING_BEAD_COUNT) {
      wx.showToast({ title: `至少选择${MIN_STRING_BEAD_COUNT}颗珠子成串`, icon: 'none' });
      return false;
    }
    if (this.data.isShuffling || this.data.isStringingFinishing || this.data.isReleasingString) {
      wx.showToast({ title: this.data.isReleasingString ? '正在散开，请稍候' : '正在成串，请稍候', icon: 'none' });
      return false;
    }
    if (this.data.isLooseMode) {
      wx.showToast({ title: '请先收拢成串后再进入结算', icon: 'none' });
      return false;
    }
    const selectedMaterials = this.getCachedSelectedMaterials(this.data.selected).filter(Boolean);
    const attachmentMaterials = (this.data.placements || []).flatMap(placement => {
      const slots = beadCapSlotsFromPlacement(placement);
      return ['left', 'right'].map(side => slots[side]).filter(Boolean);
    });
    const purchasableMaterials = [...selectedMaterials, ...attachmentMaterials];
    const unavailable = purchasableMaterials.find(material => (
      material.enabled === false
      || String(material.stock_status || (material.sku && material.sku.stock_status) || '').toLowerCase() === 'out'
    ));
    if (unavailable) {
      wx.showToast({ title: `${this.displayMaterialName(unavailable)}暂不可售，请更换后重试`, icon: 'none' });
      return false;
    }
    const invalidPrice = purchasableMaterials.find(material => {
      const price = Number(material.price);
      return !Number.isFinite(price) || price < 0;
    });
    if (invalidPrice) {
      wx.showToast({ title: `${this.displayMaterialName(invalidPrice)}价格暂不可计算`, icon: 'none' });
      return false;
    }
    return true;
  },

  confirmCheckoutWristWarning() {
    const summary = this.data.summary || {};
    const warning = String(summary.warning || '');
    if (!warning || warning === '合适') return Promise.resolve(true);
    const effectiveWrist = summary.currentWrist || '--';
    const targetWrist = this.data.wristSize || '--';
    const isTooLarge = warning === '偏长';
    const title = isTooLarge ? '有效腕围偏大' : '有效腕围偏小';
    const consequence = isTooLarge
      ? '成品佩戴时可能偏松。'
      : '成品可能偏紧或无法舒适佩戴。';
    return new Promise(resolve => {
      wx.showModal({
        title,
        content: `目标腕围 ${targetWrist}cm，当前有效腕围 ${effectiveWrist}cm，${consequence}是否仍要进入结算？`,
        cancelText: '继续调整',
        confirmText: '确认结算',
        confirmColor: '#171815',
        success: result => resolve(!!result.confirm),
        fail: () => resolve(false)
      });
    });
  },

  async checkoutCurrentDesign() {
    if (!this.validateStringedDesignForCheckout()) return;
    if (this.checkoutSubmissionInFlight || this.data.isAddingToCart) return;
    this.checkoutSubmissionInFlight = true;
    const wristConfirmed = await this.confirmCheckoutWristWarning();
    if (!wristConfirmed) {
      this.checkoutSubmissionInFlight = false;
      return;
    }
    this.setData({
      isAddingToCart: true,
      cartActionText: '正在打开...'
    });
    let user;
    try {
      user = await auth.requireLogin('登录后才能进入订单结算。');
    } catch (error) {
      this.setData({
        isAddingToCart: false,
        cartActionText: '去结算'
      });
      this.checkoutSubmissionInFlight = false;
      return;
    }
    try {
      const current = wx.getStorageSync('currentDesign') || {};
      const planName = cleanDesignName(current.name) || cleanDesignName(current.title) || DEFAULT_DESIGN_NAME;
      const placements = this.buildCurrentPersistedPlacements();
      const sequence = this.buildCurrentSequence(placements);
      const fallbackPrice = sequence.reduce((sum, item) => sum + Number(item.price || 0), 0);
      const summaryPrice = Number((this.data.summary && (this.data.summary.priceText || this.data.summary.price)) || fallbackPrice || 0);
      const price = Number.isFinite(summaryPrice) ? summaryPrice : fallbackPrice;
      const summary = {
        ...(this.data.summary || {}),
        count: this.data.selected.length,
        price,
        priceText: price.toFixed(2)
      };
      const stageLayout = this.getStageLayout();
      const updatedAt = Date.now();
      const design = {
        ...current,
        createdAt: current.createdAt || Date.now(),
        updatedAt,
        name: planName,
        title: planName,
        userId: user.user_id,
        selected: [...this.data.selected],
        materialIds: sequence.map(item => item.id || item.sku).filter(Boolean),
        placements,
        attachedPendants: [],
        wristSize: this.data.wristSize,
        wearStyle: 'single',
        isLooseMode: this.data.isLooseMode,
        trayTheme: this.data.trayTheme,
        tray_theme: this.data.trayTheme,
        trayImageUrl: this.data.trayImageUrl,
        tray_image_url: this.data.trayImageUrl,
        workspaceStageCenter: stageLayout.center,
        previewSourceCenter: stageLayout.center,
        preview_source_center: stageLayout.center,
        sourceContext: this.data.sourceContext || this.sourceContext || null,
        preview_image: '',
        previewImage: '',
        image_url: '',
        local_preview_image: '',
        summary,
        sequence
      };
      delete design.cart_item_id;
      delete design.cartItemId;
      delete design.cartIdempotencyKey;
      wx.setStorageSync('currentDesign', design);
      this.setData({ isAddingToCart: false, cartActionText: '去结算' });
      this.hideWorkspaceCanvasForOverlay();
      await this.openCheckoutPage();
    } catch (error) {
      logWorkspaceWarning('open checkout failed:', error && (error.message || error));
      this.restoreWorkspaceCanvasAfterOverlay();
      this.setData({
        isAddingToCart: false,
        cartActionText: '去结算'
      });
      wx.showToast({ title: '进入结算失败，请重试', icon: 'none' });
    } finally {
      this.checkoutSubmissionInFlight = false;
    }
  },

  openCheckoutPage() {
    return new Promise((resolve, reject) => {
      wx.navigateTo({
        url: '/pages/checkout/checkout',
        success: resolve,
        fail: navigateError => {
          wx.redirectTo({
            url: '/pages/checkout/checkout',
            success: resolve,
            fail: redirectError => reject(redirectError || navigateError)
          });
        }
      });
    });
  },

  showWorkspaceHelp() {
    wx.showModal({
      title: 'DIY工作台帮助',
      content: '点击材料可投入圆盘；成串后拖动珠子调整顺序，拖动外环旋转整串；拖出圆盘可移除；解除成串后可继续自由滚动和编辑。',
      showCancel: false,
      confirmText: '知道了'
    });
  },

  stopPropagation() {},

  showMaterialQueueToast(title) {
    const now = Date.now();
    if (now - (this.lastQueueToastAt || 0) < MATERIAL_QUEUE_TOAST_GUARD_MS) return;
    this.lastQueueToastAt = now;
    wx.showToast({ title, icon: 'none' });
  },

  buildMaterialDetail(material = {}) {
    const physical = resolveMaterialGeometry(material);
    const top = materialTop(material);
    const category = safeMaterialDisplayText(material.category || '未分类');
    const series = safeMaterialDisplayText(material.series || '');
    const name = this.displayMaterialName(material);
    const price = Number(material.price || 0);
    const unit = top === 'accessory' ? '个' : '颗';
    const effects = (Array.isArray(material.effects) ? material.effects : [material.effects])
      .map(safeMaterialDisplayText)
      .filter(Boolean);
    const introduction = safeMaterialDisplayText(
      material.description
      || material.introduction
      || `${name}，${physical.shape || '圆珠'}材质，适合用于日常 DIY 手串搭配。`
    );
    const story = safeMaterialDisplayText(material.story || '');
    const galleryImages = this.materialOwnImageUrls(material);
    const primaryImage = String(material.image_url || '').trim();
    // 图库优先；图库尚未配置时，详情仍应展示材料卡已在使用的主图。
    const images = galleryImages.length ? galleryImages : (primaryImage ? [primaryImage] : []);
    const specText = materialDetailSpecText(physical, top === 'accessory');
    const fields = [
      { label: '分类', value: category },
      ...(series && series !== category ? [{ label: '品种', value: series }] : []),
      { label: '规格', value: specText },
      { label: '计价单位', value: `每${unit}` }
    ];
    const fallbackColor = String(material.color || '#d6d0c5');
    const fallbackShine = String(material.shine || 'rgba(255,255,255,.85)');
    return {
      id: String(material.id || ''),
      cardIndex: Number((this.data.visibleMaterials || []).findIndex(item => String(item.id || '') === String(material.id || ''))),
      name,
      typeLabel: top === 'accessory' ? 'DIY 配饰' : 'DIY 珠材',
      priceText: Number.isFinite(price) ? `¥${price.toFixed(2)} / ${unit}` : '--',
      introduction,
      story,
      effects,
      images,
      fields,
      fallbackStyle: `background:radial-gradient(circle at 32% 26%,${fallbackShine} 0 10%,${fallbackColor} 12% 58%,rgba(0,0,0,.22) 100%);`
    };
  },

  openMaterialDetail(e) {
    const id = String((e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.id) || '').trim();
    if (!id) return;
    const material = this.findMaterialById(id);
    if (!material) {
      this.showMaterialQueueToast(this.data.materialsLoading ? '珠材加载中，请稍候' : '材料暂不可用');
      return;
    }
    this.lastMaterialLongPress = { id, at: Date.now() };
    // 原生 canvas 可能脱离普通 z-index 层级，打开详情前先暂停并隐藏盘面模型，
    // 避免手串渲染层穿透材料详情页。
    if (typeof this.hideWorkspaceCanvasForOverlay === 'function') {
      this.hideWorkspaceCanvasForOverlay();
    }
    this.setData({
      showMaterialDetail: true,
      materialDetail: this.buildMaterialDetail(material)
    });
  },

  closeMaterialDetail() {
    this.setData({ showMaterialDetail: false, materialDetail: null });
    if (typeof this.restoreWorkspaceCanvasAfterOverlay === 'function') {
      this.restoreWorkspaceCanvasAfterOverlay();
    }
  },

  addMaterialFromDetail() {
    const detail = this.data.materialDetail || {};
    const id = String(detail.id || '').trim();
    if (!id) return;
    this.closeMaterialDetail();
    this.addMaterial({
      currentTarget: {
        dataset: {
          id,
          index: Number.isInteger(detail.cardIndex) && detail.cardIndex >= 0 ? detail.cardIndex : 0
        }
      },
      ignoreLongPressGuard: true
    });
  },

  getTapPoint(e = {}) {
    const detail = e.detail || {};
    if (Number.isFinite(Number(detail.x)) && Number.isFinite(Number(detail.y))) {
      return { x: Number(detail.x), y: Number(detail.y) };
    }
    const touch = (e.changedTouches && e.changedTouches[0]) || (e.touches && e.touches[0]);
    if (touch && Number.isFinite(Number(touch.clientX)) && Number.isFinite(Number(touch.clientY))) {
      return { x: Number(touch.clientX), y: Number(touch.clientY) };
    }
    return null;
  },

  isValidRect(rect) {
    return !!rect
      && Number(rect.width) > 1
      && Number(rect.height) > 1
      && Number.isFinite(Number(rect.left))
      && Number.isFinite(Number(rect.top));
  },

  resolveFlightStartRect(cardRect, tapPoint, drawerRect, material = {}) {
    if (this.isValidRect(cardRect)) return cardRect;
    const size = resolveMaterialGeometry(material, { maxDisplayRpx: 72 }).displaySizeRpx;
    if (tapPoint && Number.isFinite(tapPoint.x) && Number.isFinite(tapPoint.y)) {
      return {
        left: tapPoint.x - size / 2,
        top: tapPoint.y - size / 2,
        width: size,
        height: size
      };
    }
    if (this.isValidRect(drawerRect)) {
      return {
        left: drawerRect.left + drawerRect.width * 0.68 - size / 2,
        top: drawerRect.top + Math.min(drawerRect.height * 0.42, 220) - size / 2,
        width: size,
        height: size
      };
    }
    return null;
  },

  resolveMaterialFlightTarget(task = {}, material = {}, layout = this.getStageLayout()) {
    const beadSize = resolveMaterialGeometry(material).displaySizeRpx;
    if (task.keepStringed && !this.data.isLooseMode) {
      const insertion = this.buildStringedInsertion(task.id, task.placement);
      const slot = insertion.visualSlots[insertion.selected.length - 1] || {};
      if (Number.isFinite(Number(slot.x)) && Number.isFinite(Number(slot.y))) {
        return { x: Number(slot.x), y: Number(slot.y), beadSize };
      }
    }
    const center = layout.center || 300;
    const rawX = Number(task.placement && task.placement.looseX);
    const rawY = Number(task.placement && task.placement.looseY);
    let x = Number.isFinite(rawX) ? rawX : center;
    let y = Number.isFinite(rawY) ? rawY : center;
    const safePoint = this.constrainPointInsideTray({ x, y }, beadSize, layout, 12);
    x = safePoint.x;
    y = safePoint.y;
    return { x, y, beadSize };
  },

  getMaterialFlightDuration(startX, startY, endX, endY) {
    const maxDuration = this.isLowPerformanceDevice
      ? MATERIAL_FLIGHT_LOW_PERF_DURATION
      : (this.isRealDevice ? MATERIAL_FLIGHT_REAL_DURATION : MATERIAL_FLIGHT_DEV_DURATION);
    const points = [startX, startY, endX, endY].map(Number);
    if (!points.every(Number.isFinite)) return Math.round(maxDuration * MATERIAL_FLIGHT_DURATION_SCALE);
    const distance = Math.sqrt((points[2] - points[0]) ** 2 + (points[3] - points[1]) ** 2);
    const duration = Math.max(
      MATERIAL_FLIGHT_MIN_DURATION,
      Math.min(maxDuration, distance / MATERIAL_FLIGHT_SPEED_PX_PER_MS)
    );
    return Math.round(duration * MATERIAL_FLIGHT_DURATION_SCALE);
  },

  resolveMaterialLaunchPhysics({
    startX,
    startY,
    circleRect,
    target,
    layout = this.getStageLayout(),
    scale = 1,
    previousCount = 0
  } = {}) {
    const center = Number(layout.center) || 300;
    const beadSize = Math.max(42, Math.min(78, Number(target && target.beadSize) || 54));
    const activeCount = Number(previousCount) || 0;
    this.launchSequence = (Number(this.launchSequence) || 0) + 1;
    const safeRadius = this.getTraySafeDistance(beadSize, layout, TRAY_LAUNCH_ENTRY_PADDING_RPX);
    const rectLeft = Number(circleRect && circleRect.left);
    const rectTop = Number(circleRect && circleRect.top);
    const safeScale = Number(scale) > 0 ? Number(scale) : 1;
    const logicalStartX = Number.isFinite(Number(startX)) && Number.isFinite(rectLeft)
      ? (Number(startX) - rectLeft) / safeScale
      : center;
    const logicalStartY = Number.isFinite(Number(startY)) && Number.isFinite(rectTop)
      ? (Number(startY) - rectTop) / safeScale
      : center + safeRadius + beadSize;
    let aimX = center;
    let aimY = center - safeRadius * 0.96;
    if (activeCount > 0) aimY = center - safeRadius * 0.92;
    const safeAim = this.constrainPointInsideTray({ x: aimX, y: aimY }, beadSize, layout, TRAY_LAUNCH_AIM_PADDING_RPX);
    aimX = safeAim.x;
    aimY = safeAim.y;
    let rayX = aimX - logicalStartX;
    let rayY = aimY - logicalStartY;
    let rayLength = Math.sqrt(rayX * rayX + rayY * rayY);
    if (!Number.isFinite(rayLength) || rayLength < 1) {
      rayX = center - logicalStartX;
      rayY = center - safeRadius * 0.82 - logicalStartY;
      rayLength = Math.sqrt(rayX * rayX + rayY * rayY) || 1;
    }
    const startRelX = logicalStartX - center;
    const startRelY = logicalStartY - center;
    const a = rayX * rayX + rayY * rayY;
    const b = 2 * (startRelX * rayX + startRelY * rayY);
    const c = startRelX * startRelX + startRelY * startRelY - safeRadius * safeRadius;
    const disc = b * b - 4 * a * c;
    let entryT = 0;
    if (disc >= 0 && a > 0.0001) {
      const sqrtDisc = Math.sqrt(disc);
      const t1 = (-b - sqrtDisc) / (2 * a);
      const t2 = (-b + sqrtDisc) / (2 * a);
      const candidates = [t1, t2].filter(value => Number.isFinite(value) && value >= 0 && value <= 1);
      entryT = candidates.length ? Math.min(...candidates) : 0;
    }
    let entryX = logicalStartX + rayX * entryT;
    let entryY = logicalStartY + rayY * entryT;
    const entrySafePoint = this.constrainPointInsideTray({ x: entryX, y: entryY }, beadSize, layout, TRAY_LAUNCH_ENTRY_PADDING_RPX);
    entryX = entrySafePoint.x;
    entryY = entrySafePoint.y;
    let dx = aimX - entryX;
    let dy = aimY - entryY;
    let distance = Math.sqrt(dx * dx + dy * dy);
    if (!Number.isFinite(distance) || distance < 1) {
      dx = center - entryX;
      dy = center - entryY;
      distance = Math.sqrt(dx * dx + dy * dy) || 1;
    }
    const baseSpeed = BILLIARD_LAUNCH_MIN_SPEED + Math.min(distance, 640) / 640 * 18 + Math.min(activeCount, 10) * 0.8;
    const launchStrength = BILLIARD_LAUNCH_STRENGTH_MIN
      + Math.random() * (BILLIARD_LAUNCH_STRENGTH_MAX - BILLIARD_LAUNCH_STRENGTH_MIN);
    const variedSpeed = Math.max(
      BILLIARD_LAUNCH_SOFT_MIN_SPEED,
      Math.min(
        this.isLowPerformanceDevice ? BILLIARD_LAUNCH_MAX_SPEED - 1.2 : BILLIARD_LAUNCH_MAX_SPEED,
        baseSpeed * launchStrength
      )
    );
    const speed = variedSpeed * BILLIARD_LAUNCH_SPEED_SCALE;
    const velocity = {
      x: dx / distance * speed,
      y: dy / distance * speed
    };
    return {
      x: entryX,
      y: entryY,
      entryX,
      entryY,
      velocity,
      angularVelocity: (Math.random() * 2 - 1) * 0.035,
      launchAimX: aimX,
      launchAimY: aimY,
      launchSpeed: speed,
      launchAssistMs: 0,
      billiardDamping: BILLIARD_LINEAR_DAMPING,
      angularDamping: BILLIARD_ANGULAR_DAMPING,
      frictionAir: BILLIARD_FRICTION_AIR,
      restitution: BILLIARD_BEAD_RESTITUTION,
      density: 0.0024
    };
  },

  addMaterial(e) {
    if (this.data.canvasRenderError) {
      this.showMaterialQueueToast('请先重新加载工作台');
      return;
    }
    if (this.data.isShuffling || this.data.isStringingFinishing || this.data.isReleasingString) {
      this.showMaterialQueueToast(this.data.isReleasingString ? '正在散开，请稍候' : '正在成串，请稍候');
      return;
    }
    const id = e.currentTarget.dataset.id;
    const cardIndex = Number(e.currentTarget.dataset.index);
    if (!id) return;
    const now = Date.now();
    const lastLongPress = this.lastMaterialLongPress || {};
    if (!e.ignoreLongPressGuard
      && String(lastLongPress.id || '') === String(id)
      && now - Number(lastLongPress.at || 0) < MATERIAL_LONG_PRESS_TAP_SUPPRESS_MS) return;
    if (now - (this.lastMaterialTapAt || 0) < MATERIAL_TAP_GUARD_MS) return;
    this.lastMaterialTapAt = now;
    const material = this.findMaterialById(id);
    if (!material) {
      this.showMaterialQueueToast(this.data.materialsLoading ? '珠材加载中，请稍候' : '材料暂不可用');
      return;
    }
    if (materialIsPendant(material)) {
      this.showMaterialQueueToast('吊坠功能暂未开放');
      return;
    }
    const physical = resolveMaterialGeometry(material);
    if (!physical.specComplete) {
      this.showMaterialQueueToast('该配饰规格待补充，暂不可加入');
      return;
    }
    this.ensureAudioPlayers();
    const currentMaterial = material;
    if (!this.materialOwnImageUrls(currentMaterial).length) {
      this.warmMaterialImagePool(currentMaterial);
      this.showMaterialQueueToast('图库准备中，请稍后再试');
      return;
    }
    if (isBeadCap(currentMaterial)) {
      this.promptBeadCapPlacement(currentMaterial);
      return;
    }
    const pendingCount = this.data.selected.length + this.flightQueue.length;
    if (pendingCount >= MAX_WORKSPACE_BEADS) {
      this.showMaterialQueueToast('珠子已经很多了，先整理一下');
      return;
    }
    const maxQueue = this.isLowPerformanceDevice ? 4 : MAX_MATERIAL_FLIGHT_QUEUE;
    if (this.flightQueue.length >= maxQueue) {
      this.showMaterialQueueToast('慢一点，珠子正在入盘');
      return;
    }
    const queuedPlacements = this.flightQueue.map(task => task.placement);
    const imageUrl = this.consumeNextMaterialImageUrl(currentMaterial);
    const placement = this.createLoosePlacement(
      pendingCount,
      id,
      [...this.data.placements, ...queuedPlacements],
      imageUrl
    );
    if (materialTop(currentMaterial) === 'accessory' && !placement.image_url) {
      this.showMaterialQueueToast('该配饰暂无图库图片，暂不可加入');
      return;
    }
    if (placement.image_url && this.braceletCanvasState) {
      this.getCanvasImage(placement.image_url);
    }
    this.flightQueue.push({
      id,
      cardIndex,
      placement,
      image_url: placement.image_url,
      tapPoint: this.getTapPoint(e),
      // 成串状态下，新珠直接飞入圆环，而不是落进托盘后把整串打散。
      keepStringed: !this.data.isLooseMode
    });
    this.processFlightQueue();
  },

  compatibleBeadCapHostIndices(cap) {
    const selected = this.data.selected || [];
    const placements = this.normalizePlacements(selected, this.data.placements || []);
    return selected.map((id, index) => {
      const material = this.findMaterialById(id) || {};
      const host = { ...placements[index], ...material };
      return beadCapCompatibility(cap, host).compatible ? index : -1;
    }).filter(index => index >= 0);
  },

  promptBeadCapPlacement(cap) {
    const compatibleIndices = this.compatibleBeadCapHostIndices(cap);
    if (!compatibleIndices.length) {
      const physical = resolveMaterialGeometry(cap);
      const target = physical.compatibleBeadSizeMm
        ? `${physical.compatibleBeadSizeMm}mm`
        : '对应珠径';
      this.showMaterialQueueToast(`当前盘面没有适配 ${target} 的圆珠`);
      return;
    }
    const selectedIndex = Number(this.data.selectedBeadIndex);
    const hostIndex = compatibleIndices.includes(selectedIndex)
      ? selectedIndex
      : (compatibleIndices.length === 1 ? compatibleIndices[0] : -1);
    if (hostIndex < 0) {
      this.showMaterialQueueToast('先点选要包裹的主珠');
      return;
    }
    const placement = (this.data.placements || [])[hostIndex] || {};
    const slots = beadCapSlotsFromPlacement(placement);
    const itemList = [
      slots.left ? '替换左侧包珠隔片' : '包左侧',
      slots.right ? '替换右侧包珠隔片' : '包右侧',
      slots.left || slots.right ? '左右两侧都替换' : '左右各装一个'
    ];
    wx.showActionSheet({
      itemList,
      success: result => {
        const sides = result.tapIndex === 0
          ? ['left']
          : (result.tapIndex === 1 ? ['right'] : ['left', 'right']);
        this.attachBeadCapToHost(cap, hostIndex, sides);
      }
    });
  },

  attachBeadCapToHost(material, hostIndex, sides = []) {
    if (!Number.isInteger(hostIndex) || hostIndex < 0 || hostIndex >= this.data.selected.length) return;
    const validSides = Array.from(new Set(sides)).filter(side => side === 'left' || side === 'right');
    if (!validSides.length) return;
    const placements = this.normalizePlacements(this.data.selected, this.data.placements);
    const placement = placements[hostIndex] || {};
    const slots = beadCapSlotsFromPlacement(placement);
    const imageUrl = this.consumeNextMaterialImageUrl(material) || '';
    if (!imageUrl) {
      this.showMaterialQueueToast('该配饰暂无图库图片，暂不可加入');
      return;
    }
    validSides.forEach(side => {
      slots[side] = {
        ...attachmentFromMaterial(material, imageUrl),
        side
      };
    });
    placements[hostIndex] = { ...placement, bead_caps: slots };
    this.pushHistory();
    this.setData({
      placements,
      selectedBeadIndex: hostIndex,
      selectedBeadInfo: null
    }, () => {
      this.recalculate({ persistDelay: 180 });
      wx.showToast({ title: validSides.length === 2 ? '已包裹左右两侧' : '包珠隔片已吸附', icon: 'success' });
    });
  },

  processFlightQueue() {
    this.processCanvasFlightQueue();
  },

  processCanvasFlightQueue() {
    if (this.flightActive || !this.flightQueue.length) return;
    if (!this.braceletCanvasState || !this.flightCanvasState) {
      this.canvasFlightReadyRetries = (this.canvasFlightReadyRetries || 0) + 1;
      if (this.canvasFlightReadyRetries <= 5) {
        this.initWorkspaceCanvases();
        clearTimeout(this.canvasFlightRetryTimer);
        this.canvasFlightRetryTimer = setTimeout(() => {
          this.canvasFlightRetryTimer = null;
          this.processCanvasFlightQueue();
        }, 70);
        return;
      }
      this.canvasFlightReadyRetries = 0;
      this.handleCanvasRendererFailure('workspace flight canvas unavailable');
      return;
    }
    const task = this.flightQueue.shift();
    const material = this.findMaterialById(task.id);
    if (!material) {
      this.processCanvasFlightQueue();
      return;
    }
    this.canvasFlightReadyRetries = 0;
    this.flightActive = true;
    this.armFlightSafetyTimer();
    const circleRect = this.workspaceCircleRect;
    const drawerRect = this.materialDrawerRect;
    const startRect = this.resolveFlightStartRect(null, task.tapPoint, drawerRect, material);
    if (!startRect || !circleRect) {
      this.commitMaterial(task.id, task.placement, {}, () => this.finishCanvasFlight());
      return;
    }
    const layout = this.getStageLayout();
    const logicalSize = layout.center * 2;
    const scale = circleRect.width / logicalSize;
    const startX = startRect.left + startRect.width / 2;
    const startY = startRect.top + startRect.height / 2;
    const target = this.resolveMaterialFlightTarget(task, material, layout);
    const launchPhysics = this.resolveMaterialLaunchPhysics({
      startX,
      startY,
      circleRect,
      target,
      layout,
      scale,
      previousCount: this.data.selected.length
    });
    const beadSize = target.beadSize;
    const launchPlacement = {
      ...task.placement,
      looseX: launchPhysics.x,
      looseY: launchPhysics.y
    };
    const endX = circleRect.left + launchPhysics.x * scale;
    const endY = circleRect.top + launchPhysics.y * scale;
    const controlX = (startX + endX) / 2;
    const controlY = (startY + endY) / 2;
    const sourceSize = Math.max(36, Math.min(76, Math.min(startRect.width, startRect.height)));
    const targetSize = beadSize * scale;
    const flightDuration = this.getMaterialFlightDuration(startX, startY, endX, endY);
    const flightStartDelay = 4;
    const flightMaterial = {
      ...material,
      image_url: task.image_url || material.image_url || ''
    };
    this.physicsTargets = null;
    this.pendingImpactTargets = null;
    this.pendingFrozenImpact = false;
    if (flightMaterial.image_url) this.getCanvasImage(flightMaterial.image_url);
    this.canvasFlight = {
      material: flightMaterial,
      start: { x: startX, y: startY },
      control: { x: controlX, y: controlY },
      end: { x: endX, y: endY },
      path: 'line',
      easing: 'linear',
      trail: false,
      sourceSize,
      targetSize,
      rotation: Number(task.placement.rotation || 0),
      rotationDelta: 0,
      startedAt: Date.now() + flightStartDelay,
      duration: flightDuration
    };
    this.setLaunchingMaterialState(task.id, { canvasFlightActive: true }, () => {
      this.scheduleCanvasRender(true, { markDirty: false });
      this.flightTimer = setTimeout(() => {
        this.commitMaterial(task.id, launchPlacement, launchPhysics, () => this.finishCanvasFlight());
      }, flightStartDelay + flightDuration + 4);
    });
  },

  finishCanvasFlight() {
    clearTimeout(this.flightTimer);
    this.flightTimer = null;
    clearTimeout(this.flightSafetyTimer);
    this.flightSafetyTimer = null;
    this.canvasFlight = null;
    this.clearWorkspaceFlightCanvas();
    this.setLaunchingMaterialState('', { canvasFlightActive: false }, () => {
      this.scheduleCanvasRender();
      this.flightActive = false;
      this.processCanvasFlightQueue();
    });
  },

  buildStringedInsertion(id, placement = {}) {
    const context = this.getStringedRingContext();
    const selected = [...context.selected, id];
    const sourcePlacements = [...context.placements, placement];
    const ringRotation = this.getRingRotationDelta(context.placements, context.geometry);
    const placements = this.rebuildRingPlacementsForVisualSlots(selected, sourcePlacements, ringRotation);
    const materials = this.getCachedSelectedMaterials(selected);
    const items = selected.map((materialId, index) => {
      const material = materials[index] || {};
      const currentPlacement = placements[index] || {};
      const size = Number(material.size || currentPlacement.size || currentPlacement.diameter || 8);
      return {
        ...currentPlacement,
        ...material,
        id: materialId,
        size: Number.isFinite(size) && size > 0 ? size : 8
      };
    });
    const geometry = this.getCachedBraceletGeometry(items);
    return {
      selected,
      placements,
      visualSlots: this.getRingVisualSlots(items, placements, geometry)
    };
  },

  commitMaterial(id, placement, physicsOptions = {}, onReady) {
    const wasLooseMode = this.data.isLooseMode;
    const previousCount = this.data.selected.length;
    this.playMaterialLandingSound(physicsOptions);
    if (!wasLooseMode) {
      const insertion = this.buildStringedInsertion(id, placement || {});
      this.pushHistory();
      this.stopPhysics();
      this.setData({
        selected: insertion.selected,
        placements: insertion.placements,
        isLooseMode: false,
        selectedBeadIndex: -1,
        selectedBeadInfo: null,
        draggingBeadIndex: -1,
        dragDeleteArmed: false
      }, () => {
        this.recalculate({ persistDelay: 520 });
        this.scheduleCanvasRender(true);
        if (onReady) onReady();
      });
      return;
    }
    const existingPlacements = wasLooseMode
      ? this.normalizePlacements(this.data.selected, this.data.placements)
      : this.buildLoosePlacementsFromStringedRing();
    const nextPlacement = placement || this.createLoosePlacement(previousCount, id, existingPlacements);
    const launchVelocity = physicsOptions.velocity;
    const launchAngularVelocity = physicsOptions.angularVelocity;
    if (launchVelocity) {
      this.extendTrayImpactContainment();
    }
    const existingImpactPhysics = {
      billiardDamping: BILLIARD_LINEAR_DAMPING,
      angularDamping: BILLIARD_ANGULAR_DAMPING,
      frictionAir: BILLIARD_FRICTION_AIR,
      restitution: BILLIARD_BEAD_RESTITUTION
    };
    const restingPhysicsOptions = {
      ...physicsOptions,
      velocity: { x: 0, y: 0 },
      angularVelocity: 0
    };
    this.pushHistory();
    this.setData({
      selected: [...this.data.selected, id],
      placements: [...existingPlacements, nextPlacement],
      isLooseMode: true,
      selectedBeadIndex: -1,
      selectedBeadInfo: null,
      draggingBeadIndex: -1,
      dragDeleteArmed: false
    });
    this.recalculate({ persistDelay: 520 });
    this.scheduleCanvasRender();
    this.cancelCanvasFrame(this.pendingPhysicsLaunchFrame);
    this.pendingPhysicsLaunchFrame = this.requestCanvasFrame(() => {
      this.pendingPhysicsLaunchFrame = null;
      wx.nextTick(() => {
      const existingBodiesReady = previousCount === 0
        || (this.physicsBodies || []).length >= previousCount;
      if (!this.physicsEngine || !wasLooseMode || !existingBodiesReady) {
        this.stopPhysics();
        this.createPhysicsEngine();
        this.data.selected.slice(0, previousCount).forEach((materialId, index) => {
          this.createPhysicsBody(materialId, this.data.placements[index], index, {
            ...existingImpactPhysics
          });
        });
      }
      if (Body) {
        (this.physicsBodies || []).forEach(body => {
          if (!body || !body.plugin || body.plugin.designIndex >= previousCount) return;
          body.restitution = BILLIARD_BEAD_RESTITUTION;
          body.friction = BILLIARD_FRICTION;
          body.frictionStatic = BILLIARD_STATIC_FRICTION;
          body.frictionAir = BILLIARD_FRICTION_AIR;
          body.plugin.billiardDamping = BILLIARD_LINEAR_DAMPING;
          body.plugin.angularDamping = BILLIARD_ANGULAR_DAMPING;
          if (Sleeping) Sleeping.set(body, false);
          body.isSleeping = false;
          body.sleepCounter = 0;
          Body.setVelocity(body, { x: 0, y: 0 });
          Body.setAngularVelocity(body, 0);
        });
      }
      const launchedBody = this.createPhysicsBody(
        id,
        this.data.placements[previousCount],
        previousCount,
        {
          ...restingPhysicsOptions,
          isLauncher: true,
          velocity: launchVelocity || restingPhysicsOptions.velocity,
          angularVelocity: launchAngularVelocity || restingPhysicsOptions.angularVelocity,
          billiardDamping: physicsOptions.billiardDamping || BILLIARD_LINEAR_DAMPING,
          angularDamping: physicsOptions.angularDamping || BILLIARD_ANGULAR_DAMPING,
          frictionAir: physicsOptions.frictionAir == null ? BILLIARD_FRICTION_AIR : physicsOptions.frictionAir,
          restitution: physicsOptions.restitution == null ? BILLIARD_BEAD_RESTITUTION : physicsOptions.restitution,
          density: physicsOptions.density == null ? 0.0024 : physicsOptions.density
        }
      );
      this.syncPhysicsFrame(() => {
        wx.nextTick(() => {
          if (launchVelocity) {
            if (Sleeping) Sleeping.set(launchedBody, false);
            launchedBody.isSleeping = false;
            launchedBody.sleepCounter = 0;
            Body.setVelocity(launchedBody, launchVelocity);
          }
          if (launchAngularVelocity) {
            if (Sleeping) Sleeping.set(launchedBody, false);
            launchedBody.isSleeping = false;
            launchedBody.sleepCounter = 0;
            Body.setAngularVelocity(launchedBody, launchAngularVelocity);
          }
          this.runPhysics();
          this.scheduleCanvasRender(true);
          if (onReady) onReady();
        });
      });
      });
    });
  },

  finishFlight() {
    clearTimeout(this.flightTimer);
    this.flightTimer = null;
    clearTimeout(this.flightSafetyTimer);
    this.flightSafetyTimer = null;
    this.setLaunchingMaterialState('', { flightBead: null }, () => {
      this.flightActive = false;
      this.processFlightQueue();
    });
  },

  shuffleDesign() {
    if (this.data.isShuffling || this.data.isStringingFinishing || this.data.isReleasingString) return;
    if (this.flightActive || this.flightQueue.length) {
      wx.showToast({ title: '珠子还在入盘，请稍候', icon: 'none' });
      return;
    }
    if (this.data.selected.length < MIN_STRING_BEAD_COUNT) {
      wx.showToast({ title: `至少选择${MIN_STRING_BEAD_COUNT}颗珠子成串`, icon: 'none' });
      return;
    }
    const pairs = this.data.selected.map((id, index) => ({
      id,
      placement: this.data.placements[index]
    }));
    for (let index = pairs.length - 1; index > 0; index -= 1) {
      const randomIndex = Math.floor(Math.random() * (index + 1));
      [pairs[index], pairs[randomIndex]] = [pairs[randomIndex], pairs[index]];
    }
    if (pairs.every((pair, index) => pair.id === this.data.selected[index])) {
      pairs.push(pairs.shift());
    }
    this.pushHistory();
    const shuffled = pairs.map(pair => pair.id);
    const placements = pairs.map((pair, index) => ({
      ...(pair.placement || this.createLoosePlacement(index, pair.id)),
      rotation: Math.random() < 0.5 ? 0 : 180
    }));
    this.setData({
      selected: shuffled,
      placements: this.normalizePlacements(shuffled, placements),
      selectedBeadIndex: -1,
      selectedBeadInfo: null,
      isShuffling: true,
      isLooseMode: true,
      draggingBeadIndex: -1,
      dragDeleteArmed: false
    });
    this.recalculate();
    this.stringingStartQueued = true;
    wx.nextTick(() => {
      this.stringingStartQueued = false;
      this.startStringingPhysics();
    });
  },

  startStringingPhysics() {
    try {
      this.stringingStartQueued = false;
      this.stopPhysics();
      this.dragState = null;
      this.ringDragState = null;
      this.ringSlideState = null;
      const selected = this.data.selected || [];
      if (!selected.length) {
        this.recoverStringingRuntime();
        return;
      }
      const placements = this.normalizePlacements(selected, this.data.placements);
      const materials = this.getCachedSelectedMaterials(selected);
      const items = selected.map((id, index) => {
        const material = materials[index] || {};
        const placement = placements[index] || {};
        const size = Number(material.size || placement.size || placement.diameter || 8);
        return {
          ...placement,
          ...material,
          id,
          size: Number.isFinite(size) && size > 0 ? size : 8,
          image_url: placement.image_url || material.image_url || ''
        };
      });
      const geometry = this.getCachedBraceletGeometry(items);
      const targets = geometry.angles.map((angle, index) => {
        const physical = (geometry.materialGeometries || [])[index] || resolveMaterialGeometry(items[index] || {});
        const beadSize = geometry.beadSizes[index] || this.getMaterialDisplaySize(selected[index]);
        const offset = stringedMaterialOffset(physical, beadSize / Math.max(1, physical.displaySizeRpx));
        return {
          x: geometry.center + Math.cos(angle) * geometry.radius + offset.x,
          y: geometry.center + Math.sin(angle) * geometry.radius + offset.y,
          rotation: stringedMaterialRotationDeg(angle, physical),
          beadSize
        };
      });
      if (!targets.length || targets.length !== selected.length) {
        this.completeStringing();
        return;
      }
      this.stringingStartedAt = Date.now();
      this.suppressStringingSounds = true;
      const starts = placements.map((placement, index) => ({
        x: Number(placement.looseX || geometry.center),
        y: Number(placement.looseY || geometry.center),
        rotation: Number(placement.rotation || 0),
        beadSize: Number(placement.beadSize || targets[index].beadSize)
      }));
      const duration = this.isLowPerformanceDevice ? STRINGING_LOW_PERF_DURATION : STRINGING_FLIGHT_DURATION;
      const stagger = this.isLowPerformanceDevice ? STRINGING_LOW_PERF_STAGGER_MS : STRINGING_STAGGER_MS;
      const interval = this.isLowPerformanceDevice ? 24 : (this.isRealDevice ? 18 : 16);
      const startedAt = Date.now();
      const totalDuration = duration + Math.max(0, (placements.length - 1) * stagger);
      const finishStringingFrame = () => {
        const finalPlacements = placements.map((placement, index) => ({
          ...placement,
          looseX: targets[index].x,
          looseY: targets[index].y,
          rotation: targets[index].rotation,
          beadSize: targets[index].beadSize
        }));
        this.setLivePlacements(finalPlacements);
        this.setData({
          placements: finalPlacements,
          isLooseMode: false,
          isShuffling: false,
          isStringingFinishing: false,
          isReleasingString: false,
          selectedBeadIndex: -1,
          draggingBeadIndex: -1,
          dragDeleteArmed: false
        }, () => {
          this.suppressStringingSounds = false;
          this.recalculate();
          this.refreshWorkspaceCanvasAfterDesignTransition();
        });
      };
      clearTimeout(this.stringingGuardTimer);
      this.stringingGuardTimer = null;
      clearInterval(this.stringingFinishTimer);
      this.setData({
        isStringingFinishing: true,
        selectedBeadInfo: null,
        draggingBeadIndex: -1,
        dragDeleteArmed: false,
        cartActionText: '去结算'
      });
      this.stringingFinishTimer = setInterval(() => {
        const elapsed = Date.now() - startedAt;
        const nextPlacements = placements.map((placement, index) => {
          const start = starts[index] || {};
          const target = targets[index] || {};
          const progress = Math.max(0, Math.min(1, (elapsed - index * stagger) / duration));
          const eased = 1 - (1 - progress) ** 3;
          return {
            ...placement,
            looseX: start.x + (target.x - start.x) * eased,
            looseY: start.y + (target.y - start.y) * eased,
            rotation: start.rotation + (target.rotation - start.rotation) * eased,
            beadSize: start.beadSize + (target.beadSize - start.beadSize) * eased
          };
        });
        this.setLivePlacements(nextPlacements);
        const isComplete = elapsed >= totalDuration;
        if (isComplete) {
          clearInterval(this.stringingFinishTimer);
          this.stringingFinishTimer = null;
        }
        this.scheduleCanvasRender(true);
        if (isComplete) finishStringingFrame();
      }, interval);
    } catch (error) {
      this.suppressStringingSounds = false;
      this.recoverStringingRuntime();
    }
  },

  removeItem(e) {
    const index = Number(e.currentTarget.dataset.index);
    this.removeItemAt(index);
  },

  removeItemAt(index, options = {}) {
    if (!Number.isInteger(index) || index < 0 || index >= this.data.selected.length) return;
    if (this.data.isReleasingString) return;
    if (options.pushHistory !== false) this.pushHistory();
    const selected = [...this.data.selected];
    const placements = [...this.data.placements];
    selected.splice(index, 1);
    placements.splice(index, 1);
    this.setData({
      selected,
      placements,
      selectedBeadIndex: -1,
      selectedBeadInfo: null,
      draggingBeadIndex: -1,
      dragDeleteArmed: false
    });
    this.recalculate();
    if (this.data.isLooseMode) wx.nextTick(() => this.startPhysicsFromCurrentDesign());
  },

  clearDesign() {
    if (this.data.selected.length) this.pushHistory();
    this.resetWorkspaceRuntime();
    this.resetInteractionData({
      selected: [],
      placements: [],
      attachedPendants: [],
      selectedItems: [],
      attachedPendantItems: [],
      selectedBeadIndex: -1,
      selectedBeadInfo: null,
      isLooseMode: true
    }, () => {
      this.recalculate();
      this.scheduleCanvasRender();
    });
  },

  confirmClearDesign() {
    const busy = this.hasBusyWorkspaceRuntime();
    if (!this.data.selected.length && !busy) {
      wx.showToast({ title: '盘面已经是空的', icon: 'none' });
      return;
    }
    if (!this.data.selected.length && busy) {
      this.clearDesign();
      wx.showToast({ title: '已重置盘面', icon: 'none' });
      return;
    }
    wx.showModal({
      title: '清空盘面',
      content: '确定要清空当前手串设计吗？',
      confirmText: '清空',
      confirmColor: '#7a4e3a',
      success: res => {
        if (res.confirm) {
          this.clearDesign();
        }
      }
    });
  },

  selectBead(e) {
    if (Date.now() < (this.suppressBeadTapUntil || 0)) return;
    const index = Number(e.currentTarget.dataset.index);
    this.showSelectedBeadInfo(index);
  },

  showSelectedBeadInfo(index, selected = this.data.selected, placements = this.data.placements) {
    const beadIndex = Number(index);
    if (!Number.isInteger(beadIndex) || beadIndex < 0) return;
    const updates = {
      selectedBeadIndex: beadIndex,
      selectedBeadInfo: this.buildSelectedBeadInfo(beadIndex, selected, placements)
    };
    (this.data.selectedItems || []).forEach((item, itemIndex) => {
      const isSelected = itemIndex === beadIndex;
      if (item.selected !== isSelected) {
        updates[`selectedItems[${itemIndex}].selected`] = isSelected;
      }
      const classNames = String(item.className || '').split(/\s+/).filter(name => name && name !== 'active');
      if (isSelected) classNames.push('active');
      const nextClassName = classNames.join(' ');
      if (nextClassName !== item.className) {
        updates[`selectedItems[${itemIndex}].className`] = nextClassName;
      }
    });
    this.setData(updates, () => this.scheduleCanvasRender(true));
  },

  closeSelectedBeadInfo() {
    const updates = {
      selectedBeadIndex: -1,
      selectedBeadInfo: null
    };
    (this.data.selectedItems || []).forEach((item, itemIndex) => {
      if (item.selected) updates[`selectedItems[${itemIndex}].selected`] = false;
      const classNames = String(item.className || '').split(/\s+/).filter(name => name && name !== 'active');
      const nextClassName = classNames.join(' ');
      if (nextClassName !== item.className) {
        updates[`selectedItems[${itemIndex}].className`] = nextClassName;
      }
    });
    this.setData(updates, () => this.scheduleCanvasRender(true));
  },

  removeSelectedBeadCap(e) {
    const hostIndex = Number(this.data.selectedBeadIndex);
    const side = e.currentTarget.dataset.side;
    if (!Number.isInteger(hostIndex) || hostIndex < 0 || !['left', 'right'].includes(side)) return;
    const placements = this.normalizePlacements(this.data.selected, this.data.placements);
    const placement = placements[hostIndex] || {};
    const slots = beadCapSlotsFromPlacement(placement);
    if (!slots[side]) return;
    this.pushHistory();
    delete slots[side];
    placements[hostIndex] = { ...placement, bead_caps: slots };
    this.setData({ placements, selectedBeadInfo: null }, () => {
      this.recalculate({ persistDelay: 120 });
      wx.showToast({ title: '已移除包珠隔片', icon: 'none' });
    });
  },

  onBeadTouchStart(e) {
    if (this.data.isShuffling) return;
    const index = Number(e.currentTarget.dataset.index);
    const touch = e.touches && e.touches[0];
    if (!touch || !Number.isInteger(index)) return;
    this.pushHistory();
    if (this.data.isLooseMode) {
      wx.nextTick(() => this.beginBeadDrag(index, touch));
      return;
    }
    wx.nextTick(() => this.beginRingReorder(index, touch));
  },

  getStringedRingContext() {
    const selected = this.data.selected || [];
    const placements = this.normalizePlacements(selected, this.data.placements);
    const materials = this.getCachedSelectedMaterials(selected);
    const items = selected.map((id, index) => {
      const material = materials[index] || {};
      const placement = placements[index] || {};
      const size = Number(material.size || placement.size || placement.diameter || 8);
      return {
        ...placement,
        ...material,
        id,
        size: Number.isFinite(size) && size > 0 ? size : 8
      };
    }).filter(Boolean);
    const geometry = this.getCachedBraceletGeometry(items);
    return { selected, placements, items, geometry };
  },

  buildLoosePlacementsFromStringedRing() {
    const context = this.getStringedRingContext();
    const visualSlots = this.getRingVisualSlots(context.items, context.placements, context.geometry);
    return context.placements.map((placement, index) => {
      const slot = visualSlots[index] || {};
      const looseX = Number.isFinite(Number(slot.x)) ? Number(slot.x) : Number(placement.looseX);
      const looseY = Number.isFinite(Number(slot.y)) ? Number(slot.y) : Number(placement.looseY);
      return {
        ...placement,
        dx: 0,
        dy: 0,
        looseX,
        looseY,
        beadSize: Number(context.geometry.beadSizes[index])
          || Number(placement.beadSize)
          || this.getMaterialDisplaySize(context.selected[index])
      };
    });
  },

  shouldStartRingSlide(hit) {
    if (this.data.isLooseMode || !hit || !hit.point || (this.data.selected || []).length < 3) return false;
    if (hit.index >= 0) return false;
    const context = this.getStringedRingContext();
    return this.isPointInRingSlideBand(hit.point, context.geometry);
  },

  isPointInRingSlideBand(point, geometry) {
    if (!point || !geometry) return false;
    const sizes = geometry.beadSizes || [];
    if (!sizes.length) return false;
    const averageBeadSize = sizes.reduce((sum, size) => sum + size, 0) / sizes.length;
    const dx = point.x - geometry.center;
    const dy = point.y - geometry.center;
    const distance = Math.sqrt(dx * dx + dy * dy);
    return distance >= geometry.radius + averageBeadSize * 0.08
      && distance <= geometry.radius + averageBeadSize * 0.72 + 18;
  },

  beginRingReorder(index, touch, rectOverride = null) {
    const setup = rect => {
      if (!rect) return;
      const context = this.getStringedRingContext();
      const { selected, items, geometry, placements } = context;
      const scale = rect.width / (geometry.center * 2);
      const point = this.touchToTrayPoint(touch, rect, scale);
      const visualSlots = this.getRingVisualSlots(items, placements, geometry);
      this.ringDragState = {
        currentIndex: index,
        originalIndex: index,
        rect,
        scale,
        selected,
        placements,
        items,
        geometry,
        visualSlots,
        moved: false,
        startPoint: point,
        startAngle: Math.atan2(point.y - geometry.center, point.x - geometry.center),
        dragAngle: (visualSlots[index] || {}).angle,
        draggingX: null,
        draggingY: null,
        beadSize: geometry.beadSizes[index] || 54
      };
      this.setData({
        draggingBeadIndex: index,
        selectedBeadIndex: index,
        selectedBeadInfo: this.buildSelectedBeadInfo(index),
        dragDeleteArmed: false
      });
      this.scheduleCanvasRender(true);
    };
    if (rectOverride) {
      setup(rectOverride);
      return;
    }
    const query = wx.createSelectorQuery().in(this);
    query.select('.bracelet-circle').boundingClientRect();
    query.exec(rects => setup(rects && rects[0]));
  },

  beginRingSlide(touch, rectOverride = null, options = {}) {
    const setup = rect => {
      if (!rect) return;
      const context = this.getStringedRingContext();
      if (!context.items.length) return;
      const scale = rect.width / (context.geometry.center * 2);
      const point = this.touchToTrayPoint(touch, rect, scale);
      const angle = Math.atan2(point.y - context.geometry.center, point.x - context.geometry.center);
      this.ringSlideState = {
        rect,
        scale,
        basePlacements: context.placements,
        items: context.items,
        geometry: context.geometry,
        originIndex: Number.isInteger(options.originIndex) ? options.originIndex : -1,
        lastAngle: angle,
        totalDelta: 0,
        moved: false
      };
      this.setData({
        draggingBeadIndex: -1,
        selectedBeadIndex: -1,
        selectedBeadInfo: null,
        dragDeleteArmed: false
      });
      this.scheduleCanvasRender(true);
    };
    if (rectOverride) {
      setup(rectOverride);
      return;
    }
    const query = wx.createSelectorQuery().in(this);
    query.select('.bracelet-circle').boundingClientRect();
    query.exec(rects => setup(rects && rects[0]));
  },

  normalizeAngleDelta(delta) {
    let value = Number(delta) || 0;
    while (value > Math.PI) value -= Math.PI * 2;
    while (value < -Math.PI) value += Math.PI * 2;
    return value;
  },

  buildRingSlidePlacements(basePlacements, angleDelta, geometryOverride = null) {
    const geometry = geometryOverride || this.getStringedRingContext().geometry;
    const cos = Math.cos(angleDelta);
    const sin = Math.sin(angleDelta);
    return (basePlacements || []).map((placement, index) => {
      const angle = geometry.angles[index] || 0;
      const baseX = geometry.center + Math.cos(angle) * geometry.radius;
      const baseY = geometry.center + Math.sin(angle) * geometry.radius;
      const currentX = baseX + Number(placement.dx || 0);
      const currentY = baseY + Number(placement.dy || 0);
      const relX = currentX - geometry.center;
      const relY = currentY - geometry.center;
      const rotatedX = geometry.center + relX * cos - relY * sin;
      const rotatedY = geometry.center + relX * sin + relY * cos;
      return {
        ...placement,
        dx: rotatedX - baseX,
        dy: rotatedY - baseY
      };
    });
  },

  getRingVisualSlots(items = [], placements = [], geometry) {
    if (!geometry) return [];
    const center = geometry.center;
    const count = Math.max(
      (items && items.length) || 0,
      (placements && placements.length) || 0,
      (geometry.angles && geometry.angles.length) || 0
    );
    return Array.from({ length: count }).map((_, index) => {
      const angle = geometry.angles[index] || 0;
      const placement = placements[index] || {};
      const physical = (geometry.materialGeometries || [])[index]
        || resolveMaterialGeometry((items || [])[index] || {});
      const beadSize = (geometry.beadSizes || [])[index] || physical.displaySizeRpx;
      const offset = stringedMaterialOffset(physical, beadSize / Math.max(1, physical.displaySizeRpx));
      const x = center + Math.cos(angle) * geometry.radius + offset.x + Number(placement.dx || 0);
      const y = center + Math.sin(angle) * geometry.radius + offset.y + Number(placement.dy || 0);
      return {
        x,
        y,
        angle
      };
    });
  },

  getRingRotationDelta(placements = [], geometry = {}) {
    const center = Number(geometry.center);
    const radius = Number(geometry.radius);
    const angles = geometry.angles || [];
    if (!Number.isFinite(center) || !Number.isFinite(radius) || radius <= 0) return 0;
    const deltas = placements.map((placement, index) => {
      const angle = Number(angles[index]);
      if (!Number.isFinite(angle)) return null;
      const baseX = center + Math.cos(angle) * radius;
      const baseY = center + Math.sin(angle) * radius;
      const x = baseX + Number(placement && placement.dx || 0);
      const y = baseY + Number(placement && placement.dy || 0);
      if (Math.hypot(x - center, y - center) < radius * 0.25) return null;
      return this.normalizeAngleDelta(Math.atan2(y - center, x - center) - angle);
    }).filter(value => Number.isFinite(value));
    if (!deltas.length) return 0;
    const sin = deltas.reduce((sum, value) => sum + Math.sin(value), 0);
    const cos = deltas.reduce((sum, value) => sum + Math.cos(value), 0);
    const delta = Math.atan2(sin, cos);
    // A previous bad reorder can leave item-specific offsets behind.  Only
    // retain offsets when they describe one coherent whole-ring rotation.
    const coherence = Math.hypot(sin, cos) / deltas.length;
    return coherence >= 0.96 ? delta : 0;
  },

  rebuildRingPlacementsForVisualSlots(selected, sourcePlacements, ringRotation = 0) {
    const normalized = this.normalizePlacements(selected, sourcePlacements);
    const materials = this.getCachedSelectedMaterials(selected);
    const items = selected.map((id, index) => {
      const material = materials[index] || {};
      const placement = normalized[index] || {};
      const size = Number(material.size || placement.size || placement.diameter || 8);
      return {
        ...placement,
        ...material,
        id,
        size: Number.isFinite(size) && size > 0 ? size : 8
      };
    }).filter(Boolean);
    const geometry = this.getCachedBraceletGeometry(items);
    const safeRingRotation = Number.isFinite(Number(ringRotation)) ? Number(ringRotation) : 0;
    return normalized.map((placement, index) => {
      const angle = geometry.angles[index] || 0;
      const baseX = geometry.center + Math.cos(angle) * geometry.radius;
      const baseY = geometry.center + Math.sin(angle) * geometry.radius;
      const visualX = geometry.center + Math.cos(angle + safeRingRotation) * geometry.radius;
      const visualY = geometry.center + Math.sin(angle + safeRingRotation) * geometry.radius;
      return {
        ...placement,
        dx: visualX - baseX,
        dy: visualY - baseY,
        looseX: visualX,
        looseY: visualY,
        beadSize: geometry.beadSizes[index] || placement.beadSize || this.getMaterialDisplaySize(selected[index])
      };
    });
  },

  beginBeadDrag(index, touch, rectOverride = null) {
    const setup = rect => {
      const body = this.physicsBodies.find(item => item.plugin.designIndex === index);
      if (!rect || !body) return;
      const layout = this.getStageLayout();
      const scale = rect.width / (layout.center * 2);
      const point = this.touchToTrayPoint(touch, rect, scale);
      clearTimeout(this.dragPhysicsSyncTimer);
      this.dragPhysicsSyncTimer = null;
      this.lastDragPhysicsSyncAt = Date.now();
      Body.setStatic(body, true);
      Body.setPosition(body, point);
      this.dragState = {
        index,
        body,
        rect,
        scale,
        layout,
        lastPoint: point,
        lastAt: Date.now(),
        velocity: { x: 0, y: 0 },
        angularVelocity: 0,
        moved: false
      };
      this.setData({
        draggingBeadIndex: index,
        selectedBeadIndex: index,
        selectedBeadInfo: this.buildSelectedBeadInfo(index),
        dragDeleteArmed: this.isPointOutsideTray(point, body.plugin.beadSize, layout)
      });
      this.syncPhysicsFrame();
    };
    if (rectOverride) {
      setup(rectOverride);
      return;
    }
    const query = wx.createSelectorQuery().in(this);
    query.select('.bracelet-circle').boundingClientRect();
    query.exec(rects => setup(rects && rects[0]));
  },

  onBeadTouchMove(e) {
    if (this.ringSlideState) {
      this.onRingSlideMove(e);
      return;
    }
    if (this.ringDragState) {
      this.onRingReorderMove(e);
      return;
    }
    const state = this.dragState;
    const touch = e.touches && e.touches[0];
    if (!state || !touch) return;
    const point = this.touchToTrayPoint(touch, state.rect, state.scale);
    const now = Date.now();
    const elapsed = Math.max(8, now - state.lastAt);
    const deltaX = point.x - state.lastPoint.x;
    const deltaY = point.y - state.lastPoint.y;
    state.velocity = {
      x: Math.max(-5, Math.min(5, deltaX / elapsed * 15)),
      y: Math.max(-5, Math.min(5, deltaY / elapsed * 15))
    };
    const bodyRadius = Number(state.body.plugin && (state.body.plugin.bodyRadius || state.body.plugin.beadSize * 0.5)) || 24;
    const dragSpin = (deltaX - deltaY * 0.28) / Math.max(14, bodyRadius) * DRAG_ROLLING_SPIN_FACTOR;
    if (Math.abs(dragSpin) > 0.0008) {
      Body.setAngle(state.body, state.body.angle + dragSpin);
      state.angularVelocity = this.clampAngularVelocity(dragSpin * Math.min(2.2, 18 / elapsed), 0.13);
    }
    state.lastPoint = point;
    state.lastAt = now;
    state.moved = true;
    Body.setPosition(state.body, point);
    const outside = this.isPointOutsideTray(point, state.body.plugin.beadSize, state.layout);
    if (outside !== this.data.dragDeleteArmed) {
      this.setData({ dragDeleteArmed: outside });
    }
    this.scheduleDragPhysicsFrame();
  },

  onRingSlideMove(e) {
    const state = this.ringSlideState;
    const touch = e.touches && e.touches[0];
    if (!state || !touch) return;
    const geometry = state.geometry || this.getStringedRingContext().geometry;
    const point = this.touchToTrayPoint(touch, state.rect, state.scale);
    const angle = Math.atan2(point.y - geometry.center, point.x - geometry.center);
    const delta = this.normalizeAngleDelta(angle - state.lastAngle);
    state.lastAngle = angle;
    state.totalDelta += delta;
    if (Math.abs(state.totalDelta) > RING_SLIDE_MIN_MOVE_RAD) state.moved = true;
    const placements = this.buildRingSlidePlacements(state.basePlacements, state.totalDelta, geometry);
    this.setLivePlacements(placements);
    this.scheduleCanvasRender(true);
  },

  onRingReorderMove(e) {
    const state = this.ringDragState;
    const touch = e.touches && e.touches[0];
    if (!state || !touch) return;
    const currentSelected = state.selected || this.data.selected || [];
    const currentPlacements = state.placements || this.data.placements || [];
    const items = state.items || [];
    const geometry = state.geometry || this.getStringedRingContext().geometry;
    const currentItem = items[state.currentIndex];
    if (!currentItem) return;
    const point = this.touchToTrayPoint(touch, state.rect, state.scale);
    const visualSlots = state.visualSlots || this.getRingVisualSlots(items, currentPlacements, geometry);
    const dx = point.x - geometry.center;
    const dy = point.y - geometry.center;
    const distanceFromCenter = Math.sqrt(dx ** 2 + dy ** 2);
    const stableAngleDistance = Math.max(
      geometry.radius * RING_REORDER_CENTER_DEAD_ZONE_RATIO,
      (geometry.beadSizes[state.currentIndex] || 54) * 0.75
    );
    if (distanceFromCenter >= stableAngleDistance) {
      state.dragAngle = Math.atan2(dy, dx);
    } else if (!Number.isFinite(state.dragAngle)) {
      state.dragAngle = geometry.angles[state.currentIndex] || 0;
    }
    const projected = {
      x: geometry.center + Math.cos(state.dragAngle) * geometry.radius,
      y: geometry.center + Math.sin(state.dragAngle) * geometry.radius
    };
    const outside = this.isPointOutsideTray(point, currentItem.size * 5.4, geometry);
    if (outside !== this.data.dragDeleteArmed) {
      this.setData({ dragDeleteArmed: outside });
    }
    state.moved = true;
    state.deleteArmed = outside;
    state.draggingX = outside ? point.x : projected.x;
    state.draggingY = outside ? point.y : projected.y;
    this.patchRingDraggingBeadPosition(state);
    if (outside) return;
    if (currentSelected.length < 2) return;
    let targetIndex = state.currentIndex;
    let nearestDistance = Infinity;
    visualSlots.forEach((slot, index) => {
      const targetX = Number.isFinite(slot.x) ? slot.x : geometry.center;
      const targetY = Number.isFinite(slot.y) ? slot.y : geometry.center;
      const distance = (projected.x - targetX) ** 2 + (projected.y - targetY) ** 2;
      if (distance < nearestDistance) {
        nearestDistance = distance;
        targetIndex = index;
      }
    });
    if (targetIndex === state.currentIndex) return;
    const ringRotation = this.getRingRotationDelta(currentPlacements, geometry);
    const selected = [...currentSelected];
    const itemPlacements = [...currentPlacements];
    const nextItems = [...items];
    const [selectedItem] = selected.splice(state.currentIndex, 1);
    const [placementItem] = itemPlacements.splice(state.currentIndex, 1);
    const [item] = nextItems.splice(state.currentIndex, 1);
    selected.splice(targetIndex, 0, selectedItem);
    itemPlacements.splice(targetIndex, 0, placementItem);
    nextItems.splice(targetIndex, 0, item);
    const placements = this.rebuildRingPlacementsForVisualSlots(selected, itemPlacements, ringRotation);
    const nextGeometry = this.getCachedBraceletGeometry(nextItems);
    const nextVisualSlots = this.getRingVisualSlots(nextItems, placements, nextGeometry);
    state.currentIndex = targetIndex;
    state.selected = selected;
    state.placements = placements;
    state.items = nextItems;
    state.geometry = nextGeometry;
    state.visualSlots = nextVisualSlots;
    state.beadSize = nextGeometry.beadSizes[targetIndex] || state.beadSize || 54;
    state.moved = true;
    this.setData({
      selected,
      placements,
      draggingBeadIndex: targetIndex,
      selectedBeadIndex: targetIndex,
      selectedBeadInfo: this.buildSelectedBeadInfo(targetIndex, selected, placements)
    });
    this.recalculate({ persist: false });
    wx.nextTick(() => this.patchRingDraggingBeadPosition(state));
  },

  patchRingDraggingBeadPosition(state) {
    if (!state || state.currentIndex == null || state.draggingX == null || state.draggingY == null) return;
    this.scheduleCanvasRender(true);
  },

  onBeadTouchEnd() {
    if (this.ringSlideState) {
      const state = this.ringSlideState;
      this.ringSlideState = null;
      if (state.moved) this.suppressBeadTapUntil = Date.now() + 320;
      const placements = state.moved
        ? this.buildRingSlidePlacements(state.basePlacements, state.totalDelta)
        : state.basePlacements;
      this.clearLivePlacements();
      this.setData({
        placements,
        draggingBeadIndex: -1,
        dragDeleteArmed: false
      }, () => {
        if (!state.moved && state.originIndex >= 0) {
          this.showSelectedBeadInfo(state.originIndex);
          return;
        }
        if (state.moved) {
          this.recalculate({ persist: false });
          this.scheduleDraftPersistence();
        } else {
          this.scheduleCanvasRender(true);
        }
      });
      return;
    }
    if (this.ringDragState) {
      const state = this.ringDragState;
      this.ringDragState = null;
      const shouldDelete = this.data.dragDeleteArmed;
      if (state.moved) this.suppressBeadTapUntil = Date.now() + 320;
      this.setData({
        draggingBeadIndex: -1,
        dragDeleteArmed: false
      });
      if (!state.moved) {
        this.showSelectedBeadInfo(state.currentIndex);
        return;
      }
      if (shouldDelete) {
        this.removeItemAt(state.currentIndex, { pushHistory: false });
        wx.showToast({ title: '已移出圆盘', icon: 'none' });
        return;
      }
      if (state.moved) {
        this.recalculate({ persist: false });
        this.scheduleDraftPersistence();
      }
      return;
    }
    const state = this.dragState;
    if (!state) return;
    const shouldDelete = this.data.dragDeleteArmed;
    if (state.moved) this.suppressBeadTapUntil = Date.now() + 320;
    this.dragState = null;
    if (!state.moved) {
      Body.setStatic(state.body, false);
      this.setData({ draggingBeadIndex: -1, dragDeleteArmed: false }, () => {
        this.showSelectedBeadInfo(state.index);
      });
      this.runPhysics();
      return;
    }
    if (shouldDelete) {
      clearTimeout(this.dragPhysicsSyncTimer);
      this.dragPhysicsSyncTimer = null;
      Composite.remove(this.physicsEngine.world, state.body);
      this.physicsBodies = this.physicsBodies.filter(body => body !== state.body);
      this.removeItemAt(state.index, { pushHistory: false });
      wx.showToast({ title: '已移出圆盘', icon: 'none' });
      return;
    }
    Body.setStatic(state.body, false);
    Body.setVelocity(state.body, state.velocity);
    Body.setAngularVelocity(state.body, this.clampAngularVelocity(state.angularVelocity || state.body.angularVelocity || 0, 0.13));
    this.setData({ draggingBeadIndex: -1, dragDeleteArmed: false });
    this.scheduleDragPhysicsFrame(true, () => {
      this.scheduleDraftPersistence();
    });
    this.runPhysics();
  },

  touchToTrayPoint(touch, rect, scale) {
    const clientX = Number(touch.clientX == null ? touch.pageX : touch.clientX);
    const clientY = Number(touch.clientY == null ? touch.pageY : touch.clientY);
    return {
      x: (clientX - rect.left) / scale,
      y: (clientY - rect.top) / scale
    };
  },

  isPointOutsideTray(point, beadSize, layout = this.getStageLayout()) {
    const distance = Math.sqrt(
      (point.x - layout.center) ** 2 + (point.y - layout.center) ** 2
    );
    return distance > layout.center - Math.max(10, Number(beadSize) * 0.18);
  },

  nudgeSelected(e) {
    this.moveSelectedOrder(e);
  },

  moveSelectedOrder(e) {
    const index = this.data.selectedBeadIndex;
    const direction = Number(e.currentTarget.dataset.direction);
    const nextIndex = index + direction;
    if (index < 0) {
      wx.showToast({ title: '先点选一颗珠子', icon: 'none' });
      return;
    }
    if (nextIndex < 0 || nextIndex >= this.data.selected.length) {
      wx.showToast({ title: '已经到边界了', icon: 'none' });
      return;
    }
    const context = this.getStringedRingContext();
    const ringRotation = this.data.isLooseMode
      ? 0
      : this.getRingRotationDelta(context.placements, context.geometry);
    const selected = [...this.data.selected];
    const placements = this.data.isLooseMode
      ? this.normalizePlacements(selected, this.data.placements)
      : [...context.placements];
    const selectedItem = selected[index];
    const placementItem = placements[index];
    selected[index] = selected[nextIndex];
    selected[nextIndex] = selectedItem;
    placements[index] = placements[nextIndex];
    placements[nextIndex] = placementItem;
    const nextPlacements = this.data.isLooseMode
      ? placements
      : this.rebuildRingPlacementsForVisualSlots(selected, placements, ringRotation);
    this.pushHistory();
    this.setData({
      selected,
      placements: nextPlacements,
      selectedBeadIndex: nextIndex,
      selectedBeadInfo: this.buildSelectedBeadInfo(nextIndex, selected, nextPlacements)
    });
    this.recalculate();
  },

  recalculate(options = {}) {
    const placements = this.normalizePlacements(this.data.selected, this.data.placements);
    const safeSelectedBeadIndex = this.data.selectedBeadIndex >= 0 && this.data.selectedBeadIndex < this.data.selected.length
      ? this.data.selectedBeadIndex
      : -1;
    const materials = this.getCachedSelectedMaterials(this.data.selected);
    const items = this.data.selected.map((id, index) => {
      const material = materials[index];
      const placement = placements[index] || {};
      if (!material && !(placement.name || placement.image_url || placement.size || placement.diameter)) return null;
      const size = Number((material && material.size) || placement.size || placement.diameter || placement.size_mm || 8);
      return {
        ...(material || {}),
        ...placement,
        id,
        size: Number.isFinite(size) && size > 0 ? size : 8,
        price: Number((material && material.price) || placement.price || placement.priceText || 0),
        weight: Number((material && material.weight) || placement.weight || 0),
        image_url: placement.image_url || (material && material.image_url) || ''
      };
    }).filter(Boolean);
    const attachedPendants = beadCapItemsFromPlacements(placements);
    const summaryMetrics = this.getCachedWorkspaceSummary(items, attachedPendants);
    const { summary, length } = summaryMetrics;
    const braceletGeometry = this.getCachedBraceletGeometry(items);
    const stringStyle = this.buildStringStyle(braceletGeometry);
    _energySvgCache = '';
    var energyChartSvgUrl = '';
    const actionState = this.buildActionState(items.length);
    const updates = {
      summary,
      stringStyle,
      placements,
      attachedPendants,
      countOverClass: items.length > Number(summary.maxBeadCount || MAX_RECOMMENDED_RECIPE_BEADS) ? 'over' : '',
      lengthOverClass: items.length && summary.warning !== '合适' ? 'over-length' : '',
      braceletStringClass: items.length ? 'has-beads' : 'empty',
      completionWatermarkClass: items.length ? 'has-beads' : '',
      wearStyle: 'single',
      selectedBeadIndex: safeSelectedBeadIndex,
      selectedBeadInfo: this.buildSelectedBeadInfo(safeSelectedBeadIndex, this.data.selected, placements),
      wristOptionItems: this.getCachedWristOptionItems(),
      workspacePlanLabel: this.workspaceSourceLabel(this.data.sourceContext || this.sourceContext || {}),
      ...actionState,
      energyChartSvgUrl
    };
    this.setLivePlacements(placements);
    updates.selectedItems = [];
    updates.attachedPendantItems = attachedPendants;
    this.setData(updates, () => this.scheduleCanvasRender());
    if (options.persist !== false) this.scheduleDraftPersistence(options.persistDelay);
  },

  formatBeadDiameter(size) {
    const numeric = Number(size);
    if (!Number.isFinite(numeric) || numeric <= 0) return '--';
    const text = Number.isInteger(numeric) ? String(numeric) : numeric.toFixed(1).replace(/\.0$/, '');
    return `${text}mm`;
  },

  displayMaterialName(material = {}, fallback = '') {
    const candidates = [
      material.display_name,
      material.material_name,
      material.materialName,
      material.sku && material.sku.name,
      material.name,
      material.series,
      material.category,
      fallback
    ];
    for (let index = 0; index < candidates.length; index += 1) {
      const text = repairMaybeMojibakeText(candidates[index]);
      if (text && !/^mat[_-]?\d+/i.test(text) && !/^\d{10,}$/.test(text) && !/\u672a\u547d\u540d/.test(text)) return text;
    }
    return '\u5b9a\u5236\u73e0\u6750';
  },

  buildSelectedBeadInfo(index, selected = this.data.selected, placements = this.data.placements) {
    const beadIndex = Number(index);
    if (!Number.isInteger(beadIndex) || beadIndex < 0 || beadIndex >= (selected || []).length) return null;
    const id = selected[beadIndex];
    const placement = (placements || [])[beadIndex] || {};
    const beadCaps = beadCapSlotsFromPlacement(placement);
    const cacheKey = [
      this.materialCatalogDesignVersion || 0,
      beadIndex,
      id,
      placement.image_url || '',
      placement.size || placement.size_mm || placement.diameter || '',
      placement.price || placement.priceText || '',
      placement.name || '',
      beadCaps.left && `${beadCaps.left.id}:${beadCaps.left.price}` || '',
      beadCaps.right && `${beadCaps.right.id}:${beadCaps.right.price}` || '',
    ].join('::');
    if (this.selectedBeadInfoCache && this.selectedBeadInfoCache.key === cacheKey) {
      return this.selectedBeadInfoCache.value;
    }
    const material = this.findMaterialById(id) || {};
    const source = {
      ...placement,
      ...material
    };
    const name = this.displayMaterialName(source, id);
    const diameter = source.size || source.size_mm || source.diameter || (source.sku && source.sku.size_mm) || '';
    const price = Number(source.price || 0);
    const priceText = Number.isFinite(price) && price > 0 ? `¥${price.toFixed(2).replace(/\.00$/, '')}` : '--';
    const capItems = ['left', 'right'].map(side => {
      const cap = beadCaps[side];
      if (!cap) return null;
      const capPrice = Number(cap.price || 0);
      return {
        side,
        sideLabel: side === 'left' ? '左侧' : '右侧',
        name: this.displayMaterialName(cap, '包珠隔片'),
        priceText: capPrice > 0 ? `¥${capPrice.toFixed(2).replace(/\.00$/, '')}` : '--'
      };
    }).filter(Boolean);
    const info = {
      index: beadIndex,
      position: beadIndex + 1,
      id,
      name,
      diameterText: this.formatBeadDiameter(diameter),
      priceText,
      capItems
    };
    this.selectedBeadInfoCache = { key: cacheKey, value: info };
    return info;
  },

  buildDraftPersistencePayload(existingDesign = {}) {
    const now = Date.now();
    return {
      designId: existingDesign.designId || existingDesign.design_id || '',
      design_id: existingDesign.designId || existingDesign.design_id || '',
      name: existingDesign.name || existingDesign.title || '',
      title: existingDesign.title || existingDesign.name || '',
      userId: existingDesign.userId || '',
      selected: this.data.selected,
      placements: this.data.placements,
      attachedPendants: [],
      wristSize: this.data.wristSize,
      wearStyle: 'single',
      isLooseMode: this.data.isLooseMode,
      sourceContext: this.data.sourceContext || this.sourceContext || existingDesign.sourceContext || null,
      createdAt: existingDesign.createdAt || now,
      updatedAt: now,
      summary: this.data.summary
    };
  },

  draftPersistenceSignature(payload = {}) {
    try {
      const compactPlacements = (payload.placements || []).map(placement => ({
        x: Number(Number(placement && placement.looseX).toFixed(2)) || 0,
        y: Number(Number(placement && placement.looseY).toFixed(2)) || 0,
        dx: Number(Number(placement && placement.dx).toFixed(2)) || 0,
        dy: Number(Number(placement && placement.dy).toFixed(2)) || 0,
        r: Number(Number(placement && placement.rotation).toFixed(2)) || 0,
        s: Number(Number(placement && placement.beadSize).toFixed(2)) || 0,
        size: Number(Number(placement && (placement.size || placement.size_mm || placement.diameter)).toFixed(2)) || 0,
        price: Number(Number(placement && (placement.price || placement.priceText)).toFixed(2)) || 0,
        img: placement && placement.image_url || '',
        name: placement && placement.name || '',
        caps: ['left', 'right'].map(side => {
          const cap = beadCapSlotsFromPlacement(placement)[side];
          return cap ? `${side}:${cap.id || cap.skuId || ''}:${cap.price || 0}` : '';
        }).filter(Boolean).join('|')
      }));
      const summary = payload.summary || {};
      return JSON.stringify({
        designId: payload.designId || payload.design_id || '',
        name: payload.name || payload.title || '',
        userId: payload.userId || '',
        selected: payload.selected || [],
        placements: compactPlacements,
        wristSize: Number(Number(payload.wristSize).toFixed(2)) || 0,
        isLooseMode: !!payload.isLooseMode,
        sourceContext: payload.sourceContext || null,
        summary: {
          count: Number(summary.count) || 0,
          priceText: summary.priceText || '',
          length: summary.length || '',
          currentWrist: summary.currentWrist || '',
          warning: summary.warning || ''
        }
      });
    } catch (error) {
      return '';
    }
  },

  scheduleDraftPersistence(delayMs) {
    clearTimeout(this.persistDraftTimer);
    const delay = Number(delayMs == null
      ? (this.flightActive || (this.flightQueue && this.flightQueue.length) ? 420 : 140)
      : delayMs);
    this.persistDraftTimer = setTimeout(() => {
      this.persistDraftTimer = null;
      const existingDesign = wx.getStorageSync('currentDesign') || {};
      const data = this.buildDraftPersistencePayload(existingDesign);
      const signature = this.draftPersistenceSignature(data);
      if (signature && signature === this.lastPersistedDraftSignature) return;
      this.lastPersistedDraftSignature = signature;
      wx.setStorage({
        key: 'currentDesign',
        data
      });
    }, Math.max(80, delay));
  },

  calculateBraceletGeometry(items) {
    const layout = this.getStageLayout();
    const center = layout.center;
    const materialGeometries = items.map(item => resolveMaterialGeometry(item));
    let beadSizes = materialGeometries.map(item => item.displaySizeRpx);
    let spacingSizes = materialGeometries.map(item => item.spacingSizeRpx);
    const largestBeadRadius = beadSizes.length ? Math.max(...beadSizes) / 2 : 0;
    const safeOuterRadius = Math.max(
      largestBeadRadius + 8,
      Math.min(center - 25, this.getTrayPhysicsRadius(layout) - 12)
    );
    if (items.length < 3) {
      const count = Math.max(items.length, 1);
      return {
        center,
        radius: Math.max(0, safeOuterRadius - largestBeadRadius),
        beadSizes,
        spacingSizes,
        materialGeometries,
        angles: items.map((item, index) => (-90 + (360 / count) * index) * Math.PI / 180)
      };
    }

    let radius = this.solveTangentRingRadius(spacingSizes);
    // 物理盘壁的内缘约为 center - 22rpx；额外留 3rpx 安全间距，
    // 避免成串目标与静态盘壁重叠，造成弹簧和碰撞墙持续对抗。
    const maxOuterRadius = safeOuterRadius;
    if (radius + largestBeadRadius > maxOuterRadius) {
      const scale = maxOuterRadius / (radius + largestBeadRadius);
      beadSizes = beadSizes.map(size => size * scale);
      spacingSizes = spacingSizes.map(size => size * scale);
      radius = this.solveTangentRingRadius(spacingSizes);
    }

    const angles = [-Math.PI / 2];
    for (let index = 1; index < spacingSizes.length; index += 1) {
      const centerDistance = (spacingSizes[index - 1] + spacingSizes[index]) / 2 + STRINGED_BEAD_GAP_RPX;
      const step = 2 * Math.asin(Math.min(1, centerDistance / (2 * radius)));
      angles.push(angles[index - 1] + step);
    }
    return { center, radius, beadSizes, spacingSizes, materialGeometries, angles };
  },

  solveTangentRingRadius(beadSizes) {
    const centerDistances = beadSizes.map((size, index) => {
      const nextSize = beadSizes[(index + 1) % beadSizes.length];
      return (size + nextSize) / 2 + STRINGED_BEAD_GAP_RPX;
    });
    let low = Math.max(...centerDistances) / 2 + 0.01;
    let high = Math.max(600, beadSizes.reduce((sum, size) => sum + size, 0));
    for (let iteration = 0; iteration < 48; iteration += 1) {
      const radius = (low + high) / 2;
      const angleSum = centerDistances.reduce((sum, distance) => {
        return sum + 2 * Math.asin(Math.min(1, distance / (2 * radius)));
      }, 0);
      if (angleSum > Math.PI * 2) {
        low = radius;
      } else {
        high = radius;
      }
    }
    return (low + high) / 2;
  },

  buildStringStyle(geometry) {
    const diameter = geometry.radius * 2;
    const offset = geometry.center - geometry.radius;
    return `left:${offset}rpx;top:${offset}rpx;width:${diameter}rpx;height:${diameter}rpx;`;
  },

  workspaceSummaryCacheKey(items = [], attachments = []) {
    const wristSize = Number(this.data.wristSize || 16);
    const sourceContext = this.data.sourceContext || this.sourceContext || {};
    const recommendationValidation = sourceContext.recommendation_validation || {};
    const itemKey = (items || []).map(item => [
      item.id,
      item.skuId,
      item.sku_id,
      item.material_code,
      item.size,
      item.price,
      item.weight,
      item.top,
      item.item_type,
      item.type,
      item.element_key,
      item.primary_element,
      item.element,
      item.name,
      item.category,
      item.series,
      Array.isArray(item.effects) ? item.effects.join('|') : item.effects
    ].map(value => String(value || '').trim()).join('~')).join('||');
    const attachmentKey = (attachments || []).map(item => [
      item.id,
      item.skuId,
      item.price,
      item.weight,
      item.side
    ].map(value => String(value || '').trim()).join('~')).join('||');
    return [
      this.materialCatalogDesignVersion || 0,
      wristSize,
      sourceContext.source || '',
      sourceContext.target_bead_count || '',
      recommendationValidation.estimated_stringed_length_cm || '',
      itemKey,
      attachmentKey
    ].join('::');
  },

  getCachedWorkspaceSummary(items = [], attachments = []) {
    const key = this.workspaceSummaryCacheKey(items, attachments);
    if (this.workspaceSummaryCache && this.workspaceSummaryCache.key === key) {
      return this.workspaceSummaryCache.value;
    }
    const price = [...items, ...attachments].reduce((sum, item) => sum + Number(item.price || 0), 0);
    const effectiveLengthMm = estimateStringedLengthMm(items);
    const length = effectiveLengthMm / 10;
    const roundedLength = Number(length.toFixed(1));
    const weight = [...items, ...attachments].reduce((sum, item) => sum + Number(item.weight || 0), 0);
    const wristSize = Number(this.data.wristSize || 16);
    const targetLength = wristSize + 0.8;
    const sourceContext = this.data.sourceContext || this.sourceContext || {};
    const recommendationValidation = sourceContext.recommendation_validation || {};
    const recommendationTargetCount = Number(sourceContext.target_bead_count || 0);
    const recommendedCount = this.isRecommendationWorkspaceSource() && recommendationTargetCount > 0
      ? recommendationTargetCount
      : recommendedStringedBeadCount(items, wristSize);
    const maxBeadCount = Math.min(MAX_WORKSPACE_BEADS, recommendedCount + 1);
    const warning = items.length === 0
      ? ''
      : roundedLength > targetLength + 0.5 + 1e-6
        ? '\u504f\u957f'
        : roundedLength < targetLength - 0.5 - 1e-6
          ? '\u504f\u77ed'
          : '\u5408\u9002';
    const counts = {};
    let energyItemCount = 0;
    items.forEach(item => {
      const elementKey = this.materialElementKey(item);
      if (!elementKey) return;
      energyItemCount += 1;
      counts[elementKey] = (counts[elementKey] || 0) + 1;
    });
    const energy = ELEMENTS.map(element => ({
      ...element,
      value: energyItemCount ? Math.round(((counts[element.key] || 0) / energyItemCount) * 100) : 0
    }));
    const validatedLength = this.isRecommendationWorkspaceSource()
      && recommendationValidation.is_valid === true
      && items.length === recommendationTargetCount
      ? Number(recommendationValidation.estimated_stringed_length_cm)
      : NaN;
    const displayedLength = Number.isFinite(validatedLength) ? validatedLength : roundedLength;
    const currentWrist = items.length
      ? Math.max(0, displayedLength - 0.8)
      : 0;
    const sizes = items.map(item => Number(item.size || 0)).filter(Boolean);
    const minSize = sizes.length ? Math.min(...sizes) : 0;
    const maxSize = sizes.length ? Math.max(...sizes) : 0;
    const beadSizeText = !sizes.length ? '--' : minSize === maxSize ? maxSize + 'mm' : minSize + '-' + maxSize + 'mm';
    const summary = {
      count: items.length,
      price,
      priceText: price.toFixed(2),
      length: length.toFixed(1),
      weight: weight.toFixed(2),
      currentWrist: currentWrist.toFixed(1),
      beadSizeText,
      recommendedCount,
      maxBeadCount,
      maxLength: targetLength.toFixed(1),
      warning,
      energy
    };
    const value = { summary, length };
    this.workspaceSummaryCache = { key, value };
    return value;
  },

  buildScaleTicks(geometry) {
    const wristSize = Number(this.data.wristSize || 16);
    const total = Math.max(44, Math.min(72, Math.round(wristSize * 3.6)));
    const ticks = [];
    const wristAdjustment = (wristSize - 16) * 2.6;
    const baseRadius = Math.max(0, geometry.radius + 38 + wristAdjustment);
    for (let index = 0; index < total; index += 1) {
      const angle = (360 / total) * index;
      const isMajor = index % 6 === 0;
      const isMid = !isMajor && index % 3 === 0;
      const labelIndex = Math.round(index / 6);
      ticks.push({
        id: index,
        style: `transform:rotate(${angle.toFixed(2)}deg) translateY(-${baseRadius.toFixed(1)}rpx);`,
        className: isMajor ? 'major' : (isMid ? 'mid' : ''),
        label: isMajor && labelIndex % 2 === 0 ? `${Math.round(wristSize + labelIndex - total / 12)}` : ''
      });
    }
    return ticks;
  },

  getCachedScaleTicks(geometry = {}) {
    const wristSize = Number(this.data.wristSize || 16);
    const key = [
      wristSize,
      Number(geometry.center || 0).toFixed(3),
      Number(geometry.radius || 0).toFixed(3)
    ].join('::');
    if (this.scaleTicksCache && this.scaleTicksCache.key === key) {
      return this.scaleTicksCache.ticks;
    }
    const ticks = this.buildScaleTicks(geometry);
    this.scaleTicksCache = { key, ticks };
    return ticks;
  },

  buildActionState() {
    const isWorking = this.data.isShuffling || this.data.isStringingFinishing || this.data.isReleasingString;
    const isRecommendationSource = this.isRecommendationWorkspaceSource();
    return {
      shuffleButtonClass: isWorking ? 'working' : '',
      randomIconText: isWorking ? '...' : '串',
      randomTitle: this.data.isReleasingString
        ? '正在散开'
        : this.data.isShuffling
          ? '正在成串'
          : (this.data.isLooseMode
            ? (isRecommendationSource ? '成串预览' : '随机成串')
            : (isRecommendationSource ? '散开编辑' : '解除成串')),
      randomSubtitle: this.data.isReleasingString
        ? '恢复自由编辑'
        : (this.data.isLooseMode
          ? (isRecommendationSource ? '保留当前推荐顺序' : '随机排列珠面')
          : '恢复自由编辑')
    };
  },

  buildWristOptionItems() {
    const current = Number(this.data.wristSize || 16);
    return (this.data.wristOptions || []).map(size => ({
      value: size,
      label: `${size}cm`,
      className: Number(size) === current ? 'active' : ''
    }));
  },

  getCachedWristOptionItems() {
    const current = Number(this.data.wristSize || 16);
    const optionsKey = (this.data.wristOptions || []).join('|');
    const key = `${current}::${optionsKey}`;
    if (this.wristOptionItemsCache && this.wristOptionItemsCache.key === key) {
      return this.wristOptionItemsCache.items;
    }
    const items = this.buildWristOptionItems();
    this.wristOptionItemsCache = { key, items };
    return items;
  },

  getStageLayout() {
    if (this.stageLayout && this.stageLayout.center) {
      return {
        center: this.stageLayout.center,
        radius: this.stageLayout.radius
      };
    }
    const info = this.data.deviceInfo && this.data.deviceInfo.windowWidth
      ? this.data.deviceInfo
      : getWorkspaceSystemInfo();
    const windowWidth = Number(info.windowWidth) || 375;
    const windowHeight = Number(info.windowHeight) || 667;
    const screenHeight = Number(info.screenHeight) || windowHeight;
    const safeArea = info.safeArea || {};
    const bottomInset = Number(info.bottomInset) || (safeArea.bottom ? Math.max(0, screenHeight - safeArea.bottom) : 0);
    const rpxRatio = 750 / windowWidth;
    const layout = this.buildResponsiveWorkspaceLayout({
      windowWidth,
      windowHeight,
      viewportRpx: Math.round(windowHeight * rpxRatio),
      bottomInsetRpx: Math.round(bottomInset * rpxRatio)
    }).stageLayout;
    return {
      center: layout.center,
      radius: layout.radius
    };
  },

  drawDesignPreviewBackdrop(ctx, state) {
    if (!ctx || !state) return;
    const width = state.width || 1;
    const height = state.height || 1;
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) * 0.42;
    const palette = this.getTrayPalette();
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = palette.page;
    ctx.fillRect(0, 0, width, height);

    const plate = ctx.createRadialGradient(
      centerX - radius * 0.18,
      centerY - radius * 0.22,
      radius * 0.08,
      centerX,
      centerY,
      radius * 1.15
    );
    (palette.plateStops || [
      [0, palette.inner0],
      [0.42, palette.inner1],
      [1, palette.outer]
    ]).forEach(stop => {
      plate.addColorStop(stop[0], stop[1]);
    });
    ctx.fillStyle = plate;
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
    ctx.fill();

    this.drawCanvasDitherNoise(ctx, width, height, {
      x: centerX,
      y: centerY,
      radius,
      alpha: palette.noiseAlpha
    });

    ctx.strokeStyle = palette.stroke;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius * 0.92, 0, Math.PI * 2);
    ctx.stroke();

    ctx.strokeStyle = palette.centerStroke;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius * 0.54, 0, Math.PI * 2);
    ctx.stroke();
  },

  drawCanvasDitherNoise(ctx, width, height, options = {}) {
    const alpha = Number(options.alpha || 0);
    if (!ctx || alpha <= 0) return;
    const centerX = Number(options.x || width / 2);
    const centerY = Number(options.y || height / 2);
    const radius = Number(options.radius || Math.min(width, height) / 2);
    const density = Math.max(360, Math.round(width * height / 520));
    let seed = 123456789;

    ctx.save();
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
    ctx.clip();

    for (let i = 0; i < density; i += 1) {
      seed = (seed * 1664525 + 1013904223) >>> 0;
      const x = seed % width;
      seed = (seed * 1664525 + 1013904223) >>> 0;
      const y = seed % height;
      seed = (seed * 1664525 + 1013904223) >>> 0;
      const tone = (seed & 1) ? 255 : 0;
      ctx.fillStyle = `rgba(${tone},${tone},${tone},${alpha})`;
      ctx.fillRect(x, y, 1, 1);
    }

    ctx.restore();
  },

  renderBraceletPreviewForExport() {
    const state = this.braceletCanvasState;
    if (!state || !state.ctx || !state.canvas) return false;
    const ctx = state.ctx;
    this.drawDesignPreviewBackdrop(ctx, state);
    const beadSprites = this.getCanvasBeadSprites();
    beadSprites.forEach(sprite => this.drawCanvasBead(ctx, {
      ...sprite,
      active: false,
      dragging: false,
      deleteReady: false
    }));
    return true;
  },

  captureDesignPreviewFile() {
    return new Promise(resolve => {
      const state = this.braceletCanvasState;
      if (!state || !state.canvas) {
        resolve('');
        return;
      }
      if (!this.renderBraceletPreviewForExport()) {
        resolve('');
        return;
      }
      wx.canvasToTempFilePath({
        canvas: state.canvas,
        fileType: 'jpg',
        quality: 0.86,
        destWidth: Math.round(state.width * state.dpr),
        destHeight: Math.round(state.height * state.dpr),
        success: res => resolve(res.tempFilePath || ''),
        fail: error => {
          logWorkspaceWarning('capture design preview failed:', error);
          resolve('');
        },
        complete: () => this.renderBraceletCanvas()
      }, this);
    });
  },

  async prepareCurrentDesignPreview(userId, current = {}) {
    const fallback = current.preview_image || current.previewImage || current.image_url || '';
    const filePath = await this.captureDesignPreviewFile();
    if (!filePath) return { previewImage: fallback, localPreviewImage: '' };
    try {
      const result = await uploadDesignPreview(filePath, userId);
      return {
        previewImage: result.preview_url || result.url || fallback,
        localPreviewImage: filePath
      };
    } catch (error) {
      logWorkspaceWarning('upload design preview failed:', error);
      return {
        previewImage: fallback,
        localPreviewImage: filePath
      };
    }
  },

  async uploadCurrentDesignPreview(userId, current = {}) {
    const result = await this.prepareCurrentDesignPreview(userId, current);
    return result.previewImage || result.localPreviewImage || '';
  },

  promptDesignName(defaultName = '') {
    const fallbackName = cleanDesignName(defaultName) || DEFAULT_DESIGN_NAME;
    return new Promise(resolve => {
      wx.showModal({
        title: '\u4fdd\u5b58\u65b9\u6848',
        editable: true,
        placeholderText: fallbackName,
        confirmText: '\u4fdd\u5b58',
        cancelText: '\u53d6\u6d88',
        success: res => {
          if (!res.confirm) {
            resolve('');
            return;
          }
          const name = cleanDesignName(res.content) || fallbackName;
          resolve(name.slice(0, 24));
        },
        fail: () => resolve('')
      });
    });
  },

  async saveDraft(options = {}) {
    let user;
    try {
      user = await auth.requireLogin('登录后才能保存 DIY 草稿。');
    } catch (error) {
      return false;
    }
    const current = wx.getStorageSync('currentDesign') || {};
    let designName = cleanDesignName(options.designName) || cleanDesignName(current.name) || cleanDesignName(current.title);
    if (options.promptName !== false) {
      designName = await this.promptDesignName(designName);
      if (!designName) return false;
    }
    if (!designName) designName = DEFAULT_DESIGN_NAME;
    const previewResult = await this.prepareCurrentDesignPreview(user.user_id, current);
    const previewImage = previewResult.previewImage || '';
    const displayPreviewImage = previewImage || previewResult.localPreviewImage || current.local_preview_image || '';
    const currentDesignUserId = String(current.userId || current.user_id || '');
    const reusableDesignId = currentDesignUserId === String(user.user_id || '')
      ? (current.designId || current.design_id || '')
      : '';
    const stageLayout = this.getStageLayout();
    const persistedPlacements = this.buildCurrentPersistedPlacements();
    const design = {
      designId: reusableDesignId,
      design_id: reusableDesignId,
      name: designName,
      title: designName,
      userId: user.user_id,
      selected: this.data.selected,
      placements: persistedPlacements,
      attachedPendants: [],
      wristSize: this.data.wristSize,
      wearStyle: 'single',
      isLooseMode: this.data.isLooseMode,
      workspaceStageCenter: stageLayout.center,
      previewSourceCenter: stageLayout.center,
      preview_source_center: stageLayout.center,
      sourceContext: this.data.sourceContext || this.sourceContext || current.sourceContext || null,
      preview_image: previewImage,
      previewImage,
      image_url: previewImage || current.image_url || '',
      local_preview_image: previewResult.localPreviewImage || current.local_preview_image || '',
      summary: this.data.summary
    };
    const sequence = this.buildCurrentSequence(persistedPlacements);
    design.sequence = sequence;
    try {
      const remoteDesign = { ...design };
      delete remoteDesign.local_preview_image;
      const saved = await saveDIYDesign({
        user_id: user.user_id,
        design_id: reusableDesignId || undefined,
        design: remoteDesign,
        sequence,
        status: 'saved'
      });
      design.designId = saved.design_id;
      design.design_id = saved.design_id;
    } catch (error) {
      logWorkspaceWarning('save remote DIY design failed:', error);
      wx.showToast({ title: '云端保存失败，请重试', icon: 'none' });
      return false;
    }
    wx.setStorageSync('currentDesign', {
      ...design,
      name: designName,
      title: designName,
      preview_image: previewImage,
      previewImage: previewImage,
      image_url: previewImage || current.image_url || '',
      local_preview_image: displayPreviewImage && displayPreviewImage !== previewImage ? displayPreviewImage : (design.local_preview_image || '')
    });
    if (options.showToast !== false) {
      wx.showToast({ title: options.toastTitle || '\u5df2\u4fdd\u5b58', icon: 'success' });
    }
    return true;
  },

  buildSharePath(shareToken) {
    return shareToken
      ? `/pages/workspace/workspace?shareToken=${encodeURIComponent(shareToken)}`
      : '/pages/workspace/workspace';
  },

  buildShareDesignTitle(design = {}) {
    const summary = design.summary || this.data.summary || {};
    const sourceTitle = design.title
      || design.name
      || summary.name
      || (design.sourceContext && design.sourceContext.title)
      || (this.data.sourceContext && this.data.sourceContext.title);
    return sourceTitle
      ? `查看这条宇涧水晶 DIY 方案：${sourceTitle}`
      : '查看这条宇涧水晶 DIY 手串方案';
  },

  async prepareShareDesign() {
    if (!this.data.selected.length) {
      wx.showToast({ title: '先选择至少一颗珠材', icon: 'none' });
      return;
    }
    if (this.data.sharingDesign) return;
    this.setData({ sharingDesign: true });
    wx.showLoading({ title: '生成分享...', mask: true });
    try {
      const saved = await this.saveDraft({ showToast: false, promptName: false });
      if (!saved) return;
      const current = wx.getStorageSync('currentDesign') || {};
      const designId = current.designId || current.design_id || '';
      if (!designId) {
        wx.showToast({ title: '方案保存后才能分享', icon: 'none' });
        return;
      }
      const published = await publishDIYDesign(designId, { silent: true, timeout: 10000 });
      const shareToken = published && published.share_token;
      if (!shareToken) throw new Error('分享令牌生成失败');
      this.hideWorkspaceCanvasForOverlay();
      this.setData({
        showShareSheet: true,
        shareToken,
        shareDesignTitle: this.buildShareDesignTitle(current),
        sharePreviewImage: current.preview_image || current.previewImage || current.image_url || current.local_preview_image || ''
      });
      if (wx.showShareMenu) wx.showShareMenu({ menus: ['shareAppMessage'] });
    } catch (error) {
      logWorkspaceWarning('prepare share design failed:', error);
      wx.showToast({ title: error.message || '分享方案生成失败', icon: 'none' });
    } finally {
      wx.hideLoading();
      this.setData({ sharingDesign: false });
    }
  },

  closeShareSheet() {
    this.setData({ showShareSheet: false }, () => this.restoreWorkspaceCanvasAfterOverlay());
  },

  onShareAppMessage() {
    const current = wx.getStorageSync('currentDesign') || {};
    const shareToken = this.data.shareToken || '';
    const imageUrl = this.data.sharePreviewImage || current.preview_image || current.previewImage || current.image_url || '';
    return {
      title: shareToken ? this.buildShareDesignTitle(current) : '打开宇涧水晶 DIY 工作台',
      path: this.buildSharePath(shareToken),
      imageUrl
    };
  },

  onShareTimeline() {
    const current = wx.getStorageSync('currentDesign') || {};
    const shareToken = this.data.shareToken || '';
    const imageUrl = this.data.sharePreviewImage || current.preview_image || current.previewImage || current.image_url || '';
    return {
      title: shareToken ? this.buildShareDesignTitle(current) : '宇涧水晶 DIY 工作台',
      query: shareToken ? `shareToken=${encodeURIComponent(shareToken)}` : '',
      imageUrl
    };
  },

  openWristGuideModal(e) {
    const tab = e && e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.tab;
    this.hideWorkspaceCanvasForOverlay();
    this.setData({
      showWristGuideModal: true,
      activeWristGuideTab: tab || this.data.activeWristGuideTab || 'workspace'
    });
  },

  closeWristGuideModal() {
    this.setData({ showWristGuideModal: false }, () => this.restoreWorkspaceCanvasAfterOverlay());
  },

  switchWristGuideTab(e) {
    const tab = e && e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.tab;
    if (!tab || tab === this.data.activeWristGuideTab) return;
    this.setData({ activeWristGuideTab: tab });
  },

  onWristGuideImageError() {
    wx.showToast({ title: '指南图暂时加载失败', icon: 'none' });
  },

  openEnergyModal() {
    this.hideWorkspaceCanvasForOverlay();
    if (!_energySvgCache) {
      var energyData = {};
      (this.data.summary.energy || []).forEach(function(e) { energyData[e.key] = e.value; });
      _energySvgCache = svgToDataURI(generateChartSVG(energyData, {
        width: 460,
        height: 460,
        padding: 58,
        gridColor: 'rgba(72,58,40,0.10)',
        axisColor: 'rgba(72,58,40,0.14)',
        areaStroke: '#b88a42',
        areaFillStart: '#e8cf9c',
        areaFillEnd: '#b88a42',
        labelColor: 'rgba(35,29,22,0.78)',
        valueColor: 'rgba(35,29,22,0.46)',
        showLabels: true,
        showValues: true
      }));
    }
    this.setData({ showEnergyPanel: false, showEnergyModal: true, energyChartSvgUrl: _energySvgCache });
  },

  toggleEnergyPanel() {
    this.openEnergyModal();
  },

  closeEnergyModal() {
    this.setData({ showEnergyModal: false }, () => this.restoreWorkspaceCanvasAfterOverlay());
  },

  goBack() {
    const url = '/pages/home/home';
    wx.switchTab({
      url,
      fail: () => wx.reLaunch({ url })
    });
  }

});

// ===================== 五行能量图 SVG 生成（内联） =====================

/** 五行元素配置（顺时针：火→土→金→水→木）*/
var _energySvgCache = '';

var __ELEMENTS__ = [
  { key: 'fire',  name: '火', angle: -90,         color: '#e74c3c', gs: '#e74c3c', ge: '#c0392b' },
  { key: 'earth', name: '土', angle: -18,         color: '#f1c40f', gs: '#f1c40f', ge: '#d4a017' },
  { key: 'metal', name: '金', angle: 54,          color: '#f39c12', gs: '#f9d976', ge: '#d68910' },
  { key: 'water', name: '水', angle: 126,         color: '#3498db', gs: '#5dade2', ge: '#1a5276' },
  { key: 'wood',  name: '木', angle: 198,         color: '#2ecc71', gs: '#58d68d', ge: '#1a9c5e' }
];

var __DATA_KEY_MAP__ = {};
__DATA_KEY_MAP__.gold = 'metal'; __DATA_KEY_MAP__.metal = 'metal'; __DATA_KEY_MAP__.fire = 'fire';
__DATA_KEY_MAP__.water = 'water'; __DATA_KEY_MAP__.wood = 'wood'; __DATA_KEY_MAP__.earth = 'earth';

function __getPentagonVerts__(cx, cy, r, offset) {
  if (offset === void 0) offset = -90;
  var verts = [];
  for (var i = 0; i < 5; i++) {
    var rad = (offset + i * 72) * Math.PI / 180;
    verts.push({ x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) });
  }
  return verts;
}

function __calcPoints__(data, cx, cy, maxR) {
  var verts = __getPentagonVerts__(cx, cy, maxR, -90);
  return __ELEMENTS__.map(function(el, i) {
    var dk = Object.keys(__DATA_KEY_MAP__).find(function(k) { return __DATA_KEY_MAP__[k] === el.key; }) || el.key;
    var val = Math.max(0, Math.min(100, Number(data[dk]) || 0));
    var r = val / 100;
    var v = verts[i];
    return { key: el.key, name: el.name, value: val, color: el.color, gs: el.gs, ge: el.ge,
      x: cx + (v.x - cx) * r, y: cy + (v.y - cy) * r };
  });
}

function generateChartSVG(data, opts) {
  if (opts === void 0) opts = {};
  var o = {};
  for (var k in { width: 400, height: 400, padding: 45, gridColor: 'rgba(0,0,0,0.06)', axisColor: 'rgba(0,0,0,0.1)', areaStroke: '#c0a36b', areaStrokeWidth: 2, labelColor: 'rgba(0,0,0,0.7)', valueColor: 'rgba(0,0,0,0.4)', dotRadius: 5, dotStroke: '#fff', showLabels: true, showValues: true }) o[k] = opts[k] || { width: 400, height: 400, padding: 45, gridColor: 'rgba(0,0,0,0.06)', axisColor: 'rgba(0,0,0,0.1)', areaStroke: '#c0a36b', areaStrokeWidth: 2, labelColor: 'rgba(0,0,0,0.7)', valueColor: 'rgba(0,0,0,0.4)', dotRadius: 5, dotStroke: '#fff', showLabels: true, showValues: true }[k];
  o.width = opts.width || 400; o.height = opts.height || 400; o.padding = opts.padding || 45;
  o.gridColor = opts.gridColor || 'rgba(0,0,0,0.06)'; o.axisColor = opts.axisColor || 'rgba(0,0,0,0.1)';
  o.areaStroke = opts.areaStroke || '#c0a36b'; o.labelColor = opts.labelColor || 'rgba(0,0,0,0.7)';
  o.areaFillStart = opts.areaFillStart || '#e8cf9c'; o.areaFillEnd = opts.areaFillEnd || '#b88a42';
  o.valueColor = opts.valueColor || 'rgba(0,0,0,0.4)'; o.dotRadius = opts.dotRadius || 5;
  o.showLabels = opts.showLabels !== false; o.showValues = opts.showValues !== false;

  var cx = o.width / 2, cy = o.height / 2, maxR = Math.min(o.width, o.height) / 2 - o.padding;
  var pts = __calcPoints__(data, cx, cy, maxR);
  var svg = [];

  // background
  svg.push('<svg xmlns="http://www.w3.org/2000/svg" width="' + o.width + '" height="' + o.height + '" viewBox="0 0 ' + o.width + ' ' + o.height + '">');

  // gradient
  svg.push('<defs><linearGradient id="eg" x1="0%" y1="0%" x2="100%" y2="100%">');
  svg.push('<stop offset="0%" stop-color="' + o.areaFillStart + '" stop-opacity="0.48"/><stop offset="100%" stop-color="' + o.areaFillEnd + '" stop-opacity="0.22"/></linearGradient>');
  svg.push('<filter id="energyShadow" x="-35%" y="-35%" width="170%" height="170%"><feDropShadow dx="0" dy="7" stdDeviation="8" flood-color="#6f5127" flood-opacity="0.22"/></filter>');

  // radial gradients for each dot
  pts.forEach(function(p, i) {
    svg.push('<radialGradient id="dg' + i + '" cx="30%" cy="30%" r="70%">');
    svg.push('<stop offset="0%" stop-color="' + p.gs + '"/><stop offset="100%" stop-color="' + p.ge + '"/></radialGradient>');
  });
  svg.push('</defs>');

  // concentric pentagons (grid)
  for (var lv = 1; lv <= 5; lv++) {
    var r = maxR * lv / 5, gv = __getPentagonVerts__(cx, cy, r, -90);
    var pd = gv.map(function(v, j) { return (j === 0 ? 'M' : 'L') + v.x.toFixed(1) + ',' + v.y.toFixed(1); }).join('') + 'Z';
    svg.push('<path d="' + pd + '" fill="none" stroke="' + o.gridColor + '" stroke-width="1"/>');
  }

  // axis lines
  var av = __getPentagonVerts__(cx, cy, maxR, -90);
  av.forEach(function(v) {
    svg.push('<line x1="' + cx.toFixed(1) + '" y1="' + cy.toFixed(1) + '" x2="' + v.x.toFixed(1) + '" y2="' + v.y.toFixed(1) + '" stroke="' + o.axisColor + '" stroke-width="1" stroke-dasharray="3,4"/>');
  });

  // energy polygon
  var ep = pts.map(function(p, i) { return (i === 0 ? 'M' : 'L') + p.x.toFixed(1) + ',' + p.y.toFixed(1); }).join('') + 'Z';
  svg.push('<path d="' + ep + '" fill="url(#eg)" stroke="' + o.areaStroke + '" stroke-width="' + o.areaStrokeWidth + '" stroke-linejoin="round" filter="url(#energyShadow)"/>');

  // dots and labels
  pts.forEach(function(p, i) {
    svg.push('<circle cx="' + p.x.toFixed(1) + '" cy="' + p.y.toFixed(1) + '" r="' + (o.dotRadius + 3) + '" fill="' + p.color + '" opacity="0.15"/>');
    svg.push('<circle cx="' + p.x.toFixed(1) + '" cy="' + p.y.toFixed(1) + '" r="' + o.dotRadius + '" fill="url(#dg' + i + ')" stroke="' + o.dotStroke + '" stroke-width="1.5"/>');

    if (o.showLabels) {
      var lr = maxR + 22, rad = (__ELEMENTS__[i].angle) * Math.PI / 180;
      var lx = cx + lr * Math.cos(rad), ly = cy + lr * Math.sin(rad);
      var anc = lx > cx + 5 ? 'start' : (lx < cx - 5 ? 'end' : 'middle');
      svg.push('<text x="' + lx.toFixed(1) + '" y="' + ly.toFixed(1) + '" fill="' + o.labelColor + '" font-size="13" font-weight="bold" text-anchor="' + anc + '" dominant-baseline="central">' + p.name + '</text>');
      if (o.showValues) {
        svg.push('<text x="' + lx.toFixed(1) + '" y="' + (ly + 15).toFixed(1) + '" fill="' + o.valueColor + '" font-size="10" text-anchor="' + anc + '" dominant-baseline="central">' + p.value + '%</text>');
      }
    }
  });

  svg.push('</svg>');
  return svg.join('');
}

function svgToDataURI(svgStr) {
  return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgStr).replace(/'/g, '%27').replace(/%20/g, ' ');
}
