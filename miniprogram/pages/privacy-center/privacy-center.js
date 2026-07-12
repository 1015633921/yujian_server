const auth = require('../../utils/auth');
const { getPrivacyDataSummary, deletePersonalizationData } = require('../../utils/api');
const {
  CHAKRA_OPTIONS,
  MOOD_PALETTES,
  labelForAssessmentValue,
  labelsForAssessmentValues
} = require('../../utils/assessmentOptions');

const DISCLOSURE_GROUPS = [
  {
    title: '完成基础测算所需',
    badge: '必要',
    rows: [
      { field: '昵称或称呼', purpose: '在报告和方案中称呼你', retention: '删除测算数据时一并删除报告内记录' },
      { field: '出生日期、时间、地点', purpose: '生成传统文化元素比例参考', retention: '主动删除前保留，可重新测算修改' },
      { field: '佩戴目标', purpose: '确定搭配方向与主材角色', retention: '主动删除前保留，可重新测算修改' }
    ]
  },
  {
    title: '用于个性化的可选信息',
    badge: '可跳过',
    rows: [
      { field: '性别标识、MBTI', purpose: '辅助文案语气和配色偏好', retention: '主动删除前保留，可不填写' },
      { field: '当下状态选项', purpose: '调整当天的搭配侧重点', retention: '主动删除前保留，可不填写' },
      { field: '直觉色彩偏好', purpose: '辅助选择颜色和视觉风格', retention: '主动删除前保留，可不填写' }
    ]
  },
  {
    title: '系统生成的数据',
    badge: '画像结果',
    rows: [
      { field: '五行元素比例、星座与状态画像', purpose: '展示分析结果，不用于医疗或确定性判断', retention: '删除测算数据时一并删除' },
      { field: '推荐材料与 DIY 方案', purpose: '生成可编辑的审美搭配建议', retention: '测算画像可删除；已保存 DIY 方案可在方案页单独管理' },
      { field: '每日状态记录', purpose: '生成当日搭配提示', retention: '删除测算数据时一并删除' }
    ]
  }
];

function displayValue(value, fallback = '未填写') {
  if (Array.isArray(value)) return value.filter(Boolean).join('、') || fallback;
  return String(value || '').trim() || fallback;
}

Page({
  data: {
    loading: false,
    deleting: false,
    errorText: '',
    disclosureGroups: DISCLOSURE_GROUPS,
    currentRows: [],
    countsText: '暂无已保存的测算与画像数据',
    hasPersonalizationData: false
  },

  onLoad() {
    this.loadSummary();
  },

  async loadSummary() {
    const user = auth.getStoredUser();
    if (!user || !user.user_id) {
      this.setData({ currentRows: [], hasPersonalizationData: false });
      return;
    }
    this.setData({ loading: true, errorText: '' });
    try {
      const summary = await getPrivacyDataSummary(user.user_id, { silent: true, timeout: 8000 });
      this.applySummary(summary);
    } catch (error) {
      const cachedReport = wx.getStorageSync('energyReport') || {};
      const cachedInput = cachedReport.input_summary || wx.getStorageSync('assessmentLastProfile') || {};
      this.applySummary({
        profile: user,
        latest_input: cachedInput,
        counts: {
          assessments: cachedReport.assessment_id ? 1 : 0,
          daily_energies: wx.getStorageSync('todayDailyEnergy') ? 1 : 0,
          daily_checkins: 0
        }
      }, '当前显示本机已保存的数据；云端摘要将在服务恢复后同步');
    } finally {
      this.setData({ loading: false });
    }
  },

  applySummary(summary = {}, sourceHint = '') {
    const profile = summary.profile || {};
    const input = summary.latest_input || {};
    const counts = summary.counts || {};
    const assessmentCount = Number(counts.assessments || 0);
    const dailyCount = Number(counts.daily_energies || 0) + Number(counts.daily_checkins || 0);
    this.setData({
      currentRows: [
        { label: '昵称或称呼', value: displayValue(input.name || profile.nickname) },
        { label: '出生信息', value: [input.birthday, input.birth_time, input.birth_place].filter(Boolean).join(' · ') || '未填写' },
        { label: '性格偏好', value: displayValue(input.mbti) },
        { label: '佩戴目标', value: displayValue(input.core_wishes || input.core_wish) },
        { label: '当下状态', value: labelsForAssessmentValues(input.chakra_answers, CHAKRA_OPTIONS) },
        { label: '色彩偏好', value: labelForAssessmentValue(input.mood_palette_id, MOOD_PALETTES) }
      ],
      countsText: sourceHint || (assessmentCount || dailyCount
        ? `已保存 ${assessmentCount} 份测算画像、${dailyCount} 条每日状态记录`
        : '暂无已保存的测算与画像数据'),
      hasPersonalizationData: assessmentCount > 0 || dailyCount > 0,
      errorText: ''
    });
  },

  editAssessment() {
    wx.setStorageSync('assessmentRecalculateMode', true);
    wx.setStorageSync('assessmentSuppressAutoReportOnce', true);
    wx.switchTab({ url: '/pages/assessment/assessment' });
  },

  openWechatPrivacy() {
    if (!wx.openPrivacyContract) {
      wx.showToast({ title: '当前微信版本暂不支持', icon: 'none' });
      return;
    }
    wx.openPrivacyContract({
      fail: error => wx.showToast({ title: error.errMsg || '隐私保护指引暂不可用', icon: 'none' })
    });
  },

  requestAccountDeletion() {
    wx.navigateTo({ url: '/pages/support-center/support-center?scene=account_deletion' });
  },

  deletePersonalization() {
    if (!this.data.hasPersonalizationData || this.data.deleting) return;
    wx.showModal({
      title: '删除测算与画像数据',
      content: '将删除出生信息、偏好、测算报告、画像和每日状态记录。订单及售后记录不会删除。此操作不可恢复。',
      confirmText: '确认删除',
      confirmColor: '#C83B3D',
      success: async result => {
        if (!result.confirm) return;
        const user = auth.getStoredUser();
        if (!user || !user.user_id) return;
        this.setData({ deleting: true });
        try {
          await deletePersonalizationData(user.user_id, { silent: true, timeout: 10000 });
          [
            'assessmentDraft',
            'assessmentLastProfile',
            'assessmentRecalculateMode',
            'assessmentSuppressAutoReportOnce',
            'assessmentRequestedStep',
            'assessmentReportSeed',
            'energyReport',
            'energyProfile',
            'reportBasisView',
            'todayDailyEnergy',
            'todayDailyEnergyRefreshDate',
            'recommendedRecipe',
            'recommendedWristSize',
            'workspaceWristConfirmed',
            'diyWorkbenchPayload'
          ].forEach(key => wx.removeStorageSync(key));
          wx.showToast({ title: '测算与画像数据已删除', icon: 'success' });
          await this.loadSummary();
        } catch (error) {
          wx.showModal({
            title: '删除失败',
            content: error.message || '网络异常，请稍后重试',
            showCancel: false
          });
        } finally {
          this.setData({ deleting: false });
        }
      }
    });
  },

  goBack() {
    if (getCurrentPages().length > 1) {
      wx.navigateBack();
      return;
    }
    wx.switchTab({ url: '/pages/profile/profile' });
  }
});
