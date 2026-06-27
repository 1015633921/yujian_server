const { getCommunityPost: getLocalCommunityPost } = require('../../utils/communityData');
const { getCommunityPost } = require('../../utils/api');
const { assetUrl } = require('../../utils/assets');

const ASSETS = {
  aquamarine: assetUrl('home/aquamarine.webp'),
  clearQuartz: assetUrl('home/clear-quartz.webp'),
  moonstone: assetUrl('home/moonstone.webp'),
  citrine: assetUrl('home/citrine.webp'),
  amethyst: assetUrl('home/amethyst.webp')
};

const TONE_CONFIG = {
  blue: {
    label: '清透沟通',
    color: '#4F83B7',
    soft: '#EAF3F8',
    sequence: ['aquamarine', 'clearQuartz', 'moonstone', 'aquamarine']
  },
  clear: {
    label: '清爽净化',
    color: '#7C8B92',
    soft: '#F1F4F3',
    sequence: ['clearQuartz', 'moonstone', 'aquamarine', 'clearQuartz']
  },
  gold: {
    label: '行动蓄能',
    color: '#B98A2B',
    soft: '#FBF2D8',
    sequence: ['citrine', 'clearQuartz', 'citrine', 'moonstone']
  },
  pink: {
    label: '温柔陪伴',
    color: '#C77686',
    soft: '#F8E9EC',
    sequence: ['moonstone', 'clearQuartz', 'amethyst', 'moonstone']
  },
  black: {
    label: '边界守护',
    color: '#30353A',
    soft: '#ECEEED',
    sequence: ['amethyst', 'clearQuartz', 'amethyst', 'moonstone']
  }
};

const MATERIAL_ALIAS = {
  海蓝宝: ASSETS.aquamarine,
  月光石: ASSETS.moonstone,
  白水晶: ASSETS.clearQuartz,
  黄水晶: ASSETS.citrine,
  紫水晶: ASSETS.amethyst,
  粉晶: ASSETS.moonstone,
  黑曜石: ASSETS.amethyst,
  虎眼石: ASSETS.citrine,
  银色隔珠: ASSETS.clearQuartz,
  金色隔珠: ASSETS.citrine,
  隔珠: ASSETS.clearQuartz
};

const MATERIAL_CODE_ALIAS = {
  aquamarine: ASSETS.aquamarine,
  clearQuartz: ASSETS.clearQuartz,
  moonstone: ASSETS.moonstone,
  citrine: ASSETS.citrine,
  amethyst: ASSETS.amethyst,
  roseQuartz: ASSETS.moonstone,
  obsidian: ASSETS.amethyst,
  tigerEye: ASSETS.citrine,
  silverSpacer: ASSETS.clearQuartz,
  goldSpacer: ASSETS.citrine
};

const MATERIAL_CODE_LABELS = {
  aquamarine: '海蓝宝',
  clearQuartz: '白水晶',
  moonstone: '月光石',
  citrine: '黄水晶',
  amethyst: '紫水晶',
  roseQuartz: '粉晶',
  obsidian: '黑曜石',
  tigerEye: '虎眼石',
  silverSpacer: '银色隔珠',
  goldSpacer: '金色隔珠'
};

function cleanText(value, fallback = '') {
  if (value === null || value === undefined) return fallback;
  const text = String(value).trim();
  if (!text || text === '-' || text === 'NaN') return fallback;
  return text;
}

function todayText() {
  const now = new Date();
  const month = `${now.getMonth() + 1}`.padStart(2, '0');
  const day = `${now.getDate()}`.padStart(2, '0');
  return `${now.getFullYear()}-${month}-${day}`;
}

function createRingBeads(sequence, count = 18, radius = 96, size = 42) {
  return Array.from({ length: count }, (_, index) => {
    const angle = (360 / count) * index;
    const key = sequence[index % sequence.length];
    return {
      id: `${key}-${index}`,
      src: ASSETS[key] || ASSETS.clearQuartz,
      style: `width:${size}rpx;height:${size}rpx;transform:rotate(${angle}deg) translateY(-${radius}rpx) rotate(${-angle}deg);`
    };
  });
}

function firstImageUrl(entry) {
  if (!entry || typeof entry !== 'object') return '';
  const candidates = []
    .concat(entry.image_urls || [])
    .concat(entry.image_pool || [])
    .concat(entry.images || [])
    .concat(entry.url || [])
    .concat(entry.image_url || [])
    .concat(entry.image || [])
    .concat(entry.imageUrl || [])
    .concat(entry.cover_image || [])
    .concat(entry.cover || [])
    .concat(entry.thumb_url || [])
    .concat(entry.thumbnail || [])
    .concat(entry.thumb || []);
  return candidates
    .map(item => (item && typeof item === 'object' ? item.url || item.image_url || item.image || item.src : item))
    .find(url => typeof url === 'string' && url.trim()) || '';
}

function materialCode(entry, fallback = '') {
  if (!entry || typeof entry !== 'object') return cleanText(entry, fallback);
  return cleanText(
    entry.code || entry.key || entry.id || entry.sku || entry.sku_id || entry.material_id || entry.materialId,
    fallback
  );
}

function materialName(entry, index) {
  if (!entry || typeof entry !== 'object') {
    const code = cleanText(entry, '');
    return MATERIAL_CODE_LABELS[code] || cleanText(entry, `材料 ${index + 1}`);
  }
  const code = materialCode(entry);
  return cleanText(
    entry.name || entry.title || entry.material_name || entry.materialName || entry.series || entry.category,
    MATERIAL_CODE_LABELS[code] || `材料 ${index + 1}`
  );
}

