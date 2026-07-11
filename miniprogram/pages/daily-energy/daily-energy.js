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
const STATUS_GROUPS = [
  { key: 'emotion', label: '情绪' },
  { key: 'energy', label: '精力' },
  { key: 'social', label: '人际' },
  { key: 'fortune', label: '目标' }
];

const MOOD_OPTIONS = [
  { key: 'calm', label: '平静', short_label: '平静', emoji: '🫧', group: 'emotion', desc: '状态稳定，可以轻推进', priority: 0, featured: true },
  { key: 'pressure', label: '压力山大', short_label: '压力', emoji: '🤯', group: 'emotion', desc: '脑子太满，需要降噪', priority: 1, featured: true },
  { key: 'internal_loss', label: '严重内耗', short_label: '内耗', emoji: '🥱', group: 'energy', desc: '想太多，行动太少', priority: 2, featured: true },
  { key: 'battery_low', label: '精力偏低', short_label: '低精力', emoji: '🔋', group: 'energy', desc: '精力偏低，先放慢节奏', priority: 3, featured: false },
  { key: 'money', label: '目标推进', short_label: '目标', emoji: '💰', group: 'fortune', desc: '目标明确，适合稳步推进', priority: 4, featured: true },
  { key: 'need_focus', label: '需要专注', short_label: '专注', emoji: '🎯', group: 'energy', desc: '适合减少干扰', priority: 5, featured: true },
  { key: 'emo', label: '随时 EMO', short_label: 'EMO', emoji: '🌧️', group: 'emotion', desc: '情绪起伏，需要被接住', priority: 6, featured: true },
  { key: 'lost', label: '迷茫', short_label: '迷茫', emoji: '🌫️', group: 'emotion', desc: '方向感弱，先整理优先级', priority: 7, featured: false },
  { key: 'procrastinate', label: '拖延晚期', short_label: '拖延', emoji: '⏳', group: 'energy', desc: '需要一点推进力', priority: 8, featured: false },
  { key: 'inspiration_low', label: '灵感枯竭', short_label: '灵感', emoji: '💡', group: 'energy', desc: '先输入，再输出', priority: 9, featured: false },
  { key: 'full_power', label: '满血复活', short_label: '满血', emoji: '🚀', group: 'energy', desc: '适合推进关键动作', priority: 10, featured: false },
  { key: 'angry', label: '暴躁', short_label: '暴躁', emoji: '🔥', group: 'emotion', desc: '火气偏强，需要柔化', priority: 11, featured: false },
  { key: 'hug', label: '抱抱自己', short_label: '抱抱', emoji: '🕊️', group: 'emotion', desc: '需要温柔放松', priority: 12, featured: false },
  { key: 'social_anxiety', label: '社恐发作', short_label: '社恐', emoji: '🙈', group: 'social', desc: '保持边界，低压社交', priority: 13, featured: false },
  { key: 'charm', label: '散发魅力', short_label: '魅力', emoji: '🧲', group: 'social', desc: '适合展示与见面', priority: 14, featured: false },
  { key: 'protect', label: '安定边界', short_label: '边界', emoji: '🛡️', group: 'social', desc: '不想被打扰，需要安定感', priority: 15, featured: false },
  { key: 'peach', label: '关系柔和', short_label: '关系', emoji: '🌸', group: 'social', desc: '想让关系更柔和', priority: 16, featured: false },
  { key: 'noble', label: '协作支持', short_label: '协作', emoji: '🤝', group: 'social', desc: '需要被看见与支持', priority: 17, featured: false },
  { key: 'career', label: '工作推进', short_label: '工作', emoji: '💼', group: 'fortune', desc: '适合推进工作成果', priority: 18, featured: false },
  { key: 'lucky', label: '积极期待', short_label: '积极', emoji: '🐟', group: 'fortune', desc: '想要一点积极感', priority: 19, featured: false },
  { key: 'exam', label: '考试专注', short_label: '考试', emoji: '📚', group: 'fortune', desc: '需要专注和稳定输出', priority: 20, featured: false },
  { key: 'anti_mercury', label: '沟通顺畅', short_label: '沟通', emoji: '🧿', group: 'fortune', desc: '减少沟通误会与突发干扰', priority: 21, featured: false }
];

const SCENE_OPTIONS = [
  { key: 'work', label: '上班沟通' },
  { key: 'social', label: '轻社交' },
  { key: 'focus', label: '学习专注' },
  { key: 'rest', label: '放松休息' }
];

