const auth = require('../../utils/auth');
const { getCommunityPosts: getLocalCommunityPosts } = require('../../utils/communityData');
const { getRecommendations: getLocalRecommendations } = require('../../utils/recommendationData');
const { getTodayDailyEnergy, getCommunityPosts, getRecommendationPlans, getHomeBanners } = require('../../utils/api');
const { assetUrl } = require('../../utils/assets');

const TAB_BAR_PAGES = ['/pages/home/home', '/pages/assessment/assessment', '/pages/workspace/workspace', '/pages/profile/profile'];
const DAILY_CACHE_KEY = 'todayDailyEnergy';
const DAILY_REFRESH_DATE_KEY = 'todayDailyEnergyRefreshDate';
const ASSETS = {
  aquamarine: assetUrl('home/aquamarine.webp'),
  clearQuartz: assetUrl('home/clear-quartz.webp'),
  moonstone: assetUrl('home/moonstone.webp'),
  citrine: assetUrl('home/citrine.webp'),
  amethyst: assetUrl('home/amethyst.webp')
};
const INSPIRATION_TONES = ['blue', 'clear', 'gold', 'pink', 'black'];
const INSPIRATION_TONE_BEADS = {
  blue: ['aquamarine', 'moonstone', 'clearQuartz', 'aquamarine'],
  gold: ['citrine', 'clearQuartz', 'citrine', 'moonstone'],
  pink: ['moonstone', 'clearQuartz', 'amethyst', 'moonstone'],
  clear: ['clearQuartz', 'moonstone', 'clearQuartz', 'aquamarine'],
  black: ['amethyst', 'clearQuartz', 'amethyst', 'moonstone'],
  violet: ['amethyst', 'clearQuartz', 'moonstone', 'amethyst']
};

function createRingBeads(sequence, count, radius, size) {
  return Array.from({ length: count }, (_, index) => {
    const angle = (360 / count) * index;
    const key = sequence[index % sequence.length];
    return {
      src: ASSETS[key] || ASSETS.clearQuartz,
      style: `width:${size}rpx;height:${size}rpx;transform:rotate(${angle}deg) translateY(-${radius}rpx) rotate(${-angle}deg);`
    };
  });
}

function normalizeRecommendationTone(tone) {
  const value = `${tone || ''}`.toLowerCase();
  if (['gold', 'yellow', 'warm', 'citrine'].includes(value)) return 'gold';
  if (['violet', 'purple', 'amethyst'].includes(value)) return 'violet';
  if (['blue', 'aqua', 'aquamarine'].includes(value)) return 'blue';
  return 'clear';
}

function decorateRecommendations(source) {
  const hasRemoteSource = Array.isArray(source) && source.length > 0;
  const presets = [
    {
      id: 'moonlight-sleep',
      tone: 'blue',
      sequence: ['moonstone', 'clearQuartz', 'aquamarine', 'moonstone'],
      sceneLabel: '睡眠浅、情绪敏感',
      actionLabel: '一键套用',
      shortName: '月光石轻眠',
      shortDesc: '舒缓助眠 · 温柔守护'
    },
    {
      id: 'citrine-action',
      tone: 'gold',
      sequence: ['citrine', 'clearQuartz', 'citrine'],
      sceneLabel: '事业、考试、面试',
      actionLabel: '查看搭配',
      shortName: '黄水晶能量',
      shortDesc: '自信能量 · 积极行动'
    },
    {
      id: 'amethyst-focus',
      tone: 'violet',
      sequence: ['amethyst', 'clearQuartz', 'amethyst', 'moonstone'],
      sceneLabel: '创作、学习、专注',
      actionLabel: '立即定制',
      shortName: '紫水晶灵感',
      shortDesc: '灵感创作 · 专注思考'
    }
  ];
  const presetById = presets.reduce((map, item) => {
    map[item.id] = item;
    return map;
  }, {});
  const presetByTone = {
    blue: presets[0],
    clear: { ...presets[0], tone: 'clear', sequence: ['clearQuartz', 'moonstone', 'aquamarine'] },
    gold: presets[1],
    violet: presets[2]
  };

  return (hasRemoteSource ? source : getLocalRecommendations()).map((item, index) => {
    const normalizedTone = normalizeRecommendationTone(item.tone || item.theme);
    const preset = presetById[item.id] || presetByTone[normalizedTone] || presets[index % presets.length];
    const name = item.shortName || item.short_name || item.name || preset.shortName;
    const description = item.shortDesc || item.short_desc || item.subtitle || item.desc || item.description || preset.shortDesc;
    const coverImage = item.coverImage || item.cover_image || item.image_url || item.image || '';
    return {
      ...preset,
      ...item,
      tone: normalizedTone || preset.tone,
      shortName: name,
      shortDesc: description,
      coverImage,
      sceneLabel: item.sceneLabel || item.scene_label || preset.sceneLabel,
      actionLabel: item.actionLabel || item.action_label || preset.actionLabel,
      visualBeads: createRingBeads(preset.sequence, 10, 48, 32)
    };
  });
}

