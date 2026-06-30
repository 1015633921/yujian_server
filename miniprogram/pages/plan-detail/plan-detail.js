const { getRecommendations } = require('../../utils/recommendationData');
const auth = require('../../utils/auth');
const {
  getRecommendationPlan,
  getRecommendationPlans,
  getCommunityFavorites,
  saveCommunityFavorite,
  deleteCommunityFavorite
} = require('../../utils/api');
const { assetUrl } = require('../../utils/assets');

const ASSETS = {
  aquamarine: assetUrl('home/aquamarine.webp'),
  clearQuartz: assetUrl('home/clear-quartz.webp'),
  moonstone: assetUrl('home/moonstone.webp'),
  citrine: assetUrl('home/citrine.webp'),
  amethyst: assetUrl('home/amethyst.webp'),
  tigerEye: assetUrl('home/citrine.webp')
};

const TABS = [
  { key: 'recommend', label: '推荐方案' },
  { key: 'balance', label: '平衡方案' },
  { key: 'boost', label: '增强方案' }
];

function createBeads(recipe = [], count = 14, radius = 92, size = 44) {
  const safeRecipe = recipe.length ? recipe : ['moonstone', 'clearQuartz', 'amethyst'];
  return Array.from({ length: count }, (_, index) => {
    const angle = (360 / count) * index;
    const key = safeRecipe[index % safeRecipe.length];
    return {
      src: ASSETS[key] || ASSETS.clearQuartz,
      style: `width:${size}rpx;height:${size}rpx;transform:rotate(${angle}deg) translateY(-${radius}rpx) rotate(${-angle}deg);`
    };
  });
}

function normalizePlan(plan = {}, index = 0) {
  const recipe = plan.recipe || plan.sku_list || plan.recipe_skus || [];
  const tags = plan.tags || plan.tag_list || [];
  return {
    ...plan,
    id: plan.id || plan.plan_id || `plan-${index}`,
    name: plan.name || plan.title || '水晶定制方案',
    subtitle: plan.subtitle || plan.short_desc || plan.summary || '根据场景与能量倾向推荐',
    desc: plan.desc || plan.description || plan.recommendation_copy || '以真实珠材搭配为基础，适合继续进入 DIY 工作台细调。',
    price: Number(plan.price || plan.sale_price || 299).toFixed(0),
    tone: plan.tone || 'clear',
    imageUrl: plan.image_url || plan.cover_image || plan.cover || '',
    recipe,
    tags,
    materials: plan.materials || plan.material_list || [],
    scenes: plan.scenes || ['日常佩戴', '通勤出门', '重要约见', '送礼心意'],
    designStory: plan.designStory || plan.design_story || plan.story || plan.desc || '这套方案以清晰、耐看的珠材节奏为核心，让主石和过渡珠之间保持自然呼吸。',
    designReason: plan.designReason || plan.design_reason || plan.reason || '主石负责建立整体气质，辅助珠材负责调和色彩与佩戴节奏，进入 DIY 后仍可继续替换与调整。',
    visualBeads: createBeads(recipe, 16, 94, 42),
    miniBeads: createBeads(recipe, 10, 44, 28),
    imageBroken: false
  };
}

