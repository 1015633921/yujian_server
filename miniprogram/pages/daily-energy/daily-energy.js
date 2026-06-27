const auth = require('../../utils/auth');
const { getDailyEnergyOptions, getTodayDailyEnergy } = require('../../utils/api');

const DAILY_CACHE_KEY = 'todayDailyEnergy';
const DAILY_REFRESH_DATE_KEY = 'todayDailyEnergyRefreshDate';
const ELEMENT_ORDER = ['木', '火', '土', '金', '水'];
const ELEMENT_META = {
  木: { color: '#5F8E68', soft: 'rgba(95,142,104,.12)' },
  火: { color: '#C8634F', soft: 'rgba(200,99,79,.12)' },
  土: { color: '#C59B55', soft: 'rgba(197,155,85,.14)' },
  金: { color: '#92979A', soft: 'rgba(146,151,154,.14)' },
  水: { color: '#527FA3', soft: 'rgba(82,127,163,.12)' }
};
const DIMENSION_META = {
  stability: { icon: '⚡', color: '#3F73B8' },
  action: { icon: '🔥', color: '#E28B55' },
  softness: { icon: '♡', color: '#84B965' },
  expression: { icon: '☯', color: '#8C72CF' },
  intuition: { icon: '✦', color: '#D9A43C' }
};
const COLOR_DOTS = {
  透明: '#E7EEF2',
  冰蓝: '#B9DDF0',
  奶白: '#F2EFE6',
  浅灰: '#DDE1E0',
  月雾白: '#EEF1EF',
  银灰: '#C9CED0',
  松针绿: '#8FA184',
  浅青: '#B9D9D2',
  石榴红: '#CB6B5E',
  暖白: '#F5EFE3',
  淡粉: '#EFC6CD',
  麦芽金: '#E0C37A',
  茶褐: '#B99B7D',
  奶油白: '#F4EBD9'
};
const CRYSTAL_COLORS = {
  海蓝宝: '#7DC7E7',
  白水晶: '#E7EEF2',
  月光石: '#E9E4DB',
  黄水晶: '#E3B64C',
  粉晶: '#EFB4C2',
  石榴石: '#AF3842',
  茶晶: '#9A8068',
  赤铁矿: '#74797D',
  黑曜石: '#30343A',
  黑发晶: '#34343A',
  蓝发晶: '#527FA3',
  绿幽灵: '#5F8E68',
  绿松石: '#66B9AD'
};

const MOOD_OPTIONS = [
  { key: 'calm', label: '平静', emoji: '🫧', desc: '状态稳定，可以轻推进' },
  { key: 'pressure', label: '压力山大', emoji: '🤯', desc: '脑子太满，需要降噪' },
  { key: 'battery_low', label: '电量告急', emoji: '🔋', desc: '先省电，再推进' },
  { key: 'money', label: '一心搞钱', emoji: '💰', desc: '目标明确，适合变现' }
];

const SCENE_OPTIONS = [
  { key: 'work', label: '上班沟通' },
  { key: 'social', label: '轻社交' },
  { key: 'focus', label: '学习专注' },
  { key: 'rest', label: '休息修复' }
];

const GOAL_OPTIONS = [
  { key: 'stable_expression', label: '稳定表达', wish: '正缘桃花/人际和合' },
  { key: 'less_overthinking', label: '减少内耗', wish: '健康护身/保持专注' },
  { key: 'move_task', label: '推进任务', wish: '招财进宝/事业腾飞' },
  { key: 'low_pressure_protect', label: '低压防护', wish: '辟邪防小人/消除焦虑' }
];

function firstText(value, fallback = '') {
  if (Array.isArray(value)) return value.filter(Boolean)[0] || fallback;
  return value || fallback;
}

function decorateOptions(options, selectedKey) {
  return options.map(item => ({
    ...item,
    className: item.key === selectedKey ? 'active' : ''
  }));
}

