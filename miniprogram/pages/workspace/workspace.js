const auth = require('../../utils/auth');
const { getMaterials, saveDIYDesign, getSharedDIYDesign, saveCartItem, uploadDesignPreview } = require('../../utils/api');
const { assetUrl } = require('../../utils/assets');

let Body;
let Bodies;
let Composite;
let Engine;
let Events;

const MATERIAL_PAGE_SIZE = 24;
const MATERIAL_CACHE_TTL = 30 * 60 * 1000;
const MATERIAL_CACHE_KEY = 'workspaceMaterialCatalogV6';
const ALL_OPTION_LABEL = '\u5168\u90e8';
const LEGACY_ALL_OPTION_LABELS = [ALL_OPTION_LABEL, '鍏ㄩ儴'];
const TRAY_THEME_STORAGE_KEY = 'workspaceTrayThemeV1';
const WORKSPACE_WRIST_SIZE_STORAGE_KEY = 'workspaceWristSizeV1';
const WORKSPACE_GUIDE_STORAGE_KEY = 'workspaceFirstGuideDismissedV1';
const MAX_WORKSPACE_BEADS = 40;
const MIN_STRING_BEAD_COUNT = 8;
const MAX_MATERIAL_FLIGHT_QUEUE = 6;
const MATERIAL_TAP_GUARD_MS = 80;
const MATERIAL_QUEUE_TOAST_GUARD_MS = 1200;
const STRINGED_BEAD_GAP_RPX = 0.5;
const WORKSPACE_DEBUG_LOGS = false;
const WORKSPACE_SOUND_URLS = {
  collisionSoft: assetUrl('sounds/bead-duang-soft-quick.wav'),
  collision: assetUrl('sounds/bead-duang-quick.wav'),
  collisionBright: assetUrl('sounds/bead-duang-bright-quick.wav'),
  shuffle: assetUrl('sounds/string-shuffle.wav')
};
const WORKSPACE_SOUND_POOL_SIZE = {
  collisionSoft: 3,
  collision: 4,
  collisionBright: 4,
  shuffle: 2
};
const WRIST_RULER_MIN = 10;
const WRIST_RULER_MAX = 25;
const WRIST_RULER_STEP = 0.1;
const WRIST_RULER_TICK_RPX = 22;
let materialCache = {};
let materialCacheAt = {};

const DEFAULT_MATERIALS = [
  { id: 'clearQuartz8', skuId: 'clearQuartz', top: 'bead', category: '白水晶', name: '喜马拉雅白水晶', effect: '净化与放大', element: '金', price: 5, size: 8, weight: 1.2, color: '#dfe3e5', shine: '#ffffff' },
  { id: 'clearQuartz10', skuId: 'clearQuartz', top: 'bead', category: '白水晶', name: '喜马拉雅白水晶', effect: '净化与放大', element: '金', price: 10, size: 10, weight: 1.6, color: '#d6dbde', shine: '#ffffff' },
  { id: 'clearQuartz12', skuId: 'clearQuartz', top: 'bead', category: '白水晶', name: '喜马拉雅白水晶', effect: '净化与放大', element: '金', price: 15, size: 12, weight: 2.1, color: '#cfd5d8', shine: '#ffffff' },
  { id: 'clearQuartz14', skuId: 'clearQuartz', top: 'bead', category: '白水晶', name: '喜马拉雅白水晶', effect: '净化与放大', element: '金', price: 18, size: 14, weight: 2.8, color: '#c8ced1', shine: '#ffffff' },
  { id: 'amethyst8', skuId: 'amethyst', top: 'bead', category: '紫水晶', name: '乌拉圭紫水晶', effect: '灵感与睡眠', element: '火', price: 12, size: 8, weight: 1.4, color: '#8b6aa5', shine: '#efe8ff' },
  { id: 'amethyst10', skuId: 'amethyst', top: 'bead', category: '紫水晶', name: '乌拉圭紫水晶', effect: '灵感与睡眠', element: '火', price: 18, size: 10, weight: 1.8, color: '#76508f', shine: '#efe8ff' },
  { id: 'citrine8', skuId: 'citrine', top: 'bead', category: '黄水晶', name: '巴西黄水晶', effect: '财富与行动', element: '土', price: 16, size: 8, weight: 1.5, color: '#d6ad50', shine: '#fff0b7' },
  { id: 'citrine10', skuId: 'citrine', top: 'bead', category: '黄水晶', name: '巴西黄水晶', effect: '财富与行动', element: '土', price: 22, size: 10, weight: 1.9, color: '#c79838', shine: '#fff0b7' },
  { id: 'obsidian10', skuId: 'obsidian', top: 'bead', category: '曜石', name: '冰种黑曜石', effect: '边界与守护', element: '金', price: 14, size: 10, weight: 1.8, color: '#262529', shine: '#aeb2b5' },
  { id: 'tigerEye8', skuId: 'tigerEye', top: 'bead', category: '虎眼石', name: '南非虎眼石', effect: '执行与稳定', element: '土', price: 13, size: 8, weight: 1.5, color: '#9b6a2e', shine: '#f1c06b' },
  { id: 'moonstone6', skuId: 'moonstone', top: 'bead', category: '月光石', name: '雪花幽灵', effect: '情绪修复', element: '水', price: 4, size: 6, weight: 0.9, color: '#c7cbca', shine: '#ffffff' },
  { id: 'moonstone8', skuId: 'moonstone', top: 'bead', category: '月光石', name: '雪花幽灵', effect: '情绪修复', element: '水', price: 8, size: 8, weight: 1.2, color: '#bdc2c1', shine: '#ffffff' },
  { id: 'aquamarine8', skuId: 'aquamarine', top: 'bead', category: '海蓝宝', name: '巴西海蓝宝', effect: '沟通与平静', element: '水', price: 25, size: 8, weight: 1.4, color: '#80b8c5', shine: '#e8fbff' },
  { id: 'blueRutilatedQuartz10', skuId: 'blueRutilatedQuartz', top: 'bead', category: '蓝发晶', name: '蓝发晶', effect: '冷静与洞察', element: '水', price: 38, size: 10, weight: 1.9, color: '#4f789b', shine: '#dcecf3' },
  { id: 'garnet8', skuId: 'garnet', top: 'bead', category: '石榴石', name: '石榴石', effect: '活力与自信', element: '火', price: 18, size: 8, weight: 1.5, color: '#8e2635', shine: '#e7a1aa' },
  { id: 'turquoise6', skuId: 'turquoise', top: 'bead', category: '绿松石', name: '绿松石', effect: '生机与恢复', element: '木', price: 16, size: 6, weight: 0.9, color: '#56a6a2', shine: '#d7f1ef' },
  { id: 'greenPhantom8', skuId: 'greenPhantom', top: 'bead', category: '绿幽灵', name: '绿幽灵', effect: '生长与专注', element: '木', price: 24, size: 8, weight: 1.4, color: '#4a825f', shine: '#d7eadc' },
  { id: 'smokyQuartz8', skuId: 'smokyQuartz', top: 'bead', category: '茶晶', name: '茶晶', effect: '稳定与落地', element: '土', price: 14, size: 8, weight: 1.4, color: '#766052', shine: '#d8c8bc' },
  { id: 'hematite8', skuId: 'hematite', top: 'bead', category: '赤铁矿', name: '赤铁矿', effect: '边界与决断', element: '金', price: 12, size: 8, weight: 1.7, color: '#5a5b60', shine: '#d5d6d8' },
  { id: 'roseQuartz8', skuId: 'roseQuartz', top: 'bead', category: '粉水晶', name: '马达加斯加粉晶', effect: '人缘与亲密', element: '木', price: 11, size: 8, weight: 1.3, color: '#e0a3a8', shine: '#fff1f3' },
  { id: 'silverSpacer', skuId: 'silverSpacer', top: 'accessory', category: '隔片', name: '925 银隔片', effect: '结构与光泽', element: '金', price: 18, size: 3, weight: 0.4, color: '#b9bdc2', shine: '#ffffff' },
  { id: 'goldSpacer', skuId: 'goldSpacer', top: 'accessory', category: '隔片', name: '鎏金隔片', effect: '礼物感', element: '土', price: 16, size: 3, weight: 0.4, color: '#c99d4d', shine: '#fff0b7' },
  { id: 'foxPendant', skuId: 'foxPendant', top: 'pendant', category: '吊坠', name: '粉晶狐狸吊坠', effect: '桃花与礼物', element: '木', price: 88, size: 12, weight: 2.2, color: '#d88b91', shine: '#fff1f3' }
];

const TOP_TABS = [
  { key: 'bead', label: '珠珠' },
  { key: 'accessory', label: '配饰' },
  { key: 'pendant', label: '花托' }
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
  foxPendant: 'wood',
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
  { tag: '五行', title: '查看能量占比', desc: '打开当前方案的五行分布，方便对照测算结果。' },
  { tag: '清空', title: '清空盘面', desc: '移除当前盘面所有珠子，重新开始搭配。' },
  { tag: '成串', title: '随机成串/打散', desc: '在自由摆放和圆串整理之间切换，快速预览佩戴效果。' },
  { tag: '加购', title: '加入购物车', desc: '确认方案后，可先加入购物车继续下单。' }
];

const WORKSPACE_USAGE_GUIDE_WITH_ICONS = [
  { tag: '撤回', iconClass: 'plate-icon-undo', title: '撤回上一步', desc: '误加、误删或移动珠子后，点它回到上一步。' },
  { tag: '腕围', iconClass: 'plate-icon-wrist', title: '设置腕围', desc: '调整当前手围，系统会同步重算串长和适配。' },
  { tag: '分享', iconClass: 'plate-icon-share', title: '分享方案', desc: '生成当前方案分享入口，好友打开后可直接查看。' },
  { tag: '保存', iconClass: 'plate-icon-save', title: '保存方案', desc: '把当前搭配保存为草稿，之后可以继续编辑。' },
  { tag: '五行', iconClass: 'plate-icon-energy', title: '五行图', desc: '查看当前方案的五行能量占比。' },
  { tag: '清空', iconClass: 'plate-icon-clear', title: '清空盘面', desc: '移除当前盘面所有珠子，重新开始搭配。' },
  { tag: '成串', iconClass: 'plate-random-icon', title: '随机成串 / 解除成串', desc: '在自由摆放和圆串整理之间切换，快速预览佩戴效果。' },
  { tag: '托盘', iconClass: 'workspace-icon-theme', title: '切换托盘颜色', desc: '顺序切换托盘底色，方便看清不同颜色的珠子。' },
  { tag: '加购', iconClass: 'workspace-icon-cart', title: '加入购物车', desc: '确认方案后加入购物车，后续继续下单。' }
];

const WORKSPACE_GUIDE_ITEMS = [
  { index: '01', title: '点击材料', desc: '珠子会投入圆盘，先从喜欢的材质开始。' },
  { index: '02', title: '拖动调整', desc: '轻触珠子移动位置，长按材料看实拍。' },
  { index: '03', title: '一键成串', desc: '用成串/打散按钮，在规整和自由编辑间切换。' }
];

