const { getCommunityPosts: getLocalCommunityPosts } = require('../../utils/communityData');
const { getCommunityPosts } = require('../../utils/api');
const { assetUrl } = require('../../utils/assets');

const TAB_BAR_PAGES = ['/pages/home/home', '/pages/assessment/assessment', '/pages/workspace/workspace', '/pages/profile/profile'];

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

function createRingBeads(sequence, count = 16, radius = 86, size = 42) {
  return Array.from({ length: count }, (_, index) => {
    const angle = (360 / count) * index;
    return {
      src: ASSETS[sequence[index % sequence.length]] || ASSETS.clearQuartz,
      style: `width:${size}rpx;height:${size}rpx;transform:rotate(${angle}deg) translateY(-${radius}rpx) rotate(${-angle}deg);`
    };
  });
}

function cleanText(value, fallback = '') {
  if (value === null || value === undefined) return fallback;
  const text = String(value).trim();
  if (!text || text === '-') return fallback;
  return text;
}

function normalizeLikes(item) {
  const raw = item.likes ?? item.like_count ?? item.favorite_count ?? item.views ?? item.view_count ?? item.popularity ?? 0;
  const value = Number(raw) || 0;
  if (value >= 10000) return `${(value / 10000).toFixed(1)}万`;
  return `${value}`;
}

function normalizePost(item, index) {
  const tone = cleanText(item.tone, ['blue', 'clear', 'gold', 'pink', 'black'][index % 5]);
  const tags = Array.isArray(item.tags) ? item.tags.filter(Boolean) : [];
  const title = cleanText(item.title, `灵感方案 ${index + 1}`);
  const desc = cleanText(item.desc || item.description || item.summary, '真实材质搭配，可带入 DIY 工作台继续调整。');
  const author = cleanText(item.author || item.creator || item.nickname, '宇涧灵感室');
  const imageUrl = cleanText(item.image_url || item.cover_image || item.coverUrl || item.image || item.thumbnail, '');
  const sceneText = tags[0] || cleanText(item.scene, '日常搭配');

  return {
    ...item,
    id: cleanText(item.id || item.post_id || item.slug, `community-${index}`),
    title,
    desc,
    author,
    tone,
    imageUrl,
    heatText: normalizeLikes(item),
    sceneText,
    displayTags: tags.slice(0, 3),
    searchText: [title, desc, author, sceneText, tags.join(' '), item.materials && item.materials.join(' ')].filter(Boolean).join(' ').toLowerCase(),
    visualBeads: createRingBeads(TONE_BEADS[tone] || TONE_BEADS.clear)
  };
}

function decoratePosts(source) {
  return (source || getLocalCommunityPosts()).map(normalizePost);
}

Page({
  data: {
    loading: true,
    keyword: '',
    activeTopic: 'recommend',
    topics: [
      { key: 'recommend', label: '推荐' },
      { key: 'hot', label: '热门' },
      { key: 'element', label: '五行' },
      { key: 'emotion', label: '情绪' },
      { key: 'style', label: '风格' }
    ],
    allPosts: [],
    filteredPosts: [],
    labTabbarClass: '',
    lessons: [
      { title: '第一次戴水晶需要消磁吗？', desc: '清水、月光、白水晶碎石都可以，关键是按材质选择温和方式。' },
      { title: '如何根据手围选择珠径？', desc: '8mm 更日常，10mm 存在感更强，也要结合手围和配饰比例。' },
      { title: '五行缺什么就戴什么吗？', desc: '更建议看整体比例，补弱项的同时避免单一属性过强。' }
    ]
  },

  onLoad() {
    this.applyPosts(decoratePosts(getLocalCommunityPosts()), true);
    this.loadPosts();
  },

  onShow() {
    this.hideNativeTabBar();
    this.lastCommunityScrollTop = 0;
    if (this.data.labTabbarClass) {
      this.setData({ labTabbarClass: '' });
    }
  },

  onHide() {
    clearTimeout(this.tabbarSetDataTimer);
    this.restoreNativeTabBar();
  },

  onUnload() {
    clearTimeout(this.tabbarSetDataTimer);
    this.restoreNativeTabBar();
  },

  onPageScroll(e) {
    const currentTop = Number(e.scrollTop) || 0;
    const previousTop = this.lastCommunityScrollTop || 0;
    const delta = currentTop - previousTop;
    this.lastCommunityScrollTop = currentTop;

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
    wx.hideTabBar({ animation: false, fail: () => {} });
  },

  restoreNativeTabBar() {
    if (!wx.showTabBar) return;
    wx.showTabBar({ animation: false, fail: () => {} });
  },

  applyPosts(posts, loading = false) {
    const allPosts = posts || [];
    const filteredPosts = this.filterPosts(allPosts, this.data.keyword, this.data.activeTopic);
    this.setData({ allPosts, filteredPosts, loading });
  },

  async loadPosts() {
    try {
      const posts = await getCommunityPosts({ limit: 50, silent: true, timeout: 8000 });
      if (posts && posts.length) {
        this.applyPosts(decoratePosts(posts), false);
        return;
      }
    } catch (error) {
      console.warn('community cms fallback:', error.message || error);
    }
    this.setData({ loading: false });
  },

  filterPosts(posts, keyword, activeTopic) {
    const normalizedKeyword = cleanText(keyword).toLowerCase();
    let list = posts.slice();

    if (normalizedKeyword) {
      list = list.filter(item => item.searchText.includes(normalizedKeyword));
    }

    if (activeTopic === 'hot') {
      list.sort((a, b) => (Number(b.likes || b.popularity || 0) || 0) - (Number(a.likes || a.popularity || 0) || 0));
    } else if (activeTopic === 'element') {
      list = list.filter(item => /五行|金|木|水|火|土|能量|平衡/.test(item.searchText));
    } else if (activeTopic === 'emotion') {
      list = list.filter(item => /情绪|治愈|疗愈|睡眠|放松|温柔|守护/.test(item.searchText));
    } else if (activeTopic === 'style') {
      list = list.filter(item => /风格|通勤|礼物|日常|清爽|夏日|穿搭/.test(item.searchText));
    }

    return list;
  },

  refreshFilters() {
    const filteredPosts = this.filterPosts(this.data.allPosts, this.data.keyword, this.data.activeTopic);
    this.setData({ filteredPosts });
  },

  onKeywordInput(e) {
    this.setData({ keyword: e.detail.value || '' }, () => this.refreshFilters());
  },

  submitSearch() {
    this.refreshFilters();
  },

  clearKeyword() {
    this.setData({ keyword: '' }, () => this.refreshFilters());
  },

  selectTopic(e) {
    const key = e.currentTarget.dataset.key || 'recommend';
    this.setData({ activeTopic: key }, () => this.refreshFilters());
  },

  resetFilters() {
    this.setData({ keyword: '', activeTopic: 'recommend' }, () => this.refreshFilters());
  },

  toggleFilterHint() {
    wx.showToast({ title: '可通过标签快速筛选灵感', icon: 'none' });
  },

  onImageError(e) {
    const id = e.currentTarget.dataset.id;
    const allPosts = this.data.allPosts.map(item => (item.id === id ? { ...item, imageUrl: '' } : item));
    this.applyPosts(allPosts, false);
  },

  openPost(e) {
    const id = e.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({ url: `/pages/community-detail/community-detail?id=${id}` });
  },

  useSame(e) {
    const id = e.currentTarget.dataset.id;
    const post = this.data.allPosts.find(item => item.id === id);
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
    wx.switchTab({ url: '/pages/home/home' });
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
  }
});
