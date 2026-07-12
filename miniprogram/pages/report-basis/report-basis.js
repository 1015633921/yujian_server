const REPORT_BASIS_VIEW_KEY = 'reportBasisView';
const ENERGY_REPORT_KEY = 'energyReport';
const ASSESSMENT_RECALCULATE_KEY = 'assessmentRecalculateMode';
const ASSESSMENT_REQUESTED_STEP_KEY = 'assessmentRequestedStep';
const ASSESSMENT_REPORT_SEED_KEY = 'assessmentReportSeed';
const { getReportBasis } = require('../../utils/api');
const auth = require('../../utils/auth');

function safeText(value, fallback = '') {
  if (value === null || value === undefined) return fallback;
  const text = String(value).trim();
  return text || fallback;
}

function formatReportTimestamp(value) {
  const text = safeText(value);
  if (!text) return '';
  const match = text.match(/^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})/);
  return match ? `${match[1]}-${match[2]}-${match[3]} ${match[4]}:${match[5]}` : text;
}

Page({
  data: {
    viewReport: null,
    mbtiKeywordText: '',
    inputSummaryText: '',
    generationLogicText: '',
    generatedAtText: '',
    emptyTitle: '暂时没有可查看的测算依据',
    emptyCopy: '请先返回搭配报告，再从“查看完整依据”进入。'
  },

  onLoad(options = {}) {
    const reportId = safeText(options.report_id);
    const reportVersion = Number(options.report_version);
    if (reportId && Number.isInteger(reportVersion) && reportVersion > 0) {
      this.reportRef = { reportId, reportVersion };
      this.loadVersionedBasis();
      return;
    }
    const stored = wx.getStorageSync(REPORT_BASIS_VIEW_KEY);
    if (!stored) return;
    const payload = stored.viewReport ? stored : { viewReport: stored };
    const viewReport = payload.viewReport;
    if (!viewReport) return;
    const currentReport = wx.getStorageSync(ENERGY_REPORT_KEY) || {};
    if (!this.isOwnedByCurrentUser(currentReport)) {
      wx.removeStorageSync(REPORT_BASIS_VIEW_KEY);
      this.setData({
        emptyTitle: '请先登录',
        emptyCopy: '登录后可查看当前账户生成的测算依据。'
      });
      return;
    }
    if (this.isStaleReport(payload, currentReport)) {
      this.setData({
        emptyTitle: '报告已经更新',
        emptyCopy: '请返回最新搭配报告，再重新查看本次测算依据。'
      });
      return;
    }
    this.setData({
      viewReport,
      mbtiKeywordText: this.buildMbtiKeywordText(viewReport.mbti),
      inputSummaryText: this.buildInputSummary(viewReport),
      generationLogicText: this.buildGenerationLogic(viewReport),
      generatedAtText: viewReport.generatedAtText || formatReportTimestamp(payload.createdAt)
    });
  },

  onShow() {
    if (this.reportRef) return;
    if (!this.data.viewReport) return;
    const stored = wx.getStorageSync(REPORT_BASIS_VIEW_KEY) || {};
    const payload = stored.viewReport ? stored : { viewReport: stored };
    const currentReport = wx.getStorageSync(ENERGY_REPORT_KEY) || {};
    if (!this.isOwnedByCurrentUser(currentReport)) {
      wx.removeStorageSync(REPORT_BASIS_VIEW_KEY);
      this.setData({
        viewReport: null,
        emptyTitle: '请先登录',
        emptyCopy: '登录后可查看当前账户生成的测算依据。'
      });
      return;
    }
    if (!this.isStaleReport(payload, currentReport)) return;
    this.setData({
      viewReport: null,
      emptyTitle: '报告已经更新',
      emptyCopy: '请返回最新搭配报告，再重新查看本次测算依据。'
    });
  },

  async loadVersionedBasis() {
    const user = auth.getStoredUser();
    if (!user || !user.user_id) {
      this.setData({ emptyTitle: '请先登录', emptyCopy: '登录后可查看当前账户生成的测算依据。' });
      return;
    }
    try {
      const payload = await getReportBasis(
        this.reportRef.reportId,
        this.reportRef.reportVersion,
        { silent: true }
      );
      if (!this.reportRef
        || payload.report_id !== this.reportRef.reportId
        || Number(payload.report_version) !== this.reportRef.reportVersion) return;
      this.basisPayload = payload;
      const viewReport = this.buildVersionedView(payload);
      this.setData({
        viewReport,
        mbtiKeywordText: this.buildMbtiKeywordText(viewReport.mbti),
        inputSummaryText: this.buildInputSummary(viewReport),
        generationLogicText: this.buildGenerationLogic(viewReport),
        generatedAtText: formatReportTimestamp(payload.created_at)
      });
    } catch (error) {
      this.setData({
        emptyTitle: error && error.statusCode === 409 ? '报告版本已变化' : '无法读取测算依据',
        emptyCopy: '请返回搭配报告后重新进入。'
      });
    }
  },

  buildVersionedView(payload = {}) {
    const input = payload.input_snapshot || {};
    const calibration = payload.calibration || {};
    const details = calibration.details || {};
    const baziBasis = payload.bazi_basis || {};
    const pillars = baziBasis.pillars || {};
    const mbti = payload.mbti_analysis || {};
    const chakra = payload.chakra_analysis || {};
    const mood = payload.mood_analysis || {};
    const zodiac = payload.zodiac_analysis || {};
    const moodColors = Array.isArray(mood.colors) ? mood.colors : [];
    const calibrationApplied = calibration.status === 'applied';
    return {
      assessmentId: '',
      reportId: payload.report_id,
      reportVersion: payload.report_version,
      createdAt: payload.created_at,
      generatedAtText: formatReportTimestamp(payload.created_at),
      wish: (input.core_wishes || []).join(' / ') || '未填写目标',
      hasMbtiInput: Boolean(input.mbti),
      hasChakraInput: Boolean((input.chakra_answers || []).length),
      hasMoodInput: Boolean(input.mood_palette_id),
      hasLiveInput: Boolean((input.chakra_answers || []).length || input.mood_palette_id),
      trueSolarTime: calibrationApplied ? safeText(details.calibrated_time || details.true_solar_time) : '',
      trueSolarTimeLabel: calibrationApplied ? '校准后时间' : '未完成地点校准',
      trueSolarTimeDescription: calibrationApplied
        ? '按出生地点与日期校准'
        : '当前地点不在已验证坐标数据中，本次未显示校准时间',
      hasTrueSolarTime: calibrationApplied,
      bazi: {
        pillarsText: [pillars.year, pillars.month, pillars.day, pillars.time].filter(Boolean).join(' · '),
        dayMaster: safeText(baziBasis.day_master),
        dayMasterDescription: '用于形成基础结构参考',
        strength: safeText(baziBasis.day_master_strength, '已生成'),
        strengthDescription: '作为基础结构的专业参考'
      },
      mbti: {
        selected: Boolean(input.mbti),
        type: safeText(mbti.type || input.mbti).toUpperCase(),
        keywords: Array.isArray(mbti.keywords) ? mbti.keywords : [],
        influence: safeText(mbti.influence, '用于微调材质气质与排列偏好，不单独决定最终方案。')
      },
      chakra: {
        name: chakra.primary_chakra_name || '未选择',
        summary: chakra.summary || '未选择当下状态，系统按中性状态参与计算。'
      },
      mood: {
        name: mood.name || '未选择',
        summary: mood.summary || '未选择色彩时，不额外偏向某一组情绪色。',
        colorSwatches: moodColors.map((value, index) => ({ id: `${index}-${value}`, value, label: `${mood.name || '直觉'}配色 ${index + 1}` }))
      },
      zodiac: {
        name: zodiac.name || '',
        element: zodiac.element || '',
        modality: zodiac.modality || '',
        summary: zodiac.summary || '',
        suggestion: zodiac.suggestion || ''
      },
      keywords: [],
      seasonal: {
        period: '生成时状态',
        seasonal_element: '',
        seasonal_copy: '近期提示已固定在本次报告快照中。',
        drain_point: '按本次报告生成时的信息提供参考。',
        suggestion: '如信息发生变化，请主动重新分析生成新版本。'
      }
    };
  },

  isStaleReport(payload = {}, currentReport = {}) {
    const payloadId = safeText(payload.assessmentId || (payload.viewReport && payload.viewReport.assessmentId));
    const currentId = safeText(currentReport.assessment_id);
    if (payloadId && currentId) return payloadId !== currentId;
    const payloadCreatedAt = safeText(payload.createdAt || (payload.viewReport && payload.viewReport.createdAt));
    const currentCreatedAt = safeText(currentReport.created_at);
    return Boolean(payloadCreatedAt && currentCreatedAt && payloadCreatedAt !== currentCreatedAt);
  },

  isOwnedByCurrentUser(report = {}) {
    const storedUser = wx.getStorageSync('currentUser') || {};
    const storedUserId = safeText(storedUser.user_id);
    const reportUserId = safeText(report.input_summary && report.input_summary.user_id);
    return Boolean(storedUserId && reportUserId && storedUserId === reportUserId);
  },

  buildMbtiKeywordText(mbti = {}) {
    const keywords = Array.isArray(mbti.keywords) ? mbti.keywords.filter(Boolean) : [];
    return keywords.length ? keywords.join('、') : '未加入额外性格偏好';
  },

  buildInputSummary(viewReport = {}) {
    const hasWish = safeText(viewReport.wish) && viewReport.wish !== '未填写目标';
    const parts = ['元素结构', hasWish ? '佩戴目标' : ''];
    if (viewReport.hasMbtiInput) parts.push('性格偏好');
    if (viewReport.hasLiveInput) parts.push('当前状态');
    return `本方案综合${parts.filter(Boolean).join('、')}生成。`;
  },

  buildGenerationLogic(viewReport = {}) {
    const hasWish = safeText(viewReport.wish) && viewReport.wish !== '未填写目标';
    const parts = ['元素结构影响调节方向'];
    if (hasWish) parts.push('佩戴目标影响使用场景');
    if (viewReport.hasMbtiInput) parts.push('性格偏好影响材质与排列');
    if (viewReport.hasLiveInput) parts.push('当下状态影响本次氛围建议');
    return `${parts.join('，')}。`;
  },

  showSolarTimeInfo() {
    wx.showModal({
      title: '校准后时间说明',
      content: '根据出生地点经度、时区与日期换算为真太阳时，用于统一测算中的时间基准。',
      showCancel: false,
      confirmText: '知道了'
    });
  },

  restartAssessment() {
    if (this.basisPayload && this.basisPayload.input_snapshot) {
      wx.setStorageSync(ASSESSMENT_REPORT_SEED_KEY, {
        input_summary: this.basisPayload.input_snapshot,
        created_at: this.basisPayload.created_at || ''
      });
      wx.setStorageSync(ASSESSMENT_RECALCULATE_KEY, true);
      wx.setStorageSync(ASSESSMENT_REQUESTED_STEP_KEY, 'basic');
      wx.switchTab({ url: '/pages/assessment/assessment' });
      return;
    }
    const report = wx.getStorageSync(ENERGY_REPORT_KEY) || {};
    if (report.input_summary) {
      wx.setStorageSync(ASSESSMENT_REPORT_SEED_KEY, {
        input_summary: report.input_summary,
        created_at: report.created_at || ''
      });
    }
    wx.setStorageSync(ASSESSMENT_RECALCULATE_KEY, true);
    wx.setStorageSync(ASSESSMENT_REQUESTED_STEP_KEY, 'basic');
    wx.switchTab({ url: '/pages/assessment/assessment' });
  },

  goBack() {
    const pages = getCurrentPages();
    if (pages && pages.length > 1) {
      wx.navigateBack();
      return;
    }
    const url = this.reportRef
      ? `/pages/report/report?report_id=${encodeURIComponent(this.reportRef.reportId)}&report_version=${this.reportRef.reportVersion}`
      : '/pages/report/report';
    wx.redirectTo({ url });
  }
});
