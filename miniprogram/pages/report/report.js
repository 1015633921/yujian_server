const { createDIYRecommendation } = require('../../utils/api');

const ELEMENT_META = {
  木: { key: 'wood', color: '#4f8f6f' },
  火: { key: 'fire', color: '#c75d45' },
  土: { key: 'earth', color: '#b58b4f' },
  金: { key: 'metal', color: '#9b9fa3' },
  水: { key: 'water', color: '#477b91' }
};

Page({
  data: {
    report: null,
    viewReport: null,
    avatarChar: '',
    showWristModal: false,
    wristInput: '',
    wristOptions: [14, 15, 16, 17, 18, 19],
    beadSize: 8,
    beadSizeOptions: [6, 8, 10, 12],
    generating: false
  },

  onLoad() {
    const report = wx.getStorageSync('energyReport');
    if (report) {
      this.setData({
        report,
        viewReport: this.buildViewReport(report),
        avatarChar: report.input_summary.name.slice(0, 1)
      });
    }
  },

  buildViewReport(report) {
    const elements = Object.keys(ELEMENT_META).map(name => ({
      ...ELEMENT_META[name],
      name,
      value: Number(report.final_energy_profile[name]).toFixed(2),
      width: `${Math.min(100, Number(report.final_energy_profile[name]) * 3)}%`
    }));
    return {
      title: report.interpretation.headline,
      mbti: report.input_summary.mbti || '未填写 MBTI',
      wish: (report.input_summary.core_wishes || [report.input_summary.core_wish]).join(' / '),
      summary: `${report.interpretation.strongest}${report.interpretation.weakest}`,
      strongest: report.strongest_element,
      weakest: report.weakest_element,
      balanceIndex: report.interpretation.balance_index,
      trueSolarTime: report.solar_time.true_solar_time,
      elements
    };
  },

  openWristModal() {
    const savedWrist = wx.getStorageSync('recommendedWristSize');
    this.setData({ showWristModal: true, wristInput: savedWrist ? String(savedWrist) : '' });
  },

  closeWristModal() {
    if (!this.data.generating) this.setData({ showWristModal: false });
  },

  onWristInput(e) {
    this.setData({ wristInput: e.detail.value });
  },

  selectWristOption(e) {
    this.setData({ wristInput: String(e.currentTarget.dataset.value) });
  },

  selectBeadSize(e) {
    this.setData({ beadSize: Number(e.currentTarget.dataset.value) });
  },

  async confirmWristAndRecommend() {
    const wristSize = Number(this.data.wristInput);
    if (!wristSize || wristSize < 10 || wristSize > 30) {
      wx.showToast({ title: '请输入 10-30cm 的手腕围度', icon: 'none' });
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
      wx.setStorageSync('diyWorkbenchPayload', result.workbench_payload);
      wx.setStorageSync('workspacePreset', 'backend-recommended');
      this.setData({ showWristModal: false });
      wx.switchTab({ url: '/pages/workspace/workspace' });
    } catch (error) {
      wx.showToast({ title: error.message || '生成失败，请稍后重试', icon: 'none' });
    } finally {
      wx.hideLoading();
      this.setData({ generating: false });
    }
  },

  noop() {},

  shareReport() {
    wx.showToast({ title: '报告海报生成能力待接入', icon: 'none' });
  },

  goBack() {
    wx.navigateBack();
  }
});