Page({
  data: {
    tabs: TABS,
    activeTab: 'recommend',
    currentPlan: null,
    plans: [],
    visiblePlans: [],
    isSaved: false,
    loading: true
  },

  onLoad(options = {}) {
    this.loadRecommendation(options.id);
  },

  onShow() {
    this.refreshSavedState();
  },

  async loadRecommendation(id) {
    this.setData({ loading: true });
    const localPlans = getRecommendations().map(normalizePlan);
    let plans = localPlans;
    let currentPlan = localPlans.find(item => item.id === id) || localPlans[0];

    try {
      const remotePlans = await getRecommendationPlans({ limit: 8, silent: true, timeout: 8000 });
      const normalizedRemote = (Array.isArray(remotePlans) ? remotePlans : []).map(normalizePlan);
      if (normalizedRemote.length) {
        plans = normalizedRemote;
        currentPlan = normalizedRemote.find(item => item.id === id) || normalizedRemote[0];
      }
    } catch (error) {
      console.warn('recommendation list fallback:', error.message || error);
    }

    if (id) {
      try {
        currentPlan = normalizePlan(await getRecommendationPlan(id, { silent: true, timeout: 8000 }));
        const exists = plans.some(item => item.id === currentPlan.id);
        plans = exists ? plans.map(item => (item.id === currentPlan.id ? currentPlan : item)) : [currentPlan, ...plans];
      } catch (error) {
        console.warn('recommendation detail fallback:', error.message || error);
      }
    }

    this.setData({
      plans,
      currentPlan,
      visiblePlans: this.buildVisiblePlans(plans, currentPlan.id),
      loading: false
    });
    wx.setNavigationBarTitle({ title: '为你推荐的方案' });
    this.refreshSavedState();
  },

  buildVisiblePlans(plans, currentId) {
    return plans.filter(item => item.id !== currentId).slice(0, 4);
  },

  switchTab(e) {
    const key = e.currentTarget.dataset.key;
    const currentPlan = this.pickPlanForTab(key) || this.data.currentPlan;
    this.setData({
      activeTab: key,
      currentPlan,
      visiblePlans: this.buildVisiblePlans(this.data.plans, currentPlan.id)
    });
    this.refreshSavedState(currentPlan);
  },

  pickPlanForTab(key) {
    const plans = this.data.plans;
    if (!plans.length) return null;
    const indexMap = { recommend: 0, balance: 1, boost: 2 };
    return plans[indexMap[key] || 0] || plans[0];
  },

  selectPlan(e) {
    const id = e.currentTarget.dataset.id;
    const currentPlan = this.data.plans.find(item => item.id === id);
    if (!currentPlan) return;
    this.setData({
      currentPlan,
      visiblePlans: this.buildVisiblePlans(this.data.plans, id)
    });
    wx.pageScrollTo({ scrollTop: 0, duration: 220 });
    this.refreshSavedState(currentPlan);
  },

  async refreshSavedState(plan = this.data.currentPlan) {
    if (!plan) return;
    const cart = wx.getStorageSync('inspirationCart') || [];
    this.setData({
      isSaved: cart.some(item => item.id === plan.id || item.name === plan.name)
    });
    const user = auth.getStoredUser();
    if (!user || !user.user_id) return;
    try {
      const favorites = await getCommunityFavorites(user.user_id, { silent: true, timeout: 8000 });
      const favoriteId = `recommendation:${plan.id}`;
      this.setData({
        isSaved: favorites.some(item => (item.post_id || item.id) === favoriteId)
      });
    } catch (error) {
      console.warn('plan favorite state fallback:', error.message || error);
    }
  },

  onImageError(e) {
    const id = e.currentTarget.dataset.id;
    const patchBroken = item => (item.id === id ? { ...item, imageBroken: true, imageUrl: '' } : item);
    const plans = this.data.plans.map(patchBroken);
    const currentPlan = patchBroken(this.data.currentPlan);
    this.setData({
      plans,
      currentPlan,
      visiblePlans: this.buildVisiblePlans(plans, currentPlan.id)
    });
  },

  async toggleSave() {
    const plan = this.data.currentPlan;
    if (!plan) return;
    let user;
    try {
      user = await auth.requireLogin('登录后才能收藏灵感。');
    } catch (error) {
      return;
    }
    const favoriteId = `recommendation:${plan.id}`;
    const isSaved = this.data.isSaved;
    try {
      if (isSaved) {
        await deleteCommunityFavorite(user.user_id, favoriteId);
      } else {
        await saveCommunityFavorite({
          user_id: user.user_id,
          post_id: favoriteId,
          item: {
            id: favoriteId,
            source_id: plan.id,
            favorite_type: 'recommendation_plan',
            title: plan.name,
            desc: plan.subtitle,
            price: plan.price,
            tone: plan.tone,
            recipe: plan.recipe,
            image_url: plan.imageUrl,
            addedAt: Date.now()
          }
        });
      }
      this.setData({ isSaved: !isSaved });
      await this.refreshSavedState(plan);
      wx.showToast({ title: isSaved ? '已取消收藏' : '已收藏', icon: 'none' });
    } catch (error) {
      wx.showToast({ title: error.message || '收藏失败，请重试', icon: 'none' });
    }
  },

  startDiy() {
    const plan = this.data.currentPlan;
    if (!plan) return;
    wx.setStorageSync('recommendedRecipe', plan.recipe);
    wx.setStorageSync('workspacePreset', 'recommended');
    wx.switchTab({ url: '/pages/workspace/workspace' });
  },

  viewMore() {
    wx.navigateTo({ url: '/pages/community/community' });
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