function decorateInspirations(source) {
  const imageByTone = {
    blue: ASSETS.aquamarine,
    clear: ASSETS.clearQuartz,
    pink: ASSETS.moonstone,
    black: ASSETS.amethyst,
    gold: ASSETS.citrine,
    violet: ASSETS.amethyst
  };
  const rows = Array.isArray(source) && source.length
    ? source
    : getLocalCommunityPosts().slice(0, 4);
  return rows.slice(0, 8).map((item, index) => {
    const tone = `${item.tone || INSPIRATION_TONES[index % INSPIRATION_TONES.length]}`.toLowerCase();
    const normalizedTone = INSPIRATION_TONE_BEADS[tone] ? tone : INSPIRATION_TONES[index % INSPIRATION_TONES.length];
    const title = item.title || item.name || `灵感方案 ${index + 1}`;
    const desc = item.desc || item.description || item.summary || item.scene || '';
    const coverImage = item.coverImage || item.cover_image || item.image_url || item.imageUrl || item.image || item.thumbnail || '';
    return {
      ...item,
      id: item.id || item.post_id || item.slug || `inspiration-${index}`,
      tone: normalizedTone,
      coverImage,
      previewImage: coverImage || imageByTone[normalizedTone] || ASSETS.clearQuartz,
      shortName: title,
      shortDesc: desc,
      visualBeads: item.visualBeads || createRingBeads(INSPIRATION_TONE_BEADS[normalizedTone] || INSPIRATION_TONE_BEADS.clear, 10, 48, 32)
    };
  });
}

function defaultHomeBanners() {
  return [
    {
      id: 'local-main',
      title: '真实自然，灵感有根',
      subtitle: '实拍选材 · 手围适配 · 成串预览 · 方案留存，让每一串都清清楚楚来处。',
      eyebrow: 'CRYSTAL HANDMADE STUDIO',
      actionText: '开始定制 →',
      actionUrl: '/pages/custom-mode/custom-mode',
      image_url: '',
      theme: 'dark'
    },
    {
      id: 'local-workspace',
      title: '先看见，再下单',
      subtitle: '进入 DIY 工作台，拖拽珠材、调整腕围、实时查看成串效果。',
      eyebrow: 'DIY WORKBENCH',
      actionText: '打开工作台 →',
      actionUrl: '/pages/workspace/workspace',
      image_url: '',
      theme: 'warm'
    }
  ];
}

function decorateHomeBanners(source) {
  const rows = source && source.length ? source : defaultHomeBanners();
  return rows.map((item, index) => ({
    id: item.id || `banner-${index}`,
    title: item.title || '宇涧水晶手作',
    subtitle: item.subtitle || '',
    eyebrow: item.eyebrow || 'CRYSTAL HANDMADE STUDIO',
    actionText: item.actionText || item.action_text || '开始定制 →',
    actionUrl: item.actionUrl || item.action_url || '/pages/custom-mode/custom-mode',
    image_url: item.image_url || item.image || '',
    theme: item.theme || 'dark'
  }));
}

function todayKey() {
  const now = new Date();
  const month = `${now.getMonth() + 1}`.padStart(2, '0');
  const day = `${now.getDate()}`.padStart(2, '0');
  return `${now.getFullYear()}-${month}-${day}`;
}

function isFreshDailyPayload(daily) {
  return !!(
    daily
    && Number(daily.content_version) >= 2
    && daily.season_hint
    && daily.season_hint.summary
  );
}

