const { createDIYRecommendation } = require('../../utils/api');

const ELEMENT_META = {
  木: { key: 'wood', color: '#548B62', softColor: 'rgba(84,139,98,.12)' },
  火: { key: 'fire', color: '#C75B4B', softColor: 'rgba(199,91,75,.12)' },
  土: { key: 'earth', color: '#C89A45', softColor: 'rgba(200,154,69,.14)' },
  金: { key: 'metal', color: '#9B9FA3', softColor: 'rgba(155,159,163,.14)' },
  水: { key: 'water', color: '#4E7893', softColor: 'rgba(78,120,147,.12)' }
};
const ELEMENT_ORDER = ['木', '火', '土', '金', '水'];
const STEPS = [
  { key: 'basic', index: 1, label: '基础信息', activeClass: 'done' },
  { key: 'wish', index: 2, label: '核心愿望', activeClass: 'done' },
  { key: 'state', index: 3, label: '当下状态', activeClass: 'done' },
  { key: 'analysis', index: 4, label: '能量分析', activeClass: 'active' }
];
const POSTER_WIDTH = 750;
const POSTER_HEIGHT = 1200;
const WRIST_RULER_MIN = 10;
const WRIST_RULER_MAX = 25;
const WRIST_RULER_STEP = 0.1;
const WRIST_RULER_TICK_RPX = 22;
const ASSESSMENT_RECALCULATE_KEY = 'assessmentRecalculateMode';
const ASSESSMENT_SUPPRESS_AUTO_REPORT_ONCE_KEY = 'assessmentSuppressAutoReportOnce';

function safeText(value, fallback = '') {
  if (value === null || value === undefined) return fallback;
  const text = String(value).trim();
  return text || fallback;
}

