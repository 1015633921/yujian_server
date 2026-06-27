const { calculateEnergy } = require('../../utils/api');
const auth = require('../../utils/auth');

const TAB_BAR_PAGES = ['/pages/home/home', '/pages/assessment/assessment', '/pages/workspace/workspace', '/pages/profile/profile'];

const DEFAULT_WISH = '情绪平衡';
const GENDER_OPTIONS = [
  { value: 'female', label: '女' },
  { value: 'male', label: '男' },
  { value: 'other', label: '不限定' }
];
const MBTI_TYPES = [
  'INTJ', 'INTP', 'ENTJ', 'ENTP',
  'INFJ', 'INFP', 'ENFJ', 'ENFP',
  'ISTJ', 'ISFJ', 'ESTJ', 'ESFJ',
  'ISTP', 'ISFP', 'ESTP', 'ESFP'
];
const WISHES = ['情绪平衡', '事业财富', '爱情人缘', '睡眠修复', '专注灵感', '守护辟邪'];
const WISH_MAPPING = {
  情绪平衡: '辟邪防小人/消除焦虑',
  事业财富: '招财进宝/事业腾飞',
  爱情人缘: '正缘桃花/人际和合',
  睡眠修复: '辟邪防小人/消除焦虑',
  专注灵感: '健康护身/保持专注',
  守护辟邪: '辟邪防小人/消除焦虑'
};
const MODE_COPY = {
  wuxing: {
    navTitle: '五行测算',
    kicker: 'BASIC PROFILE',
    title: '建立你的五行能量档案',
    desc: '填写出生日期、时间和地点后，先生成能量分布，再进入专属手串推荐。'
  },
  astro: {
    navTitle: '星座灵感',
    kicker: 'ASTRO PROFILE',
    title: '结合星座气质做灵感推荐',
    desc: '出生信息会帮助系统理解你的阶段状态，并生成更适合的水晶搭配方向。'
  },
  mbti: {
    navTitle: 'MBTI 定制',
    kicker: 'MBTI PROFILE',
    title: '用性格偏好辅助配色与主石',
    desc: '你可以补充 MBTI 与当下愿望，让推荐方案更贴近日常佩戴场景。'
  }
};
const STEPS = [
  { key: 'basic', index: 1, label: '基础信息', activeClass: 'active' },
  { key: 'analysis', index: 2, label: '能量分析', activeClass: '' },
  { key: 'recommend', index: 3, label: '推荐方案', activeClass: '' }
];