function decorateTagOptions(options, selectedKeys = []) {
  return options.map(item => ({
    ...item,
    className: selectedKeys.includes(item.key) ? 'active' : ''
  }));
}

function normalizeRuleOptions(payload = {}) {
  const statusTags = Array.isArray(payload.status_tags) && payload.status_tags.length ? payload.status_tags : MOOD_OPTIONS;
  const scenes = Array.isArray(payload.scenes) && payload.scenes.length ? payload.scenes : SCENE_OPTIONS;
  const goals = Array.isArray(payload.goals) && payload.goals.length ? payload.goals : GOAL_OPTIONS;
  return {
    rulesVersion: payload.rules_version || '',
    statusTags,
    scenes,
    goals
  };
}

function isFreshDailyPayload(daily) {
  return !!(
    daily
    && Number(daily.content_version) >= 3
    && daily.season_hint
    && daily.season_hint.summary
  );
}

function todayKey() {
  const now = new Date();
  const month = `${now.getMonth() + 1}`.padStart(2, '0');
  const day = `${now.getDate()}`.padStart(2, '0');
  return `${now.getFullYear()}-${month}-${day}`;
}

Page({
  data: {
    loading: true,
    refreshing: false,
    daily: null,
    viewDaily: null,
    rulesVersion: '',
    rawStatusOptions: MOOD_OPTIONS,
    rawSceneOptions: SCENE_OPTIONS,
    rawGoalOptions: GOAL_OPTIONS,
    moodOptions: decorateTagOptions(MOOD_OPTIONS, ['calm']),
    sceneOptions: decorateOptions(SCENE_OPTIONS, 'work'),
    goalOptions: decorateOptions(GOAL_OPTIONS, 'stable_expression'),
    selectedStatusTags: ['calm'],
    selectedScene: 'work',
    selectedGoal: 'stable_expression'
  },

  async onLoad() {
    await this.loadRuleOptions();
    const cached = wx.getStorageSync(DAILY_CACHE_KEY);
    if (cached && cached.date === todayKey() && isFreshDailyPayload(cached) && (!this.data.rulesVersion || cached.rules_version === this.data.rulesVersion)) {
      this.applyDaily(cached);
      return;
    }
    await this.loadDaily({ force: false });
  },

  async loadRuleOptions() {
    try {
      const options = normalizeRuleOptions(await getDailyEnergyOptions());
      const selectedStatusTags = this.data.selectedStatusTags.length
        ? this.data.selectedStatusTags.filter(key => options.statusTags.some(item => item.key === key))
        : [];
      const nextStatusTags = selectedStatusTags.length ? selectedStatusTags : [options.statusTags[0]?.key].filter(Boolean);
      const selectedScene = options.scenes.some(item => item.key === this.data.selectedScene)
        ? this.data.selectedScene
        : options.scenes[0]?.key || '';
      const selectedGoal = options.goals.some(item => item.key === this.data.selectedGoal)
        ? this.data.selectedGoal
        : options.goals[0]?.key || '';
      this.setData({
        rulesVersion: options.rulesVersion,
        rawStatusOptions: options.statusTags,
        rawSceneOptions: options.scenes,
        rawGoalOptions: options.goals,
        selectedStatusTags: nextStatusTags,
        selectedScene,
        selectedGoal,
        moodOptions: decorateTagOptions(options.statusTags, nextStatusTags),
        sceneOptions: decorateOptions(options.scenes, selectedScene),
        goalOptions: decorateOptions(options.goals, selectedGoal)
      });
    } catch (error) {
      this.setData({
        moodOptions: decorateTagOptions(MOOD_OPTIONS, this.data.selectedStatusTags),
        sceneOptions: decorateOptions(SCENE_OPTIONS, this.data.selectedScene),
        goalOptions: decorateOptions(GOAL_OPTIONS, this.data.selectedGoal)
      });
    }
  },

  async loadDaily(options = {}) {
    this.setData({ loading: true });
    try {
      const user = await auth.requireLogin('登录后才能查看今日能量建议。');
      const goal = this.currentGoal();
      const daily = await getTodayDailyEnergy(user.user_id, {
        initialWish: goal && goal.wish,
        statusTags: this.data.selectedStatusTags,
        sceneKey: this.data.selectedScene,
        goalKeys: this.data.selectedGoal ? [this.data.selectedGoal] : [],
        forceRecalculate: !!options.force
      });
      this.applyDaily(daily);
      if (options.force || isFreshDailyPayload(daily)) {
        wx.setStorageSync(DAILY_REFRESH_DATE_KEY, todayKey());
      }
      return daily;
    } catch (error) {
      wx.showToast({ title: error.message || '今日建议获取失败', icon: 'none' });
      return null;
    } finally {
      this.setData({ loading: false });
    }
  },

  applyDaily(daily) {
    const viewDaily = this.buildViewDaily(daily || {});
    wx.setStorageSync(DAILY_CACHE_KEY, daily);
    this.setData({ daily, viewDaily, loading: false });
  },

  buildViewDaily(raw) {
    const score = Math.max(0, Math.min(100, Math.round(Number(raw.score) || 76)));
    const keywords = Array.isArray(raw.keywords) && raw.keywords.length
      ? raw.keywords.slice(0, 3)
      : [raw.daily_keyword || raw.theme || '稳定', '表达', '清透'].slice(0, 3);
    const crystals = raw.recommended_crystals || [];
    const combo = this.buildCombo(raw.crystal_combo, crystals);
    const dimensions = this.buildDimensions(raw.dimensions, raw.energy_profile, score);
    const wearing = raw.wearing_guide || {};
    const actionAdvice = raw.action_advice || raw.actions || [];
    const dailyPlan = raw.daily_plan || {};
    const scene = this.currentScene();
    const seasonHint = this.buildSeasonHint(raw.season_hint, raw);
    const wearingView = {
      hand: wearing.hand || '建议左手佩戴，用更安静的方式稳定状态。',
      colors: wearing.colors || ['透明', '冰蓝', '奶白'],
      avoid: wearing.avoid || '避免过于强烈的颜色和厚重金属感。',
      scenes: wearing.scenes || [scene.label, '上班沟通', '轻社交'],
      notRecommended: wearing.not_recommended || '高压谈判或强对抗场合。'
    };
    wearingView.colorsText = wearingView.colors.join('、');
    wearingView.scenesText = wearingView.scenes.join('、');
    wearingView.colorDots = wearingView.colors.map(name => ({
      name,
      color: COLOR_DOTS[name] || '#EAE7DF'
    }));
    return {
      dateText: raw.date || '今天',
      score,
      status: raw.today_status || raw.level || '温和上升',
      keywords,
      keywordText: keywords.join(' · '),
      title: raw.title || raw.theme || '今日能量建议',
      summary: raw.summary || '今天适合用更轻盈的方式推进事情，不必强行加速。',
      seasonHint,
      dimensions,
      dimensionCommentary: raw.dimension_commentary || '先完成一件确定的小事，再推进复杂任务。',
      combo,
      recommendedNames: combo.map(item => item.name).filter(Boolean).slice(0, 3).join(' · '),
      wearing: wearingView,
      actions: (actionAdvice.length ? actionAdvice : [
        '先完成一件确定的小事，再推进复杂任务。',
        '沟通时少解释过程，多表达结论。',
        '晚上适合整理手串或保存一个新的搭配方案。'
      ]).slice(0, 3).map((text, index) => ({ index: index + 1, text })),
      plan: {
        title: dailyPlan.title || '今日专属手串方案',
        style: dailyPlan.style || '清透通勤款',
        mainColors: dailyPlan.main_colors || ['冰蓝', '透明', '奶白'],
        beadSizes: dailyPlan.bead_sizes || ['6mm', '8mm'],
        wristHint: dailyPlan.wrist_hint || '将按你在 DIY 工作台选择的手围自动排布。',
        description: dailyPlan.description || `以${firstText(crystals.map(item => item.name), '今日主石')}作为主石，生成可继续编辑的方案。`,
        visuals: this.buildPlanVisuals(crystals, combo)
      },
      elementBars: this.buildElementBars(raw.energy_profile || {})
    };
  },

  buildSeasonHint(hint, raw) {
    const seasonHint = hint || {};
    const focusElement = raw.dominant_element || raw.supporting_element || '水';
    const supportElement = raw.supporting_element || '金';
    return {
      summary: seasonHint.summary || `近期适合把节奏放稳，先照顾${supportElement}能量，再顺着${focusElement}能量推进事情。`,
      drainPoint: seasonHint.drain_point || seasonHint.drainPoint || `${supportElement}能量不足时，容易出现注意力分散或节奏断档。`,
      suggestion: seasonHint.suggestion || '先完成一件确定的小事，再推进需要沟通、创意或临场判断的任务。'
    };
  },

  buildCombo(combo, crystals) {
    if (combo) {
      return ['main', 'support', 'balance', 'accent']
        .map(key => combo[key])
        .filter(Boolean)
        .map((item, index) => ({
          ...item,
          index: index + 1,
          label: item.label || ['主石', '辅石', '平衡石', '点缀'][index],
          color: this.crystalColor(item.name, crystals[index]),
          orbStyle: this.orbStyle(this.crystalColor(item.name, crystals[index]))
        }));
    }
    const fallback = crystals.length ? crystals : [
      { name: '海蓝宝', reason: '表达、沟通、舒缓紧张感' },
      { name: '白水晶', reason: '清透、放大整体能量' },
      { name: '月光石', reason: '柔和情绪、增加稳定陪伴感' }
    ];
    return fallback.slice(0, 3).map((item, index) => ({
      index: index + 1,
      label: ['主石', '辅石', '平衡石'][index],
      name: item.name,
      role: item.role || item.reason || '适合今日状态',
      reason: item.reason || '',
      color: this.crystalColor(item.name, item),
      orbStyle: this.orbStyle(this.crystalColor(item.name, item))
    })).concat([{
      index: 4,
      label: '点缀',
      name: '银色隔片 / 透明隔珠',
      role: '让整体更清爽',
      color: '#CBD0D2',
      orbStyle: this.orbStyle('#CBD0D2')
    }]);
  },

  crystalColor(name, crystal) {
    return (crystal && crystal.color) || CRYSTAL_COLORS[name] || '#DDE4E2';
  },

  orbStyle(color) {
    return `background: radial-gradient(circle at 30% 24%, #fff 0 10%, ${color} 22% 62%, rgba(35,35,35,.22) 100%);`;
  },

  buildDimensions(dimensions, profile, score) {
    if (Array.isArray(dimensions) && dimensions.length) {
      return dimensions.map((item, index) => {
        const meta = DIMENSION_META[item.key] || Object.values(DIMENSION_META)[index % 5];
        const value = Math.max(0, Math.min(100, Math.round(Number(item.value) || 0)));
        return {
        ...item,
          icon: meta.icon,
          color: meta.color,
          value,
          width: `${value}%`
        };
      });
    }
    const base = Math.round(score || 76);
    const values = [
      { key: 'stability', name: '稳定能量', value: base + 4 },
      { key: 'action', name: '行动能量', value: base - 8 },
      { key: 'softness', name: '情绪柔和', value: base - 2 },
      { key: 'expression', name: '表达社交', value: base + 1 },
      { key: 'intuition', name: '灵感直觉', value: base - 12 }
    ];
    return values.map(item => {
      const meta = DIMENSION_META[item.key] || DIMENSION_META.stability;
      const value = Math.max(45, Math.min(96, item.value));
      return {
        ...item,
        icon: meta.icon,
        color: meta.color,
        value,
        width: `${value}%`,
        description: ''
      };
    });
  },

  buildPlanVisuals(crystals, combo) {
    const names = [
      ...combo.map(item => item.name).filter(Boolean),
      ...crystals.map(item => item.name).filter(Boolean)
    ];
    const fallback = ['海蓝宝', '白水晶', '月光石', '白水晶', '海蓝宝'];
    const source = names.length ? names : fallback;
    return Array.from({ length: 9 }, (_, index) => {
      const name = source[index % source.length];
      return {
        index,
        name,
        color: CRYSTAL_COLORS[name] || '#E6ECEB',
        style: `background: radial-gradient(circle at 30% 24%, #fff 0 10%, ${CRYSTAL_COLORS[name] || '#E6ECEB'} 22% 62%, rgba(35,35,35,.22) 100%);`
      };
    });
  },

  buildElementBars(profile) {
    const raw = ELEMENT_ORDER.map(name => ({
      name,
      value: Math.max(0, Number(profile[name]) || 0),
      ...ELEMENT_META[name]
    }));
    const total = raw.reduce((sum, item) => sum + item.value, 0) || 1;
    return raw.map(item => {
      const percent = Math.round((item.value / total) * 100);
      return { ...item, percent, width: `${percent}%` };
    });
  },

  currentMood() {
    return this.data.moodOptions.filter(item => this.data.selectedStatusTags.includes(item.key));
  },

  currentScene() {
    return this.data.sceneOptions.find(item => item.key === this.data.selectedScene) || this.data.sceneOptions[0];
  },

  currentGoal() {
    return this.data.goalOptions.find(item => item.key === this.data.selectedGoal) || this.data.goalOptions[0];
  },

  selectMood(e) {
    const key = e.currentTarget.dataset.key;
    let selectedStatusTags = [...this.data.selectedStatusTags];
    if (selectedStatusTags.includes(key)) {
      selectedStatusTags = selectedStatusTags.filter(item => item !== key);
    } else {
      selectedStatusTags.push(key);
    }
    selectedStatusTags = selectedStatusTags.slice(-3);
    this.setData({
      selectedStatusTags,
      moodOptions: decorateTagOptions(this.data.rawStatusOptions || MOOD_OPTIONS, selectedStatusTags)
    });
  },

  selectScene(e) {
    const selectedScene = e.currentTarget.dataset.key;
    this.setData({
      selectedScene,
      sceneOptions: decorateOptions(this.data.rawSceneOptions || SCENE_OPTIONS, selectedScene)
    });
  },

  selectGoal(e) {
    const selectedGoal = e.currentTarget.dataset.key;
    this.setData({
      selectedGoal,
      goalOptions: decorateOptions(this.data.rawGoalOptions || GOAL_OPTIONS, selectedGoal)
    });
  },

  async refreshDaily() {
    if (this.data.refreshing) return;
    this.setData({ refreshing: true });
    wx.showLoading({ title: '正在生成' });
    try {
      await auth.requireLogin('登录后才能更新今日建议。');
      await this.loadDaily({ force: true });
      wx.showToast({ title: '今日建议已更新', icon: 'none' });
    } catch (error) {
      wx.showToast({ title: error.message || '更新失败', icon: 'none' });
    } finally {
      wx.hideLoading();
      this.setData({ refreshing: false });
    }
  },

  generateDailyDiy() {
    const daily = this.data.daily || {};
    const payload = daily.workbench_payload;
    if (!payload || !payload.bracelet_plan || !payload.bracelet_plan.layout) {
      wx.showToast({ title: '今日方案暂不可生成，请稍后再试', icon: 'none' });
      return;
    }
    wx.setStorageSync(DAILY_CACHE_KEY, daily);
    wx.setStorageSync('diyWorkbenchPayload', payload);
    wx.setStorageSync('workspacePreset', 'backend-recommended');
    wx.switchTab({ url: '/pages/workspace/workspace' });
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
