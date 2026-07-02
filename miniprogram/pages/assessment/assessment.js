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
const REGION_OPTIONS = [
  { province: '北京市', cities: ['北京市'] },
  { province: '天津市', cities: ['天津市'] },
  { province: '河北省', cities: ['石家庄市', '唐山市', '秦皇岛市', '邯郸市', '邢台市', '保定市', '张家口市', '承德市', '沧州市', '廊坊市', '衡水市'] },
  { province: '山西省', cities: ['太原市', '大同市', '阳泉市', '长治市', '晋城市', '朔州市', '晋中市', '运城市', '忻州市', '临汾市', '吕梁市'] },
  { province: '内蒙古自治区', cities: ['呼和浩特市', '包头市', '乌海市', '赤峰市', '通辽市', '鄂尔多斯市', '呼伦贝尔市', '巴彦淖尔市', '乌兰察布市', '兴安盟', '锡林郭勒盟', '阿拉善盟'] },
  { province: '辽宁省', cities: ['沈阳市', '大连市', '鞍山市', '抚顺市', '本溪市', '丹东市', '锦州市', '营口市', '阜新市', '辽阳市', '盘锦市', '铁岭市', '朝阳市', '葫芦岛市'] },
  { province: '吉林省', cities: ['长春市', '吉林市', '四平市', '辽源市', '通化市', '白山市', '松原市', '白城市', '延边朝鲜族自治州'] },
  { province: '黑龙江省', cities: ['哈尔滨市', '齐齐哈尔市', '鸡西市', '鹤岗市', '双鸭山市', '大庆市', '伊春市', '佳木斯市', '七台河市', '牡丹江市', '黑河市', '绥化市', '大兴安岭地区'] },
  { province: '上海市', cities: ['上海市'] },
  { province: '江苏省', cities: ['南京市', '无锡市', '徐州市', '常州市', '苏州市', '南通市', '连云港市', '淮安市', '盐城市', '扬州市', '镇江市', '泰州市', '宿迁市'] },
  { province: '浙江省', cities: ['杭州市', '宁波市', '温州市', '嘉兴市', '湖州市', '绍兴市', '金华市', '衢州市', '舟山市', '台州市', '丽水市'] },
  { province: '安徽省', cities: ['合肥市', '芜湖市', '蚌埠市', '淮南市', '马鞍山市', '淮北市', '铜陵市', '安庆市', '黄山市', '滁州市', '阜阳市', '宿州市', '六安市', '亳州市', '池州市', '宣城市'] },
  { province: '福建省', cities: ['福州市', '厦门市', '莆田市', '三明市', '泉州市', '漳州市', '南平市', '龙岩市', '宁德市'] },
  { province: '江西省', cities: ['南昌市', '景德镇市', '萍乡市', '九江市', '新余市', '鹰潭市', '赣州市', '吉安市', '宜春市', '抚州市', '上饶市'] },
  { province: '山东省', cities: ['济南市', '青岛市', '淄博市', '枣庄市', '东营市', '烟台市', '潍坊市', '济宁市', '泰安市', '威海市', '日照市', '临沂市', '德州市', '聊城市', '滨州市', '菏泽市'] },
  { province: '河南省', cities: ['郑州市', '开封市', '洛阳市', '平顶山市', '安阳市', '鹤壁市', '新乡市', '焦作市', '濮阳市', '许昌市', '漯河市', '三门峡市', '南阳市', '商丘市', '信阳市', '周口市', '驻马店市', '济源市'] },
  { province: '湖北省', cities: ['武汉市', '黄石市', '十堰市', '宜昌市', '襄阳市', '鄂州市', '荆门市', '孝感市', '荆州市', '黄冈市', '咸宁市', '随州市', '恩施土家族苗族自治州', '仙桃市', '潜江市', '天门市', '神农架林区'] },
  { province: '湖南省', cities: ['长沙市', '株洲市', '湘潭市', '衡阳市', '邵阳市', '岳阳市', '常德市', '张家界市', '益阳市', '郴州市', '永州市', '怀化市', '娄底市', '湘西土家族苗族自治州'] },
  { province: '广东省', cities: ['广州市', '韶关市', '深圳市', '珠海市', '汕头市', '佛山市', '江门市', '湛江市', '茂名市', '肇庆市', '惠州市', '梅州市', '汕尾市', '河源市', '阳江市', '清远市', '东莞市', '中山市', '潮州市', '揭阳市', '云浮市'] },
  { province: '广西壮族自治区', cities: ['南宁市', '柳州市', '桂林市', '梧州市', '北海市', '防城港市', '钦州市', '贵港市', '玉林市', '百色市', '贺州市', '河池市', '来宾市', '崇左市'] },
  { province: '海南省', cities: ['海口市', '三亚市', '三沙市', '儋州市', '五指山市', '琼海市', '文昌市', '万宁市', '东方市', '定安县', '屯昌县', '澄迈县', '临高县', '白沙黎族自治县', '昌江黎族自治县', '乐东黎族自治县', '陵水黎族自治县', '保亭黎族苗族自治县', '琼中黎族苗族自治县'] },
  { province: '重庆市', cities: ['重庆市'] },
  { province: '四川省', cities: ['成都市', '自贡市', '攀枝花市', '泸州市', '德阳市', '绵阳市', '广元市', '遂宁市', '内江市', '乐山市', '南充市', '眉山市', '宜宾市', '广安市', '达州市', '雅安市', '巴中市', '资阳市', '阿坝藏族羌族自治州', '甘孜藏族自治州', '凉山彝族自治州'] },
  { province: '贵州省', cities: ['贵阳市', '六盘水市', '遵义市', '安顺市', '毕节市', '铜仁市', '黔西南布依族苗族自治州', '黔东南苗族侗族自治州', '黔南布依族苗族自治州'] },
  { province: '云南省', cities: ['昆明市', '曲靖市', '玉溪市', '保山市', '昭通市', '丽江市', '普洱市', '临沧市', '楚雄彝族自治州', '红河哈尼族彝族自治州', '文山壮族苗族自治州', '西双版纳傣族自治州', '大理白族自治州', '德宏傣族景颇族自治州', '怒江傈僳族自治州', '迪庆藏族自治州'] },
  { province: '西藏自治区', cities: ['拉萨市', '日喀则市', '昌都市', '林芝市', '山南市', '那曲市', '阿里地区'] },
  { province: '陕西省', cities: ['西安市', '铜川市', '宝鸡市', '咸阳市', '渭南市', '延安市', '汉中市', '榆林市', '安康市', '商洛市'] },
  { province: '甘肃省', cities: ['兰州市', '嘉峪关市', '金昌市', '白银市', '天水市', '武威市', '张掖市', '平凉市', '酒泉市', '庆阳市', '定西市', '陇南市', '临夏回族自治州', '甘南藏族自治州'] },
  { province: '青海省', cities: ['西宁市', '海东市', '海北藏族自治州', '黄南藏族自治州', '海南藏族自治州', '果洛藏族自治州', '玉树藏族自治州', '海西蒙古族藏族自治州'] },
  { province: '宁夏回族自治区', cities: ['银川市', '石嘴山市', '吴忠市', '固原市', '中卫市'] },
  { province: '新疆维吾尔自治区', cities: ['乌鲁木齐市', '克拉玛依市', '吐鲁番市', '哈密市', '昌吉回族自治州', '博尔塔拉蒙古自治州', '巴音郭楞蒙古自治州', '阿克苏地区', '克孜勒苏柯尔克孜自治州', '喀什地区', '和田地区', '伊犁哈萨克自治州', '塔城地区', '阿勒泰地区', '石河子市', '阿拉尔市', '图木舒克市', '五家渠市', '北屯市', '铁门关市', '双河市', '可克达拉市', '昆玉市', '胡杨河市', '新星市', '白杨市'] },
  { province: '台湾省', cities: ['台北市', '高雄市', '台中市', '台南市', '基隆市', '新竹市', '嘉义市'] },
  { province: '香港特别行政区', cities: ['香港特别行政区'] },
  { province: '澳门特别行政区', cities: ['澳门特别行政区'] }
];
const REGION_PROVINCES = REGION_OPTIONS.map(item => item.province);
const DEFAULT_BIRTH_REGION = ['上海市', '上海市'];