Page({
  data: {
    modeCopy: MODE_COPY.wuxing,
    steps: STEPS,
    form: {
      name: '',
      gender: 'female',
      birthDate: '2000-01-01',
      birthTime: '',
      birthTimeUnknown: true,
      birthPlace: '上海市',
      birthRegion: ['上海市', '上海市'],
      mbti: '',
      wishes: []
    },
    birthTimeLabel: '未知',
    birthTimeUnknownClass: 'active',
    genderOptions: [],
    mbtiOptions: [],
    wishOptions: [],
    selectedWishMap: {},
    submitting: false,
    labTabbarClass: ''
  },

  onLoad(options = {}) {
    const storedMode = wx.getStorageSync('customMode') || {};
    const modeId = options.mode || storedMode.id || 'wuxing';
    this.setData({ modeCopy: MODE_COPY[modeId] || MODE_COPY.wuxing });
    this.refreshOptionState();
  },

  onShow() {
    this.hideNativeTabBar();
    this.lastAssessmentScrollTop = 0;
    if (this.data.labTabbarClass) {
      this.setData({ labTabbarClass: '' });
    }
    const storedMode = wx.getStorageSync('customMode') || {};
    const modeId = storedMode.id || 'wuxing';
    this.setData({ modeCopy: MODE_COPY[modeId] || MODE_COPY.wuxing });
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
    const previousTop = this.lastAssessmentScrollTop || 0;
    const delta = currentTop - previousTop;
    this.lastAssessmentScrollTop = currentTop;

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

  refreshOptionState() {
    const form = this.data.form;
    const selectedWishMap = this.buildWishMap(form.wishes);
    this.setData({
      selectedWishMap,
      birthTimeUnknownClass: form.birthTimeUnknown ? 'active' : '',
      genderOptions: GENDER_OPTIONS.map(item => ({ ...item, activeClass: form.gender === item.value ? 'active' : '' })),
      mbtiOptions: MBTI_TYPES.map(item => ({ value: item, label: item, activeClass: form.mbti === item ? 'active' : '' })),
      wishOptions: WISHES.map(item => ({ value: item, label: item, activeClass: selectedWishMap[item] ? 'active' : '' }))
    });
  },

  onInput(e) {
    this.setData({ [`form.${e.currentTarget.dataset.field}`]: e.detail.value });
  },

  selectGender(e) {
    this.setData({ 'form.gender': e.currentTarget.dataset.value });
    this.refreshOptionState();
  },

  selectMbti(e) {
    this.setData({ 'form.mbti': e.currentTarget.dataset.value });
    this.refreshOptionState();
  },

  clearMbti() {
    this.setData({ 'form.mbti': '' });
    this.refreshOptionState();
  },

  toggleWish(e) {
    const value = e.currentTarget.dataset.value;
    const wishes = [...this.data.form.wishes];
    const index = wishes.indexOf(value);
    if (index > -1) {
      wishes.splice(index, 1);
    } else if (wishes.length >= 3) {
      wx.showToast({ title: '最多选择 3 项愿望', icon: 'none' });
      return;
    } else {
      wishes.push(value);
    }
    this.setData({ 'form.wishes': wishes });
    this.refreshOptionState();
  },

  buildWishMap(wishes) {
    return wishes.reduce((map, wish) => {
      map[wish] = true;
      return map;
    }, {});
  },

  onDateChange(e) {
    this.setData({ 'form.birthDate': e.detail.value });
  },

  onTimeChange(e) {
    this.setData({
      'form.birthTime': e.detail.value,
      'form.birthTimeUnknown': false,
      birthTimeLabel: e.detail.value
    });
    this.refreshOptionState();
  },

  setBirthTimeUnknown() {
    this.setData({ 'form.birthTime': '', 'form.birthTimeUnknown': true, birthTimeLabel: '未知' });
    this.refreshOptionState();
  },

  onRegionChange(e) {
    const region = e.detail.value || [];
    const city = region[1] || region[0] || '';
    this.setData({
      'form.birthRegion': region.slice(0, 2),
      'form.birthPlace': city
    });
  },

  async startAssessment() {
    let user;
    try {
      user = await auth.requireLogin('登录后才能保存测算结果和生成每日能量。');
    } catch (error) {
      return;
    }
    const form = this.data.form;
    if (!form.name.trim()) {
      wx.showToast({ title: '请填写姓名', icon: 'none' });
      return;
    }
    const selectedWishes = form.wishes.length ? form.wishes : [DEFAULT_WISH];
    const coreWishes = Array.from(new Set(selectedWishes.map(wish => WISH_MAPPING[wish])));
    const payload = {
      user_id: user.user_id,
      name: form.name.trim(),
      birthday: form.birthDate,
      birth_time: form.birthTimeUnknown || !form.birthTime ? '12:00' : form.birthTime,
      birth_place: form.birthPlace || '中国',
      mbti: form.mbti || null,
      core_wishes: coreWishes,
      force_recalculate: true
    };
    this.setData({ submitting: true });
    wx.showLoading({ title: '正在计算能量' });
    try {
      const report = await calculateEnergy(payload);
      wx.setStorageSync('energyReport', report);
      wx.setStorageSync('energyProfile', {
        name: report.input_summary.name,
        mbti: report.input_summary.mbti || '未填写',
        title: report.interpretation.headline,
        wish: report.input_summary.core_wishes.join(' / '),
        luckyStone: '等待生成专属手串'
      });
      wx.navigateTo({ url: '/pages/report/report' });
    } catch (error) {
      wx.showToast({ title: error.message || '测算失败，请稍后重试', icon: 'none' });
    } finally {
      wx.hideLoading();
      this.setData({ submitting: false });
    }
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
    if (!url || url === '/pages/assessment/assessment') return;
    if (TAB_BAR_PAGES.includes(url)) {
      wx.switchTab({ url });
      return;
    }
    wx.navigateTo({ url });
  },

  viewShoppingCart() {
    wx.navigateTo({ url: '/pages/inspiration-cart/inspiration-cart' });
  }
});