const GOAL_OPTIONS = [
  { key: 'stable_expression', label: '稳定表达', wish: '正缘桃花/人际和合' },
  { key: 'less_overthinking', label: '减少内耗', wish: '健康护身/保持专注' },
  { key: 'move_task', label: '推进任务', wish: '招财进宝/事业腾飞' },
  { key: 'low_pressure_protect', label: '低压边界', wish: '辟邪防小人/消除焦虑' }
];

const DISPLAY_REPLACEMENTS = [
  ['招财进宝/事业腾飞', '事业专注/稳步推进'],
  ['正缘桃花/人际和合', '人际亲和/柔和沟通'],
  ['辟邪防小人/消除焦虑', '安定边界/舒缓压力'],
  ['健康护身/保持专注', '日常平衡/保持专注'],
  ['运势', '目标'],
  ['搞钱', '目标'],
  ['桃花绝缘体', '关系柔和'],
  ['桃花', '亲和'],
  ['求贵人', '协作支持'],
  ['贵人', '协作'],
  ['锦鲤本鲤', '积极期待'],
  ['好运', '积极感'],
  ['逢考必过', '考试专注'],
  ['水逆退散', '沟通顺畅'],
  ['自动退散', '安定边界'],
  ['防护', '边界'],
  ['修复睡眠', '放松休息'],
  ['睡眠修复', '放松休息'],
  ['休息修复', '放松休息'],
  ['改善睡眠', '帮助放松'],
  ['缓解焦虑', '舒缓压力'],
  ['助眠', '睡前放松'],
  ['太阳神经丛', '行动力'],
  ['海底轮', '稳定感'],
  ['脐轮', '情绪流动'],
  ['心轮', '关系感'],
  ['喉轮', '表达感'],
  ['眉心轮', '灵感'],
  ['顶轮', '思考感'],
  ['疗效', '搭配感受'],
  ['治疗', '舒缓'],
  ['功效', '搭配特点'],
  ['上火', '节奏偏急'],
  ['低速修复', '慢节奏'],
  ['慢修复', '慢节奏'],
  ['能量不足', '状态偏弱'],
  ['能量偏低', '精力偏低'],
  ['能量', '状态'],
  ['流月', '近期'],
  ['天干地支', '传统历法'],
  ['招财', '目标感'],
  ['辟邪', '安定'],
  ['护身', '安定'],
  ['疗愈', '舒缓'],
  ['净化磁场', '整理氛围'],
  ['磁场', '氛围']
];

function sanitizeDisplayText(value, fallback = '') {
  let text = `${value || fallback || ''}`.trim();
  DISPLAY_REPLACEMENTS.forEach(([from, to]) => {
    text = text.split(from).join(to);
  });
  return text;
}

function decorateOptions(options, selectedKey) {
  return options.map(item => ({
    ...item,
    label: sanitizeDisplayText(item.label || item.key),
    desc: sanitizeDisplayText(item.desc || ''),
    className: item.key === selectedKey ? 'active' : ''
  }));
}

