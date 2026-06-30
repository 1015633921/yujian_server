const { calculateEnergy, getAssessmentOptions } = require('../../utils/api');
const auth = require('../../utils/auth');

const DEFAULT_WISH = '情绪平衡';
const ASSESSMENT_DRAFT_KEY = 'assessmentDraft';
const ASSESSMENT_PROFILE_KEY = 'assessmentLastProfile';
const ASSESSMENT_RECALCULATE_KEY = 'assessmentRecalculateMode';
const ASSESSMENT_SUPPRESS_AUTO_REPORT_ONCE_KEY = 'assessmentSuppressAutoReportOnce';
const ENERGY_REPORT_KEY = 'energyReport';
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
const CHAKRA_OPTIONS = [
  { value: 'state_expression', label: '表达卡住', desc: '喉轮' },
  { value: 'state_soft_heart', label: '关系消耗', desc: '心轮' },
  { value: 'state_low_confidence', label: '缺少底气', desc: '太阳神经丛' },
  { value: 'state_unsettled', label: '不够安定', desc: '海底轮' },
  { value: 'state_low_inspiration', label: '灵感变少', desc: '眉心轮' },
  { value: 'need_grounding', label: '想更稳定', desc: '海底轮' },
  { value: 'need_flow', label: '想更流动', desc: '脐轮' },
  { value: 'need_action', label: '想更行动', desc: '太阳神经丛' },
  { value: 'need_acceptance', label: '想更柔软', desc: '心轮' },
  { value: 'need_clarity', label: '想更清晰', desc: '喉轮' }
];
const MOOD_PALETTES = [
  { value: 'sea_salt_blue', label: '海盐蓝白', desc: '表达 · 清澈', colors: ['#DCEFF2', '#F8F7F2', '#6D8FA3'] },
  { value: 'rose_garden', label: '粉绿花园', desc: '接纳 · 关系', colors: ['#F0B7C3', '#DDEAD7', '#7EA27E'] },
  { value: 'sunlit_gold', label: '金橙日光', desc: '自信 · 行动', colors: ['#F1C75B', '#E9924E', '#FFF1C8'] },
  { value: 'moon_violet', label: '紫白月光', desc: '灵感 · 安静', colors: ['#DDD7EF', '#F7F5F0', '#8177B4'] },
  { value: 'earth_red', label: '红棕大地', desc: '稳定 · 安全', colors: ['#8E3F35', '#B9835A', '#E8D8C7'] },
  { value: 'black_gold', label: '黑金镜面', desc: '边界 · 保护', colors: ['#1F2225', '#C8A95B', '#F5F2EA'] }
];
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
const FLOW_STEPS = [
  { key: 'basic', label: '基础', title: '基础信息', desc: '先建立真实命盘底色。', badge: '必填', optional: false },
  { key: 'wish', label: '愿望', title: '核心愿望', desc: '选择这次最想被手串承接的方向。', badge: '必填', optional: false },
  { key: 'mbti', label: '性格', title: '性格偏好', desc: 'MBTI 会辅助理解表达方式，不填写也可以继续。', badge: '可选', optional: true },
  { key: 'state', label: '状态', title: '当下状态', desc: '用七脉轮捕捉最近的身体感受和情绪倾向。', badge: '可选', optional: true },
  { key: 'palette', label: '色彩', title: '直觉色彩', desc: '凭第一眼选择最吸引你的颜色气质。', badge: '可选', optional: true },
  { key: 'review', label: '确认', title: '确认信息', desc: '确认无误后生成专属能量报告。', badge: '生成', optional: false }
];

function decorateSteps(activeIndex) {
  return FLOW_STEPS.map((step, index) => ({
    ...step,
    index: index + 1,
    activeClass: index < activeIndex ? 'done' : index === activeIndex ? 'active' : ''
  }));
}

