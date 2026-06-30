const { getCommunityPosts: getLocalCommunityPosts, getCommunityPost } = require('../../utils/communityData');
const auth = require('../../utils/auth');
const {
  getCommunityPosts: getRemoteCommunityPosts,
  getCommunityFavorites,
  getCommunityPost: getRemoteCommunityPost,
  deleteCommunityFavorite
} = require('../../utils/api');
const { assetUrl } = require('../../utils/assets');

const ASSETS = {
  aquamarine: assetUrl('home/aquamarine.webp'),
  clearQuartz: assetUrl('home/clear-quartz.webp'),
  moonstone: assetUrl('home/moonstone.webp'),
  citrine: assetUrl('home/citrine.webp'),
  amethyst: assetUrl('home/amethyst.webp')
};

const TONE_BEADS = {
  blue: ['aquamarine', 'moonstone', 'clearQuartz', 'aquamarine'],
  gold: ['citrine', 'clearQuartz', 'citrine', 'moonstone'],
  pink: ['moonstone', 'clearQuartz', 'amethyst', 'moonstone'],
  clear: ['clearQuartz', 'moonstone', 'clearQuartz', 'aquamarine'],
  black: ['amethyst', 'clearQuartz', 'amethyst', 'moonstone']
};

const TYPE_LABELS = {
  community_post: '灵感搭配',
  recommendation_plan: '推荐方案',
  daily_energy: '每日能量',
  material_inspiration: '材料灵感'
};

const TYPE_AUTHORS = {
  community_post: '宇涧灵感室',
  recommendation_plan: '宇涧测算工坊',
  daily_energy: '今日能量',
  material_inspiration: '宇涧材料库'
};

function cleanText(value, fallback = '') {
  if (value === null || value === undefined) return fallback;
  const text = String(value).trim();
  if (!text || text === '-' || text === 'NaN') return fallback;
  return text;
}

function createRingBeads(sequence, count = 16, radius = 86, size = 42) {
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
    .concat(entry.cover_images || [])
    .concat(entry.imageUrl || [])
    .concat(entry.image_url || [])
    .concat(entry.cover_image || [])
    .concat(entry.coverUrl || [])
    .concat(entry.cover || [])
    .concat(entry.thumbnail_url || [])
    .concat(entry.thumb_url || [])
    .concat(entry.thumbnail || [])
    .concat(entry.thumb || [])
    .concat(entry.image || []);

  return candidates
    .map(item => (item && typeof item === 'object' ? item.url || item.image_url || item.image || item.src : item))
    .find(url => typeof url === 'string' && url.trim()) || '';
}

function favoriteId(item) {
  const favorite = item && (item.item || item);
  return cleanText(
    (item && (item.post_id || item.id)) || (favorite && (favorite.post_id || favorite.id)),
    ''
  );
}

function tagsFor(base, favoriteType) {
  const tags = Array.isArray(base.tags) ? base.tags.filter(Boolean) : [];
  if (tags.length) return tags.slice(0, 3);
  if (Array.isArray(base.materials) && base.materials.length) {
    return base.materials.map(item => cleanText(item && (item.name || item.title) || item)).filter(Boolean).slice(0, 3);
  }
  if (favoriteType === 'daily_energy') return ['今日能量', '可带入 DIY'];
  if (favoriteType === 'material_inspiration') return ['材料灵感', '单珠收藏'];
  if (favoriteType === 'recommendation_plan') return ['测算推荐', '定制方案'];
  return ['灵感搭配'];
}

function actionTextFor(favoriteType) {
  if (favoriteType === 'recommendation_plan') return '查看方案详情 →';
  if (favoriteType === 'daily_energy') return '进入工作台调整 →';
  if (favoriteType === 'material_inspiration') return '用这颗材料开工 →';
  return '查看搭配故事 →';
}

function normalizeFavorite(item, post, index) {
  if (!item) return null;
  const favorite = item.item || item;
  const id = favoriteId(item);
  if (!id) return null;

  const favoriteType = cleanText(favorite.favorite_type || favorite.type || item.favorite_type, 'community_post');
  const base = favoriteType === 'community_post'
    ? { ...favorite, ...(post || {}) }
    : { ...(post || {}), ...favorite };
  const tone = cleanText(base.tone, ['blue', 'clear', 'gold', 'pink', 'black'][index % 5]);
  const title = cleanText(base.title || base.name, '灵感方案');
  const desc = cleanText(
    base.desc || base.description || base.summary || base.effect || base.story,
    '真实材质搭配，可带入 DIY 工作台继续调整。'
  );
  const displayTags = tagsFor(base, favoriteType);

  return {
    ...base,
    id,
    favoriteType,
    sourceId: base.source_id || base.sourceId || id,
    title,
    desc,
    tone,
    imageUrl: firstImageUrl(base),
    author: cleanText(base.author || base.creator || base.nickname, TYPE_AUTHORS[favoriteType] || '宇涧灵感室'),
    sceneText: cleanText(base.sceneText || base.scene || displayTags[0], TYPE_LABELS[favoriteType] || '灵感收藏'),
    displayTags,
    typeLabel: TYPE_LABELS[favoriteType] || '灵感收藏',
    actionText: actionTextFor(favoriteType),
    visualBeads: createRingBeads(TONE_BEADS[tone] || TONE_BEADS.clear),
    addedAt: item.addedAt || item.updated_at || item.created_at || favorite.addedAt || 0
  };
}