function normalizeStatusTag(item = {}, index = 0) {
  const label = sanitizeDisplayText(item.label || item.short_label || item.shortLabel || item.key || '');
  const shortLabel = sanitizeDisplayText(item.short_label || item.shortLabel || label);
  const priority = Number.isFinite(Number(item.priority)) ? Number(item.priority) : index + 999;
  return {
    ...item,
    label,
    shortLabel: String(shortLabel || label).slice(0, 5),
    emoji: item.emoji || item.icon || '',
    group: item.group || 'emotion',
    desc: sanitizeDisplayText(item.desc || ''),
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
    .map(item => ({ key: item.key, label: sanitizeDisplayText(item.label || item.key) }))
    .filter(item => !usedGroups.size || usedGroups.has(item.key));
  return normalized.length ? normalized : STATUS_GROUPS;
}

function decorateStatusGroups(groups, selectedKey) {
  return groups.map(item => ({
    ...item,
    label: sanitizeDisplayText(item.label || item.key),
    className: item.key === selectedKey ? 'active' : ''
  }));
}

function decorateTagOptions(options, selectedKeys = [], activeGroup = '') {
  return sortStatusTags(options)
    .filter(item => !activeGroup || item.group === activeGroup)
    .map(item => ({
      ...item,
      label: sanitizeDisplayText(item.label || item.key),
      shortLabel: sanitizeDisplayText(item.shortLabel || item.short_label || item.label || item.key),
      desc: sanitizeDisplayText(item.desc || ''),
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
    && Number(daily.content_version) >= 6
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
      const user = await auth.requireLogin('登录后才能查看今日状态建议。');
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
    const keywords = (Array.isArray(raw.keywords) && raw.keywords.length
      ? raw.keywords.slice(0, 3)
      : [raw.daily_keyword || raw.theme || '稳定', '表达', '清透'].slice(0, 3)
    ).map(item => sanitizeDisplayText(item));
    const dimensions = this.buildDimensions(raw.dimensions, raw.energy_profile, score);
    const wearing = raw.wearing_guide || {};
    const actionAdvice = raw.action_advice || raw.actions || [];
    const dailyPlan = raw.daily_plan || {};
    const scene = this.currentScene();
    const seasonHint = this.buildSeasonHint(raw.season_hint, raw);
    const wearingView = {
      hand: sanitizeDisplayText(wearing.hand || '建议左手佩戴，用更安静的方式稳定状态。'),
      colors: (wearing.colors || ['透明', '冰蓝', '奶白']).map(item => sanitizeDisplayText(item)),
      avoid: sanitizeDisplayText(wearing.avoid || '避免过于强烈的颜色和厚重金属感。'),
      scenes: (wearing.scenes || [scene.label, '上班沟通', '轻社交']).map(item => sanitizeDisplayText(item)),
      notRecommended: sanitizeDisplayText(wearing.not_recommended || '高压谈判或强对抗场合。')
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
      status: sanitizeDisplayText(raw.today_status || raw.level || '温和上升'),
      keywords,
      keywordText: keywords.join(' · '),
      title: sanitizeDisplayText(raw.title || raw.theme || '今日状态建议'),
      summary: sanitizeDisplayText(raw.summary || '今天适合用更轻盈的方式推进事情，不必强行加速。'),
      seasonHint,
      dimensions,
      dimensionCommentary: sanitizeDisplayText(raw.dimension_commentary || '先完成一件确定的小事，再推进复杂任务。'),
      wearing: wearingView,
      actions: (actionAdvice.length ? actionAdvice : [
        '先完成一件确定的小事，再推进复杂任务。',
        '沟通时少解释过程，多表达结论。',
        '晚上适合整理手串或保存一个新的搭配方案。'
      ]).slice(0, 3).map((text, index) => ({ index: index + 1, text: sanitizeDisplayText(text) })),
      plan: {
        title: sanitizeDisplayText(dailyPlan.title || '今日专属手串方案'),
        style: sanitizeDisplayText(dailyPlan.style || '清透通勤款'),
        mainColors: (dailyPlan.main_colors || ['冰蓝', '透明', '奶白']).map(item => sanitizeDisplayText(item)),
        beadSizes: dailyPlan.bead_sizes || ['6mm', '8mm'],
        wristHint: sanitizeDisplayText(dailyPlan.wrist_hint || '将按你在 DIY 工作台选择的手围自动排布。'),
        description: sanitizeDisplayText(dailyPlan.description || '结合今日状态方向生成可继续编辑的手串方案。')
      },
      elementBars: this.buildElementBars(raw.energy_profile || {})
    };
  },

  buildSeasonHint(hint, raw) {
    const seasonHint = hint || {};
    const focusElement = raw.dominant_element || raw.supporting_element || '水';
    const supportElement = raw.supporting_element || '金';
    return {
      summary: sanitizeDisplayText(seasonHint.summary || `近期适合把节奏放稳，先照顾${supportElement}元素，再顺着${focusElement}元素推进事情。`),
      drainPoint: sanitizeDisplayText(seasonHint.drain_point || seasonHint.drainPoint || `${supportElement}元素状态偏弱时，容易出现注意力分散或节奏断档。`),
      suggestion: sanitizeDisplayText(seasonHint.suggestion || '先完成一件确定的小事，再推进需要沟通、创意或临场判断的任务。')
    };
  },

  buildDimensions(dimensions, profile, score) {
    if (Array.isArray(dimensions) && dimensions.length) {
      return dimensions.map((item, index) => {
        const meta = DIMENSION_META[item.key] || Object.values(DIMENSION_META)[index % 5];
        const value = Math.max(0, Math.min(100, Math.round(Number(item.value) || 0)));
        return {
          ...item,
          name: sanitizeDisplayText(item.name || ''),
          description: sanitizeDisplayText(item.description || ''),
          icon: meta.icon,
          color: meta.color,
          value,
          width: `${value}%`
        };
      });
    }
    const base = Math.round(score || 76);
    const values = [
      { key: 'stability', name: '稳定状态', value: base + 4 },
      { key: 'action', name: '行动状态', value: base - 8 },
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