Page({
  data: {
    daily: {
      vitality: 82,
      inspiration: 94,
      color: '海盐蓝',
      number: 7,
      stone: '海蓝宝',
      keyword: '稳定流动的一天',
      keywords: ['稳定', '表达', '清透'],
      summary: '登录后获取你的今日能量，并生成适合今天佩戴的手串。',
      actionTip: '先让节奏慢下来',
      recommendedCrystals: [],
      recommendedNames: '海蓝宝 · 白水晶 · 月光石',
      commerceEntry: {},
      workbenchPayload: null,
      loaded: false,
      loginHint: '登录后获取你的今日能量',
      raw: null
    },
    homeBanners: decorateHomeBanners(),
    homeAssets: ASSETS,
    currentBannerIndex: 0,
    heroBeads: createRingBeads(['aquamarine', 'moonstone', 'clearQuartz', 'moonstone', 'amethyst'], 12, 66, 48),
    bestSellers: decorateRecommendations(),
    inspirations: decorateInspirations(),
    inspirationCart: [],
    shoppingCart: [],
    showStoneSheet: false,
    dailyStoneDetail: null,
    labTabbarClass: ''
  },

  onShow() {
    this.hideNativeTabBar();
    this.lastHomeScrollTop = 0;
    if (this.data.labTabbarClass) {
      this.setData({ labTabbarClass: '' });
    }
    this.setData({
      inspirationCart: wx.getStorageSync('inspirationCart') || [],
      shoppingCart: wx.getStorageSync('diyDesignCart') || []
    });
    this.hydrateDailyEnergyFromStorage();
    this.refreshDailyEnergyOnEntry();
    this.loadCmsContent();
  },

  onHide() {
    clearTimeout(this.tabbarSetDataTimer);
    this.restoreNativeTabBar();
  },

  onUnload() {
    this.restoreNativeTabBar();
  },

  onPageScroll(e) {
    const currentTop = Number(e.scrollTop) || 0;
    const previousTop = this.lastHomeScrollTop || 0;
    const delta = currentTop - previousTop;
    this.lastHomeScrollTop = currentTop;

    if (Math.abs(delta) < 12) return;

    const shouldHide = delta > 0 && currentTop > 80;
    const nextClass = shouldHide ? 'is-hidden' : '';
    if (nextClass === this.data.labTabbarClass) return;

    clearTimeout(this.tabbarSetDataTimer);
    this.tabbarSetDataTimer = setTimeout(() => {
      this.setData({ labTabbarClass: nextClass });
    }, 16);
  },

  hideNativeTabBar() {
    if (!wx.hideTabBar) return;
    wx.hideTabBar({
      animation: false,
      fail: () => {}
    });
  },

  restoreNativeTabBar() {
    clearTimeout(this.tabbarSetDataTimer);
    if (!wx.showTabBar) return;
    wx.showTabBar({
      animation: false,
      fail: () => {}
    });
  },

  async loadCmsContent() {
    try {
      const [banners, recommendations, posts] = await Promise.all([
        getHomeBanners({ limit: 8 }),
        getRecommendationPlans({ homeHot: true, limit: 8 }),
        getCommunityPosts({ limit: 8 })
      ]);
      this.setData({
        homeBanners: decorateHomeBanners(banners),
        bestSellers: decorateRecommendations(recommendations.length ? recommendations : undefined),
        inspirations: decorateInspirations(posts.length ? posts : undefined)
      });
    } catch (error) {
      console.warn('home cms fallback:', error.message || error);
    }
  },

  hydrateDailyEnergyFromStorage() {
    const cached = wx.getStorageSync(DAILY_CACHE_KEY);
    if (cached) this.applyDailyEnergy(cached);
  },

  async refreshDailyEnergyOnEntry() {
    const cached = wx.getStorageSync(DAILY_CACHE_KEY);
    const refreshedDate = wx.getStorageSync(DAILY_REFRESH_DATE_KEY);
    const shouldRefresh = refreshedDate !== todayKey() || !isFreshDailyPayload(cached);
    if (!shouldRefresh || this.dailyAutoRefreshing) return;
    this.dailyAutoRefreshing = true;
    try {
      const user = await auth.silentLogin();
      await this.loadDailyEnergy(user.user_id, { force: true });
    } catch (error) {
      console.warn('daily energy entry refresh skipped:', error.message || error);
    } finally {
      this.dailyAutoRefreshing = false;
    }
  },

  applyDailyEnergy(daily) {
    if (!daily) return this.data.daily;
    const recommendedCrystals = daily.recommended_crystals || [];
    const primaryCrystal = recommendedCrystals[0] || {};
    const recommendedNames = recommendedCrystals.length
      ? recommendedCrystals.map(item => item.name).filter(Boolean).slice(0, 3).join(' · ')
      : this.data.daily.recommendedNames;
    this.setData({
      daily: {
        vitality: daily.score || this.data.daily.vitality,
        inspiration: daily.score || this.data.daily.inspiration,
        color: daily.lucky_color || this.data.daily.color,
        number: daily.lucky_number || this.data.daily.number,
        stone: daily.recommended_stone || daily.lucky_crystal || primaryCrystal.name || this.data.daily.stone,
        keyword: daily.daily_keyword || daily.title || daily.theme || this.data.daily.keyword,
        keywords: daily.keywords || this.data.daily.keywords,
        summary: daily.summary || this.data.daily.summary,
        actionTip: daily.action_tip || (daily.actions && daily.actions[0]) || this.data.daily.actionTip,
        recommendedCrystals,
        recommendedNames,
        commerceEntry: daily.commerce_entry || {},
        workbenchPayload: daily.workbench_payload || null,
        loaded: true,
        loginHint: daily.title || daily.theme || daily.summary || '今日能量已更新',
        raw: daily
      }
    });
    return this.data.daily;
  },

  async loadDailyEnergy(userId, options = {}) {
    try {
      const daily = await getTodayDailyEnergy(userId, { forceRecalculate: !!options.force });
      wx.setStorageSync(DAILY_CACHE_KEY, daily);
      if (options.force) wx.setStorageSync(DAILY_REFRESH_DATE_KEY, todayKey());
      this.applyDailyEnergy(daily);
      return this.data.daily;
    } catch (error) {
      console.warn('daily energy skipped:', error.message || error);
      return this.data.daily;
    }
  },

  async ensureDailyEnergy(options = {}) {
    if (this.data.daily.loaded) return this.data.daily;
    const user = await auth.requireLogin('登录后才能查看你的每日能量补给。');
    return this.loadDailyEnergy(user.user_id, options);
  },

  async onDailyTap() {
    try {
      const cached = wx.getStorageSync(DAILY_CACHE_KEY);
      if (cached) {
        this.applyDailyEnergy(cached);
      } else {
        await this.ensureDailyEnergy({ force: false });
      }
      const daily = this.data.daily;
      if (daily && daily.raw) wx.setStorageSync(DAILY_CACHE_KEY, daily.raw);
      wx.navigateTo({ url: '/pages/daily-energy/daily-energy' });
    } catch (error) {
      // requireLogin already shows the guide.
    }
  },

  goToPage(e) {
    const url = e.currentTarget.dataset.url;
    if (!url) return;
    if (url === '/pages/assessment/assessment') {
      wx.setStorageSync('customMode', {
        id: 'wuxing',
        title: '五行定制',
        selectedAt: Date.now()
      });
    }
    if (TAB_BAR_PAGES.includes(url)) {
      wx.switchTab({ url });
      return;
    }
    wx.navigateTo({ url });
  },

  onBannerChange(e) {
    this.setData({ currentBannerIndex: e.detail.current || 0 });
  },

  openHomeBanner(e) {
    const index = Number(e.currentTarget.dataset.index) || 0;
    const banner = this.data.homeBanners[index];
    const url = banner && banner.actionUrl;
    if (!url) return;
    if (TAB_BAR_PAGES.includes(url)) {
      wx.switchTab({ url });
      return;
    }
    wx.navigateTo({ url });
  },

  openInspiration(e) {
    const id = e.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({ url: `/pages/community-detail/community-detail?id=${id}` });
  },

  openRecommendation(e) {
    const id = e.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({ url: `/pages/plan-detail/plan-detail?id=${id}` });
  },

  useRecommendation(e) {
    const id = e.currentTarget.dataset.id;
    const product = this.data.bestSellers.find(item => item.id === id);
    if (!product) return;
    wx.setStorageSync('recommendedRecipe', product.recipe);
    wx.setStorageSync('workspacePreset', 'recommended');
    wx.switchTab({ url: '/pages/workspace/workspace' });
  },

  async onDailyStoneTap() {
    let daily;
    try {
      daily = await this.ensureDailyEnergy();
    } catch (error) {
      return;
    }
    const crystals = daily.recommendedCrystals || [];
    const primaryCrystal = crystals[0] || {};
    const stone = daily.stone || primaryCrystal.name || '海蓝宝';
    const detailMap = {
      海蓝宝: { name: '海蓝宝', tone: 'blue', image: ASSETS.aquamarine, desc: '适合沟通、平静和情绪整理。今天先把表达放慢一点。', recipe: ['aquamarine', 'clearQuartz', 'moonstone'] },
      紫水晶: { name: '紫水晶', tone: 'violet', image: ASSETS.amethyst, desc: '适合灵感、专注和睡眠前的放松。', recipe: ['amethyst', 'clearQuartz', 'moonstone'] },
      黄水晶: { name: '黄水晶', tone: 'gold', image: ASSETS.citrine, desc: '适合行动力、目标感和财富议题。', recipe: ['citrine', 'tigerEye', 'clearQuartz'] }
    };
    const backendDetail = primaryCrystal.name ? {
      name: primaryCrystal.name,
      tone: 'blue',
      image: ASSETS.aquamarine,
      desc: `${primaryCrystal.reason || daily.summary || '适合今天的能量状态'}｜${daily.actionTip || ''}`,
      recipe: (daily.workbenchPayload && daily.workbenchPayload.bracelet_plan && daily.workbenchPayload.bracelet_plan.layout || [])
        .map(item => item.crystal_code),
      workbenchPayload: daily.workbenchPayload,
      crystals
    } : null;
    this.setData({
      dailyStoneDetail: backendDetail || detailMap[stone] || { name: stone, tone: 'blue', image: ASSETS.aquamarine, desc: '适合今天的能量状态，可作为主石或点缀珠。', recipe: ['aquamarine', 'clearQuartz'] },
      showStoneSheet: true
    });
  },

  quickAddProduct(e) {
    const id = e.currentTarget.dataset.id;
    const product = this.data.bestSellers.find(item => item.id === id);
    if (!product) return;
    const cart = wx.getStorageSync('inspirationCart') || [];
    const exists = cart.some(item => item.name === product.name);
    const nextCart = exists ? cart : [{ ...product, addedAt: Date.now() }, ...cart];
    wx.setStorageSync('inspirationCart', nextCart);
    this.setData({ inspirationCart: nextCart });
    wx.showToast({ title: exists ? '已在收藏中' : '已收藏灵感', icon: 'none' });
  },

  addDailyStoneToCart() {
    const detail = this.data.dailyStoneDetail;
    if (!detail) return;
    const cart = wx.getStorageSync('inspirationCart') || [];
    const item = {
      name: `${detail.name}今日能量`,
      desc: detail.desc,
      price: 0,
      tone: detail.tone,
      recipe: detail.recipe,
      source: 'daily_energy',
      sourceContext: (detail.workbenchPayload && detail.workbenchPayload.source_context) || null,
      crystals: detail.crystals || [],
      addedAt: Date.now()
    };
    const exists = cart.some(entry => entry.name === item.name);
    const nextCart = exists ? cart : [item, ...cart];
    wx.setStorageSync('inspirationCart', nextCart);
    this.setData({ inspirationCart: nextCart, showStoneSheet: false });
    wx.showToast({ title: exists ? '已在收藏中' : '已收藏灵感', icon: 'none' });
  },

  startDailyStoneDiy() {
    const detail = this.data.dailyStoneDetail;
    if (!detail) return;
    if (detail.workbenchPayload) {
      wx.setStorageSync('diyWorkbenchPayload', detail.workbenchPayload);
      wx.setStorageSync('workspacePreset', 'backend-recommended');
    } else {
      wx.setStorageSync('recommendedRecipe', detail.recipe);
      wx.setStorageSync('workspacePreset', 'recommended');
    }
    this.setData({ showStoneSheet: false });
    wx.switchTab({ url: '/pages/workspace/workspace' });
  },

  closeStoneSheet() {
    this.setData({ showStoneSheet: false });
  },

  noop() {},

  viewShoppingCart() {
    wx.navigateTo({ url: '/pages/inspiration-cart/inspiration-cart' });
  },

  onSearch() {
    wx.navigateTo({ url: '/pages/search/search' });
  }
});
