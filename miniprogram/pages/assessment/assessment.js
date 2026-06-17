const { calculateEnergy } = require('../../utils/api');
const auth = require('../../utils/auth');

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

Page({
  data: {
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
    submitting: false
  },

  onLoad() {
    this.refreshOptionState();
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
    wx.navigateBack();
  }
});