function findBirthRegionSelection(region = [], birthPlace = '') {
  const values = Array.isArray(region)
    ? region.map(item => String(item || '').trim()).filter(Boolean)
    : [];
  const provinceHint = values[0] || '';
  const cityHint = values[1] || birthPlace || provinceHint;
  let provinceIndex = REGION_OPTIONS.findIndex(item => item.province === provinceHint);
  if (provinceIndex < 0 && cityHint) {
    provinceIndex = REGION_OPTIONS.findIndex(item => item.cities.indexOf(cityHint) !== -1 || item.province === cityHint);
  }
  if (provinceIndex < 0) {
    provinceIndex = REGION_OPTIONS.findIndex(item => item.province === DEFAULT_BIRTH_REGION[0]);
  }
  const province = REGION_OPTIONS[Math.max(0, provinceIndex)] || REGION_OPTIONS[0];
  let cityIndex = province.cities.indexOf(cityHint);
  if (cityIndex < 0) cityIndex = province.cities.indexOf(provinceHint);
  if (cityIndex < 0) cityIndex = 0;
  return {
    provinceIndex: Math.max(0, provinceIndex),
    cityIndex,
    province: province.province,
    city: province.cities[cityIndex] || province.province
  };
}

function buildBirthRegionPickerState(region = DEFAULT_BIRTH_REGION, birthPlace = '') {
  const selection = findBirthRegionSelection(region, birthPlace);
  const province = REGION_OPTIONS[selection.provinceIndex] || REGION_OPTIONS[0];
  return {
    birthRegionColumns: [REGION_PROVINCES, province.cities],
    birthRegionIndex: [selection.provinceIndex, selection.cityIndex],
    birthRegion: [selection.province, selection.city],
    birthPlace: selection.city
  };
}