function drawRoundRect(ctx, x, y, width, height, radius) {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + width - r, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + r);
  ctx.lineTo(x + width, y + height - r);
  ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
  ctx.lineTo(x + r, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function fillRoundRect(ctx, x, y, width, height, radius, color) {
  drawRoundRect(ctx, x, y, width, height, radius);
  ctx.fillStyle = color;
  ctx.fill();
}

function strokeRoundRect(ctx, x, y, width, height, radius, color, lineWidth = 1) {
  drawRoundRect(ctx, x, y, width, height, radius);
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  ctx.stroke();
}

function drawWrappedText(ctx, text, x, y, maxWidth, lineHeight, maxLines) {
  const chars = safeText(text).split('');
  let line = '';
  let lines = 0;
  let cursorY = y;
  for (let index = 0; index < chars.length; index += 1) {
    const testLine = line + chars[index];
    const isLast = index === chars.length - 1;
    if (ctx.measureText(testLine).width > maxWidth && line) {
      lines += 1;
      if (lines >= maxLines) {
        const ellipsis = `${line.slice(0, Math.max(0, line.length - 1))}…`;
        ctx.fillText(ellipsis, x, cursorY);
        return cursorY + lineHeight;
      }
      ctx.fillText(line, x, cursorY);
      cursorY += lineHeight;
      line = chars[index];
    } else {
      line = testLine;
    }
    if (isLast && line) {
      ctx.fillText(line, x, cursorY);
      cursorY += lineHeight;
    }
  }
  return cursorY;
}

function drawElementRing(ctx, elements, cx, cy, radius, lineWidth) {
  let start = -Math.PI / 2;
  const total = elements.reduce((sum, item) => sum + (Number(item.percent) || 0), 0) || 100;
  elements.forEach(item => {
    const sweep = ((Number(item.percent) || 0) / total) * Math.PI * 2;
    ctx.beginPath();
    ctx.arc(cx, cy, radius, start, start + sweep);
    ctx.strokeStyle = item.color;
    ctx.lineWidth = lineWidth;
    ctx.lineCap = 'round';
    ctx.stroke();
    start += sweep;
  });
}

function drawPosterElementRows(ctx, elements, x, y, width) {
  elements.forEach((item, index) => {
    const rowY = y + index * 54;
    ctx.fillStyle = item.color;
    ctx.font = '700 24px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText(item.name, x, rowY + 24);
    fillRoundRect(ctx, x + 58, rowY + 8, width - 132, 16, 8, '#ECE9E2');
    fillRoundRect(ctx, x + 58, rowY + 8, Math.max(18, (width - 132) * ((Number(item.percent) || 0) / 100)), 16, 8, item.color);
    ctx.fillStyle = '#20201F';
    ctx.textAlign = 'right';
    ctx.fillText(`${item.percent}%`, x + width, rowY + 24);
    ctx.textAlign = 'left';
  });
}

function drawPosterTags(ctx, keywords, x, y, maxWidth) {
  let cursorX = x;
  let cursorY = y;
  const tags = keywords.length ? keywords.slice(0, 4) : [{ label: '清透' }, { label: '稳定' }, { label: '调和' }];
  tags.forEach(item => {
    const label = safeText(item.label, '能量标签');
    ctx.font = '700 24px "PingFang SC", "Microsoft YaHei", sans-serif';
    const tagWidth = Math.min(210, Math.max(104, ctx.measureText(label).width + 42));
    if (cursorX + tagWidth > x + maxWidth) {
      cursorX = x;
      cursorY += 54;
    }
    fillRoundRect(ctx, cursorX, cursorY, tagWidth, 40, 20, '#F8F6F1');
    strokeRoundRect(ctx, cursorX, cursorY, tagWidth, 40, 20, '#E5E2DC', 1);
    ctx.fillStyle = '#4F5F52';
    ctx.fillText(label, cursorX + 21, cursorY + 27);
    cursorX += tagWidth + 12;
  });
  return cursorY + 48;
}

Page({
  data: {
    report: null,
    viewReport: null,
    steps: STEPS,
    avatarChar: '',
    showWristModal: false,
    wristInput: '',
    wristRulerValue: '16.0',
    wristRulerTicks: [],
    wristRulerScrollLeft: 0,
    wristRulerTickWidth: 11,
    wristRulerSidePadding: 180,
    wristRulerRangeText: '10.0–25.0cm',
    beadSize: 8,
    beadSizeOptions: [6, 8, 10, 12],
    generating: false,
    posterGenerating: false,
    posterPath: '',
    posterSaving: false,
    showPosterModal: false
  },

  onLoad() {
    const report = wx.getStorageSync('energyReport');
    if (report) {
      const inputSummary = report.input_summary || {};
      this.setData({
        report,
        viewReport: this.buildViewReport(report),
        avatarChar: safeText(inputSummary.name, '宇').slice(0, 1)
      });
    }
  },

  onUnload() {
    if (this.skipSuppressAssessmentAutoReport) return;
    const pages = getCurrentPages();
    const previousPage = pages && pages.length > 1 ? pages[pages.length - 2] : null;
    if (previousPage && previousPage.route === 'pages/assessment/assessment') {
      wx.setStorageSync(ASSESSMENT_SUPPRESS_AUTO_REPORT_ONCE_KEY, true);
    }
  },

  buildViewReport(report) {
    const profile = report.final_energy_profile || {};
    const rawElements = ELEMENT_ORDER.map(name => ({
      ...ELEMENT_META[name],
      name,
      rawValue: Math.max(0, Number(profile[name]) || 0)
    }));
    const total = rawElements.reduce((sum, item) => sum + item.rawValue, 0) || 1;
    const elements = rawElements.map(item => {
      const percent = Math.round((item.rawValue / total) * 100);
      return {
        ...item,
        value: item.rawValue.toFixed(2),
        percent,
        width: `${Math.min(100, percent)}%`
      };
    });
    const score = this.normalizeScore(report.interpretation && report.interpretation.balance_index);
    return {
      title: (report.interpretation && report.interpretation.headline) || '你的五行能量分布已生成',
      mbti: (report.input_summary && report.input_summary.mbti) || '未填写 MBTI',
      wish: this.buildWishText(report.input_summary || {}),
      summary: this.buildSummary(report),
      strongest: report.strongest_element,
      weakest: report.weakest_element,
      balanceIndex: score,
      score,
      statusText: this.scoreStatus(score),
      trueSolarTime: report.solar_time && report.solar_time.true_solar_time ? report.solar_time.true_solar_time : '已按出生地校准',
      keywords: this.buildKeywordTags(report.energy_keywords),
      seasonal: this.buildSeasonalEnergy(report.seasonal_energy, report),
      bazi: this.buildBaziView(report.bazi_basis || {}),
      chakra: this.buildChakraView(report.chakra_analysis || {}),
      mood: this.buildMoodView(report.mood_analysis || {}),
      recommendationStrategy: report.recommendation_strategy || '',
      recommendationReasons: this.buildRecommendationReasons(report, elements),
      elements,
      ringGradient: this.buildRingGradient(elements)
    };
  },

  normalizeScore(value) {
    const score = Number(value);
    if (!Number.isFinite(score)) return 72;
    return Math.max(0, Math.min(100, Math.round(score)));
  },

  scoreStatus(score) {
    if (score >= 85) return '状态稳定';
    if (score >= 70) return '状态良好';
    if (score >= 55) return '可继续调和';
    return '建议温柔补足';
  },

  buildWishText(inputSummary) {
    const wishes = inputSummary.core_wishes || (inputSummary.core_wish ? [inputSummary.core_wish] : []);
    return wishes.length ? wishes.join(' / ') : '未填写愿望';
  },

  buildSummary(report) {
    const interpretation = report.interpretation || {};
    const strongest = interpretation.strongest || `${report.strongest_element || '优势'}能量较为鲜明。`;
    const weakest = interpretation.weakest || `${report.weakest_element || '待补'}能量适合慢慢调和。`;
    return `${strongest}${weakest}`;
  },

  buildKeywordTags(keywords) {
    const list = Array.isArray(keywords) ? keywords : [];
    return list.map(item => {
      if (typeof item === 'string') return { label: item, source: '能量标签' };
      return {
        label: item.label || '',
        source: item.source || '能量标签',
        element: item.element || ''
      };
    }).filter(item => item.label);
  },

  buildSeasonalEnergy(seasonal, report) {
    if (seasonal && seasonal.summary) return seasonal;
    const strongest = report.strongest_element || '优势';
    const weakest = report.weakest_element || '待补';
    return {
      title: '近期能量运势提示',
      period: '当前流月',
      seasonal_element: strongest,
      seasonal_copy: '当下适合观察自己的能量节奏。',
      notice: `你的${strongest}能量较明显。`,
      drain_point: `${weakest}能量适合慢慢补足，不宜一次调整太多。`,
      suggestion: '保持规律作息，把注意力放回最重要的一件事。',
      summary: `你的${strongest}能量较明显，${weakest}能量适合慢慢补足。保持规律作息，把注意力放回最重要的一件事。`
    };
  },

  buildBaziView(bazi) {
    const pillars = bazi.pillars || {};
    const useful = Array.isArray(bazi.useful_elements) ? bazi.useful_elements.join(' / ') : '';
    return {
      pillarsText: [pillars.year, pillars.month, pillars.day, pillars.time].filter(Boolean).join(' · '),
      dayMaster: bazi.day_master ? `${bazi.day_master}日主` : '',
      strength: bazi.day_master_strength || '',
      usefulText: useful,
      strategy: bazi.strategy || ''
    };
  },

  buildChakraView(chakra) {
    const keywords = Array.isArray(chakra.keywords) ? chakra.keywords.join(' / ') : '';
    return {
      name: chakra.primary_chakra_name || '未选择',
      keywords,
      summary: chakra.summary || '未选择当下状态，系统按中性状态参与计算。',
      colors: Array.isArray(chakra.colors) ? chakra.colors : []
    };
  },

  buildMoodView(mood) {
    return {
      name: mood.name || '未选择',
      subtitle: mood.subtitle || '未选择直觉色彩',
      summary: mood.summary || '未选择色彩时，系统不额外偏向某一组情绪色。',
      colors: Array.isArray(mood.colors) ? mood.colors : []
    };
  },

  buildRecommendationReasons(report, elements) {
    const inputSummary = report.input_summary || {};
    const wishes = inputSummary.core_wishes || (inputSummary.core_wish ? [inputSummary.core_wish] : []);
    const bazi = report.bazi_basis || {};
    const usefulElements = Array.isArray(bazi.useful_elements) ? bazi.useful_elements.filter(Boolean) : [];
    const strategy = safeText(bazi.strategy || report.recommendation_strategy);
    const strongest = safeText(report.strongest_element, '优势');
    const weakest = safeText(report.weakest_element, '待补');
    const chakra = report.chakra_analysis || {};
    const mood = report.mood_analysis || {};
    const topElements = (elements || [])
      .slice()
      .sort((a, b) => (Number(b.percent) || 0) - (Number(a.percent) || 0))
      .slice(0, 2)
      .map(item => item.name)
      .filter(Boolean);
    const usefulText = usefulElements.length ? usefulElements.join(' / ') : weakest;
    const baseDesc = strategy
      || `当前${strongest}能量较明显，${usefulText}适合温柔调和，推荐会优先选择能让整体比例更平衡的材料。`;
    const wishDesc = wishes.length
      ? `你选择了「${wishes.slice(0, 2).join('、')}」，材料筛选会更偏向这个佩戴目标和场景。`
      : '未填写愿望时，系统会先以五行平衡和佩戴舒适度作为主要推荐依据。';
    const stateParts = [
      chakra.primary_chakra_name ? `七脉轮偏向「${chakra.primary_chakra_name}」` : '',
      mood.name ? `直觉色彩选择「${mood.name}」` : ''
    ].filter(Boolean);
    const stateDesc = stateParts.length
      ? `${stateParts.join('，')}，会影响辅助珠的颜色、功效标签和排序权重。`
      : '未选择当下状态时，推荐会保持中性，不额外放大某一类颜色或情绪标签。';

    return [
      {
        index: '01',
        title: '命盘与五行',
        desc: baseDesc,
        meta: topElements.length ? `主要参考：${topElements.join(' / ')}` : '主要参考：五行比例'
      },
      {
        index: '02',
        title: '愿望与场景',
        desc: wishDesc,
        meta: wishes.length ? `愿望：${wishes.slice(0, 3).join(' / ')}` : '愿望：未填写'
      },
      {
        index: '03',
        title: '当下状态',
        desc: stateDesc,
        meta: '七脉轮 / 直觉色彩'
      }
    ];
  },

  buildRingGradient(elements) {
    let cursor = 0;
    const segments = elements.map(item => {
      const start = cursor;
      const end = cursor + (item.percent / 100) * 360;
      cursor = end;
      return `${item.color} ${start.toFixed(1)}deg ${end.toFixed(1)}deg`;
    });
    if (cursor < 360) {
      segments.push(`#ECE9E2 ${cursor.toFixed(1)}deg 360deg`);
    }
    return `conic-gradient(${segments.join(', ')})`;
  },

  openWristModal() {
    const savedWrist = Number(wx.getStorageSync('recommendedWristSize')) || 16;
    const wristSize = this.normalizeWristValue(savedWrist);
    const display = this.formatWristValue(wristSize);
    this.setData({
      showWristModal: true,
      wristInput: display,
      wristRulerValue: display
    });
    wx.nextTick(() => this.prepareWristRuler(wristSize));
  },

  closeWristModal() {
    if (!this.data.generating) this.setData({ showWristModal: false });
  },

  prepareWristRuler(value = 16) {
    const tickWidth = this.getWristTickWidthPx();
    const viewportWidth = this.getWristRulerViewportWidth();
    const sidePadding = Math.max(0, Math.round((viewportWidth - tickWidth) / 2));
    const wristValue = this.normalizeWristValue(value);
    const display = this.formatWristValue(wristValue);
    this.wristRulerTickWidthPx = tickWidth;
    this.wristRulerLastDisplay = display;
    this.setData({
      wristRulerTicks: this.buildWristRulerTicks(),
      wristRulerTickWidth: tickWidth,
      wristRulerSidePadding: sidePadding,
      wristRulerValue: display,
      wristInput: display,
      wristRulerScrollLeft: this.wristValueToScrollLeft(wristValue, tickWidth)
    });
  },

  getWindowWidthPx() {
    try {
      const info = wx.getWindowInfo ? wx.getWindowInfo() : wx.getSystemInfoSync();
      return Number(info && info.windowWidth) || 375;
    } catch (error) {
      return 375;
    }
  },

  getWristTickWidthPx() {
    const windowWidth = this.getWindowWidthPx();
    return Math.max(8, Math.round(WRIST_RULER_TICK_RPX * windowWidth / 750 * 10) / 10);
  },

  getWristRulerViewportWidth() {
    const windowWidth = this.getWindowWidthPx();
    const horizontalPaddingPx = 60 * windowWidth / 750;
    return Math.max(240, windowWidth - horizontalPaddingPx);
  },

  buildWristRulerTicks() {
    const total = Math.round((WRIST_RULER_MAX - WRIST_RULER_MIN) / WRIST_RULER_STEP);
    return Array.from({ length: total + 1 }).map((_, index) => {
      const value = this.normalizeWristValue(WRIST_RULER_MIN + index * WRIST_RULER_STEP);
      const isMajor = index % 10 === 0;
      const isMid = index % 5 === 0;
      return {
        index,
        value,
        label: isMajor ? String(Math.round(value)) : '',
        className: isMajor ? 'major' : (isMid ? 'middle' : 'minor')
      };
    });
  },

  normalizeWristValue(value) {
    const numeric = Number(value) || 16;
    const clamped = Math.max(WRIST_RULER_MIN, Math.min(WRIST_RULER_MAX, numeric));
    return Math.round(clamped * 10) / 10;
  },

  formatWristValue(value) {
    return this.normalizeWristValue(value).toFixed(1);
  },

  wristValueToScrollLeft(value, tickWidth = this.wristRulerTickWidthPx || this.getWristTickWidthPx()) {
    return Math.round((this.normalizeWristValue(value) - WRIST_RULER_MIN) * 10 * tickWidth);
  },

  scrollLeftToWristValue(scrollLeft) {
    const tickWidth = this.wristRulerTickWidthPx || this.getWristTickWidthPx();
    const maxIndex = Math.round((WRIST_RULER_MAX - WRIST_RULER_MIN) * 10);
    const index = Math.max(0, Math.min(maxIndex, Math.round((Number(scrollLeft) || 0) / tickWidth)));
    return this.normalizeWristValue(WRIST_RULER_MIN + index * WRIST_RULER_STEP);
  },

  onWristRulerTouchStart() {
    this.wristRulerInteracting = true;
    clearTimeout(this.wristRulerSnapTimer);
  },

  onWristRulerTouchEnd() {
    this.wristRulerInteracting = false;
    clearTimeout(this.wristRulerSnapTimer);
    this.wristRulerSnapTimer = setTimeout(() => this.snapWristRuler(), 220);
  },

  onWristRulerScroll(e) {
    const scrollLeft = Number(e.detail && e.detail.scrollLeft) || 0;
    const value = this.scrollLeftToWristValue(scrollLeft);
    const display = this.formatWristValue(value);
    this.currentWristRulerScrollLeft = scrollLeft;
    if (display !== this.wristRulerLastDisplay) {
      this.wristRulerLastDisplay = display;
      this.setData({
        wristRulerValue: display,
        wristInput: display
      });
    }
    if (!this.wristRulerInteracting) {
      clearTimeout(this.wristRulerSnapTimer);
      this.wristRulerSnapTimer = setTimeout(() => this.snapWristRuler(), 180);
    }
  },

  snapWristRuler() {
    if (!this.data.showWristModal) return;
    const value = this.scrollLeftToWristValue(this.currentWristRulerScrollLeft || this.data.wristRulerScrollLeft);
    const display = this.formatWristValue(value);
    this.setData({
      wristRulerValue: display,
      wristInput: display,
      wristRulerScrollLeft: this.wristValueToScrollLeft(value)
    });
  },

  selectBeadSize(e) {
    this.setData({ beadSize: Number(e.currentTarget.dataset.value) });
  },

  async confirmWristAndRecommend() {
    const wristSize = this.normalizeWristValue(Number(this.data.wristRulerValue || this.data.wristInput));
    if (!wristSize || wristSize < WRIST_RULER_MIN || wristSize > WRIST_RULER_MAX) {
      wx.showToast({ title: '请选择 10.0-25.0cm 的手腕围度', icon: 'none' });
      return;
    }
    this.setData({ generating: true });
    wx.showLoading({ title: '正在生成手串' });
    try {
      const result = await createDIYRecommendation(this.data.report.assessment_id, {
        wrist_size_cm: wristSize,
        bead_size_mm: this.data.beadSize
      });
      wx.setStorageSync('energyReport', result);
      wx.setStorageSync('recommendedWristSize', wristSize);
      wx.setStorageSync('workspaceWristConfirmed', true);
      wx.setStorageSync('diyWorkbenchPayload', result.workbench_payload);
      wx.setStorageSync('workspacePreset', 'backend-recommended');
      this.setData({ showWristModal: false });
      this.skipSuppressAssessmentAutoReport = true;
      wx.switchTab({ url: '/pages/workspace/workspace' });
    } catch (error) {
      wx.showToast({ title: error.message || '生成失败，请稍后重试', icon: 'none' });
    } finally {
      wx.hideLoading();
      this.setData({ generating: false });
    }
  },

  noop() {},

  async shareReport() {
    if (!this.data.report || this.data.posterGenerating) return;
    this.setData({ posterGenerating: true });
    wx.showLoading({ title: '正在生成海报' });
    try {
      const posterPath = await this.generateReportPoster();
      this.setData({ posterPath, showPosterModal: true });
    } catch (error) {
      console.warn('generate report poster failed:', error);
      wx.showToast({ title: error.message || '海报生成失败', icon: 'none' });
    } finally {
      wx.hideLoading();
      this.setData({ posterGenerating: false });
    }
  },

  closePosterModal() {
    this.setData({ showPosterModal: false });
  },

  previewPoster() {
    if (!this.data.posterPath) return;
    wx.previewImage({
      current: this.data.posterPath,
      urls: [this.data.posterPath]
    });
  },

  savePosterImage() {
    if (!this.data.posterPath || this.data.posterSaving || this.photoAlbumPermissionPending) return;
    this.photoAlbumPermissionPending = true;
    this.ensurePhotoAlbumPermission()
      .then(() => {
        this.photoAlbumPermissionPending = false;
        this.savePosterToAlbum();
      })
      .catch(error => {
        this.photoAlbumPermissionPending = false;
        if (error && error.handled) return;
        const message = error && error.message ? error.message : '请稍后重试，或长按海报图片保存。';
        wx.showToast({ title: message, icon: 'none' });
      });
  },

  ensurePhotoAlbumPermission() {
    return new Promise((resolve, reject) => {
      if (!wx.getSetting) {
        resolve();
        return;
      }
      wx.getSetting({
        success: setting => {
          const authSetting = setting.authSetting || {};
          const albumScope = authSetting['scope.writePhotosAlbum'];
          if (albumScope === true) {
            resolve();
            return;
          }
          if (albumScope === false) {
            this.openPhotoAlbumSetting(resolve, reject);
            return;
          }
          if (!wx.authorize) {
            resolve();
            return;
          }
          this.requestPhotoAlbumAuthorize(resolve, reject);
        },
        fail: () => resolve()
      });
    });
  },

  requestPhotoAlbumAuthorize(resolve, reject) {
    wx.showModal({
      title: '保存海报到相册',
      content: '需要获得“保存到相册”权限，授权后我会自动把这张报告海报保存到你的手机相册。',
      confirmText: '允许保存',
      cancelText: '先不了',
      success: res => {
        if (!res.confirm) {
          reject({ handled: true });
          return;
        }
        wx.authorize({
          scope: 'scope.writePhotosAlbum',
          success: resolve,
          fail: error => {
            console.warn('authorize photo album failed:', error);
            this.openPhotoAlbumSetting(resolve, reject);
          }
        });
      },
      fail: () => reject({ handled: true })
    });
  },

  openPhotoAlbumSetting(resolve = () => {}, reject = () => {}) {
    wx.showModal({
      title: '开启保存权限',
      content: '刚才没有获得相册写入权限。请在下一页打开“保存到相册”开关，返回后我会继续保存海报。',
      confirmText: '去开启',
      cancelText: '先不了',
      success: res => {
        if (!res.confirm) {
          reject({ handled: true });
          return;
        }
        if (!wx.openSetting) {
          reject({ message: '当前微信版本不支持打开设置页' });
          return;
        }
        wx.openSetting({
          success: setting => {
            const authSetting = setting.authSetting || {};
            if (authSetting['scope.writePhotosAlbum']) {
              resolve();
              return;
            }
            wx.showModal({
              title: '还没有开启权限',
              content: '需要打开“保存到相册”开关后才能保存海报。你也可以长按海报图片，用系统菜单手动保存。',
              showCancel: false
            });
            reject({ handled: true });
          },
          fail: () => reject({ message: '无法打开设置页，请长按海报图片保存。' })
        });
      },
      fail: () => reject({ handled: true })
    });
  },

  savePosterToAlbum() {
    if (!wx.saveImageToPhotosAlbum) {
      wx.showModal({
        title: '当前微信版本不支持',
        content: '请长按海报图片，使用系统菜单保存到相册。',
        showCancel: false
      });
      return;
    }
    this.setData({ posterSaving: true });
    wx.showLoading({ title: '正在保存' });
    wx.saveImageToPhotosAlbum({
      filePath: this.data.posterPath,
      success: () => {
        wx.showToast({ title: '已保存到相册', icon: 'success' });
      },
      fail: error => {
        console.warn('save poster image failed:', error);
        const message = error.errMsg || '';
        if (this.isPhotoAlbumAuthError(message)) {
          wx.hideLoading();
          this.setData({ posterSaving: false });
          this.openPhotoAlbumSetting(
            () => this.savePosterToAlbum(),
            retryError => {
              if (retryError && retryError.handled) return;
              wx.showToast({ title: retryError.message || '请长按海报图片保存', icon: 'none' });
            }
          );
          return;
        }
        wx.showModal({
          title: '保存失败',
          content: '请长按海报图片保存，或稍后重试。',
          showCancel: false
        });
      },
      complete: () => {
        wx.hideLoading();
        this.setData({ posterSaving: false });
      }
    });
  },

  isPhotoAlbumAuthError(message = '') {
    const text = String(message).toLowerCase();
    return text.includes('auth deny')
      || text.includes('auth denied')
      || text.includes('authorize')
      || text.includes('permission')
      || text.includes('scope.writephotosalbum')
      || text.includes('deny');
  },

  restartAssessment() {
    wx.setStorageSync(ASSESSMENT_RECALCULATE_KEY, true);
    wx.switchTab({ url: '/pages/assessment/assessment' });
  },

  ensurePosterCanvas() {
    if (this.posterCanvasState) return Promise.resolve(this.posterCanvasState);
    return new Promise((resolve, reject) => {
      const query = wx.createSelectorQuery().in(this);
      query.select('#reportPosterCanvas').fields({ node: true, size: true });
      query.exec(res => {
        const info = res && res[0];
        if (!info || !info.node) {
          reject(new Error('海报画布初始化失败'));
          return;
        }
        const canvas = info.node;
        const rawDpr = (wx.getWindowInfo && wx.getWindowInfo().pixelRatio)
          || (wx.getSystemInfoSync && wx.getSystemInfoSync().pixelRatio)
          || 1;
        const dpr = Math.min(2, Math.max(1, rawDpr));
        canvas.width = POSTER_WIDTH * dpr;
        canvas.height = POSTER_HEIGHT * dpr;
        const ctx = canvas.getContext('2d');
        if (ctx.setTransform) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        else ctx.scale(dpr, dpr);
        this.posterCanvasState = { canvas, ctx, dpr, width: POSTER_WIDTH, height: POSTER_HEIGHT };
        resolve(this.posterCanvasState);
      });
    });
  },

  generateReportPoster() {
    return this.ensurePosterCanvas().then(state => {
      this.drawReportPoster(state);
      return new Promise((resolve, reject) => {
        wx.canvasToTempFilePath({
          canvas: state.canvas,
          fileType: 'jpg',
          quality: 0.94,
          destWidth: POSTER_WIDTH * state.dpr,
          destHeight: POSTER_HEIGHT * state.dpr,
          success: res => resolve(res.tempFilePath),
          fail: reject
        }, this);
      });
    });
  },

  drawReportPoster(state) {
    const ctx = state.ctx;
    const report = this.data.report || {};
    const view = this.data.viewReport || this.buildViewReport(report);
    const input = report.input_summary || {};
    const name = safeText(input.name, '你');
    const seasonal = view.seasonal || {};
    const mainTitle = `${name}的五行能量报告`;
    const wishText = safeText(view.wish, '保持稳定与清透');
    const summaryText = safeText(view.summary, '你的能量分布已经生成，适合以温和的方式继续调和。');
    const suggestion = safeText(seasonal.suggestion || seasonal.summary, '保持规律作息，把注意力放回最重要的一件事。');
    const elements = view.elements || [];
    const strongest = safeText(view.strongest, '优势');
    const weakest = safeText(view.weakest, '待补');

    ctx.clearRect(0, 0, POSTER_WIDTH, POSTER_HEIGHT);
    const bg = ctx.createLinearGradient(0, 0, 0, POSTER_HEIGHT);
    bg.addColorStop(0, '#FBFAF7');
    bg.addColorStop(1, '#F1EEE7');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, POSTER_WIDTH, POSTER_HEIGHT);

    ctx.fillStyle = '#20201F';
    ctx.font = '800 28px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText('宇涧水晶', 58, 76);
    ctx.fillStyle = '#8B8881';
    ctx.font = '700 18px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText('WU XING ENERGY REPORT', 58, 106);
    ctx.textAlign = 'right';
    ctx.fillText('LIGHT STUDIO LAB', 692, 82);
    ctx.textAlign = 'left';

    fillRoundRect(ctx, 44, 140, 662, 360, 32, '#FFFFFF');
    strokeRoundRect(ctx, 44, 140, 662, 360, 32, '#E5E2DC', 1);
    ctx.fillStyle = '#20201F';
    ctx.font = '900 44px "PingFang SC", "Microsoft YaHei", sans-serif';
    drawWrappedText(ctx, mainTitle, 76, 206, 336, 54, 2);
    ctx.fillStyle = '#64615B';
    ctx.font = '500 24px "PingFang SC", "Microsoft YaHei", sans-serif';
    drawWrappedText(ctx, `愿望：${wishText}`, 76, 320, 340, 34, 2);
    ctx.fillStyle = '#8B8881';
    ctx.font = '600 22px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText(`MBTI：${safeText(view.mbti, '未填写')}`, 76, 420);
    ctx.fillText(`偏强 ${strongest} · 待补 ${weakest}`, 76, 456);

    drawElementRing(ctx, elements, 560, 296, 96, 24);
    fillRoundRect(ctx, 494, 230, 132, 132, 66, '#FBFAF7');
    ctx.textAlign = 'center';
    ctx.fillStyle = '#20201F';
    ctx.font = '900 54px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText(String(view.score), 560, 292);
    ctx.fillStyle = '#8B8881';
    ctx.font = '700 21px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText(view.statusText, 560, 330);
    ctx.textAlign = 'left';

    fillRoundRect(ctx, 44, 526, 662, 302, 28, '#FFFFFF');
    strokeRoundRect(ctx, 44, 526, 662, 302, 28, '#E5E2DC', 1);
    ctx.fillStyle = '#20201F';
    ctx.font = '800 30px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText('五行比例', 76, 584);
    drawPosterElementRows(ctx, elements, 76, 622, 598);

    fillRoundRect(ctx, 44, 854, 662, 204, 28, '#FFFFFF');
    strokeRoundRect(ctx, 44, 854, 662, 204, 28, '#E5E2DC', 1);
    ctx.fillStyle = '#20201F';
    ctx.font = '800 30px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText('专属关键词', 76, 912);
    const afterTagsY = drawPosterTags(ctx, view.keywords || [], 76, 934, 598);
    ctx.fillStyle = '#64615B';
    ctx.font = '500 22px "PingFang SC", "Microsoft YaHei", sans-serif';
    drawWrappedText(ctx, summaryText, 76, afterTagsY + 8, 598, 32, 2);

    fillRoundRect(ctx, 44, 1080, 662, 74, 24, '#20201F');
    ctx.fillStyle = '#FFFFFF';
    ctx.font = '800 24px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText('调和建议', 76, 1125);
    ctx.font = '500 22px "PingFang SC", "Microsoft YaHei", sans-serif';
    drawWrappedText(ctx, suggestion, 188, 1125, 390, 28, 1);
    ctx.textAlign = 'right';
    ctx.fillStyle = '#D8D4CC';
    ctx.font = '700 20px "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText('打开小程序生成你的专属手串', 674, 1125);
    ctx.textAlign = 'left';
  },

  goBack() {
    wx.setStorageSync(ASSESSMENT_SUPPRESS_AUTO_REPORT_ONCE_KEY, true);
    const pages = getCurrentPages();
    if (pages.length > 1) {
      wx.navigateBack();
      return;
    }
    wx.switchTab({ url: '/pages/assessment/assessment' });
  }
});