Page({
  data: {
    modeCopy: MODE_COPY.wuxing,
    steps: decorateSteps(0),
    form: {
      name: '',
      gender: 'female',
      birthDate: '2000-01-01',
      birthTime: '',
      birthTimeUnknown: true,
      birthPlace: '上海市',
      birthRegion: ['上海市', '上海市'],
      mbti: '',
      wishes: [],
      chakraAnswers: [],
      moodPaletteId: ''
    },
    birthTimeLabel: '未知',
    birthTimeUnknownClass: 'active',
    currentStepIndex: 0,
    currentStepKey: FLOW_STEPS[0].key,
    currentStep: FLOW_STEPS[0],
    progressText: `1 / ${FLOW_STEPS.length}`,
    canProceed: false,
    showPrevious: false,
    showSkip: false,
    primaryButtonText: '下一步',
    reviewRows: [],
    genderOptions: [],
    mbtiOptions: [],
    wishOptions: [],
    chakraOptions: [],
    moodPalettes: [],
    rawChakraOptions: CHAKRA_OPTIONS,
    rawMoodPalettes: MOOD_PALETTES,
    selectedWishMap: {},
    selectedChakraMap: {},
    submitting: false
  },

  onLoad(options = {}) {
    const storedMode = wx.getStorageSync('customMode') || {};
    const modeId = options.mode || storedMode.id || 'wuxing';
    if (options.recalculate === '1' || options.recalculate === 'true') {
      wx.setStorageSync(ASSESSMENT_RECALCULATE_KEY, true);
    }
    this.restoreDraft();
    this.setData({ modeCopy: MODE_COPY[modeId] || MODE_COPY.wuxing });
    this.refreshOptionState();
    this.loadAssessmentOptions();
  },

  onShow() {
    this.hideNativeTabBar();
    const storedMode = wx.getStorageSync('customMode') || {};
    const modeId = storedMode.id || 'wuxing';
    this.setData({ modeCopy: MODE_COPY[modeId] || MODE_COPY.wuxing });
    this.openExistingReportIfNeeded();
  },

  onHide() {
    this.restoreNativeTabBar();
  },

  onUnload() {
    this.restoreNativeTabBar();
  },

  hideNativeTabBar() {
    if (!wx.hideTabBar) return;
    wx.hideTabBar({
      animation: false,
      fail: () => {}
    });
  },

  restoreNativeTabBar() {
    if (!wx.showTabBar) return;
    wx.showTabBar({
      animation: false,
      fail: () => {}
    });
  },

  openGuide() {
    wx.navigateTo({ url: '/pages/assessment-guide/assessment-guide' });
  },

  hasValidReport(report) {
    return !!(
      report
      && typeof report === 'object'
      && (report.assessment_id || report.final_energy_profile || report.input_summary)
    );
  },

  openExistingReportIfNeeded() {
    if (this.autoReportNavigating || this.data.submitting) return;
    if (wx.getStorageSync(ASSESSMENT_SUPPRESS_AUTO_REPORT_ONCE_KEY)) {
      wx.removeStorageSync(ASSESSMENT_SUPPRESS_AUTO_REPORT_ONCE_KEY);
      return;
    }
    if (wx.getStorageSync(ASSESSMENT_RECALCULATE_KEY)) return;
    const report = wx.getStorageSync(ENERGY_REPORT_KEY);
    if (!this.hasValidReport(report)) return;
    this.autoReportNavigating = true;
    wx.navigateTo({
      url: '/pages/report/report?from=assessment',
      complete: () => {
        this.autoReportNavigating = false;
      }
    });
  },

  refreshOptionState() {
    const form = this.data.form;
    const selectedWishMap = this.buildWishMap(form.wishes);
    const selectedChakraMap = this.buildWishMap(form.chakraAnswers);
    this.persistDraft();
    this.setData({
      selectedWishMap,
      selectedChakraMap,
      birthTimeUnknownClass: form.birthTimeUnknown ? 'active' : '',
      genderOptions: GENDER_OPTIONS.map(item => ({ ...item, activeClass: form.gender === item.value ? 'active' : '' })),
      mbtiOptions: MBTI_TYPES.map(item => ({ value: item, label: item, activeClass: form.mbti === item ? 'active' : '' })),
      wishOptions: WISHES.map(item => ({ value: item, label: item, activeClass: selectedWishMap[item] ? 'active' : '' })),
      chakraOptions: (this.data.rawChakraOptions || CHAKRA_OPTIONS).map(item => ({ ...item, activeClass: selectedChakraMap[item.value] ? 'active' : '' })),
      moodPalettes: (this.data.rawMoodPalettes || MOOD_PALETTES).map(item => ({ ...item, activeClass: form.moodPaletteId === item.value ? 'active' : '' })),
      ...this.buildFlowState(form)
    });
  },

  buildFlowState(form = this.data.form) {
    const currentStepIndex = this.data.currentStepIndex || 0;
    const currentStep = FLOW_STEPS[currentStepIndex] || FLOW_STEPS[0];
    return {
      steps: decorateSteps(currentStepIndex),
      currentStep,
      currentStepKey: currentStep.key,
      progressText: `${currentStepIndex + 1} / ${FLOW_STEPS.length}`,
      canProceed: this.canProceed(currentStep.key, form),
      showPrevious: currentStepIndex > 0,
      showSkip: Boolean(currentStep.optional),
      primaryButtonText: currentStep.key === 'review' ? '开始测算' : '下一步',
      reviewRows: this.buildReviewRows(form)
    };
  },

  canProceed(stepKey, form = this.data.form) {
    if (stepKey === 'basic') {
      return Boolean(form.name && form.name.trim() && form.birthDate && form.birthPlace);
    }
    if (stepKey === 'wish') {
      return form.wishes.length > 0;
    }
    return true;
  },

  restoreDraft() {
    const draft = wx.getStorageSync(ASSESSMENT_DRAFT_KEY) || {};
    const lastProfile = wx.getStorageSync(ASSESSMENT_PROFILE_KEY) || {};
    const user = auth.getStoredUser && auth.getStoredUser();
    const baseForm = this.buildPrefilledForm(lastProfile, user);
    if (!draft.form) {
      this.setData({
        form: baseForm,
        birthTimeLabel: baseForm.birthTimeUnknown || !baseForm.birthTime ? '未知' : baseForm.birthTime
      });
      return;
    }
    const form = this.mergeDraftForm(baseForm, draft.form);
    const currentStepIndex = Math.max(0, Math.min(FLOW_STEPS.length - 1, Number(draft.currentStepIndex) || 0));
    this.setData({
      form,
      currentStepIndex,
      birthTimeLabel: draft.birthTimeLabel || (form.birthTimeUnknown || !form.birthTime ? '未知' : form.birthTime)
    });
  },

  buildPrefilledForm(lastProfile = {}, user = null) {
    const form = { ...this.data.form, ...lastProfile };
    if ((!form.name || !String(form.name).trim()) && user && user.nickname) {
      form.name = user.nickname;
    }
    form.birthRegion = this.normalizeBirthRegion(form.birthRegion, form.birthPlace);
    form.birthPlace = form.birthPlace || form.birthRegion[1] || form.birthRegion[0] || '上海市';
    form.wishes = Array.isArray(form.wishes) ? form.wishes : [];
    form.chakraAnswers = Array.isArray(form.chakraAnswers) ? form.chakraAnswers : [];
    form.birthTimeUnknown = form.birthTimeUnknown !== false || !form.birthTime;
    if (form.birthTimeUnknown) form.birthTime = '';
    return form;
  },

  mergeDraftForm(baseForm, draftForm = {}) {
    const form = { ...baseForm, ...draftForm };
    ['name', 'birthDate', 'birthPlace'].forEach(field => {
      if (!form[field] && baseForm[field]) form[field] = baseForm[field];
    });
    if ((!Array.isArray(form.birthRegion) || !form.birthRegion.length) && baseForm.birthRegion) {
      form.birthRegion = baseForm.birthRegion;
    }
    const draftHasBirthTimeChoice = Object.prototype.hasOwnProperty.call(draftForm, 'birthTimeUnknown')
      || Object.prototype.hasOwnProperty.call(draftForm, 'birthTime');
    if (!draftHasBirthTimeChoice && !form.birthTime && baseForm.birthTime && baseForm.birthTimeUnknown === false) {
      form.birthTime = baseForm.birthTime;
      form.birthTimeUnknown = false;
    }
    return form;
  },

  normalizeBirthRegion(region, birthPlace = '') {
    if (Array.isArray(region) && region.length) return region.slice(0, 2);
    const place = String(birthPlace || '').trim();
    if (!place) return ['上海市', '上海市'];
    return [place, place];
  },

  persistDraft() {
    wx.setStorageSync(ASSESSMENT_DRAFT_KEY, {
      form: this.data.form,
      birthTimeLabel: this.data.birthTimeLabel,
      currentStepIndex: this.data.currentStepIndex,
      updatedAt: Date.now()
    });
  },

  persistLastProfile(form = this.data.form) {
    wx.setStorageSync(ASSESSMENT_PROFILE_KEY, {
      name: String(form.name || '').trim(),
      gender: form.gender || 'female',
      birthDate: form.birthDate || '2000-01-01',
      birthTime: form.birthTimeUnknown ? '' : (form.birthTime || ''),
      birthTimeUnknown: Boolean(form.birthTimeUnknown || !form.birthTime),
      birthPlace: form.birthPlace || '',
      birthRegion: this.normalizeBirthRegion(form.birthRegion, form.birthPlace),
      mbti: form.mbti || '',
      updatedAt: Date.now()
    });
  },

  async loadAssessmentOptions() {
    try {
      const options = await getAssessmentOptions({ silent: true, timeout: 8000 });
      const chakraOptions = this.normalizeChakraOptions(options.chakra_questions);
      const moodPalettes = this.normalizeMoodPalettes(options.mood_palettes);
      this.setData({
        rawChakraOptions: chakraOptions.length ? chakraOptions : CHAKRA_OPTIONS,
        rawMoodPalettes: moodPalettes.length ? moodPalettes : MOOD_PALETTES
      });
      this.refreshOptionState();
    } catch (error) {
      console.warn('load assessment options failed:', error);
    }
  },

  normalizeChakraOptions(questions = []) {
    const result = [];
    questions.forEach(question => {
      (question.options || []).forEach(option => {
        result.push({
          value: option.id,
          label: option.label,
          desc: question.title || option.chakra || '当下状态'
        });
      });
    });
    return result.filter(item => item.value && item.label);
  },

  normalizeMoodPalettes(palettes = []) {
    return palettes.map(item => ({
      value: item.id || item.value,
      label: item.name || item.label,
      desc: item.subtitle || item.desc || '',
      colors: Array.isArray(item.colors) ? item.colors : []
    })).filter(item => item.value && item.label);
  },

  buildReviewRows(form = this.data.form) {
    const selectedStates = this.labelsForValues(form.chakraAnswers, this.data.rawChakraOptions || CHAKRA_OPTIONS);
    const selectedPalette = this.labelForValue(form.moodPaletteId, this.data.rawMoodPalettes || MOOD_PALETTES);
    return [
      { label: '昵称', value: form.name || '未填写', stepIndex: 0 },
      { label: '出生日期', value: form.birthDate || '未填写', stepIndex: 0 },
      { label: '出生时刻', value: form.birthTimeUnknown || !form.birthTime ? '未知，按 12:00 估算' : form.birthTime, stepIndex: 0 },
      { label: '出生地点', value: form.birthRegion.join(' ') || form.birthPlace || '未填写', stepIndex: 0 },
      { label: '核心愿望', value: form.wishes.length ? form.wishes.join(' / ') : '未选择', stepIndex: 1 },
      { label: 'MBTI', value: form.mbti || '已跳过', stepIndex: 2 },
      { label: '当下状态', value: selectedStates.length ? selectedStates.join(' / ') : '已跳过', stepIndex: 3 },
      { label: '直觉色彩', value: selectedPalette || '已跳过', stepIndex: 4 }
    ];
  },

  labelsForValues(values = [], options = []) {
    return values.map(value => this.labelForValue(value, options)).filter(Boolean);
  },

  labelForValue(value, options = []) {
    const item = options.find(option => option.value === value || option.id === value);
    return item ? item.label || item.name : '';
  },

  onInput(e) {
    this.setData({ [`form.${e.currentTarget.dataset.field}`]: e.detail.value }, () => this.refreshOptionState());
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

  toggleChakraAnswer(e) {
    const value = e.currentTarget.dataset.value;
    const answers = [...this.data.form.chakraAnswers];
    const index = answers.indexOf(value);
    if (index > -1) {
      answers.splice(index, 1);
    } else if (answers.length >= 5) {
      wx.showToast({ title: '最多选择 5 项状态', icon: 'none' });
      return;
    } else {
      answers.push(value);
    }
    this.setData({ 'form.chakraAnswers': answers });
    this.refreshOptionState();
  },

  selectMoodPalette(e) {
    const value = e.currentTarget.dataset.value;
    this.setData({ 'form.moodPaletteId': this.data.form.moodPaletteId === value ? '' : value });
    this.refreshOptionState();
  },

  buildWishMap(wishes) {
    return wishes.reduce((map, wish) => {
      map[wish] = true;
      return map;
    }, {});
  },

  onDateChange(e) {
    this.setData({ 'form.birthDate': e.detail.value }, () => this.refreshOptionState());
  },

  onTimeChange(e) {
    this.setData({
      'form.birthTime': e.detail.value,
      'form.birthTimeUnknown': false,
      birthTimeLabel: e.detail.value
    }, () => this.refreshOptionState());
  },

  setBirthTimeUnknown() {
    this.setData({ 'form.birthTime': '', 'form.birthTimeUnknown': true, birthTimeLabel: '未知' }, () => this.refreshOptionState());
  },

  onRegionChange(e) {
    const region = e.detail.value || [];
    const city = region[1] || region[0] || '';
    this.setData({
      'form.birthRegion': region.slice(0, 2),
      'form.birthPlace': city
    }, () => this.refreshOptionState());
  },

  handlePrimaryAction() {
    const currentStep = this.data.currentStep || FLOW_STEPS[0];
    if (!this.canProceed(currentStep.key)) {
      wx.showToast({ title: this.validationMessage(currentStep.key), icon: 'none' });
      return;
    }
    if (currentStep.key === 'review') {
      this.startAssessment();
      return;
    }
    this.goToStep(this.data.currentStepIndex + 1);
  },

  validationMessage(stepKey) {
    if (stepKey === 'basic') return '请先填写昵称';
    if (stepKey === 'wish') return '请选择至少 1 项愿望';
    return '请完善当前步骤';
  },

  previousStep() {
    this.goToStep(Math.max(0, this.data.currentStepIndex - 1));
  },

  skipStep() {
    const currentStep = this.data.currentStep || FLOW_STEPS[0];
    const nextData = {};
    if (currentStep.key === 'mbti') nextData['form.mbti'] = '';
    if (currentStep.key === 'state') nextData['form.chakraAnswers'] = [];
    if (currentStep.key === 'palette') nextData['form.moodPaletteId'] = '';
    this.setData(nextData, () => {
      this.refreshOptionState();
      this.goToStep(this.data.currentStepIndex + 1);
    });
  },

  jumpToStep(e) {
    const index = Number(e.currentTarget.dataset.index);
    if (!Number.isFinite(index)) return;
    if (index > this.data.currentStepIndex) return;
    this.goToStep(index);
  },

  goToStep(index) {
    const nextIndex = Math.max(0, Math.min(FLOW_STEPS.length - 1, index));
    this.setData({ currentStepIndex: nextIndex }, () => {
      this.refreshOptionState();
      if (wx.pageScrollTo) {
        wx.pageScrollTo({ scrollTop: 0, duration: 180 });
      }
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
      this.goToStep(0);
      wx.showToast({ title: '请填写姓名', icon: 'none' });
      return;
    }
    if (!form.wishes.length) {
      this.goToStep(1);
      wx.showToast({ title: '请选择至少 1 项愿望', icon: 'none' });
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
      chakra_answers: form.chakraAnswers,
      mood_palette_id: form.moodPaletteId || null,
      force_recalculate: true
    };
    this.setData({ submitting: true });
    wx.showLoading({ title: '正在计算能量' });
    try {
      const report = await calculateEnergy(payload);
      this.persistLastProfile(form);
      wx.removeStorageSync(ASSESSMENT_DRAFT_KEY);
      wx.setStorageSync(ENERGY_REPORT_KEY, report);
      wx.removeStorageSync(ASSESSMENT_RECALCULATE_KEY);
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
  }
});