const DEFAULT_REGION_PICKER_STATE = buildBirthRegionPickerState(DEFAULT_BIRTH_REGION);

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
      birthPlace: DEFAULT_REGION_PICKER_STATE.birthPlace,
      birthRegion: DEFAULT_REGION_PICKER_STATE.birthRegion,
      mbti: '',
      wishes: [],
      chakraAnswers: [],
      moodPaletteId: ''
    },
    birthRegionColumns: DEFAULT_REGION_PICKER_STATE.birthRegionColumns,
    birthRegionIndex: DEFAULT_REGION_PICKER_STATE.birthRegionIndex,
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
      const pickerState = buildBirthRegionPickerState(baseForm.birthRegion, baseForm.birthPlace);
      baseForm.birthRegion = pickerState.birthRegion;
      baseForm.birthPlace = pickerState.birthPlace;
      this.setData({
        form: baseForm,
        birthRegionColumns: pickerState.birthRegionColumns,
        birthRegionIndex: pickerState.birthRegionIndex,
        birthTimeLabel: baseForm.birthTimeUnknown || !baseForm.birthTime ? '未知' : baseForm.birthTime
      });
      return;
    }
    const form = this.mergeDraftForm(baseForm, draft.form);
    const pickerState = buildBirthRegionPickerState(form.birthRegion, form.birthPlace);
    form.birthRegion = pickerState.birthRegion;
    form.birthPlace = pickerState.birthPlace;
    const currentStepIndex = Math.max(0, Math.min(FLOW_STEPS.length - 1, Number(draft.currentStepIndex) || 0));
    this.setData({
      form,
      birthRegionColumns: pickerState.birthRegionColumns,
      birthRegionIndex: pickerState.birthRegionIndex,
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
    form.birthPlace = form.birthRegion[1] || form.birthRegion[0] || DEFAULT_BIRTH_REGION[1];
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
    form.birthRegion = this.normalizeBirthRegion(form.birthRegion, form.birthPlace);
    form.birthPlace = form.birthRegion[1] || form.birthPlace || DEFAULT_BIRTH_REGION[1];
    return form;
  },

  normalizeBirthRegion(region, birthPlace = '') {
    return buildBirthRegionPickerState(region, birthPlace).birthRegion;
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

  regionFromPickerIndex(indexes = this.data.birthRegionIndex) {
    const provinceIndex = Math.max(0, Math.min(REGION_OPTIONS.length - 1, Number(indexes[0]) || 0));
    const province = REGION_OPTIONS[provinceIndex] || REGION_OPTIONS[0];
    const cityIndex = Math.max(0, Math.min(province.cities.length - 1, Number(indexes[1]) || 0));
    return {
      birthRegionColumns: [REGION_PROVINCES, province.cities],
      birthRegionIndex: [provinceIndex, cityIndex],
      birthRegion: [province.province, province.cities[cityIndex] || province.province],
      birthPlace: province.cities[cityIndex] || province.province
    };
  },

  applyBirthRegionPickerIndex(indexes) {
    const selected = this.regionFromPickerIndex(indexes);
    this.setData({
      birthRegionColumns: selected.birthRegionColumns,
      birthRegionIndex: selected.birthRegionIndex,
      'form.birthRegion': selected.birthRegion,
      'form.birthPlace': selected.birthPlace
    }, () => this.refreshOptionState());
  },

  onBirthRegionColumnChange(e) {
    const column = Number(e.detail.column);
    const value = Number(e.detail.value);
    const indexes = [...this.data.birthRegionIndex];
    if (column === 0) {
      indexes[0] = Number.isFinite(value) ? value : 0;
      indexes[1] = 0;
    } else {
      indexes[1] = Number.isFinite(value) ? value : 0;
    }
    const selected = this.regionFromPickerIndex(indexes);
    this.setData({
      birthRegionColumns: selected.birthRegionColumns,
      birthRegionIndex: selected.birthRegionIndex
    });
  },

  onBirthRegionCancel() {
    const pickerState = buildBirthRegionPickerState(this.data.form.birthRegion, this.data.form.birthPlace);
    this.setData({
      birthRegionColumns: pickerState.birthRegionColumns,
      birthRegionIndex: pickerState.birthRegionIndex
    });
  },

  onRegionChange(e) {
    const indexes = (e && e.detail && e.detail.value) || this.data.birthRegionIndex;
    this.applyBirthRegionPickerIndex(indexes);
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
