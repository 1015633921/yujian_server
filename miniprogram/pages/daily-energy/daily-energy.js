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

const STATUS_GROUPS = [
  { key: 'emotion', label: '情绪' },
  { key: 'energy', label: '精力' },
  { key: 'social', label: '人际' },
  { key: 'fortune', label: '运势' }
];

const MOOD_OPTIONS = [
  { key: 'calm', label: '平静', short_label: '平静', emoji: '🫧', group: 'emotion', desc: '状态稳定，可以轻推进', priority: 0, featured: true },
  { key: 'pressure', label: '压力山大', short_label: '压力', emoji: '🤯', group: 'emotion', desc: '脑子太满，需要降噪', priority: 1, featured: true },
  { key: 'internal_loss', label: '严重内耗', short_label: '内耗', emoji: '🥱', group: 'energy', desc: '想太多，行动太少', priority: 2, featured: true },
  { key: 'battery_low', label: '电量告急', short_label: '低电量', emoji: '🔋', group: 'energy', desc: '能量偏低，先省电', priority: 3, featured: false },
  { key: 'money', label: '一心搞钱', short_label: '搞钱', emoji: '💰', group: 'fortune', desc: '目标明确，适合稳步变现', priority: 4, featured: true },
  { key: 'need_focus', label: '需要专注', short_label: '专注', emoji: '🎯', group: 'energy', desc: '适合减少干扰', priority: 5, featured: true },
  { key: 'emo', label: '随时 EMO', short_label: 'EMO', emoji: '🌧️', group: 'emotion', desc: '情绪起伏，需要被接住', priority: 6, featured: true },
  { key: 'lost', label: '迷茫', short_label: '迷茫', emoji: '🌫️', group: 'emotion', desc: '方向感弱，先整理优先级', priority: 7, featured: false },
  { key: 'procrastinate', label: '拖延晚期', short_label: '拖延', emoji: '⏳', group: 'energy', desc: '需要一点推进力', priority: 8, featured: false },
  { key: 'inspiration_low', label: '灵感枯竭', short_label: '灵感', emoji: '💡', group: 'energy', desc: '先输入，再输出', priority: 9, featured: false },
  { key: 'full_power', label: '满血复活', short_label: '满血', emoji: '🚀', group: 'energy', desc: '适合推进关键动作', priority: 10, featured: false },
  { key: 'angry', label: '暴躁', short_label: '暴躁', emoji: '🔥', group: 'emotion', desc: '火气偏强，需要柔化', priority: 11, featured: false },
  { key: 'hug', label: '抱抱自己', short_label: '抱抱', emoji: '🕊️', group: 'emotion', desc: '需要温柔修复', priority: 12, featured: false },
  { key: 'social_anxiety', label: '社恐发作', short_label: '社恐', emoji: '🙈', group: 'social', desc: '保持边界，低压社交', priority: 13, featured: false },
  { key: 'charm', label: '散发魅力', short_label: '魅力', emoji: '🧲', group: 'social', desc: '适合展示与见面', priority: 14, featured: false },
  { key: 'protect', label: '自动退散', short_label: '防护', emoji: '🛡️', group: 'social', desc: '不想被打扰，需要防护感', priority: 15, featured: false },
  { key: 'peach', label: '桃花绝缘体', short_label: '桃花', emoji: '🌸', group: 'social', desc: '想让关系更柔和', priority: 16, featured: false },
  { key: 'noble', label: '求贵人', short_label: '贵人', emoji: '🤝', group: 'social', desc: '需要被看见与支持', priority: 17, featured: false },
  { key: 'career', label: '搞事业', short_label: '事业', emoji: '💼', group: 'fortune', desc: '适合推进工作成果', priority: 18, featured: false },
  { key: 'lucky', label: '锦鲤本鲤', short_label: '好运', emoji: '🐟', group: 'fortune', desc: '想要一点好运气', priority: 19, featured: false },
  { key: 'exam', label: '逢考必过', short_label: '考试', emoji: '📚', group: 'fortune', desc: '需要专注和稳定输出', priority: 20, featured: false },
  { key: 'anti_mercury', label: '水逆退散', short_label: '退散', emoji: '🧿', group: 'fortune', desc: '减少沟通误会与突发干扰', priority: 21, featured: false }
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

function normalizeStatusTag(item = {}, index = 0) {
  const label = item.label || item.short_label || item.shortLabel || item.key || '';
  const shortLabel = item.short_label || item.shortLabel || label;
  const priority = Number.isFinite(Number(item.priority)) ? Number(item.priority) : index + 999;
  return {
    ...item,
    label,
    shortLabel: String(shortLabel || label).slice(0, 5),
    emoji: item.emoji || item.icon || '',
    group: item.group || 'emotion',
    desc: item.desc || '',
    priority,
    featured: item.featured === undefined ? false : !!item.featured
  };
}

function sortStatusTags(options = []) {
  return options.slice().sort((left, right) => {
    const leftPriority = Number.isFinite(Number(left.priority)) ? Number(left.priority) : 999;
    const rightPriority = Number.isFinite(Number(right.priority)) ? Number(right.priority) : 999;
    if (leftPriority !== rightPriority) return leftPriority - rightPriority;
    return String(left.label || '').localeCompare(String(right.label || ''), 'zh-Hans-CN');
  });
}

function normalizeStatusGroups(groups = [], tags = []) {
  const source = Array.isArray(groups) && groups.length ? groups : STATUS_GROUPS;
  const usedGroups = new Set(tags.map(item => item.group).filter(Boolean));
  const normalized = source
    .filter(item => item && item.key)
    .map(item => ({ key: item.key, label: item.label || item.key }))
    .filter(item => !usedGroups.size || usedGroups.has(item.key));
  return normalized.length ? normalized : STATUS_GROUPS;
}

function decorateStatusGroups(groups, selectedKey) {
  return groups.map(item => ({
    ...item,
    className: item.key === selectedKey ? 'active' : ''
  }));
}

function decorateTagOptions(options, selectedKeys = [], activeGroup = '') {
  return sortStatusTags(options)
    .filter(item => !activeGroup || item.group === activeGroup)
    .map(item => ({
      ...item,
      className: selectedKeys.includes(item.key) ? 'active' : ''
    }));
}

function buildSelectedStatusView(options = [], selectedKeys = []) {
  const selected = selectedKeys
    .map(key => options.find(item => item.key === key))
    .filter(Boolean);
  if (!selected.length) {
    return {
      summary: '未选择',
      desc: '可以选择 1-3 个最贴近当下的状态。',
      items: []
    };
  }
  return {
    summary: selected.map(item => item.shortLabel || item.label).join(' · '),
    desc: selected.map(item => item.desc).filter(Boolean).join('；'),
    items: selected.map(item => ({
      key: item.key,
      label: item.label,
      shortLabel: item.shortLabel || item.label,
      emoji: item.emoji || ''
    }))
  };
}

function normalizeRuleOptions(payload = {}) {
  const rawStatusTags = Array.isArray(payload.status_tags) && payload.status_tags.length ? payload.status_tags : MOOD_OPTIONS;
  const statusTags = sortStatusTags(rawStatusTags.map((item, index) => normalizeStatusTag(item, index)));
  const statusGroups = normalizeStatusGroups(payload.status_groups, statusTags);
  const scenes = Array.isArray(payload.scenes) && payload.scenes.length ? payload.scenes : SCENE_OPTIONS;
  const goals = Array.isArray(payload.goals) && payload.goals.length ? payload.goals : GOAL_OPTIONS;
  return {
    rulesVersion: payload.rules_version || '',
    statusGroups,
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
    rawStatusGroups: STATUS_GROUPS,
    rawSceneOptions: SCENE_OPTIONS,
    rawGoalOptions: GOAL_OPTIONS,
    activeStatusGroup: 'emotion',
    statusGroups: decorateStatusGroups(STATUS_GROUPS, 'emotion'),
    moodOptions: decorateTagOptions(MOOD_OPTIONS, ['calm'], 'emotion'),
    selectedStatusView: buildSelectedStatusView(MOOD_OPTIONS, ['calm']),
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
      const activeStatusGroup = options.statusGroups.some(item => item.key === this.data.activeStatusGroup)
        ? this.data.activeStatusGroup
        : (options.statusTags.find(item => nextStatusTags.includes(item.key))?.group || options.statusGroups[0]?.key || '');
      const selectedScene = options.scenes.some(item => item.key === this.data.selectedScene)
        ? this.data.selectedScene
        : options.scenes[0]?.key || '';
      const selectedGoal = options.goals.some(item => item.key === this.data.selectedGoal)
        ? this.data.selectedGoal
        : options.goals[0]?.key || '';
      this.setData({
        rulesVersion: options.rulesVersion,
        rawStatusOptions: options.statusTags,
        rawStatusGroups: options.statusGroups,
        rawSceneOptions: options.scenes,
        rawGoalOptions: options.goals,
        activeStatusGroup,
        statusGroups: decorateStatusGroups(options.statusGroups, activeStatusGroup),
        selectedStatusTags: nextStatusTags,
        selectedStatusView: buildSelectedStatusView(options.statusTags, nextStatusTags),
        selectedScene,
        selectedGoal,
        moodOptions: decorateTagOptions(options.statusTags, nextStatusTags, activeStatusGroup),
        sceneOptions: decorateOptions(options.scenes, selectedScene),
        goalOptions: decorateOptions(options.goals, selectedGoal)
      });
    } catch (error) {
      const activeStatusGroup = STATUS_GROUPS.some(item => item.key === this.data.activeStatusGroup)
        ? this.data.activeStatusGroup
        : STATUS_GROUPS[0].key;
      this.setData({
        rawStatusGroups: STATUS_GROUPS,
        activeStatusGroup,
        statusGroups: decorateStatusGroups(STATUS_GROUPS, activeStatusGroup),
        selectedStatusView: buildSelectedStatusView(MOOD_OPTIONS, this.data.selectedStatusTags),
        moodOptions: decorateTagOptions(MOOD_OPTIONS, this.data.selectedStatusTags, activeStatusGroup),
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
    return (this.data.rawStatusOptions || MOOD_OPTIONS).filter(item => this.data.selectedStatusTags.includes(item.key));
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
      selectedStatusView: buildSelectedStatusView(this.data.rawStatusOptions || MOOD_OPTIONS, selectedStatusTags),
      moodOptions: decorateTagOptions(this.data.rawStatusOptions || MOOD_OPTIONS, selectedStatusTags, this.data.activeStatusGroup)
    });
  },

  selectStatusGroup(e) {
    const activeStatusGroup = e.currentTarget.dataset.key;
    this.setData({
      activeStatusGroup,
      statusGroups: decorateStatusGroups(this.data.rawStatusGroups || STATUS_GROUPS, activeStatusGroup),
      moodOptions: decorateTagOptions(this.data.rawStatusOptions || MOOD_OPTIONS, this.data.selectedStatusTags, activeStatusGroup)
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