Page({
  data: {
    loading: true,
    posts: []
  },

  onShow() {
    this.loadFavorites();
  },

  async loadFavorites() {
    this.setData({ loading: true });
    let stored = wx.getStorageSync('communityFavorites') || [];
    try {
      const user = await auth.requireLogin('登录后才能查看灵感收藏。');
      const rows = await getCommunityFavorites(user.user_id, { silent: true, timeout: 8000 });
      stored = Array.isArray(rows) ? rows : [];
      wx.setStorageSync('communityFavorites', stored);
    } catch (error) {
      console.warn('load community favorites fallback:', error.message || error);
    }

    const seen = new Set();
    const favorites = (Array.isArray(stored) ? stored : []).filter(item => {
      const id = favoriteId(item);
      if (!item || !id || seen.has(id)) return false;
      seen.add(id);
      return true;
    });

    const postMap = new Map(getLocalCommunityPosts().map(post => [post.id, post]));
    try {
      const remotePosts = await getRemoteCommunityPosts({ limit: 80, silent: true, timeout: 8000 });
      (remotePosts || []).forEach(post => {
        const id = cleanText(post && (post.id || post.post_id || post.slug), '');
        if (id) postMap.set(id, post);
      });
    } catch (error) {
      console.warn('favorite community post map fallback:', error.message || error);
    }

    const posts = favorites
      .map((item, index) => normalizeFavorite(item, postMap.get(favoriteId(item)), index))
      .filter(Boolean);

    this.setData({ posts, loading: false });
  },

  openPost(e) {
    const id = e.currentTarget.dataset.id;
    if (!id) return;
    const post = this.data.posts.find(item => item.id === id);
    if (post && post.favoriteType === 'recommendation_plan') {
      wx.navigateTo({
        url: `/pages/plan-detail/plan-detail?id=${encodeURIComponent(post.sourceId || id.replace(/^recommendation:/, ''))}`
      });
      return;
    }
    if (post && ['daily_energy', 'material_inspiration'].includes(post.favoriteType)) {
      if (post.recipe) wx.setStorageSync('recommendedRecipe', post.recipe);
      wx.setStorageSync('workspacePreset', 'recommended');
      wx.switchTab({ url: '/pages/workspace/workspace' });
      return;
    }
    wx.navigateTo({
      url: `/pages/community-detail/community-detail?id=${id}&from=favorites`
    });
  },

  async useSame(e) {
    const id = e.currentTarget.dataset.id;
    let post = this.data.posts.find(item => item.id === id) || getCommunityPost(id);
    if (post && post.favoriteType !== 'recommendation_plan') {
      try {
        const remotePost = await getRemoteCommunityPost(id, { silent: true, timeout: 8000 });
        post = {
          ...post,
          ...remotePost,
          recipe: remotePost.recipe || post.recipe
        };
      } catch (error) {
        console.warn('favorite detail fallback:', error.message || error);
      }
    }
    if (!post) return;
    wx.setStorageSync('recommendedRecipe', post.recipe);
    wx.setStorageSync('workspacePreset', 'recommended');
    wx.switchTab({ url: '/pages/workspace/workspace' });
  },

  removeFavorite(e) {
    const id = e.currentTarget.dataset.id;
    const post = this.data.posts.find(item => item.id === id);
    if (!post) return;
    wx.showModal({
      title: '取消收藏？',
      content: post.title,
      confirmText: '取消收藏',
      confirmColor: '#7A4E3A',
      success: res => {
        if (!res.confirm) return;
        this.removeFavoriteFromServer(id);
      }
    });
  },

  async removeFavoriteFromServer(id) {
    try {
      const user = await auth.requireLogin('登录后才能管理灵感收藏。');
      await deleteCommunityFavorite(user.user_id, id);
      const favorites = (wx.getStorageSync('communityFavorites') || [])
        .filter(item => favoriteId(item) !== id);
      wx.setStorageSync('communityFavorites', favorites);
      this.loadFavorites();
    } catch (error) {
      wx.showToast({ title: error.message || '取消收藏失败', icon: 'none' });
    }
  },

  onImageError(e) {
    const id = e.currentTarget.dataset.id;
    const posts = this.data.posts.map(item => (item.id === id ? { ...item, imageUrl: '' } : item));
    this.setData({ posts });
  },

  goCommunity() {
    wx.navigateTo({ url: '/pages/community/community' });
  }
});