function materialRole(entry, index, roles) {
  if (entry && typeof entry === 'object') {
    return cleanText(entry.role || entry.type || entry.position, roles[index] || '材料');
  }
  return roles[index] || '材料';
}

function materialDesc(entry, index) {
  if (entry && typeof entry === 'object') {
    const text = cleanText(entry.desc || entry.description || entry.effect || entry.reason || entry.note, '');
    if (text) return text;
  }
  return index === 0
    ? '承接整条手串的主要气质'
    : index === 1
      ? '让搭配更稳定耐看'
      : index === 2
        ? '补足清透与层次'
        : '增加细节与呼吸感';
}

function materialImage(entry, recipeEntry, title, toneConfig, index) {
  const code = materialCode(entry, materialCode(recipeEntry, ''));
  const recipeCode = materialCode(recipeEntry, '');
  return firstImageUrl(entry)
    || firstImageUrl(recipeEntry)
    || MATERIAL_ALIAS[title]
    || MATERIAL_CODE_ALIAS[code]
    || MATERIAL_CODE_ALIAS[recipeCode]
    || ASSETS[toneConfig.sequence[index % toneConfig.sequence.length]]
    || '';
}

function materialEntries(post, toneConfig) {
  const recipe = Array.isArray(post.recipe) ? post.recipe : [];
  const materials = Array.isArray(post.materials) && post.materials.length
    ? post.materials
    : (recipe.length ? recipe : ['主石', '辅石', '平衡石', '点缀隔珠']);
  const roles = ['主石', '辅石', '平衡石', '点缀'];
  return materials.map((entry, index) => {
    const recipeEntry = recipe[index];
    const title = materialName(entry, index);
    return {
      index: index + 1,
      role: materialRole(entry, index, roles),
      name: title,
      desc: materialDesc(entry, index),
      image: materialImage(entry, recipeEntry, title, toneConfig, index),
      color: toneConfig.color
    };
  });
}

function normalizePost(post) {
  const tone = cleanText(post.tone, 'clear');
  const toneConfig = TONE_CONFIG[tone] || TONE_CONFIG.clear;
  const title = cleanText(post.title, '灵感方案');
  const desc = cleanText(post.desc || post.description || post.summary, '真实材质搭配，可带入 DIY 工作台继续调整。');
  const story = cleanText(post.story, '这条方案以清透、耐看和日常佩戴为核心，适合从真实材质出发继续微调。');
  const scene = cleanText(post.scene, '适合通勤、轻社交、日常穿搭和想要低负担佩戴的场景。');
  const authorNote = cleanText(post.authorNote || post.author_note, '进入 DIY 工作台后，可以按自己的手围、预算和颜色偏好继续调整。');
  const imageUrl = cleanText(post.image_url || post.cover_image || post.coverUrl || post.image || post.thumbnail, '');
  return {
    raw: post,
    id: cleanText(post.id || post.post_id || post.slug, ''),
    title,
    author: cleanText(post.author || post.creator || post.nickname, '宇涧灵感室'),
    desc,
    story,
    scene,
    authorNote,
    tone,
    toneLabel: toneConfig.label,
    toneColor: toneConfig.color,
    toneSoft: toneConfig.soft,
    imageUrl,
    dateText: cleanText(post.updated_at, todayText()).slice(0, 10),
    materials: materialEntries(post, toneConfig),
    visualBeads: createRingBeads(toneConfig.sequence),
    sceneItems: scene.split(/、|，|,|；|;/).map(item => cleanText(item)).filter(Boolean).slice(0, 4),
    recipe: post.recipe || []
  };
}

Page({
  data: {
    post: null,
    viewPost: null,
    isFavorite: false,
    favoriteText: '收藏灵感'
  },

  onLoad(options) {
    this.loadPost(options.id);
  },

  async loadPost(id) {
    let post = getLocalCommunityPost(id);
    try {
      post = await getCommunityPost(id);
    } catch (error) {
      console.warn('community detail fallback:', error.message || error);
    }

    const viewPost = normalizePost(post || {});
    const favorites = wx.getStorageSync('communityFavorites') || [];
    this.setData({
      post: viewPost.raw,
      viewPost,
      isFavorite: favorites.some(item => item.id === viewPost.id),
      favoriteText: favorites.some(item => item.id === viewPost.id) ? '已收藏' : '收藏灵感'
    });
  },

  toggleFavorite() {
    const post = this.data.viewPost;
    if (!post) return;
    const favorites = wx.getStorageSync('communityFavorites') || [];
    const isFavorite = favorites.some(item => item.id === post.id);
    const nextFavorites = isFavorite
      ? favorites.filter(item => item.id !== post.id)
      : [{ id: post.id, title: post.title, tone: post.tone, recipe: post.recipe, addedAt: Date.now() }, ...favorites];
    wx.setStorageSync('communityFavorites', nextFavorites);
    this.setData({
      isFavorite: !isFavorite,
      favoriteText: isFavorite ? '收藏灵感' : '已收藏'
    });
    wx.showToast({ title: isFavorite ? '已取消收藏' : '已收藏', icon: 'none' });
  },

  useSame() {
    const post = this.data.viewPost;
    if (!post) return;
    wx.setStorageSync('recommendedRecipe', post.recipe);
    wx.setStorageSync('workspacePreset', 'recommended');
    wx.switchTab({ url: '/pages/workspace/workspace' });
  },

  goBack() {
    const pages = getCurrentPages();
    if (pages.length > 1) {
      wx.navigateBack();
      return;
    }
    wx.navigateTo({ url: '/pages/community/community' });
  },

  noop() {},

  todayText
});