Page({
  data: {
    visibleMaterials: [],
    hasMoreMaterials: false,
    materialsLoading: true,
    materialsLoadingMore: false,
    materialsErrorText: '',
    materialSkeletons: [1, 2, 3, 4],
    materialSearchKeyword: '',
    categories: [],
    categoryRailSeries: [],
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
    workspaceGuideItems: WORKSPACE_GUIDE_ITEMS,
    wristSize: 16,
    wearStyle: 'single',
    selected: [],
    placements: [],
    selectedItems: [],
    useCanvasRenderer: true,
    workspaceCanvasVisible: true,
    trayImageUrl: TRAY_THEMES[0].imageUrl,
    trayTheme: 'warm',
    trayThemeItems: [],
    trayImageFailed: false,
    canvasFlightActive: false,
    stringStyle: '',
    scaleTicks: [],
    countOverClass: '',
    braceletStringClass: 'empty',
    completionWatermarkClass: '',
    shuffleButtonClass: '',
    randomIconText: '串',
    randomTitle: '随机成串',
    randomSubtitle: '随机排列珠面',
    flightBead: null,
    launchingMaterialId: '',
    isShuffling: false,
    isStringingFinishing: false,
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
    wristRulerTicks: [],
    wristRulerScrollLeft: 0,
    wristRulerTickWidth: 11,
    wristRulerSidePadding: 180,
    wristRulerRangeText: '10.0–25.0cm',
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
    shareDesignId: '',
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
      weight: '0.00',
      maxLength: '16.8',
      warning: '',
      energy: []
    }
  },

  onLoad(query) {
    this.materialCatalog = DEFAULT_MATERIALS;
    this.filteredMaterialCatalog = [];
    this.flightQueue = [];
    this.flightActive = false;
    this.lastMaterialTapAt = 0;
    this.lastQueueToastAt = 0;
    this.physicsBodies = [];
    this.physicsFramePending = false;
    this.soundEnabled = true;
    this.audioPlayers = {};
    this.audioPlayerCursors = {};
    this.audioPlayersReady = false;
    this.lastSoundAt = {};
    this.sourceContext = null;
    this.pendingBackendRecommendation = false;
    this.pendingRecommendedRecipe = false;
    this.pendingSharedDesign = null;
    this.pendingSharedDesignId = '';
    this.materialPayloadReady = false;
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
    const sharedDesignId = this.getSharedDesignIdFromQuery(query);
    if (wx.showShareMenu) wx.showShareMenu({ menus: ['shareAppMessage'] });
    if (sharedDesignId) {
      this.pendingSharedDesignId = sharedDesignId;
      this.loadSharedDesign(sharedDesignId);
    } else if (query.preset === 'backend-recommended') {
      this.pendingBackendRecommendation = true;
      this.applyBackendRecommendation();
    } else if (query.preset === 'recommended') {
      this.pendingRecommendedRecipe = true;
      this.applyRecommendedRecipe();
    } else {
      this.loadDraft();
    }
    this.loadMaterials();
    this.wristPromptTimer = setTimeout(() => this.promptInitialWristSize(), 420);
  },

  deferNonCriticalWorkspaceTasks() {
    clearTimeout(this.nonCriticalTaskTimer);
    this.nonCriticalTaskTimer = setTimeout(() => {
      this.loadProfileEnergy();
      this.ensureAudioPlayers();
    }, this.isLowPerformanceDevice ? 520 : 260);
  },

  getSharedDesignIdFromQuery(query = {}) {
    const raw = query.shareDesignId || query.share_design_id || query.sharedDesignId || '';
    if (!raw) return '';
    try {
      return decodeURIComponent(String(raw)).trim();
    } catch (error) {
      return String(raw).trim();
    }
  },

  async loadSharedDesign(designId) {
    if (!designId) return false;
    this.setData({ sharedDesignLoading: true });
    try {
      const sharedDesign = await getSharedDIYDesign(designId, { silent: true, timeout: 10000 });
      this.pendingSharedDesign = sharedDesign;
      this.pendingSharedDesignId = sharedDesign.design_id || designId;
      if (this.materialPayloadReady) {
        const applied = await this.ensurePendingMaterialDetails({ silent: true, keepPendingOnEmpty: true });
        if (applied) return true;
        return this.applySharedDesign(sharedDesign);
      }
      return false;
    } catch (error) {
      logWorkspaceWarning('load shared DIY design failed:', error);
      this.pendingSharedDesign = null;
      this.pendingSharedDesignId = '';
      this.setData({ sharedDesignLoading: false });
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
      .map(item => item && (item.id || item.material_id || item.materialId || item.sku || item.skuId || item.sku_id))
      .filter(Boolean);
    const selected = (selectedFromDesign.length ? selectedFromDesign : selectedFromSequence)
      .map(id => String(id))
      .filter(Boolean);
    const sequencePlacements = sequence.map(item => item && item.placement).filter(Boolean);
    const placements = Array.isArray(design.placements) && design.placements.length
      ? design.placements
      : sequencePlacements;
    const summary = design.summary || {};
    const sourceContext = design.sourceContext || design.source_context || {
      source: 'shared_design',
      source_label: '分享方案',
      title: (summary && summary.name) || '好友分享方案',
      design_id: sharedDesign.design_id || design.designId || design.design_id || ''
    };
    return {
      ...design,
      designId: sharedDesign.design_id || design.designId || design.design_id || '',
      design_id: sharedDesign.design_id || design.design_id || design.designId || '',
      userId: sharedDesign.user_id || design.userId || design.user_id || '',
      user_id: sharedDesign.user_id || design.user_id || design.userId || '',
      selected,
      placements,
      wristSize: Number(design.wristSize || design.wrist_size || summary.wristSize || 16) || 16,
      wearStyle: 'single',
      isLooseMode: design.isLooseMode === true,
      sourceContext,
      summary: {
        ...summary,
        count: selected.length || summary.count || sequence.length || 0
      },
      sequence
    };
  },

  applySharedDesign(sharedDesign = {}, options = {}) {
    if (!this.materialPayloadReady) return false;
    const normalized = this.normalizeSharedDesignPayload(sharedDesign);
    const selected = this.resolveSharedDesignSelectedIds(normalized);
    if (!selected.length) {
      if (!options.keepPendingOnEmpty) {
        this.pendingSharedDesign = null;
        this.pendingSharedDesignId = '';
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
    const draft = {
      ...normalized,
      selected,
      sourceContext,
      isSharedDesign: true
    };
    this.pendingSharedDesign = null;
    this.pendingSharedDesignId = '';
    this.sourceContext = sourceContext;
    wx.setStorageSync('currentDesign', draft);
    wx.setStorageSync('workspaceWristConfirmed', true);
    this.resetWorkspaceRuntime();
    this.setData({
      selected,
      placements: this.normalizePlacements(selected, normalized.placements),
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
      draggingBeadIndex: -1,
      dragDeleteArmed: false,
      sharedDesignLoading: false,
      shareDesignId: normalized.designId || '',
      shareDesignTitle: this.buildShareDesignTitle(draft),
      sharePreviewImage: draft.preview_image || draft.previewImage || draft.image_url || ''
    });
    this.recalculate();
    if (normalized.isLooseMode) {
      wx.nextTick(() => this.startPhysicsFromCurrentDesign());
    }
    if (!options.silent) wx.showToast({ title: '已打开分享方案', icon: 'success' });
    return true;
  },

  onReady() {
    this.initWorkspaceCanvases();
  },

  initDeviceLayout(options = {}) {
    const info = wx.getSystemInfoSync ? wx.getSystemInfoSync() : {};
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
    const bottomInsetRpx = Math.round(bottomInset * rpxRatio);
    const aspectRatio = windowHeight / windowWidth;
    const classes = ['device-regular'];
    if (windowWidth <= 340) classes.push('device-narrow');
    if (windowHeight <= 720) classes.push('device-short');
    if (windowHeight <= 780) classes.push('device-compact');
    if (aspectRatio >= 2.05) classes.push('device-tall');
    if (windowWidth >= 414) classes.push('device-wide');
    if (bottomInset > 0) classes.push('device-safe-bottom');
    if (statusBarHeight >= 40) classes.push('device-deep-status');
    if (isRealDevice) classes.push('device-real');
    if (isLowPerformanceDevice) classes.push('device-low-performance');
    this.isRealDevice = isRealDevice;
    this.isLowPerformanceDevice = isLowPerformanceDevice;
    this.physicsStepMs = isLowPerformanceDevice ? 34 : (isRealDevice ? 20 : 1000 / 60);
    this.physicsTimerInterval = isLowPerformanceDevice ? 34 : (isRealDevice ? 20 : 16);
    this.physicsRenderInterval = isLowPerformanceDevice ? 58 : (isRealDevice ? 34 : 24);
    this.materialPageSize = isLowPerformanceDevice ? 16 : 24;
    this.physicsFrameSequence = 0;
    const workspaceLayout = this.buildResponsiveWorkspaceLayout({
      windowWidth,
      windowHeight,
      viewportRpx,
      bottomInsetRpx,
      aspectRatio
    });
    this.stageLayout = workspaceLayout.stageLayout;
    this.setData({
      deviceClass: classes.join(' '),
      deviceInfo: {
        windowWidth,
        windowHeight,
        screenHeight,
        statusBarHeight,
        bottomInset,
        benchmarkLevel: benchmarkLevel || 0,
        isRealDevice,
        isLowPerformanceDevice
      },
      workspaceLayoutStyle: workspaceLayout.style,
      canUndo: this.historyStack.length > 0,
      canRedo: options.preserveActionState ? this.data.canRedo : false
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

  buildResponsiveWorkspaceLayout({ windowWidth, windowHeight, viewportRpx, bottomInsetRpx, aspectRatio }) {
    const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
    const isNarrow = windowWidth <= 340;
    const isShort = windowHeight <= 720 || viewportRpx <= 1420;
    const isCompact = windowHeight <= 780 || viewportRpx <= 1500;
    const isRoomy = viewportRpx >= 1600;
    const topChrome = 122;
    const summaryHeight = isShort || isNarrow ? 72 : 78;
    const colorTop = summaryHeight + (isShort ? 8 : 14);
    const colorBlockHeight = 0;
    const stageGapTop = isShort ? 8 : (isCompact ? 12 : 16);
    const stageTop = colorTop + colorBlockHeight + stageGapTop;
    const visualScale = 1.18;
    const drawerMin = isShort ? 400 : (isCompact ? 500 : 560);
    const drawerMax = isRoomy ? 760 : (isCompact ? 700 : 724);
    const drawerGap = isShort ? 14 : (isCompact ? 18 : 22);
    const maxStageByWidth = isNarrow ? 650 : (isShort ? 676 : (isRoomy ? 706 : 694));
    const minStage = isShort ? 550 : (isCompact ? 610 : 650);
    const maxStageByHeight = (viewportRpx - topChrome - drawerMin - stageTop - drawerGap) / visualScale;
    let stageSize = Math.round(clamp(maxStageByHeight, minStage, maxStageByWidth));
    if (maxStageByHeight < minStage) {
      stageSize = Math.max(420, Math.round(maxStageByHeight));
    }
    const trayVisualSize = stageSize * 1.26;
    const trayVisualLeft = (750 - stageSize) / 2 - stageSize * 0.13;
    const trayVisualTop = stageTop - stageSize * 0.13;
    const plateToolWidth = isShort || isNarrow ? 58 : 62;
    const plateToolHeight = isShort || isNarrow ? 58 : 62;
    const plateToolGap = isShort ? 18 : 22;
    const shareToolSize = plateToolWidth;
    const wristGuideWidth = shareToolSize;
    const wristGuideHeight = shareToolSize;
    const undoButtonSize = isShort || isNarrow ? 58 : 62;
    const wristButtonWidth = isShort || isNarrow ? 154 : 164;
    const wristButtonHeight = isShort || isNarrow ? 58 : 62;
    const leftStackGap = isShort ? 18 : 20;
    const randomButtonWidth = isShort || isNarrow ? 172 : 188;
    const randomButtonHeight = isShort || isNarrow ? 58 : 64;
    const randomDrawerGap = isShort ? 10 : 12;
    const themeWidth = wristButtonWidth;
    const themeHeight = wristButtonHeight;
    const preferredRandomButtonTop = Math.round(trayVisualTop + trayVisualSize - randomButtonHeight * 0.72);
    const idealDrawerHeight = viewportRpx - topChrome - preferredRandomButtonTop - randomButtonHeight - randomDrawerGap;
    const adaptiveDrawerMax = isRoomy ? Math.max(drawerMax, Math.round(viewportRpx * 0.52)) : drawerMax;
    const drawerHeight = Math.round(clamp(idealDrawerHeight, drawerMin, adaptiveDrawerMax));
    const drawerTopInCanvas = Math.max(360, viewportRpx - topChrome - drawerHeight);
    const railWidth = 90;
    const railSide = isShort || isNarrow ? 10 : 14;
    const railGap = isShort ? 14 : (isCompact ? 16 : 18);
    const toolItemHeight = isShort || isNarrow ? 94 : 100;
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
      stageTop + stageSize * (isShort ? 0.14 : 0.15),
      minRailTop,
      Math.max(minRailTop, drawerTopInCanvas - leftRailHeight - 16)
    ));
    const rightRailTop = Math.round(clamp(
      stageTop + stageSize * (isShort ? 0.17 : 0.18),
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
    const shareToolRadius = trayVisualSize / 2 + (isShort ? 8 : 10);
    const shareToolLeft = Math.round(clamp(
      trayVisualCenterX + shareToolRadius * 0.70 - shareToolSize / 2,
      510,
      750 - shareToolSize - (isShort || isNarrow ? 26 : 30)
    ));
    const shareToolTop = Math.round(clamp(
      trayVisualCenterY - shareToolRadius * 0.70 - shareToolSize / 2,
      colorTop + 10,
      leftOneTop - shareToolSize - 24
    ));
    const wristGuideLeft = Math.round(clamp(
      750 - shareToolLeft - wristGuideWidth,
      isShort || isNarrow ? 18 : 24,
      trayVisualCenterX - wristGuideWidth - 84
    ));
    const wristGuideTop = shareToolTop;
    const rightToolLeft = Math.round(clamp(
      750 - plateToolWidth - (isShort || isNarrow ? 22 : 28),
      24,
      750 - plateToolWidth - 20
    ));
    const rightOneTop = leftOneTop;
    const rightTwoTop = leftTwoTop;
    const rightThreeTop = themeTop;
    const randomButtonLeft = Math.round((750 - randomButtonWidth) / 2);
    const randomButtonTop = Math.round(drawerTopInCanvas - randomButtonHeight - randomDrawerGap);
    const toolHeight = toolItemHeight;
    const toolGap = railGap;
    const stageToolGap = drawerGap;
    const canvasHeight = Math.round(drawerTopInCanvas);
    const stageCenter = Math.round(stageSize / 2);
    const stageRadius = Math.round(stageSize * 0.39);
    return {
      stageLayout: {
        center: stageCenter,
        radius: stageRadius,
        size: stageSize,
        top: stageTop
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
        `--workspace-tool-bottom:${drawerHeight + toolGap}rpx`,
        `--workspace-tool-height:${toolHeight}rpx`,
        `--workspace-tool-gap:${toolGap}rpx`,
        `--workspace-stage-tool-gap:${stageToolGap}rpx`,
        `--workspace-safe-bottom:${bottomInsetRpx}rpx`
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
        this.setData({ materialsLoading: false, materialsErrorText: '' });
      }
    } catch (error) {
      logWorkspaceWarning('load materials fallback:', error.message || error);
      this.setData({
        materialsLoading: false,
        materialsErrorText: cachedPayload ? '已使用本地缓存，最新珠材稍后自动同步' : '珠材加载失败，请稍后重试'
      });
    }
  },

  loadMaterials() {
    return this.loadMaterialPage(1, { reset: true, useStorage: true });
  },

  isAllFilterValue(value) {
    return !value || LEGACY_ALL_OPTION_LABELS.includes(value);
  },

  materialRequestFilters() {
    const keyword = this.normalizeMaterialSearchKeyword(this.data.materialSearchKeyword);
    const hasKeyword = !!keyword;
    return {
      top: this.data.activeTop || 'bead',
      category: hasKeyword || this.isAllFilterValue(this.data.activeCategory) ? '' : this.data.activeCategory,
      series: hasKeyword || this.isAllFilterValue(this.data.activeSeries) ? '' : this.data.activeSeries,
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
      this.setData({
        visibleMaterials: [],
        hasMoreMaterials: false,
        materialsLoading: true,
        materialsLoadingMore: false,
        materialsErrorText: ''
      });
    } else {
      this.setData({ materialsLoadingMore: true, materialsErrorText: '' });
    }

    let cachedPayload = null;
    if (materialCache[cacheKey] && Date.now() - Number(materialCacheAt[cacheKey] || 0) < MATERIAL_CACHE_TTL) {
      cachedPayload = materialCache[cacheKey];
      this.applyPagedMaterialPayload(cachedPayload, { append: !reset, keepLoading: true, fromCache: true });
    } else if (options.useStorage && page === 1) {
      cachedPayload = await this.readStoredMaterialPage(cacheKey);
      if (cachedPayload) {
        if (this.materialPageRequesting !== cacheKey || this.materialRequestKey(page) !== cacheKey) return;
        materialCache[cacheKey] = cachedPayload;
        materialCacheAt[cacheKey] = Date.now();
        this.applyPagedMaterialPayload(cachedPayload, { append: false, keepLoading: true, fromCache: true });
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
      if (this.materialPageRequesting !== cacheKey || this.materialRequestKey(page) !== cacheKey) return;
      const optimized = this.optimizeMaterialPayload(data);
      this.storeMaterialPage(cacheKey, optimized);
      this.applyPagedMaterialPayload(optimized, { append: !reset });
    } catch (error) {
      logWorkspaceWarning('load materials fallback:', error.message || error);
      this.setData({
        materialsLoading: false,
        materialsLoadingMore: false,
        materialsErrorText: cachedPayload ? '已使用本地缓存，最新珠材稍后自动同步' : '珠材加载失败，请稍后重试'
      });
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
    const effects = energy.effects || item.effects || [];
    const primaryElement = energy.primary_element || item.primary_element || item.element || '';
    return {
      ...item,
      sku,
      energy,
      visual,
      rules,
      id: sku.id || item.id,
      skuId: sku.sku_id || item.skuId || item.sku_id,
      material_code: sku.material_code || item.material_code,
      top: sku.top || item.top,
      category: sku.category || item.category,
      series: sku.series || item.series,
      grade: sku.grade || item.grade,
      name: sku.name || item.name,
      price: Number(sku.price_per_bead ?? item.price ?? 0),
      size: Number(sku.size_mm ?? item.size ?? 8),
      weight: Number(sku.weight_g ?? item.weight ?? 1),
      stock: Number(sku.stock ?? item.stock ?? 0),
      enabled: sku.enabled ?? item.enabled,
      sort_order: Number(sku.sort_order ?? item.sort_order ?? item.sortOrder ?? 0),
      element: primaryElement,
      primary_element: primaryElement,
      secondary_elements: energy.secondary_elements || item.secondary_elements || [],
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
      conflict_codes: rules.conflict_codes || item.conflict_codes || [],
      material_params: visual.material_params || item.material_params || {}
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
    const previousCatalog = this.materialCatalog || DEFAULT_MATERIALS;
    const nextCatalog = data.materials && data.materials.length ? data.materials : DEFAULT_MATERIALS;
    const topTabs = (data.top_tabs || TOP_TABS).filter(item => item.key !== 'incense');
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
    });
    this.materialCatalog = nextCatalog;
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
    });
    this.refreshFilters();
    if (this.pendingSharedDesign || this.pendingBackendRecommendation || this.pendingRecommendedRecipe) {
      this.ensurePendingMaterialDetails({ silent: true, keepPendingOnEmpty: true });
      return;
    }
    this.recalculate();
  },

  mergeMaterialCatalog(materials = []) {
    const byId = {};
    (this.materialCatalog || DEFAULT_MATERIALS).forEach(item => {
      if (item && item.id) byId[item.id] = item;
    });
    (materials || []).forEach(item => {
      if (item && item.id) byId[item.id] = item;
    });
    this.materialCatalog = Object.keys(byId).map(id => byId[id]);
  },

  applyPagedMaterialPayload(data, options = {}) {
    const materials = data.materials && data.materials.length ? data.materials : [];
    const pagination = data.pagination || {};
    this.mergeMaterialCatalog(materials);
    this.materialPayloadReady = true;
    const topTabs = (data.top_tabs || this.data.topTabs || TOP_TABS).filter(item => item.key !== 'incense');
    const activeTop = topTabs.some(item => item.key === this.data.activeTop) ? this.data.activeTop : 'bead';
    this.categoriesByTop = data.categories_by_top || this.categoriesByTop || {};
    this.seriesByCategory = data.series_by_category || this.seriesByCategory || {};
    const searchTarget = !options.append ? this.resolveMaterialSearchTarget(materials) : null;
    let categoryNames = (this.categoriesByTop || {})[activeTop] || [ALL_OPTION_LABEL];
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
    const categoryRailSeries = this.buildCategoryRailSeries(seriesOptions, activeCategory, activeSeries);
    const activeCategoryAnchor = this.getActiveOptionAnchor(decoratedCategories);
    const activeSeriesAnchor = this.getActiveOptionAnchor(decoratedSeriesOptions);
    const currentMaterials = options.append ? (this.data.visibleMaterials || []) : [];
    const visibleMaterials = this.decorateVisibleMaterials([...currentMaterials, ...materials]);
    const total = Number(pagination.total || visibleMaterials.length || materials.length || 0);
    const filterSummary = `${activeCategory} · ${activeSeries} · ${total} 款`;
    this.materialPageState = {
      page: Number(pagination.page || 1),
      pageSize: Number(pagination.page_size || this.materialPageSize || MATERIAL_PAGE_SIZE),
      total,
      hasMore: !!pagination.has_more,
      key: this.materialRequestKey(1)
    };
    this.setData({
      topTabs: this.decorateOptionList(topTabs, activeTop, 'key'),
      activeTop,
      categories: decoratedCategories,
      activeCategory,
      activeCategoryAnchor,
      categoryRailSeries,
      seriesOptions: decoratedSeriesOptions,
      activeSeries,
      activeSeriesAnchor,
      visibleMaterials,
      hasMoreMaterials: !!pagination.has_more,
      materialsLoading: !!options.keepLoading,
      materialsLoadingMore: false,
      materialsErrorText: '',
      filterSummary
    }, () => {
      this.scheduleMaterialPreload(visibleMaterials);
    });

    if (this.pendingSharedDesign || this.pendingBackendRecommendation || this.pendingRecommendedRecipe) {
      this.ensurePendingMaterialDetails({ silent: true, keepPendingOnEmpty: true });
      return;
    }
    this.ensurePendingMaterialDetails();
    this.ensureMissingSelectedMaterials();
    this.recalculate();
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
      recipe.forEach(id => ids.push(LEGACY_ID_MAP[id] || id));
    }
    return Array.from(new Set(ids.map(id => String(id || '').trim()).filter(Boolean)));
  },

  async ensurePendingMaterialDetails(options = {}) {
    const missing = this.pendingMaterialIds().filter(id => !this.hasResolvableMaterialIdentifier(id));
    if (missing.length) {
      await this.fetchMaterialsByIds(missing);
    }
    let applied = false;
    const applyOptions = {
      silent: options.silent !== false,
      keepPendingOnEmpty: options.keepPendingOnEmpty !== false
    };
    if (this.pendingSharedDesign) {
      applied = this.applySharedDesign(this.pendingSharedDesign, applyOptions) || applied;
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
    if (!missing.length) return;
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
  },

  async fetchMaterialsByIds(ids = []) {
    const missing = Array.from(new Set((ids || []).filter(Boolean))).filter(id => !this.hasResolvableMaterialIdentifier(id));
    if (!missing.length) return;
    const requestKey = missing.sort().join(',');
    if (this.materialDetailsRequesting === requestKey) return;
    this.materialDetailsRequesting = requestKey;
    try {
      const data = await getMaterials({ ids: missing, slim: true, silent: true, timeout: 8000 });
      const optimized = this.optimizeMaterialPayload(data);
      this.mergeMaterialCatalog(optimized.materials || []);
    } catch (error) {
      logWorkspaceWarning('load selected material details fallback:', error.message || error);
    } finally {
      this.materialDetailsRequesting = '';
    }
  },

  findMaterialById(id) {
    return (this.materialCatalog || DEFAULT_MATERIALS).find(material => material.id === id);
  },

  pickMaterialImageUrl(material = {}) {
    const pool = (material.image_urls || material.image_pool || [])
      .concat(material.image_url || [])
      .filter(Boolean);
    if (!pool.length) return '';
    return pool[Math.floor(Math.random() * pool.length)];
  },

  normalizeImageUrlIdentity(url = '') {
    return String(url || '').split('?')[0];
  },

  findCurrentMaterialImageUrl(id, imageUrl) {
    if (!imageUrl) return '';
    const material = this.findMaterialById(id) || {};
    const target = this.normalizeImageUrlIdentity(imageUrl);
    return (material.image_urls || material.image_pool || [])
      .concat(material.image_url || [])
      .filter(Boolean)
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
    (normalized.sequence || []).forEach(item => {
      this.sharedSequenceMaterialIdentifiers(item).forEach(id => ids.push(id));
    });
    return Array.from(new Set(ids.map(id => String(id || '').trim()).filter(Boolean)));
  },

  resolveSharedDesignSelectedIds(normalized = {}) {
    const selected = [];
    const rawSelected = normalized.selected || [];
    const sequence = normalized.sequence || [];
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
      if (resolvedId) selected.push(resolvedId);
    }
    return selected;
  },

  materialSearchText(material = {}) {
    return [
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
  },

  normalizeMaterialSearchKeyword(value) {
    return String(value || '').trim().replace(/\s+/g, ' ');
  },

  materialMatchesSearch(material = {}, keyword = this.data.materialSearchKeyword) {
    const normalized = this.normalizeMaterialSearchKeyword(keyword).toLowerCase();
    if (!normalized) return true;
    const searchText = this.materialSearchText(material);
    return normalized.split(' ').filter(Boolean).every(term => searchText.includes(term));
  },

  resolveMaterialSearchTarget(materials = []) {
    const keyword = this.normalizeMaterialSearchKeyword(this.data.materialSearchKeyword);
    if (!keyword) return null;
    return (materials || []).find(item => this.materialMatchesSearch(item, keyword))
      || (materials || []).find(Boolean)
      || null;
  },

  materialElementKey(material = {}) {
    const elementKey = ELEMENT_CN_TO_EN[material.primary_element || material.element];
    if (elementKey) return elementKey;
    const skuKey = MATERIAL_ELEMENT_KEY[material.skuId];
    if (skuKey) return skuKey;
    const text = this.materialSearchText(material);
    if (/金|银|白|钛|发晶|铁|曜|耀/.test(text)) return 'metal';
    if (/绿|木|松|幽灵|东陵/.test(text)) return 'wood';
    if (/蓝|海|水|黑/.test(text)) return 'water';
    if (/红|南红|玛瑙|石榴|火|粉|草莓/.test(text)) return 'fire';
    if (/黄|茶|烟|土|虎眼/.test(text)) return 'earth';
    return '';
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
    const catalog = (this.materialCatalog || DEFAULT_MATERIALS).filter(item => item.top === 'bead');
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
    const sizeByCode = {};
    const materialByCode = {};
    (plan.items || []).forEach(item => {
      if (item && item.code) sizeByCode[item.code] = Number(item.bead_size_mm) || Number(plan.bead_size_mm) || 8;
      if (item && item.code && (item.material_id || item.source_material_id || item.id)) {
        materialByCode[item.code] = item.material_id || item.source_material_id || item.id;
      }
    });
    return (plan.layout || [])
      .map(item => {
        const explicitId = item.material_id || item.source_material_id || materialByCode[item.crystal_code] || '';
        const resolvedExplicitId = explicitId ? this.resolveMaterialId(explicitId) : '';
        if (resolvedExplicitId && this.hasMaterial(resolvedExplicitId)) return resolvedExplicitId;
        return this.resolveBackendCrystalMaterialId(
          item.crystal_code,
          sizeByCode[item.crystal_code] || Number(item.bead_size_mm) || Number(plan.bead_size_mm) || Number(payload.bead_size_mm) || 8
        );
      })
      .filter(Boolean);
  },

  onShow() {
    wx.hideTabBar({ animation: false });
    if (this.deferFirstShowProfileEnergy) {
      this.deferFirstShowProfileEnergy = false;
    } else {
      this.loadProfileEnergy();
    }
    if (this.data.useCanvasRenderer) this.scheduleCanvasRender();
    if (this.data.isLooseMode && this.physicsEngine) this.runPhysics();
    if (wx.getStorageSync('workspaceOpenDesign')) {
      wx.removeStorageSync('workspaceOpenDesign');
      this.pendingBackendRecommendation = false;
      this.pendingRecommendedRecipe = false;
      this.loadDraft();
      return;
    }
    if (wx.getStorageSync('workspacePreset') === 'backend-recommended') {
      wx.removeStorageSync('workspacePreset');
      this.pendingBackendRecommendation = true;
      this.applyBackendRecommendation();
      return;
    }
    if (wx.getStorageSync('workspacePreset') === 'recommended') {
      wx.removeStorageSync('workspacePreset');
      this.pendingRecommendedRecipe = true;
      this.applyRecommendedRecipe();
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
    clearTimeout(this.shuffleTimer);
    clearTimeout(this.canvasResizeTimer);
    clearTimeout(this.audioPrewarmTimer);
    clearTimeout(this.nonCriticalTaskTimer);
    clearTimeout(this.materialPreloadTimer);
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
    this.stopPhysics();
    wx.showTabBar({ animation: false });
  },

  onHide() {
    this.pausePhysics();
    this.stopCanvasRenderLoop();
    wx.showTabBar({ animation: false });
  },

  loadDraft() {
    const draft = wx.getStorageSync('currentDesign');
    this.resetWorkspaceRuntime();
    if (draft && draft.selected && draft.selected.length) {
      this.setData({
        selected: draft.selected.map(id => LEGACY_ID_MAP[id] || id),
        placements: this.normalizePlacements(draft.selected, draft.placements),
        isLooseMode: draft.isLooseMode === true,
        wristSize: this.normalizeWristValue(draft.wristSize || this.data.wristSize || 16),
        wearStyle: 'single',
        canvasFlightActive: false,
        flightBead: null,
        launchingMaterialId: '',
        isShuffling: false,
        isStringingFinishing: false,
        selectedBeadIndex: -1,
        draggingBeadIndex: -1,
        dragDeleteArmed: false
      });
      this.recalculate();
    } else {
      this.resetInteractionData({
        selected: [],
        placements: [],
        selectedItems: [],
        selectedBeadIndex: -1,
        isLooseMode: true
      }, () => this.recalculate());
    }
  },

  applyRecommendedRecipe(options = {}) {
    if (!this.materialPayloadReady) return false;
    const recipe = wx.getStorageSync('recommendedRecipe') || ['aquamarine', 'amethyst', 'clearQuartz', 'moonstone'];
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
      goldSpacer: 'goldSpacer',
      foxPendant: 'foxPendant'
    };
    const materialIds = (recipe.length ? recipe : ['aquamarine', 'amethyst', 'clearQuartz', 'moonstone'])
      .map(id => this.resolveMaterialId(idMap[id] || id))
      .filter(id => this.hasMaterial(id));
    const selected = [];
    const targetLengthMm = wristSize * 10 + 8;
    let currentLengthMm = 0;
    let cursor = 0;
    while (materialIds.length && currentLengthMm < targetLengthMm && selected.length < 40) {
      const materialId = materialIds[cursor % materialIds.length];
      const material = this.findMaterialById(materialId);
      selected.push(materialId);
      currentLengthMm += material ? material.size : 8;
      cursor += 1;
    }
    if (!selected.length) {
      if (!options.silent) wx.showToast({ title: '暂未匹配到可用珠材', icon: 'none' });
      if (!options.keepPendingOnEmpty) this.pendingRecommendedRecipe = false;
      return false;
    }
    this.pendingRecommendedRecipe = false;
    this.resetWorkspaceRuntime();
    this.pushHistory();
    wx.setStorageSync('recommendedWristSize', wristSize);
    wx.setStorageSync('workspaceWristConfirmed', true);
    this.setData({
      wristSize,
      selected,
      placements: this.normalizePlacements(selected),
      isLooseMode: false,
      selectedBeadIndex: -1,
      canvasFlightActive: false,
      flightBead: null,
      launchingMaterialId: '',
      isShuffling: false,
      isStringingFinishing: false,
      draggingBeadIndex: -1,
      dragDeleteArmed: false
    });
    this.recalculate();
    return true;
  },

  applyBackendRecommendation(options = {}) {
    const payload = wx.getStorageSync('diyWorkbenchPayload');
    if (!payload || !payload.bracelet_plan || !payload.bracelet_plan.layout) {
      if (!options.silent) wx.showToast({ title: '未找到推荐方案', icon: 'none' });
      if (!options.keepPendingOnEmpty) {
        this.pendingBackendRecommendation = false;
        this.loadDraft();
      }
      return false;
    }
    if (!this.materialPayloadReady) return false;
    const selected = this.buildBackendRecommendationSelected(payload);
    if (!selected.length) {
      if (!options.silent) wx.showToast({ title: '推荐方案暂未匹配到可用珠材', icon: 'none' });
      if (!options.keepPendingOnEmpty) this.pendingBackendRecommendation = false;
      return false;
    }
    const sourceContext = payload.source_context || {
      source: payload.source || 'backend_recommendation',
      source_label: payload.source_label || '推荐方案',
      date: payload.date || '',
      keyword: payload.keyword || '',
      title: payload.bracelet_plan.title || ''
    };
    this.sourceContext = sourceContext;
    const wristSize = Number(payload.wrist_size_cm) || Number(wx.getStorageSync('recommendedWristSize')) || this.data.wristSize || 16;
    this.pendingBackendRecommendation = false;
    this.resetWorkspaceRuntime();
    this.pushHistory();
    wx.setStorageSync('recommendedWristSize', wristSize);
    wx.setStorageSync('workspaceWristConfirmed', true);
    this.setData({
      wristSize,
      selected,
      placements: this.normalizePlacements(selected),
      isLooseMode: false,
      selectedBeadIndex: -1,
      showTip: false,
      canvasFlightActive: false,
      flightBead: null,
      launchingMaterialId: '',
      isShuffling: false,
      isStringingFinishing: false,
      draggingBeadIndex: -1,
      dragDeleteArmed: false,
      sourceContext
    });
    this.recalculate();
    if (!options.silent) wx.showToast({ title: '已载入专属推荐', icon: 'success' });
    return true;
  },

  normalizePlacements(selected, placements) {
    const normalized = [];
    selected.forEach((id, index) => {
      const previous = placements && placements[index];
      const loose = previous && Number.isFinite(previous.looseX) && Number.isFinite(previous.looseY)
        ? previous
        : this.createLoosePlacement(index, id, normalized);
      normalized.push({
        id,
        image_url: this.findCurrentMaterialImageUrl(id, previous && previous.image_url)
          || this.pickMaterialImageUrl(this.findMaterialById(id) || {}),
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
    return material ? Math.max(42, Math.min(78, material.size * 5.4)) : 54;
  },

  createLoosePlacement(index, id, existingPlacements = []) {
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
      image_url: this.pickMaterialImageUrl(this.findMaterialById(id) || {}),
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

    const wallCount = this.isLowPerformanceDevice ? 32 : 40;
    const wallRadius = layout.center - 8;
    const wallThickness = 28;
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
          restitution: 0.72,
          friction: 0.022,
          label: 'tray-wall'
        }
      );
      walls.push(wall);
    }
    Composite.add(engine.world, walls);
    this.bindPhysicsCollisionSound(engine);
    this.physicsEngine = engine;
    this.physicsBodies = [];
  },

  ensurePhysicsRuntime() {
    if (Engine) return;
    const Matter = require('../../utils/vendor/matter.min');
    ({ Body, Bodies, Composite, Engine, Events } = Matter);
  },

  ensureAudioPlayers() {
    if (!wx.createInnerAudioContext || this.audioPlayersReady) return;
    const createPlayer = (src, name) => {
      const audio = wx.createInnerAudioContext();
      audio.obeyMuteSwitch = false;
      audio.autoplay = false;
      audio.loop = false;
      audio.startTime = 0;
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
    const cursor = Number(this.audioPlayerCursors[name] || 0);
    this.audioPlayerCursors[name] = cursor + 1;
    return pool[cursor % pool.length];
  },

  playSoundEffect(name, throttleMs = 0) {
    if (!this.soundEnabled) return;
    this.ensureAudioPlayers();
    const audio = this.pickAudioPlayer(name);
    if (!audio) return;
    const now = Date.now();
    const lastAt = Number(this.lastSoundAt[name] || 0);
    if (throttleMs && now - lastAt < throttleMs) return;
    this.lastSoundAt[name] = now;
    try {
      if (audio.__playing && audio.stop) audio.stop();
      audio.startTime = 0;
      audio.__playing = true;
      audio.play();
    } catch (error) {
      audio.__playing = false;
      logWorkspaceWarning('play sound failed:', name, error.message || error);
    }
  },

  bindPhysicsCollisionSound(engine) {
    if (!engine || !Events) return;
    if (this.physicsCollisionBoundEngine === engine) return;
    this.physicsCollisionBoundEngine = engine;
    Events.on(engine, 'collisionStart', event => {
      const pairs = event && event.pairs ? event.pairs : [];
      if (!pairs.length) return;
      this.handleFrozenImpactCollision(pairs);
      let maxRelSpeed = 0;
      let impactVector = null;
      pairs.forEach(pair => {
        const bodyA = pair.bodyA;
        const bodyB = pair.bodyB;
        if (!bodyA || !bodyB) return;
        const plugA = bodyA.plugin || {};
        const plugB = bodyB.plugin || {};
        const beadA = plugA.materialId && plugA.designIndex != null;
        const beadB = plugB.materialId && plugB.designIndex != null;
        if (!beadA && !beadB) return;
        const relSpeed = Math.sqrt(
          (bodyA.velocity.x - bodyB.velocity.x) ** 2 +
          (bodyA.velocity.y - bodyB.velocity.y) ** 2
        );
        if (relSpeed > maxRelSpeed) {
          maxRelSpeed = relSpeed;
          impactVector = {
            x: bodyA.velocity.x - bodyB.velocity.x,
            y: bodyA.velocity.y - bodyB.velocity.y
          };
        }
      });
      if (maxRelSpeed <= 0.9) return;
      const now = Date.now();
      if (!this.lastTrayImpactAt || now - this.lastTrayImpactAt > 90) {
        this.lastTrayImpactAt = now;
        this.triggerTrayImpactFeedback(impactVector || { x: 1, y: 0 });
      }
      const soundName = maxRelSpeed > 2.4
        ? 'collisionBright'
        : (maxRelSpeed > 1.45 ? 'collision' : 'collisionSoft');
      if (this.soundEnabled) this.playSoundEffect(soundName, 40);
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

  releaseFrozenBodiesFromImpact(launcher, hitBody) {
    if (!this.pendingFrozenImpact || !Body) return;
    this.pendingFrozenImpact = false;
    const origin = (launcher && launcher.position) || this.getStageLayout();
    const launchVelocity = (launcher && launcher.velocity) || { x: 1, y: 0 };
    const launchSpeed = Math.sqrt(launchVelocity.x ** 2 + launchVelocity.y ** 2) || 1;
    const baseSpeed = Math.max(1.2, Math.min(4.8, launchSpeed * 0.18));
    (this.physicsBodies || []).forEach((body, index) => {
      if (!body || !body.plugin || !body.plugin.frozenUntilImpact) return;
      const dx = body.position.x - origin.x;
      const dy = body.position.y - origin.y;
      const distance = Math.max(1, Math.sqrt(dx * dx + dy * dy));
      const nearBoost = body === hitBody ? 1.55 : Math.max(0.55, 1.2 - distance / 520);
      Body.setStatic(body, false);
      body.plugin.frozenUntilImpact = false;
      Body.setVelocity(body, {
        x: dx / distance * baseSpeed * nearBoost + launchVelocity.x * 0.08,
        y: dy / distance * baseSpeed * nearBoost + launchVelocity.y * 0.08
      });
      Body.setAngularVelocity(body, (index % 2 ? 1 : -1) * 0.035 * nearBoost);
    });
    this.triggerTrayImpactFeedback(launchVelocity);
    if (this.pendingImpactTargets && this.pendingImpactTargets.length) {
      this.physicsTargets = this.pendingImpactTargets;
      this.pendingImpactTargets = null;
      this.stringingStartedAt = Date.now();
      this.physicsStillFrames = 0;
    }
    this.playSoundEffect('collisionBright', 0);
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
    if (!this.data.useCanvasRenderer || this.data.workspaceCanvasVisible === false) return;
    clearTimeout(this.canvasResizeTimer);
    this.canvasResizeTimer = setTimeout(() => this.initWorkspaceCanvases(), 120);
  },

  initWorkspaceCanvases() {
    if (!this.data.useCanvasRenderer || this.data.workspaceCanvasVisible === false) return;
    const query = wx.createSelectorQuery().in(this);
    query.select('#braceletCanvas').fields({ node: true, size: true });
    query.select('#workspaceFlightCanvas').fields({ node: true, size: true });
    query.select('.bracelet-circle').boundingClientRect();
    query.exec(res => {
      const braceletInfo = res && res[0];
      const flightInfo = res && res[1];
      const circleRect = res && res[2];
      const braceletCanvasState = this.setupCanvasNode(braceletInfo, circleRect);
      if (!braceletCanvasState || !braceletCanvasState.ctx) {
        this.switchToDomRendererFallback('bracelet canvas unavailable');
        return;
      }
      this.braceletCanvasState = braceletCanvasState;
      this.flightCanvasState = this.setupCanvasNode(flightInfo, {
        left: 0,
        top: 0,
        width: (this.data.deviceInfo && this.data.deviceInfo.windowWidth) || 375,
        height: (this.data.deviceInfo && this.data.deviceInfo.windowHeight) || 667
      });
      this.canvasImageCache = this.canvasImageCache || {};
      this.materialImagePreloadSet = this.materialImagePreloadSet || {};
      this.scheduleCanvasRender();
      this.scheduleMaterialPreload(this.data.visibleMaterials);
    });
  },

  switchToDomRendererFallback(reason = '') {
    if (!this.data.useCanvasRenderer) return;
    logWorkspaceWarning('workspace canvas fallback:', reason);
    this.stopCanvasRenderLoop();
    this.braceletCanvasState = null;
    this.flightCanvasState = null;
    this.canvasImageCache = {};
    this.canvasTextureCache = {};
    this.materialImagePreloadSet = {};
    this.canvasFlight = null;
    this.setData({
      useCanvasRenderer: false,
      canvasFlightActive: false
    }, () => this.recalculate({ persist: false }));
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

  scheduleCanvasRender(keepLoop = false) {
    if (!this.data.useCanvasRenderer || this.data.workspaceCanvasVisible === false) return;
    this.canvasKeepLoop = this.canvasKeepLoop || keepLoop;
    if (this.canvasFramePending) return;
    this.canvasFramePending = true;
    this.canvasFrame = this.requestCanvasFrame(() => {
      this.canvasFramePending = false;
      if (this.data.workspaceCanvasVisible === false) return;
      this.renderBraceletCanvas();
      this.renderWorkspaceFlightCanvas();
      const shouldContinue = this.canvasKeepLoop
        || !!this.physicsTimer
        || !!this.canvasFlight
        || !!this.dragState
        || !!this.ringDragState
        || this.data.isShuffling;
      this.canvasKeepLoop = false;
      if (shouldContinue) this.scheduleCanvasRender(true);
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
    this.setData({
      workspaceCanvasVisible: false,
      canvasFlightActive: false
    });
  },

  restoreWorkspaceCanvasAfterOverlay() {
    if (this.data.workspaceCanvasVisible) return;
    this.setData({ workspaceCanvasVisible: true }, () => {
      wx.nextTick(() => {
        this.initWorkspaceCanvases();
        if (this.data.useCanvasRenderer) this.scheduleCanvasRender();
      });
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
    const progress = flight.easing === 'linear' ? raw : this.easeOutCubic(raw);
    const point = flight.path === 'line'
      ? {
        x: flight.start.x + (flight.end.x - flight.start.x) * progress,
        y: flight.start.y + (flight.end.y - flight.start.y) * progress
      }
      : this.quadraticBezier(flight.start, flight.control, flight.end, progress);
    const size = flight.sourceSize + (flight.targetSize - flight.sourceSize) * progress;
    const rotation = flight.rotation + flight.rotationDelta * progress;
    this.drawCanvasBead(ctx, {
      item: flight.material,
      x: point.x,
      y: point.y,
      size,
      rotation,
      active: false,
      deleteReady: false,
      screenSpace: true
    });
  },

  renderBraceletCanvas() {
    const state = this.braceletCanvasState;
    if (!state || !state.ctx) return;
    const ctx = state.ctx;
    ctx.clearRect(0, 0, state.width, state.height);
    const impactOffset = this.getCanvasImpactOffset();
    ctx.save();
    ctx.translate(impactOffset.x, impactOffset.y);
    const sprites = this.getCanvasBeadSprites();
    const normal = [];
    const floating = [];
    sprites.forEach(sprite => {
      if (sprite.dragging || sprite.active) floating.push(sprite);
      else normal.push(sprite);
    });
    normal.concat(floating).forEach(sprite => this.drawCanvasBead(ctx, sprite));
    ctx.restore();
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
      (items || []).map(item => `${item.id}:${item.size}`).join('|')
    ].join('::');
    if (this.canvasGeometryCache && this.canvasGeometryCache.key === key) {
      return this.canvasGeometryCache.geometry;
    }
    const geometry = this.calculateBraceletGeometry(items || []);
    this.canvasGeometryCache = { key, geometry };
    return geometry;
  },

  getCanvasImage(url) {
    if (!url || !this.braceletCanvasState || !this.braceletCanvasState.canvas) return null;
    this.canvasImageCache = this.canvasImageCache || {};
    const cached = this.canvasImageCache[url];
    if (cached && cached.loaded) return cached.image;
    if (cached && cached.loading) return null;
    const image = this.braceletCanvasState.canvas.createImage();
    const entry = { image, loading: true, loaded: false, failed: false };
    this.canvasImageCache[url] = entry;
    image.onload = () => {
      entry.loading = false;
      entry.loaded = true;
      this.scheduleCanvasRender();
    };
    image.onerror = () => {
      entry.loading = false;
      entry.failed = true;
      this.scheduleCanvasRender();
    };
    image.src = url;
    return null;
  },

  preloadVisibleCanvasImages(materials = []) {
    if (!this.data.useCanvasRenderer || !this.braceletCanvasState || !this.braceletCanvasState.canvas) return;
    const preloadCount = this.isLowPerformanceDevice ? 4 : 8;
    (materials || [])
      .slice(0, preloadCount)
      .forEach(item => {
        if (item && item.image_url) this.getCanvasImage(item.image_url);
      });
  },

  scheduleMaterialPreload(materials = []) {
    clearTimeout(this.materialPreloadTimer);
    const delay = this.isLowPerformanceDevice ? 420 : 180;
    this.materialPreloadTimer = setTimeout(() => {
      this.preloadMaterialImages(materials);
      this.preloadVisibleCanvasImages(materials);
    }, delay);
  },

  preloadMaterialImages(materials = []) {
    if (!wx.getImageInfo) return;
    this.materialImagePreloadSet = this.materialImagePreloadSet || {};
    const preloadCount = this.isLowPerformanceDevice ? 4 : 10;
    (materials || [])
      .slice(0, preloadCount)
      .forEach(item => {
        const url = item && item.image_url;
        if (!url || this.materialImagePreloadSet[url]) return;
        this.materialImagePreloadSet[url] = true;
        wx.getImageInfo({
          src: url,
          success: () => {},
          fail: () => {}
        });
      });
  },

  getCanvasBeadTexture(item = {}, size = 64) {
    const dpr = (this.braceletCanvasState && this.braceletCanvasState.dpr) || 1;
    const baseSize = Math.round(Number(size) || 64);
    const bucket = Math.max(64, Math.min(item.image_url ? 256 : 160, Math.round(baseSize * dpr)));
    const key = `${item.id || item.skuId || item.image_url || item.name || 'bead'}::${item.image_url || item.color || ''}::${bucket}`;
    this.canvasTextureCache = this.canvasTextureCache || {};
    const cached = this.canvasTextureCache[key];
    if (cached && cached.ready) return cached.canvas;
    if (!wx.createOffscreenCanvas) return null;
    const sourceImage = item.image_url ? this.getCanvasImage(item.image_url) : null;
    if (item.image_url && !sourceImage) return null;
    try {
      const canvas = wx.createOffscreenCanvas({ type: '2d', width: bucket, height: bucket });
      const ctx = canvas.getContext('2d');
      const radius = bucket / 2;
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
      if (sourceImage) {
        const imageInset = -bucket * 0.025;
        ctx.globalAlpha = 0.98;
        ctx.drawImage(sourceImage, imageInset, imageInset, bucket - imageInset * 2, bucket - imageInset * 2);
        ctx.globalAlpha = 1;
      } else {
        ctx.fillStyle = 'rgba(255,255,255,0.52)';
        ctx.beginPath();
        ctx.arc(bucket * 0.38, bucket * 0.34, bucket * 0.11, 0, Math.PI * 2);
        ctx.fill();
      }
      const shade = ctx.createRadialGradient(bucket * 0.36, bucket * 0.32, bucket * 0.08, radius, radius, radius);
      shade.addColorStop(0, 'rgba(255,255,255,0.03)');
      shade.addColorStop(0.62, 'rgba(255,255,255,0)');
      shade.addColorStop(1, sourceImage ? 'rgba(0,0,0,0.12)' : 'rgba(0,0,0,0.20)');
      ctx.fillStyle = shade;
      ctx.fillRect(0, 0, bucket, bucket);
      ctx.restore();
      ctx.beginPath();
      ctx.arc(radius, radius, radius - 0.8, 0, Math.PI * 2);
      ctx.strokeStyle = sourceImage ? 'rgba(32,32,31,0.18)' : 'rgba(255,255,255,0.16)';
      ctx.lineWidth = sourceImage ? 1.2 : 0.8;
      ctx.stroke();
      this.canvasTextureCache[key] = { ready: true, canvas };
      return canvas;
    } catch (error) {
      this.canvasTextureCache[key] = { ready: false, failed: true };
      return null;
    }
  },

  drawCanvasBead(ctx, sprite) {
    if (!ctx || !sprite || !sprite.item) return;
    const size = Math.max(8, Number(sprite.size) || 48);
    const radius = size / 2;
    ctx.save();
    ctx.globalAlpha = sprite.deleteReady ? 0.58 : 1;
    ctx.translate(sprite.x, sprite.y);
    ctx.rotate((Number(sprite.rotation) || 0) * Math.PI / 180);
    ctx.save();
    ctx.shadowColor = 'rgba(42, 31, 22, 0.20)';
    ctx.shadowBlur = sprite.screenSpace ? 6 : 8;
    ctx.shadowOffsetY = sprite.screenSpace ? 2 : 3;
    ctx.fillStyle = 'rgba(0,0,0,0.02)';
    ctx.beginPath();
    ctx.arc(0, 0, radius - 0.6, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
    if (sprite.active || sprite.deleteReady) {
      ctx.save();
      ctx.beginPath();
      ctx.arc(0, 0, radius + (sprite.deleteReady ? 5 : 4), 0, Math.PI * 2);
      ctx.strokeStyle = sprite.deleteReady ? 'rgba(188, 62, 55, 0.86)' : 'rgba(18, 18, 18, 0.82)';
      ctx.lineWidth = sprite.deleteReady ? 3 : 2.5;
      ctx.stroke();
      ctx.restore();
    }
    ctx.save();
    ctx.beginPath();
    ctx.arc(0, 0, radius, 0, Math.PI * 2);
    ctx.clip();
    const hasImage = Boolean(sprite.item.image_url);
    const texture = this.getCanvasBeadTexture(sprite.item, size);
    const image = texture ? null : this.getCanvasImage(sprite.item.image_url);
    if (texture) {
      ctx.drawImage(texture, -radius, -radius, size, size);
    } else if (image) {
      ctx.drawImage(image, -radius, -radius, size, size);
    } else {
      const gradient = ctx.createRadialGradient(-radius * 0.28, -radius * 0.34, radius * 0.06, 0, 0, radius);
      gradient.addColorStop(0, sprite.item.shine || '#ffffff');
      gradient.addColorStop(0.18, sprite.item.color || '#d8d2c8');
      gradient.addColorStop(0.72, sprite.item.color || '#d8d2c8');
      gradient.addColorStop(1, 'rgba(32,24,18,0.34)');
      ctx.fillStyle = gradient;
      ctx.fillRect(-radius, -radius, size, size);
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
      ctx.fillRect(-radius, -radius, size, size);
    }
    ctx.restore();
    ctx.beginPath();
    ctx.arc(0, 0, radius - 1, 0, Math.PI * 2);
    ctx.strokeStyle = hasImage ? 'rgba(32,32,31,0.20)' : 'rgba(255,255,255,0.16)';
    ctx.lineWidth = hasImage ? 1.1 : 0.8;
    ctx.stroke();
    ctx.restore();
  },

  getCanvasBeadSprites() {
    const selected = this.data.selected || [];
    if (!selected.length) return [];
    const placements = this.normalizePlacements(selected, this.livePlacements || this.data.placements);
    const items = selected.map((id, index) => {
      const material = this.findMaterialById(id);
      if (!material) return null;
      const placement = placements[index] || {};
      return {
        ...material,
        image_url: placement.image_url || material.image_url || ''
      };
    }).filter(Boolean);
    const geometry = this.getCachedBraceletGeometry(items);
    const layout = this.getStageLayout();
    const logicalSize = layout.center * 2;
    const state = this.braceletCanvasState;
    const scale = state && state.width ? state.width / logicalSize : 1;
    const bodyByIndex = {};
    (this.physicsBodies || []).forEach(body => {
      if (body && body.plugin && body.plugin.designIndex != null) {
        bodyByIndex[body.plugin.designIndex] = body;
      }
    });
    return items.map((item, index) => {
      const placement = placements[index] || {};
      const angle = geometry.angles[index] || 0;
      const body = bodyByIndex[index];
      const beadSize = geometry.beadSizes[index] || this.getMaterialDisplaySize(item.id);
      let x;
      let y;
      let rotation;
      if (this.data.isLooseMode) {
        x = body && body.position ? body.position.x : Number(placement.looseX || layout.center);
        y = body && body.position ? body.position.y : Number(placement.looseY || layout.center);
        rotation = body && body.angle != null ? body.angle * 180 / Math.PI : Number(placement.rotation || 0);
      } else {
        x = layout.center + Math.cos(angle) * geometry.radius;
        y = layout.center + Math.sin(angle) * geometry.radius;
        rotation = angle * 180 / Math.PI;
      }
      x += Number(placement.dx || 0);
      y += Number(placement.dy || 0);
      let dragging = false;
      let deleteReady = false;
      if (this.dragState && this.dragState.index === index && this.dragState.body && this.dragState.body.position) {
        x = this.dragState.body.position.x;
        y = this.dragState.body.position.y;
        rotation = this.dragState.body.angle * 180 / Math.PI;
        dragging = true;
        deleteReady = !!this.data.dragDeleteArmed;
      }
      if (this.ringDragState && this.ringDragState.currentIndex === index && this.ringDragState.draggingX != null) {
        x = this.ringDragState.draggingX;
        y = this.ringDragState.draggingY;
        rotation = Math.atan2(y - layout.center, x - layout.center) * 180 / Math.PI;
        dragging = true;
        deleteReady = !!this.data.dragDeleteArmed;
      }
      return {
        item,
        index,
        x: x * scale,
        y: y * scale,
        size: beadSize * scale,
        logicalX: x,
        logicalY: y,
        logicalSize: beadSize,
        rotation,
        active: index === this.data.selectedBeadIndex,
        dragging,
        deleteReady
      };
    });
  },

  hitTestCanvasBead(touch) {
    const point = this.touchToCanvasTrayPoint(touch);
    if (!point) return -1;
    const sprites = this.getCanvasBeadSprites();
    for (let index = sprites.length - 1; index >= 0; index -= 1) {
      const sprite = sprites[index];
      const dx = point.x - sprite.logicalX;
      const dy = point.y - sprite.logicalY;
      const radius = Math.max(24, sprite.logicalSize / 2 + 8);
      if (dx * dx + dy * dy <= radius * radius) return sprite.index;
    }
    return -1;
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
      y: (clientY - state.rect.top) / scale
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
    if (this.data.isShuffling) return;
    const touch = e.touches && e.touches[0];
    if (!touch) return;
    this.refreshBraceletCanvasRect(rect => {
      const index = this.hitTestCanvasBead(touch);
      if (!Number.isInteger(index) || index < 0) return;
      this.pushHistory();
      if (this.data.isLooseMode && (!this.physicsBodies || !this.physicsBodies.length)) {
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
    const bodyRadius = Math.max(19, beadSize * 0.5 - 0.2);
    const body = Bodies.circle(
      options.x == null ? placement.looseX : options.x,
      options.y == null ? placement.looseY : options.y,
      bodyRadius,
      {
        isStatic: !!options.isStatic,
        restitution: options.restitution == null ? 0.62 : options.restitution,
        friction: options.friction == null ? 0.028 : options.friction,
        frictionStatic: options.frictionStatic == null ? 0.12 : options.frictionStatic,
        frictionAir: options.frictionAir == null ? 0.018 : options.frictionAir,
        density: options.density == null ? 0.0018 : options.density,
        slop: options.slop == null ? 0.006 : options.slop,
        sleepThreshold: 44,
        label: `bead-${index}`
      }
    );
    body.plugin = {
      designIndex: index,
      materialId: id,
      beadSize,
      bodyRadius,
      isLauncher: !!options.isLauncher,
      frozenUntilImpact: !!options.frozenUntilImpact,
      billiardDamping: options.billiardDamping
    };
    Body.setAngle(body, (Number(placement.rotation) || 0) * Math.PI / 180);
    if (options.velocity) Body.setVelocity(body, options.velocity);
    if (options.angularVelocity) Body.setAngularVelocity(body, options.angularVelocity);
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

  runPhysics() {
    if (!this.physicsEngine || this.physicsTimer) return;
    this.physicsLastTime = Date.now();
    this.physicsLastRender = 0;
    this.physicsStillFrames = 0;
    if (this.data.useCanvasRenderer) this.scheduleCanvasRender(true);
    this.physicsTimer = setInterval(() => {
      try {
        const now = Date.now();
        this.physicsLastTime = now;
        if (this.physicsTargets) this.applyStringingForces();
        Engine.update(this.physicsEngine, this.physicsStepMs || 1000 / 30);
        if (!this.physicsTargets) this.applyBilliardDamping();
        this.resolveBeadOverlaps();
        this.clampBodiesInsideTray();
        if (this.pendingFrozenImpact && now - (this.pendingFrozenImpactAt || now) > 760) {
          const launcher = (this.physicsBodies || []).find(body => body && body.plugin && body.plugin.isLauncher);
          this.releaseFrozenBodiesFromImpact(launcher, null);
        }
        if (this.physicsTargets && this.isStringingSettled()) {
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
        const allSleeping = this.physicsBodies.length > 0
          && this.physicsBodies.every(body => body.isSleeping);
        if (!this.physicsTargets) {
          this.physicsStillFrames = allSleeping ? this.physicsStillFrames + 1 : 0;
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

  resolveBeadOverlaps() {
    const bodies = this.physicsBodies || [];
    if (bodies.length < 2 || !Body) return;
    const maxCorrectionPerPass = this.isLowPerformanceDevice ? 16 : 26;
    const passes = this.isLowPerformanceDevice ? 2 : 3;
    for (let pass = 0; pass < passes; pass += 1) {
      for (let i = 0; i < bodies.length - 1; i += 1) {
        const bodyA = bodies[i];
        if (!bodyA || !bodyA.position) continue;
        for (let j = i + 1; j < bodies.length; j += 1) {
          const bodyB = bodies[j];
          if (!bodyB || !bodyB.position) continue;
          const radiusA = Number(bodyA.plugin && (bodyA.plugin.bodyRadius || bodyA.plugin.beadSize * 0.5)) || 24;
          const radiusB = Number(bodyB.plugin && (bodyB.plugin.bodyRadius || bodyB.plugin.beadSize * 0.5)) || 24;
          const minDistance = radiusA + radiusB + 3.2;
          let dx = bodyB.position.x - bodyA.position.x;
          let dy = bodyB.position.y - bodyA.position.y;
          let distanceSq = dx * dx + dy * dy;
          if (distanceSq <= 0.0001) {
            const seed = (i + 1) * 17 + (j + 1) * 31 + pass * 13;
            dx = Math.cos(seed);
            dy = Math.sin(seed);
            distanceSq = 1;
          }
          const distance = Math.sqrt(distanceSq);
          const overlap = minDistance - distance;
          if (overlap <= 0) continue;
          const normalX = dx / distance;
          const normalY = dy / distance;
          const correction = Math.min(overlap, maxCorrectionPerPass) * 0.82;
          if (bodyA.isStatic && bodyB.isStatic) continue;
          if (bodyA.isStatic) {
            Body.setPosition(bodyB, {
              x: bodyB.position.x + normalX * correction,
              y: bodyB.position.y + normalY * correction
            });
            Body.setVelocity(bodyB, { x: bodyB.velocity.x * 0.84, y: bodyB.velocity.y * 0.84 });
          } else if (bodyB.isStatic) {
            Body.setPosition(bodyA, {
              x: bodyA.position.x - normalX * correction,
              y: bodyA.position.y - normalY * correction
            });
            Body.setVelocity(bodyA, { x: bodyA.velocity.x * 0.84, y: bodyA.velocity.y * 0.84 });
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
          }
        }
      }
    }
  },

  applyBilliardDamping() {
    const bodies = this.physicsBodies || [];
    if (!bodies.length || !Body) return;
    const defaultMu = this.isLowPerformanceDevice ? 0.82 : (this.isRealDevice ? 0.86 : 0.875);
    bodies.forEach(body => {
      if (!body || !body.position || body.isStatic) return;
      const plugin = body.plugin || {};
      const mu = Number(plugin.billiardDamping || defaultMu);
      if (body.speed < 0.045) {
        Body.setVelocity(body, { x: 0, y: 0 });
        Body.setAngularVelocity(body, 0);
        return;
      }
      Body.setVelocity(body, {
        x: body.velocity.x * mu,
        y: body.velocity.y * mu
      });
      Body.setAngularVelocity(body, body.angularVelocity * Math.max(0.72, mu - 0.04));
    });
  },

  clampBodiesInsideTray() {
    const bodies = this.physicsBodies || [];
    if (!bodies.length || !Body) return;
    const layout = this.getStageLayout();
    const center = layout.center;
    bodies.forEach(body => {
      if (!body || !body.position || body.isStatic) return;
      const radius = Number(body.plugin && (body.plugin.bodyRadius || body.plugin.beadSize * 0.5)) || 24;
      const maxDistance = center - radius - 9;
      let dx = body.position.x - center;
      let dy = body.position.y - center;
      let distance = Math.sqrt(dx * dx + dy * dy);
      if (distance <= maxDistance) return;
      if (distance <= 0.0001) {
        dx = 1;
        dy = 0;
        distance = 1;
      }
      const normalX = dx / distance;
      const normalY = dy / distance;
      Body.setPosition(body, {
        x: center + normalX * maxDistance,
        y: center + normalY * maxDistance
      });
      const outwardSpeed = body.velocity.x * normalX + body.velocity.y * normalY;
      if (outwardSpeed > 0) {
        Body.setVelocity(body, {
          x: body.velocity.x - normalX * outwardSpeed * 1.28,
          y: body.velocity.y - normalY * outwardSpeed * 1.28
        });
      }
    });
  },

  syncPhysicsFrame(onSynced) {
    if (this.physicsFramePending) {
      if (onSynced) {
        setTimeout(
          () => this.syncPhysicsFrame(onSynced),
          this.physicsRenderInterval || 50
        );
      }
      return;
    }
    if (!this.data.isLooseMode || !this.physicsBodies.length) {
      if (onSynced) onSynced();
      return;
    }
    this.physicsFramePending = true;
    const placements = this.normalizePlacements(this.data.selected, this.data.placements);
    this.physicsBodies.forEach(body => {
      const index = body.plugin.designIndex;
      if (!placements[index]) return;
      placements[index] = {
        ...placements[index],
        looseX: body.position.x,
        looseY: body.position.y,
        rotation: body.angle * 180 / Math.PI,
        beadSize: body.plugin.beadSize
      };
    });
    const items = this.data.selected.map(id => this.findMaterialById(id)).filter(Boolean);
    const geometry = this.calculateBraceletGeometry(items);
    this.livePlacements = placements;
    this.physicsFrameSequence = (this.physicsFrameSequence || 0) + 1;
    if (this.data.useCanvasRenderer) {
      this.scheduleCanvasRender(true);
      const shouldPersistFrame = onSynced || this.physicsFrameSequence % 10 === 0;
      if (shouldPersistFrame) {
        this.setData({ placements }, () => {
          this.physicsFramePending = false;
          if (onSynced) onSynced();
        });
      } else {
        this.physicsFramePending = false;
        if (onSynced) onSynced();
      }
      return;
    }
    const selectedItems = this.layoutSelectedItems(items, placements, geometry);
    const canPatchStyles = (this.data.selectedItems || []).length === selectedItems.length;
    const updates = {};
    if (canPatchStyles) {
      selectedItems.forEach((item, index) => {
        updates[`selectedItems[${index}].style`] = item.style;
      });
      if (onSynced || this.physicsFrameSequence % 4 === 0) {
        updates.placements = placements;
      }
    } else {
      updates.placements = placements;
      updates.selectedItems = selectedItems;
    }
    this.setData(updates, () => {
      this.physicsFramePending = false;
      if (onSynced) onSynced();
    });
  },

  applyStringingForces() {
    this.physicsBodies.forEach((body, index) => {
      const target = this.physicsTargets[index];
      if (!target) return;
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

  isStringingSettled() {
    return this.physicsBodies.every((body, index) => {
      const target = this.physicsTargets[index];
      if (!target) return true;
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
    const starts = this.physicsBodies.map(body => ({
      x: body.position.x,
      y: body.position.y,
      angle: body.angle
    }));
    const stageCenter = this.getStageLayout().center;
    const targetAngles = targets.map(target => (
      Math.atan2(target.y - stageCenter, target.x - stageCenter)
    ));
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
          const target = targets[index];
          const start = starts[index];
          if (!target || !start) return;
          Body.setPosition(body, {
            x: start.x + (target.x - start.x) * eased,
            y: start.y + (target.y - start.y) * eased
          });
          const targetAngle = targetAngles[index] || 0;
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
    this.setData({
      isLooseMode: false,
      isShuffling: false,
      isStringingFinishing: false,
      draggingBeadIndex: -1,
      dragDeleteArmed: false
    }, () => {
      this.recalculate();
      this.stopPhysics();
    });
  },

  pausePhysics() {
    if (this.physicsTimer) {
      clearInterval(this.physicsTimer);
      this.physicsTimer = null;
    }
    if (this.data.isLooseMode && this.livePlacements) {
      this.setData({ placements: this.livePlacements });
    }
  },

  stopPhysics() {
    this.pausePhysics();
    clearInterval(this.stringingFinishTimer);
    this.stringingFinishTimer = null;
    clearTimeout(this.stringingCompleteTimer);
    this.stringingCompleteTimer = null;
    clearTimeout(this.stringingGuardTimer);
    this.stringingGuardTimer = null;
    if (this.physicsEngine) Engine.clear(this.physicsEngine);
    this.physicsEngine = null;
    this.physicsBodies = [];
    this.physicsTargets = null;
    this.pendingImpactTargets = null;
    this.pendingFrozenImpact = false;
    this.pendingFrozenImpactAt = 0;
    this.physicsFramePending = false;
    this.livePlacements = null;
  },

  clearFlightRuntime() {
    clearTimeout(this.flightTimer);
    this.flightTimer = null;
    clearTimeout(this.flightSafetyTimer);
    this.flightSafetyTimer = null;
    this.flightQueue = [];
    this.flightActive = false;
    this.canvasFlightReadyRetries = 0;
    this.canvasFlight = null;
    this.clearWorkspaceFlightCanvas();
  },

  resetWorkspaceRuntime() {
    this.clearFlightRuntime();
    this.livePlacements = null;
    this.stopPhysics();
    this.dragState = null;
    this.ringDragState = null;
    this.suppressBeadTapUntil = 0;
  },

  resetInteractionData(extra = {}, callback) {
    const nextData = {
      canvasFlightActive: false,
      flightBead: null,
      launchingMaterialId: '',
      isShuffling: false,
      isStringingFinishing: false,
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
      || this.data.canvasFlightActive
      || this.flightActive
      || (this.flightQueue && this.flightQueue.length)
      || this.canvasFlight
      || this.physicsTimer
      || this.stringingFinishTimer
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
      wristSize: this.data.wristSize,
      wearStyle: 'single',
      isLooseMode: this.data.isLooseMode
    });
    this.historyStack = history.slice(-30);
    this.redoStack = [];
    wx.setStorage({ key: 'workspaceHistory', data: this.historyStack });
    this.setData({ canUndo: true, canRedo: false });
  },

  currentDesignSnapshot() {
    return {
      selected: [...this.data.selected],
      placements: this.data.placements.map(item => ({ ...item })),
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
    wx.setStorage({ key: 'workspaceHistory', data: history });
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
    wx.setStorage({ key: 'workspaceHistory', data: this.historyStack });
    this.restoreDesignSnapshot(next);
  },

  refreshFilters(options = {}) {
    const pool = (this.materialCatalog || DEFAULT_MATERIALS).filter(item => item.top === this.data.activeTop);
    const backendCategories = (this.categoriesByTop || {})[this.data.activeTop] || [];
    const keyword = this.normalizeMaterialSearchKeyword(this.data.materialSearchKeyword);
    const searchPool = keyword ? pool.filter(item => this.materialMatchesSearch(item, keyword)) : [];
    const searchTarget = keyword ? this.resolveMaterialSearchTarget(searchPool) : null;
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
    const categoryRailSeries = this.buildCategoryRailSeries(seriesOptions, activeCategory, activeSeries);
    const activeCategoryAnchor = this.getActiveOptionAnchor(decoratedCategories);
    const activeSeriesAnchor = this.getActiveOptionAnchor(decoratedSeriesOptions);
    const filteredMaterials = keyword ? searchPool : categoryPool.filter(item => {
      const series = item.series || item.name || '';
      const matchesSeries = this.isAllFilterValue(activeSeries) || series === activeSeries;
      return matchesSeries && this.materialMatchesSearch(item);
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
      categoryRailSeries,
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
    const currentCount = this.data.visibleMaterials.length;
    if (currentCount >= filteredMaterials.length) return;
    const visibleMaterials = this.decorateVisibleMaterials(filteredMaterials.slice(
      0,
      currentCount + (this.materialPageSize || MATERIAL_PAGE_SIZE)
    ));
    this.setData({
      visibleMaterials,
      hasMoreMaterials: visibleMaterials.length < filteredMaterials.length
    }, () => {
      this.scheduleMaterialPreload(visibleMaterials);
    });
  },

  buildCategoryRailSeries(seriesOptions = [], activeCategory = ALL_OPTION_LABEL, activeSeries = ALL_OPTION_LABEL) {
    if (this.isAllFilterValue(activeCategory)) return [];
    return this.decorateOptionList(seriesOptions, activeSeries, '', 'category-series');
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

  decorateVisibleMaterials(materials) {
    return (materials || []).map((item, index) => ({
      ...item,
      cardClass: `material-card-${index}${this.data.launchingMaterialId === item.id ? ' launching' : ''}`,
      effectText: [
        item.series && item.series !== item.name ? item.series : '',
        item.grade || '',
        (item.effects || []).slice(0, 2).join(' / ')
      ].filter(Boolean).join(' · ')
    }));
  },

  selectTop(e) {
    this.setData({ activeTop: e.currentTarget.dataset.top, activeCategory: ALL_OPTION_LABEL, activeSeries: ALL_OPTION_LABEL }, () => {
      if (this.useServerMaterialPagination) this.loadMaterials();
      else this.refreshFilters();
    });
  },

  selectCategory(e) {
    this.setData({ activeCategory: e.currentTarget.dataset.category, activeSeries: ALL_OPTION_LABEL }, () => {
      if (this.useServerMaterialPagination) this.loadMaterials();
      else this.refreshFilters();
    });
  },

  selectSeries(e) {
    this.setData({ activeSeries: e.currentTarget.dataset.series }, () => {
      if (this.useServerMaterialPagination) this.loadMaterials();
      else this.refreshFilters();
    });
  },

  reloadMaterialsForSearch() {
    if (this.useServerMaterialPagination) this.loadMaterials();
    else this.refreshFilters();
  },

  onMaterialSearchInput(e) {
    const keyword = (e.detail && e.detail.value) || '';
    this.setData({ materialSearchKeyword: keyword });
    clearTimeout(this.materialSearchTimer);
    this.materialSearchTimer = setTimeout(() => {
      this.reloadMaterialsForSearch();
    }, 320);
  },

  submitMaterialSearch(e) {
    const keyword = (e.detail && e.detail.value) || this.data.materialSearchKeyword || '';
    clearTimeout(this.materialSearchTimer);
    this.setData({ materialSearchKeyword: keyword }, () => this.reloadMaterialsForSearch());
  },

  clearMaterialSearch() {
    if (!this.data.materialSearchKeyword) return;
    clearTimeout(this.materialSearchTimer);
    this.setData({ materialSearchKeyword: '' }, () => this.reloadMaterialsForSearch());
  },

  onMaterialImageError(e) {
    const id = e.currentTarget.dataset.id;
    if (!id) return;
    this.materialCatalog = (this.materialCatalog || DEFAULT_MATERIALS).map(item => (
      item.id === id ? { ...item, image_url: '' } : item
    ));
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
      limit: Math.max(this.materialPageSize || MATERIAL_PAGE_SIZE, this.data.visibleMaterials.length)
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
    if (wx.getStorageSync(WORKSPACE_GUIDE_STORAGE_KEY)) return;
    this.setData({ showWorkspaceGuide: true });
  },

  dismissWorkspaceGuide(e) {
    const dataset = (e && e.currentTarget && e.currentTarget.dataset) || {};
    if (dataset.forever) {
      wx.setStorageSync(WORKSPACE_GUIDE_STORAGE_KEY, true);
    }
    this.setData({ showWorkspaceGuide: false });
  },

  openWristSetting() {
    this.hideWorkspaceCanvasForOverlay();
    this.setData({ showWristPicker: true });
    wx.nextTick(() => this.prepareWristRuler(this.data.wristSize));
  },

  closeWristSetting() {
    this.setData({ showWristPicker: false }, () => this.restoreWorkspaceCanvasAfterOverlay());
  },

  prepareWristRuler(value = this.data.wristSize || 16) {
    const tickWidth = this.getWristTickWidthPx();
    const viewportWidth = this.getWristRulerViewportWidth();
    const sidePadding = Math.max(0, Math.round((viewportWidth - tickWidth) / 2));
    const wristValue = this.normalizeWristValue(value);
    const ticks = this.buildWristRulerTicks();
    this.wristRulerTickWidthPx = tickWidth;
    this.wristRulerLastTick = Math.round((wristValue - WRIST_RULER_MIN) * 10);
    this.wristRulerLastDisplay = this.formatWristValue(wristValue);
    this.setData({
      wristRulerTicks: ticks,
      wristRulerTickWidth: tickWidth,
      wristRulerSidePadding: sidePadding,
      wristRulerValue: this.formatWristValue(wristValue),
      wristRulerScrollLeft: this.wristValueToScrollLeft(wristValue, tickWidth)
    });
  },

  getWristTickWidthPx() {
    const windowWidth = Number(this.data.deviceInfo && this.data.deviceInfo.windowWidth) || 375;
    return Math.max(8, Math.round(WRIST_RULER_TICK_RPX * windowWidth / 750 * 10) / 10);
  },

  getWristRulerViewportWidth() {
    const windowWidth = Number(this.data.deviceInfo && this.data.deviceInfo.windowWidth) || 375;
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
    const index = Math.max(0, Math.min(150, Math.round((Number(scrollLeft) || 0) / tickWidth)));
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
    const tickWidth = this.wristRulerTickWidthPx || this.getWristTickWidthPx();
    const index = Math.max(0, Math.min(150, Math.round(scrollLeft / tickWidth)));
    const value = this.normalizeWristValue(WRIST_RULER_MIN + index * WRIST_RULER_STEP);
    const display = this.formatWristValue(value);
    this.currentWristRulerIndex = index;
    this.currentWristRulerScrollLeft = scrollLeft;
    if (display !== this.wristRulerLastDisplay) {
      this.wristRulerLastDisplay = display;
      this.setData({ wristRulerValue: display });
    }
    this.wristRulerLastTick = index;
    if (!this.wristRulerInteracting) {
      clearTimeout(this.wristRulerSnapTimer);
      this.wristRulerSnapTimer = setTimeout(() => this.snapWristRuler(), 180);
    }
  },

  snapWristRuler() {
    if (!this.data.showWristPicker) return;
    const value = this.scrollLeftToWristValue(this.currentWristRulerScrollLeft || this.data.wristRulerScrollLeft);
    this.setData({
      wristRulerValue: this.formatWristValue(value),
      wristRulerScrollLeft: this.wristValueToScrollLeft(value)
    });
  },

  confirmWristRuler() {
    const wristSize = this.normalizeWristValue(Number(this.data.wristRulerValue));
    const isSameWristSize = wristSize === Number(this.data.wristSize);
    const rememberedWristSize = this.rememberWristSize(wristSize);
    if (isSameWristSize) {
      this.setData({ wristSize: rememberedWristSize, showWristPicker: false }, () => this.restoreWorkspaceCanvasAfterOverlay());
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
    });
    wx.showToast({ title: `${this.formatWristValue(rememberedWristSize)}cm 手围`, icon: 'success' });
  },

  chooseWristSize(e) {
    const wristSize = this.normalizeWristValue(Number(e.currentTarget.dataset.size));
    if (!wristSize) return;
    const isSameWristSize = wristSize === Number(this.data.wristSize);
    const rememberedWristSize = this.rememberWristSize(wristSize);
    if (isSameWristSize) {
      this.setData({ wristSize: rememberedWristSize, showWristPicker: false }, () => this.restoreWorkspaceCanvasAfterOverlay());
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
    });
    wx.showToast({ title: `${this.formatWristValue(rememberedWristSize)}cm 手围`, icon: 'success' });
  },

  promptInitialWristSize() {
    if (wx.getStorageSync('workspaceWristConfirmed')) return;
    if (this.pendingSharedDesign || this.pendingSharedDesignId || this.pendingBackendRecommendation || this.pendingRecommendedRecipe) return;
    const workspacePreset = wx.getStorageSync('workspacePreset');
    if (workspacePreset === 'backend-recommended' || workspacePreset === 'recommended') return;
    this.openWristSetting();
  },

  releaseString() {
    if (this.data.isLooseMode || !this.data.selected.length || this.data.isShuffling) return;
    this.pushHistory();
    const placements = [];
    this.data.selected.forEach((id, index) => {
      const previous = this.data.placements[index] || {};
      const loosePlacement = this.createLoosePlacement(index, id, placements);
      placements.push({
        ...loosePlacement,
        image_url: previous.image_url || loosePlacement.image_url || ''
      });
    });
    this.setData({
      placements,
      isLooseMode: true,
      selectedBeadIndex: -1,
      draggingBeadIndex: -1,
      dragDeleteArmed: false
    });
    this.recalculate();
    wx.nextTick(() => this.startPhysicsFromCurrentDesign());
  },

  toggleStringMode() {
    if (this.data.isLooseMode) {
      this.shuffleDesign();
      return;
    }
    this.releaseString();
  },

  buildCurrentSequence() {
    const timestamp = new Date().toISOString();
    return (this.data.selected || []).map((id, index) => {
      const material = this.findMaterialById(id) || {};
      const placement = (this.data.placements || [])[index] || {};
      const imageUrls = (material.image_urls || material.image_pool || [])
        .concat(material.image_url || [])
        .filter(Boolean);
      const size = material.size || material.diameter || placement.diameter || '';
      const price = Number(material.price ?? material.priceText ?? material.amount ?? material.sale_price ?? 0);
      return {
        index: index + 1,
        id,
        material_id: material.id || id,
        sku: material.skuId || material.sku || id,
        name: material.name || material.series || material.category || id,
        category: material.category || '',
        series: material.series || '',
        grade: material.grade || '',
        effect: material.effect || '',
        element: material.element || '',
        color: material.color || '',
        size,
        diameter: size,
        price: Number.isFinite(price) ? price : 0,
        weight: Number(material.weight || 0),
        image_url: placement.image_url || imageUrls[0] || '',
        image_urls: imageUrls,
        placement: {
          x: placement.x,
          y: placement.y,
          angle: placement.angle,
          diameter: placement.diameter,
          image_url: placement.image_url || ''
        },
        snapshot_at: timestamp
      };
    });
  },

  async addDesignToCart() {
    if (!this.data.selected.length) {
      wx.showToast({ title: '请先选择珠子', icon: 'none' });
      return;
    }
    let user;
    try {
      user = await auth.requireLogin('登录后才能保存购物车方案预览。');
    } catch (error) {
      return;
    }
    wx.showLoading({ title: '生成预览...', mask: true });
    const sequence = this.buildCurrentSequence();
    const fallbackPrice = sequence.reduce((sum, item) => sum + Number(item.price || 0), 0);
    const summaryPrice = Number((this.data.summary && (this.data.summary.priceText || this.data.summary.price)) || fallbackPrice || 0);
    const price = Number.isFinite(summaryPrice) ? summaryPrice : fallbackPrice;
    const summary = {
      ...(this.data.summary || {}),
      count: sequence.length,
      price,
      priceText: price.toFixed(2)
    };
    const previewResult = await this.prepareCurrentDesignPreview(user.user_id, {});
    const previewImage = previewResult.previewImage || previewResult.localPreviewImage || '';
    wx.hideLoading();
    if (!previewImage) {
      wx.showToast({ title: '预览图生成失败，请重试', icon: 'none' });
      return;
    }
    const localId = `diy-${Date.now()}`;
    const cartPayload = {
      id: localId,
      createdAt: Date.now(),
      name: 'DIY 手串方案',
      userId: user.user_id,
      selected: [...this.data.selected],
      materialIds: sequence.map(item => item.id || item.sku).filter(Boolean),
      placements: this.data.placements.map(item => ({ ...item })),
      wristSize: this.data.wristSize,
      wearStyle: 'single',
      isLooseMode: this.data.isLooseMode,
      sourceContext: this.data.sourceContext || this.sourceContext || null,
      preview_image: previewImage,
      previewImage,
      image_url: previewImage,
      local_preview_image: previewResult.localPreviewImage || '',
      summary,
      sequence
    };
    try {
      const saved = await saveCartItem({
        user_id: user.user_id,
        cart_item_id: localId,
        item_type: 'diy_design',
        item_id: localId,
        item: cartPayload,
        quantity: 1
      });
      const cart = wx.getStorageSync('diyDesignCart') || [];
      const storedItem = {
        ...cartPayload,
        ...(saved.item || {}),
        id: saved.cart_item_id || localId,
        key: saved.cart_item_id || localId,
        cart_item_id: saved.cart_item_id || localId,
        quantity: saved.quantity || 1,
        qty: saved.quantity || 1
      };
      wx.setStorage({
        key: 'diyDesignCart',
        data: [storedItem, ...cart.filter(item => (item.cart_item_id || item.id) !== storedItem.cart_item_id)].slice(0, 20),
        success: () => wx.showToast({ title: '已加入购物车', icon: 'success' })
      });
    } catch (error) {
      wx.showToast({ title: error.message || '购物车保存失败，请重试', icon: 'none' });
    }
    return;
    const cart = wx.getStorageSync('diyDesignCart') || [];
    cart.push({
      id: `diy-${Date.now()}`,
      createdAt: Date.now(),
      name: 'DIY 手串方案',
      userId: user.user_id,
      selected: [...this.data.selected],
      materialIds: sequence.map(item => item.id || item.sku).filter(Boolean),
      placements: this.data.placements.map(item => ({ ...item })),
      wristSize: this.data.wristSize,
      wearStyle: 'single',
      isLooseMode: this.data.isLooseMode,
      sourceContext: this.data.sourceContext || this.sourceContext || null,
      preview_image: previewImage,
      previewImage,
      image_url: previewImage,
      local_preview_image: previewResult.localPreviewImage || '',
      summary,
      sequence
    });
    wx.setStorage({
      key: 'diyDesignCart',
      data: cart.slice(-20),
      success: () => wx.showToast({ title: '已加入购物车', icon: 'success' })
    });
  },

  showWorkspaceHelp() {
    wx.showModal({
      title: 'DIY工作台帮助',
      content: '点击材料可投入圆盘；拖动珠子调整位置，拖出圆盘可移除；随机成串会重新排列并随机旋转珠面；解除组串后可继续自由滚动和编辑。',
      showCancel: false,
      confirmText: '知道了'
    });
  },

  stopPropagation() {},

  openToolbox() {
    wx.showActionSheet({
      itemList: ['撤回上一步', '还原排列', '保存草稿', '分享方案', '调整手围', '加入购物车', '使用帮助', '清空设计'],
      success: res => {
        if (res.tapIndex === 0) this.undo();
        if (res.tapIndex === 1) this.redo();
        if (res.tapIndex === 2) this.saveDraft();
        if (res.tapIndex === 3) this.prepareShareDesign();
        if (res.tapIndex === 4) this.openWristSetting();
        if (res.tapIndex === 5) this.addDesignToCart();
        if (res.tapIndex === 6) this.showWorkspaceHelp();
        if (res.tapIndex === 7) this.confirmClearDesign();
      }
    });
  },

  showMaterialQueueToast(title) {
    const now = Date.now();
    if (now - (this.lastQueueToastAt || 0) < MATERIAL_QUEUE_TOAST_GUARD_MS) return;
    this.lastQueueToastAt = now;
    wx.showToast({ title, icon: 'none' });
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
    const size = Math.max(38, Math.min(72, Number(material.size || 8) * 5.4));
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

  addMaterial(e) {
    if (this.data.isShuffling) {
      this.showMaterialQueueToast('正在成串，请稍候');
      return;
    }
    const id = e.currentTarget.dataset.id;
    const cardIndex = Number(e.currentTarget.dataset.index);
    if (!id) return;
    const now = Date.now();
    if (now - (this.lastMaterialTapAt || 0) < MATERIAL_TAP_GUARD_MS) return;
    this.lastMaterialTapAt = now;
    const material = this.findMaterialById(id);
    if (!material) {
      this.showMaterialQueueToast(this.data.materialsLoading ? '珠材加载中，请稍候' : '材料暂不可用');
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
    const placement = this.createLoosePlacement(
      pendingCount,
      id,
      [...this.data.placements, ...queuedPlacements]
    );
    this.flightQueue.push({
      id,
      cardIndex,
      placement,
      image_url: placement.image_url || '',
      tapPoint: this.getTapPoint(e)
    });
    this.processFlightQueue();
  },

  processFlightQueue() {
    if (this.data.useCanvasRenderer) {
      this.processCanvasFlightQueue();
      return;
    }
    if (this.flightActive || !this.flightQueue.length) return;
    const task = this.flightQueue.shift();
    const material = this.findMaterialById(task.id);
    if (!material) {
      this.processFlightQueue();
      return;
    }
    this.flightActive = true;
    this.armFlightSafetyTimer();
    const query = wx.createSelectorQuery();
    query.select(`.material-card-${task.cardIndex} .material-sphere`).boundingClientRect();
    query.select('.bracelet-circle').boundingClientRect();
    query.exec(rects => {
      const cardRect = rects && rects[0];
      const circleRect = rects && rects[1];
      if (!cardRect || !circleRect) {
        this.commitMaterial(task.id, task.placement, {}, () => this.finishFlight());
        return;
      }
      const layout = this.getStageLayout();
      const logicalSize = layout.center * 2;
      const scale = circleRect.width / logicalSize;
      const startX = cardRect.left + cardRect.width / 2;
      const startY = cardRect.top + cardRect.height / 2;
      const beadSize = Math.max(42, Math.min(78, material.size * 5.4));
      const launchIndex = this.data.selected.length + this.flightQueue.length;
      const launchSeed = (task.placement.rotation + launchIndex * 47) % 101;
      const laneBias = ((launchIndex % 6) - 2.5) / 2.5;
      const entryAngle = Math.PI / 2 + laneBias * 0.92 + ((launchSeed / 100) - 0.5) * 0.38;
      const entryRadius = layout.center - 28 - beadSize / 2;
      const entryLogicalX = layout.center + Math.cos(entryAngle) * entryRadius;
      const entryLogicalY = layout.center + Math.sin(entryAngle) * entryRadius;
      const launchSpeed = 16.2 + (launchSeed % 12) * 0.5 + Math.min(launchIndex, 12) * 0.22;
      const targetAngle = -Math.PI / 2 + laneBias * 0.58 + ((launchSeed / 100) - 0.5) * 0.62;
      const targetRadius = layout.center * (0.26 + (launchSeed % 5) * 0.018);
      const aimX = layout.center + Math.cos(targetAngle) * targetRadius;
      const aimY = layout.center + Math.sin(targetAngle) * targetRadius;
      const aimDx = aimX - entryLogicalX;
      const aimDy = aimY - entryLogicalY;
      const aimLength = Math.max(1, Math.sqrt(aimDx ** 2 + aimDy ** 2));
      const tangentX = -aimDy / aimLength;
      const tangentY = aimDx / aimLength;
      const scatterStrength = 2.1 + Math.abs(laneBias) * 1.06;
      const endX = circleRect.left + entryLogicalX * scale;
      const endY = circleRect.top + entryLogicalY * scale;
      const sourceSize = Math.min(cardRect.width, cardRect.height);
      const targetSize = beadSize * scale;
      const animation = wx.createAnimation({ transformOrigin: '50% 50%' });
      const flightDelay = this.isRealDevice ? 34 : 18;
      const flightDuration = this.isLowPerformanceDevice ? 430 : (this.isRealDevice ? 390 : 320);
      this.setData({
        flightBead: {
          id: `${task.id}-${Date.now()}`,
          image_url: task.image_url || material.image_url || '',
          color: material.color,
          shine: material.shine,
          style: `left:${(startX - sourceSize / 2).toFixed(1)}px;top:${(startY - sourceSize / 2).toFixed(1)}px;width:${sourceSize.toFixed(1)}px;height:${sourceSize.toFixed(1)}px;`,
          animation: {}
        }
      }, () => {
        // 先确保飞行替身已经在素材珠子上方完成首帧绘制，再隐藏原珠。
        // 多留一个绘制帧后才启动动画，避免繁忙设备直接跳到圆盘入口。
        this.setData({ launchingMaterialId: task.id }, () => {
          setTimeout(() => {
            animation
              .translate(endX - startX, endY - startY)
              .rotate(22 + task.placement.rotation * 0.08)
              .scale(targetSize / sourceSize)
              .step({ duration: flightDuration, timingFunction: 'cubic-bezier(.16,.92,.24,1)' });
            this.setData({ 'flightBead.animation': animation.export() });
          }, flightDelay);
        });
      });
      this.flightTimer = setTimeout(() => {
        const launchPlacement = {
          ...task.placement,
          looseX: entryLogicalX,
          looseY: entryLogicalY
        };
        this.commitMaterial(task.id, launchPlacement, {
          x: entryLogicalX,
          y: entryLogicalY,
          velocity: {
            x: aimDx / aimLength * launchSpeed + tangentX * scatterStrength,
            y: aimDy / aimLength * launchSpeed + tangentY * scatterStrength
          },
          angularVelocity: ((task.placement.rotation % 9) - 4) * 0.009
        }, () => this.finishFlight());
      }, flightDelay + flightDuration + 24);
    });
  },

  processCanvasFlightQueue() {
    if (this.flightActive || !this.flightQueue.length) return;
    if (!this.braceletCanvasState || !this.flightCanvasState) {
      this.canvasFlightReadyRetries = (this.canvasFlightReadyRetries || 0) + 1;
      if (this.canvasFlightReadyRetries <= 5) {
        this.initWorkspaceCanvases();
        setTimeout(() => this.processCanvasFlightQueue(), 70);
        return;
      }
      this.canvasFlightReadyRetries = 0;
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
    const query = wx.createSelectorQuery().in(this);
    query.select(`.material-card-${task.cardIndex} .material-sphere`).boundingClientRect();
    query.select('.bracelet-circle').boundingClientRect();
    query.select('.material-drawer').boundingClientRect();
    query.exec(rects => {
      const cardRect = rects && rects[0];
      const circleRect = rects && rects[1];
      const drawerRect = rects && rects[2];
      const startRect = this.resolveFlightStartRect(cardRect, task.tapPoint, drawerRect, material);
      if (!startRect || !circleRect) {
        this.commitMaterial(task.id, task.placement, {}, () => this.finishCanvasFlight());
        return;
      }
      const layout = this.getStageLayout();
      const logicalSize = layout.center * 2;
      const scale = circleRect.width / logicalSize;
      const beadSize = Math.max(42, Math.min(78, material.size * 5.4));
      const launchIndex = this.data.selected.length + this.flightQueue.length;
      const launchSeed = (task.placement.rotation + launchIndex * 47) % 101;
      const startX = startRect.left + startRect.width / 2;
      const startY = startRect.top + startRect.height / 2;
      const startLogicalX = (startX - circleRect.left) / scale;
      const startLogicalY = (startY - circleRect.top) / scale;
      const shotDx = layout.center - startLogicalX;
      const shotDy = layout.center - startLogicalY;
      const shotLength = Math.max(1, Math.sqrt(shotDx ** 2 + shotDy ** 2));
      const shotX = shotDx / shotLength;
      const shotY = shotDy / shotLength;
      const entryRadius = layout.center - beadSize / 2 - 14;
      const entryLogicalX = layout.center - shotX * entryRadius;
      const entryLogicalY = layout.center - shotY * entryRadius;
      const tangentX = -shotY;
      const tangentY = shotX;
      const baseLaunchSpeed = this.isLowPerformanceDevice ? 38 : (this.isRealDevice ? 48 : 52);
      const powerRoll = Math.random();
      const powerFactor = powerRoll < 0.12
        ? 0.92 + Math.random() * 0.08
        : (powerRoll > 0.84 ? 1.12 + Math.random() * 0.12 : 1.0 + Math.random() * 0.12);
      const launchSpeed = baseLaunchSpeed * powerFactor + (launchSeed % 7) * 0.35;
      const scatterStrength = (Math.random() - 0.5) * 0.9;
      const launchPlacement = {
        ...task.placement,
        looseX: entryLogicalX,
        looseY: entryLogicalY
      };
      const endX = circleRect.left + entryLogicalX * scale;
      const endY = circleRect.top + entryLogicalY * scale;
      const controlX = (startX + endX) / 2;
      const controlY = (startY + endY) / 2;
      const sourceSize = Math.max(36, Math.min(76, Math.min(startRect.width, startRect.height)));
      const targetSize = beadSize * scale;
      const flightDuration = this.isLowPerformanceDevice ? 300 : (this.isRealDevice ? 270 : 240);
      const flightStartDelay = this.isRealDevice ? 48 : 24;
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
        sourceSize,
        targetSize,
        rotation: Number(task.placement.rotation || 0),
        rotationDelta: 8 + (launchSeed % 5),
        startedAt: Date.now() + flightStartDelay,
        duration: flightDuration
      };
      this.setData({ launchingMaterialId: task.id }, () => {
        this.setData({ canvasFlightActive: true }, () => this.scheduleCanvasRender(true));
        this.flightTimer = setTimeout(() => {
          this.commitMaterial(task.id, launchPlacement, {
            x: entryLogicalX,
            y: entryLogicalY,
            billiardDamping: this.isLowPerformanceDevice ? 0.88 : 0.92,
            frictionAir: 0.002,
            restitution: 0.9,
            velocity: {
              x: shotX * launchSpeed + tangentX * scatterStrength,
              y: shotY * launchSpeed + tangentY * scatterStrength
            },
            angularVelocity: ((task.placement.rotation % 9) - 4) * 0.018
          }, () => this.finishCanvasFlight());
        }, flightStartDelay + flightDuration + 18);
      });
    });
  },

  finishCanvasFlight() {
    clearTimeout(this.flightTimer);
    this.flightTimer = null;
    clearTimeout(this.flightSafetyTimer);
    this.flightSafetyTimer = null;
    this.canvasFlight = null;
    this.clearWorkspaceFlightCanvas();
    this.setData({ canvasFlightActive: false, launchingMaterialId: '' }, () => {
      this.scheduleCanvasRender();
      this.flightActive = false;
      this.processCanvasFlightQueue();
    });
  },

  commitMaterial(id, placement, physicsOptions = {}, onReady) {
    const wasLooseMode = this.data.isLooseMode;
    const previousCount = this.data.selected.length;
    const launchVelocity = physicsOptions.velocity;
    const launchAngularVelocity = physicsOptions.angularVelocity;
    const freezeExistingUntilImpact = !!physicsOptions.freezeExistingUntilImpact && previousCount > 0;
    const restingPhysicsOptions = {
      ...physicsOptions,
      velocity: { x: 0, y: 0 },
      angularVelocity: 0
    };
    this.pushHistory();
    this.setData({
      selected: [...this.data.selected, id],
      placements: [...this.data.placements, placement || this.createLoosePlacement(this.data.selected.length, id)],
      isLooseMode: true,
      selectedBeadIndex: -1
    });
    this.recalculate();
    wx.nextTick(() => {
      if (freezeExistingUntilImpact || !this.physicsEngine || !wasLooseMode) {
        this.stopPhysics();
        this.createPhysicsEngine();
        this.data.selected.slice(0, previousCount).forEach((materialId, index) => {
          this.createPhysicsBody(materialId, this.data.placements[index], index, {
            isStatic: freezeExistingUntilImpact,
            frozenUntilImpact: freezeExistingUntilImpact,
            billiardDamping: 0.86,
            frictionAir: freezeExistingUntilImpact ? 0.045 : 0.07,
            restitution: 0.68
          });
        });
      }
      if (freezeExistingUntilImpact) {
        this.pendingFrozenImpact = true;
        this.pendingFrozenImpactAt = Date.now();
        this.pendingImpactTargets = physicsOptions.impactTargets || null;
      } else if (Body) {
        (this.physicsBodies || []).forEach(body => {
          if (!body || !body.plugin || body.plugin.designIndex >= previousCount) return;
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
          billiardDamping: physicsOptions.billiardDamping || 0.86,
          frictionAir: physicsOptions.frictionAir == null ? 0.075 : physicsOptions.frictionAir,
          restitution: physicsOptions.restitution == null ? 0.74 : physicsOptions.restitution,
          density: physicsOptions.density == null ? 0.0022 : physicsOptions.density
        }
      );
      this.syncPhysicsFrame(() => {
        if (onReady) onReady();
        wx.nextTick(() => {
          if (launchVelocity) Body.setVelocity(launchedBody, launchVelocity);
          if (launchAngularVelocity) Body.setAngularVelocity(launchedBody, launchAngularVelocity);
          this.runPhysics();
        });
      });
    });
  },

  finishFlight() {
    clearTimeout(this.flightTimer);
    this.flightTimer = null;
    clearTimeout(this.flightSafetyTimer);
    this.flightSafetyTimer = null;
    this.setData({ flightBead: null, launchingMaterialId: '' });
    this.flightActive = false;
    this.processFlightQueue();
  },

  shuffleDesign() {
    if (this.data.isShuffling) return;
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
      isShuffling: true,
      isLooseMode: true
    });
    this.recalculate();
    wx.nextTick(() => this.startStringingPhysics());
  },

  startStringingPhysics() {
    try {
      this.stopPhysics();
      if (!this.data.selected.length) {
        this.recoverStringingRuntime();
        return;
      }
      this.createPhysicsEngine();
      this.playSoundEffect('shuffle', 0);
      this.physicsEngine.enableSleeping = false;
      this.physicsEngine.gravity.scale = 0;
      const placements = this.normalizePlacements(this.data.selected, this.data.placements);
      this.data.selected.forEach((id, index) => {
        const body = this.createPhysicsBody(id, placements[index], index);
        body.collisionFilter.group = 0;
        body.collisionFilter.mask = 0xFFFFFFFF;
      });
      const items = this.data.selected.map(id => this.findMaterialById(id)).filter(Boolean);
      const geometry = this.calculateBraceletGeometry(items);
      this.physicsTargets = geometry.angles.map(angle => ({
        x: geometry.center + Math.cos(angle) * geometry.radius,
        y: geometry.center + Math.sin(angle) * geometry.radius
      }));
      if (!this.physicsBodies.length || this.physicsTargets.length !== this.physicsBodies.length) {
        this.completeStringing();
        return;
      }
      this.physicsBodies.forEach((body, index) => {
        const target = this.physicsTargets[index];
        const tangentX = -(target.y - geometry.center);
        const tangentY = target.x - geometry.center;
        const tangentLength = Math.max(1, Math.sqrt(tangentX ** 2 + tangentY ** 2));
        const pullX = target.x - body.position.x;
        const pullY = target.y - body.position.y;
        const pullLength = Math.max(1, Math.sqrt(pullX ** 2 + pullY ** 2));
        const swirlSpeed = this.isLowPerformanceDevice ? 2.1 : (this.isRealDevice ? 3.0 : 3.2);
        const pullSpeed = Math.min(7.2, Math.max(2.3, pullLength * 0.026));
        Body.setVelocity(body, {
          x: tangentX / tangentLength * swirlSpeed + pullX / pullLength * pullSpeed,
          y: tangentY / tangentLength * swirlSpeed + pullY / pullLength * pullSpeed
        });
        Body.setAngularVelocity(body, (index % 2 ? 1 : -1) * 0.038);
      });
      this.stringingStartedAt = Date.now();
      clearTimeout(this.stringingGuardTimer);
      this.stringingGuardTimer = setTimeout(() => {
        if (this.data.isShuffling) this.finishStringing();
      }, 1600);
      this.runPhysics();
    } catch (error) {
      this.recoverStringingRuntime();
    }
  },

  removeItem(e) {
    const index = Number(e.currentTarget.dataset.index);
    this.removeItemAt(index);
  },

  removeItemAt(index, options = {}) {
    if (!Number.isInteger(index) || index < 0 || index >= this.data.selected.length) return;
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
      selectedItems: [],
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
    const updates = {
      selectedBeadIndex: index,
      selectedBeadInfo: this.buildSelectedBeadInfo(index)
    };
    (this.data.selectedItems || []).forEach((item, itemIndex) => {
      const selected = itemIndex === index;
      if (item.selected !== selected) {
        updates[`selectedItems[${itemIndex}].selected`] = selected;
      }
    });
    this.setData(updates);
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

  beginRingReorder(index, touch, rectOverride = null) {
    const setup = rect => {
      if (!rect) return;
      const items = this.data.selected.map(id => this.findMaterialById(id)).filter(Boolean);
      const geometry = this.calculateBraceletGeometry(items);
      this.ringDragState = {
        currentIndex: index,
        originalIndex: index,
        rect,
        scale: rect.width / (geometry.center * 2),
        moved: false,
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

  beginBeadDrag(index, touch, rectOverride = null) {
    const setup = rect => {
      const body = this.physicsBodies.find(item => item.plugin.designIndex === index);
      if (!rect || !body) return;
      const layout = this.getStageLayout();
      const scale = rect.width / (layout.center * 2);
      const point = this.touchToTrayPoint(touch, rect, scale);
      Body.setStatic(body, true);
      Body.setPosition(body, point);
      this.dragState = {
        index,
        body,
        rect,
        scale,
        lastPoint: point,
        lastAt: Date.now(),
        velocity: { x: 0, y: 0 },
        moved: false
      };
      this.setData({
        draggingBeadIndex: index,
        selectedBeadIndex: index,
        selectedBeadInfo: this.buildSelectedBeadInfo(index),
        dragDeleteArmed: this.isPointOutsideTray(point, body.plugin.beadSize)
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
    state.velocity = {
      x: Math.max(-5, Math.min(5, (point.x - state.lastPoint.x) / elapsed * 15)),
      y: Math.max(-5, Math.min(5, (point.y - state.lastPoint.y) / elapsed * 15))
    };
    state.lastPoint = point;
    state.lastAt = now;
    state.moved = true;
    Body.setPosition(state.body, point);
    const outside = this.isPointOutsideTray(point, state.body.plugin.beadSize);
    if (outside !== this.data.dragDeleteArmed) {
      this.setData({ dragDeleteArmed: outside });
    }
    this.syncPhysicsFrame();
  },

  onRingReorderMove(e) {
    const state = this.ringDragState;
    const touch = e.touches && e.touches[0];
    if (!state || !touch) return;
    const items = this.data.selected.map(id => this.findMaterialById(id)).filter(Boolean);
    const currentItem = items[state.currentIndex];
    if (!currentItem) return;
    const geometry = this.calculateBraceletGeometry(items);
    const point = this.touchToTrayPoint(touch, state.rect, state.scale);
    const dx = point.x - geometry.center;
    const dy = point.y - geometry.center;
    const length = Math.max(1, Math.sqrt(dx ** 2 + dy ** 2));
    const outside = this.isPointOutsideTray(point, currentItem.size * 5.4);
    if (outside !== this.data.dragDeleteArmed) {
      this.setData({ dragDeleteArmed: outside });
    }
    state.moved = true;
    state.deleteArmed = outside;
    state.draggingX = point.x;
    state.draggingY = point.y;
    this.patchRingDraggingBeadPosition(state);
    if (outside) return;
    if (this.data.selected.length < 2) return;
    const projected = {
      x: geometry.center + dx / length * geometry.radius,
      y: geometry.center + dy / length * geometry.radius
    };
    let targetIndex = state.currentIndex;
    let nearestDistance = Infinity;
    geometry.angles.forEach((angle, index) => {
      const targetX = geometry.center + Math.cos(angle) * geometry.radius;
      const targetY = geometry.center + Math.sin(angle) * geometry.radius;
      const distance = (projected.x - targetX) ** 2 + (projected.y - targetY) ** 2;
      if (distance < nearestDistance) {
        nearestDistance = distance;
        targetIndex = index;
      }
    });
    if (targetIndex === state.currentIndex) return;
    const selected = [...this.data.selected];
    const placements = [...this.data.placements];
    const [selectedItem] = selected.splice(state.currentIndex, 1);
    const [placementItem] = placements.splice(state.currentIndex, 1);
    selected.splice(targetIndex, 0, selectedItem);
    placements.splice(targetIndex, 0, placementItem);
    state.currentIndex = targetIndex;
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
    if (this.data.useCanvasRenderer) {
      this.scheduleCanvasRender(true);
      return;
    }
    const items = this.data.selected.map(id => this.findMaterialById(id)).filter(Boolean);
    const geometry = this.calculateBraceletGeometry(items);
    const beadSize = Number(state.beadSize || geometry.beadSizes[state.currentIndex] || 54);
    const left = state.draggingX - beadSize / 2;
    const top = state.draggingY - beadSize / 2;
    const rad = Math.atan2(state.draggingY - geometry.center, state.draggingX - geometry.center);
    const updates = {};
    updates[`selectedItems[${state.currentIndex}].style`] = `left:0;top:0;width:${beadSize}rpx;height:${beadSize}rpx;background:${this.buildBeadBackground(items[state.currentIndex])};transform:translate3d(${left.toFixed(1)}rpx,${top.toFixed(1)}rpx,0) rotate(${(rad * 180 / Math.PI).toFixed(1)}deg);`;
    const baseClass = state.currentIndex === this.data.selectedBeadIndex ? 'active' : '';
    updates[`selectedItems[${state.currentIndex}].className`] = `${baseClass} dragging${state.deleteArmed ? ' delete-ready' : ''}`.trim();
    this.setData(updates);
  },

  onBeadTouchEnd() {
    if (this.ringDragState) {
      const state = this.ringDragState;
      this.ringDragState = null;
      const shouldDelete = this.data.dragDeleteArmed;
      if (state.moved) this.suppressBeadTapUntil = Date.now() + 320;
      this.setData({
        draggingBeadIndex: -1,
        dragDeleteArmed: false
      });
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
    if (shouldDelete) {
      Composite.remove(this.physicsEngine.world, state.body);
      this.physicsBodies = this.physicsBodies.filter(body => body !== state.body);
      this.removeItemAt(state.index, { pushHistory: false });
      wx.showToast({ title: '已移出圆盘', icon: 'none' });
      return;
    }
    Body.setStatic(state.body, false);
    Body.setVelocity(state.body, state.velocity);
    this.setData({ draggingBeadIndex: -1, dragDeleteArmed: false });
    this.scheduleDraftPersistence();
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

  isPointOutsideTray(point, beadSize) {
    const layout = this.getStageLayout();
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
    const selected = [...this.data.selected];
    const placements = this.normalizePlacements(selected, this.data.placements);
    const selectedItem = selected[index];
    const placementItem = placements[index];
    selected[index] = selected[nextIndex];
    selected[nextIndex] = selectedItem;
    placements[index] = placements[nextIndex];
    placements[nextIndex] = placementItem;
    this.pushHistory();
    this.setData({
      selected,
      placements,
      selectedBeadIndex: nextIndex,
      selectedBeadInfo: this.buildSelectedBeadInfo(nextIndex, selected, placements)
    });
    this.recalculate();
  },

  recalculate(options = {}) {
    const placements = this.normalizePlacements(this.data.selected, this.data.placements);
    const safeSelectedBeadIndex = this.data.selectedBeadIndex >= 0 && this.data.selectedBeadIndex < this.data.selected.length
      ? this.data.selectedBeadIndex
      : -1;
    const items = this.data.selected.map((id, index) => {
      const material = this.findMaterialById(id);
      if (!material) return null;
      const placement = placements[index] || {};
      return {
        ...material,
        image_url: placement.image_url || material.image_url || ''
      };
    }).filter(Boolean);
    const price = items.reduce((sum, item) => sum + item.price, 0);
    const length = items.reduce((sum, item) => sum + item.size, 0) / 10;
    const weight = items.reduce((sum, item) => sum + item.weight, 0);
    const targetLength = this.data.wristSize + 0.8;
    const warning = items.length === 0
      ? ''
      : length > targetLength + 0.5
        ? '偏长'
        : length < targetLength - 0.5
          ? '偏短'
          : '合适';
    const braceletGeometry = this.calculateBraceletGeometry(items);
    const selectedItems = this.layoutSelectedItems(items, placements, braceletGeometry);
    const stringStyle = this.buildStringStyle(braceletGeometry);
    const counts = {};
    items.forEach(item => {
      const key = MATERIAL_ELEMENT_KEY[item.skuId] || ELEMENT_CN_TO_EN[item.element] || 'metal';
      counts[key] = (counts[key] || 0) + 1;
    });
    const energy = ELEMENTS.map(element => ({
      ...element,
      value: items.length ? Math.round(((counts[element.key] || 0) / items.length) * 100) : 0
    }));

    const currentWrist = items.length
      ? Math.max(0, length - 0.8)
      : 0;
    const sizes = items.map(item => Number(item.size || 0)).filter(Boolean);
    const minSize = sizes.length ? Math.min(...sizes) : 0;
    const maxSize = sizes.length ? Math.max(...sizes) : 0;
    const beadSizeText = !sizes.length ? '--' : minSize === maxSize ? maxSize + 'mm' : minSize + '-' + maxSize + 'mm';
    const summary = {
      count: items.length,
      price: price,
      priceText: price.toFixed(2),
      length: length.toFixed(1),
      weight: weight.toFixed(2),
      currentWrist: currentWrist.toFixed(1),
      beadSizeText: beadSizeText,
      maxLength: targetLength.toFixed(1),
      warning: warning,
      energy: energy
    };
    _energySvgCache = '';
    var energyChartSvgUrl = '';
    const scaleTicks = this.buildScaleTicks(braceletGeometry);
    const actionState = this.buildActionState(items.length);
    const updates = {
      summary,
      stringStyle,
      placements,
      scaleTicks,
      countOverClass: items.length > 18 ? 'over' : '',
      braceletStringClass: items.length ? 'has-beads' : 'empty',
      completionWatermarkClass: items.length ? 'has-beads' : '',
      wearStyle: 'single',
      selectedBeadIndex: safeSelectedBeadIndex,
      selectedBeadInfo: this.buildSelectedBeadInfo(safeSelectedBeadIndex, this.data.selected, placements),
      wristOptionItems: this.buildWristOptionItems(),
      ...actionState,
      energyChartSvgUrl
    };
    if (this.data.useCanvasRenderer) {
      this.livePlacements = placements;
      updates.selectedItems = [];
    } else {
      updates.selectedItems = selectedItems;
    }
    this.setData(updates, () => {
      if (this.data.useCanvasRenderer) this.scheduleCanvasRender();
    });
    if (options.persist !== false) this.scheduleDraftPersistence();
  },

  formatBeadDiameter(size) {
    const numeric = Number(size);
    if (!Number.isFinite(numeric) || numeric <= 0) return '--';
    const text = Number.isInteger(numeric) ? String(numeric) : numeric.toFixed(1).replace(/\.0$/, '');
    return `${text}mm`;
  },

  buildSelectedBeadInfo(index, selected = this.data.selected, placements = this.data.placements) {
    const beadIndex = Number(index);
    if (!Number.isInteger(beadIndex) || beadIndex < 0 || beadIndex >= (selected || []).length) return null;
    const id = selected[beadIndex];
    const material = this.findMaterialById(id) || {};
    const placement = (placements || [])[beadIndex] || {};
    const name = material.name || material.series || material.category || id || '未命名珠子';
    const diameter = material.size || material.size_mm || (material.sku && material.sku.size_mm) || '';
    return {
      index: beadIndex,
      position: beadIndex + 1,
      id,
      name,
      category: material.category || '',
      series: material.series || '',
      diameterText: this.formatBeadDiameter(diameter),
      imageUrl: placement.image_url || material.image_url || ''
    };
  },

  scheduleDraftPersistence() {
    clearTimeout(this.persistDraftTimer);
    this.persistDraftTimer = setTimeout(() => {
      const existingDesign = wx.getStorageSync('currentDesign') || {};
      wx.setStorage({
        key: 'currentDesign',
        data: {
          designId: existingDesign.designId || existingDesign.design_id || '',
          design_id: existingDesign.designId || existingDesign.design_id || '',
          userId: existingDesign.userId || '',
          selected: this.data.selected,
          placements: this.data.placements,
          wristSize: this.data.wristSize,
          wearStyle: 'single',
          isLooseMode: this.data.isLooseMode,
          sourceContext: this.data.sourceContext || this.sourceContext || existingDesign.sourceContext || null,
          summary: this.data.summary
        }
      });
    }, 140);
  },

  layoutSelectedItems(items, placements, geometry) {
    const center = geometry.center;
    return items.map((item, index) => {
      const beadSize = geometry.beadSizes[index];
      const placement = placements[index] || { dx: 0, dy: 0 };
      const rad = geometry.angles[index];
      const targetX = this.data.isLooseMode ? placement.looseX : center + Math.cos(rad) * geometry.radius;
      const targetY = this.data.isLooseMode ? placement.looseY : center + Math.sin(rad) * geometry.radius;
      const left = targetX - beadSize / 2 + placement.dx;
      const top = targetY - beadSize / 2 + placement.dy;
      const ringRotation = rad * 180 / Math.PI;
      const containerRotation = this.data.isLooseMode
        ? Number(placement.rotation || 0)
        : ringRotation;
      const faceRotation = this.data.isLooseMode
        ? 0
        : (Math.round(Number(placement.rotation || 0) / 180) * 180);
      const background = this.buildBeadBackground(item);
      const classes = [];
      if (item.image_url) classes.push('has-image');
      if (index === this.data.selectedBeadIndex) classes.push('active');
      if (index === this.data.draggingBeadIndex) classes.push('dragging');
      if (index === this.data.draggingBeadIndex && this.data.dragDeleteArmed) classes.push('delete-ready');
      return {
        ...item,
        index,
        selected: index === this.data.selectedBeadIndex,
        className: classes.join(' '),
        beadSize,
        shortName: item.name.slice(0, 1),
        imageStyle: `transform:scale(1.02) rotate(${faceRotation}deg);`,
        style: `left:0;top:0;width:${beadSize}rpx;height:${beadSize}rpx;background:${background};transform:translate3d(${left.toFixed(1)}rpx,${top.toFixed(1)}rpx,0) rotate(${containerRotation.toFixed(1)}deg);`
      };
    });
  },

  buildBeadBackground(item = {}) {
    return `radial-gradient(circle at 32% 28%, ${item.shine || '#fff'} 0 10%, ${item.color || '#d8d2c8'} 12% 58%, rgba(0,0,0,.22) 100%)`;
  },

  calculateBraceletGeometry(items) {
    const layout = this.getStageLayout();
    const center = layout.center;
    if (items.length < 3) {
      const count = Math.max(items.length, 1);
      return {
        center,
        radius: layout.radius,
        beadSizes: items.map(item => Math.max(42, Math.min(78, item.size * 5.4))),
        angles: items.map((item, index) => (-90 + (360 / count) * index) * Math.PI / 180)
      };
    }

    let beadSizes = items.map(item => Math.max(42, Math.min(78, item.size * 5.4)));
    let radius = this.solveTangentRingRadius(beadSizes);
    // 物理盘壁的内缘约为 center - 22rpx；额外留 3rpx 安全间距，
    // 避免成串目标与静态盘壁重叠，造成弹簧和碰撞墙持续对抗。
    const maxOuterRadius = center - 25;
    const largestBeadRadius = Math.max(...beadSizes) / 2;
    if (radius + largestBeadRadius > maxOuterRadius) {
      const scale = maxOuterRadius / (radius + largestBeadRadius);
      beadSizes = beadSizes.map(size => size * scale);
      radius = this.solveTangentRingRadius(beadSizes);
    }

    const angles = [-Math.PI / 2];
    for (let index = 1; index < beadSizes.length; index += 1) {
      const centerDistance = (beadSizes[index - 1] + beadSizes[index]) / 2 + STRINGED_BEAD_GAP_RPX;
      const step = 2 * Math.asin(Math.min(1, centerDistance / (2 * radius)));
      angles.push(angles[index - 1] + step);
    }
    return { center, radius, beadSizes, angles };
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

  buildActionState() {
    return {
      shuffleButtonClass: this.data.isShuffling ? 'working' : '',
      randomIconText: this.data.isShuffling ? '...' : '串',
      randomTitle: this.data.isShuffling
        ? '正在成串'
        : (this.data.isLooseMode ? '随机成串' : '解除成串'),
      randomSubtitle: this.data.isLooseMode ? '随机排列珠面' : '恢复自由编辑'
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

  getStageLayout() {
    if (this.stageLayout && this.stageLayout.center) {
      return {
        center: this.stageLayout.center,
        radius: this.stageLayout.radius
      };
    }
    const deviceClass = this.data.deviceClass || '';
    if (deviceClass.includes('device-narrow')) {
      return { center: 260, radius: 200 };
    }
    if (deviceClass.includes('device-short') || deviceClass.includes('device-compact')) {
      return { center: 270, radius: 208 };
    }
    if (deviceClass.includes('device-tall') || deviceClass.includes('device-wide')) {
      return { center: 310, radius: 242 };
    }
    return { center: 288, radius: 224 };
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
    this.getCanvasBeadSprites().forEach(sprite => this.drawCanvasBead(ctx, {
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
      if (!this.data.useCanvasRenderer || !state || !state.canvas) {
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

  async saveDraft(options = {}) {
    let user;
    try {
      user = await auth.requireLogin('登录后才能保存 DIY 草稿。');
    } catch (error) {
      return false;
    }
    const current = wx.getStorageSync('currentDesign') || {};
    const previewResult = await this.prepareCurrentDesignPreview(user.user_id, current);
    const previewImage = previewResult.previewImage || '';
    const displayPreviewImage = previewImage || previewResult.localPreviewImage || current.local_preview_image || '';
    const currentDesignUserId = String(current.userId || current.user_id || '');
    const reusableDesignId = currentDesignUserId === String(user.user_id || '')
      ? (current.designId || current.design_id || '')
      : '';
    const design = {
      designId: reusableDesignId,
      design_id: reusableDesignId,
      userId: user.user_id,
      selected: this.data.selected,
      placements: this.data.placements,
      wristSize: this.data.wristSize,
      wearStyle: 'single',
      isLooseMode: this.data.isLooseMode,
      sourceContext: this.data.sourceContext || this.sourceContext || current.sourceContext || null,
      preview_image: previewImage,
      previewImage,
      image_url: previewImage || current.image_url || '',
      local_preview_image: previewResult.localPreviewImage || current.local_preview_image || '',
      summary: this.data.summary
    };
    const sequence = this.buildCurrentSequence();
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
      preview_image: previewImage,
      previewImage: previewImage,
      image_url: previewImage || current.image_url || '',
      local_preview_image: displayPreviewImage && displayPreviewImage !== previewImage ? displayPreviewImage : (design.local_preview_image || '')
    });
    if (options.showToast !== false) {
      wx.showToast({ title: options.toastTitle || '已保存', icon: 'success' });
    }
    return true;
  },

  buildSharePath(designId) {
    return designId
      ? `/pages/workspace/workspace?shareDesignId=${encodeURIComponent(designId)}`
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
      const saved = await this.saveDraft({ showToast: false });
      if (!saved) return;
      const current = wx.getStorageSync('currentDesign') || {};
      const designId = current.designId || current.design_id || '';
      if (!designId) {
        wx.showToast({ title: '方案保存后才能分享', icon: 'none' });
        return;
      }
      this.hideWorkspaceCanvasForOverlay();
      this.setData({
        showShareSheet: true,
        shareDesignId: designId,
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
    const designId = this.data.shareDesignId || current.designId || current.design_id || '';
    const imageUrl = this.data.sharePreviewImage || current.preview_image || current.previewImage || current.image_url || '';
    return {
      title: designId ? this.buildShareDesignTitle(current) : '打开宇涧水晶 DIY 工作台',
      path: this.buildSharePath(designId),
      imageUrl
    };
  },

  onShareTimeline() {
    const current = wx.getStorageSync('currentDesign') || {};
    const designId = this.data.shareDesignId || current.designId || current.design_id || '';
    const imageUrl = this.data.sharePreviewImage || current.preview_image || current.previewImage || current.image_url || '';
    return {
      title: designId ? this.buildShareDesignTitle(current) : '宇涧水晶 DIY 工作台',
      query: designId ? `shareDesignId=${encodeURIComponent(designId)}` : '',
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
      _energySvgCache = svgToDataURI(generateChartSVG(energyData, { width: 460, height: 460, padding: 50, gridColor: 'rgba(0,0,0,0.06)', axisColor: 'rgba(0,0,0,0.1)', areaStroke: '#c0a36b', labelColor: 'rgba(0,0,0,0.7)', valueColor: 'rgba(0,0,0,0.4)', showLabels: true, showValues: true }));
    }
    this.setData({ showEnergyModal: true, energyChartSvgUrl: _energySvgCache });
  },

  toggleEnergyPanel() {
    this.setData({ showEnergyPanel: !this.data.showEnergyPanel });
  },

  closeEnergyModal() {
    this.setData({ showEnergyModal: false }, () => this.restoreWorkspaceCanvasAfterOverlay());
  },

  goBack() {
    const pages = getCurrentPages();
    if (pages.length > 1) {
      wx.navigateBack();
      return;
    }
    wx.switchTab({ url: '/pages/home/home' });
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
  o.valueColor = opts.valueColor || 'rgba(0,0,0,0.4)'; o.dotRadius = opts.dotRadius || 5;
  o.showLabels = opts.showLabels !== false; o.showValues = opts.showValues !== false;

  var cx = o.width / 2, cy = o.height / 2, maxR = Math.min(o.width, o.height) / 2 - o.padding;
  var pts = __calcPoints__(data, cx, cy, maxR);
  var svg = [];

  // background
  svg.push('<svg xmlns="http://www.w3.org/2000/svg" width="' + o.width + '" height="' + o.height + '" viewBox="0 0 ' + o.width + ' ' + o.height + '">');

  // gradient
  svg.push('<defs><linearGradient id="eg" x1="0%" y1="0%" x2="100%" y2="100%">');
  svg.push('<stop offset="0%" stop-color="' + o.areaStroke.replace(/[^,]+\)$/, '0.35)') + '"/><stop offset="100%" stop-color="' + o.areaStroke.replace(/[^,]+\)$/, '0.1)') + '"/></linearGradient>');

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
  svg.push('<path d="' + ep + '" fill="url(#eg)" stroke="' + o.areaStroke + '" stroke-width="' + o.areaStrokeWidth + '" stroke-linejoin="round" opacity="0.85"/>');

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
