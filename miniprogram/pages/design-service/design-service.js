const auth = require('../../utils/auth');
const {
  createCustomDesignRequest,
  getCustomDesignRequests,
  confirmCustomDesignRequest,
  reviseCustomDesignRequest
} = require('../../utils/api');

const STATUS_TEXT = {
  submitted: '已提交，等待设计',
  designing: '设计中',
  proposed: '方案待确认',
  revision_requested: '等待调整',
  confirmed: '已确认方案',
  closed: '服务已结束'
};

const WRIST_SIZE_OPTIONS = Array.from({ length: 29 }, (_, index) => (12 + index * 0.5).toFixed(1));
const BEAD_SIZE_OPTIONS = Array.from({ length: 11 }, (_, index) => index + 6);
const BUDGET_OPTIONS = ['100–200 元', '200–300 元', '300–500 元', '500–800 元', '800 元以上'];

function closestOptionIndex(options, value) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return 0;
  return options.reduce((bestIndex, option, index) => (
    Math.abs(Number(option) - numericValue) < Math.abs(Number(options[bestIndex]) - numericValue)
      ? index
      : bestIndex
  ), 0);
}

Page({
  data: {
    reportId: '',
    reportVersion: 0,
    assessmentId: '',
    request: null,
    loading: true,
    submitting: false,
    revisionOpen: false,
    wristSizeOptions: WRIST_SIZE_OPTIONS,
    beadSizeOptions: BEAD_SIZE_OPTIONS,
    budgetOptions: BUDGET_OPTIONS,
    wristSizeIndex: 8,
    beadSizeIndex: 2,
    budgetIndex: 2,
    form: {
      wrist_size_cm: '16.0',
      bead_size_mm: 8,
      budget: '300–500 元',
      style_preference: '清透自然',
      color_preference: '',
      accessory_preference: '适量点缀',
      wear_scene: '日常佩戴',
      note: ''
    }
  },

  onLoad(options = {}) {
    const wristSizeIndex = closestOptionIndex(WRIST_SIZE_OPTIONS, wx.getStorageSync('recommendedWristSize') || 16);
    const beadSizeIndex = closestOptionIndex(BEAD_SIZE_OPTIONS, wx.getStorageSync('recommendedBeadSize') || 8);
    this.setData({
      reportId: String(options.report_id || ''),
      reportVersion: Number(options.report_version) || 0,
      assessmentId: String(options.assessment_id || ''),
      wristSizeIndex,
      beadSizeIndex,
      'form.wrist_size_cm': WRIST_SIZE_OPTIONS[wristSizeIndex],
      'form.bead_size_mm': BEAD_SIZE_OPTIONS[beadSizeIndex]
    });
    this.loadRequests();
  },

  async onShow() {
    if (this.data.reportId) await this.loadRequests(true);
  },

  async loadRequests(silent = false) {
    const user = auth.getStoredUser() || {};
    if (!user.user_id) {
      this.setData({ loading: false });
      return;
    }
    try {
      const requests = await getCustomDesignRequests({ silent });
      const request = this.data.reportId
        ? ((requests || []).find(item => item.report_id === this.data.reportId && Number(item.report_version) === this.data.reportVersion) || null)
        : ((requests || [])[0] || null);
      this.setData({ request: this.decorateRequest(request), loading: false });
    } catch (error) {
      this.setData({ loading: false });
      if (!silent) wx.showToast({ title: error.message || '加载服务进度失败', icon: 'none' });
    }
  },

  onFieldInput(event) {
    const field = event.currentTarget.dataset.field;
    if (!field) return;
    this.setData({ [`form.${field}`]: event.detail.value });
  },

  chooseOption(event) {
    const { field, value } = event.currentTarget.dataset;
    if (!field) return;
    this.setData({ [`form.${field}`]: field === 'bead_size_mm' ? Number(value) : String(value) });
  },

  onWristSizeChange(event) {
    const wristSizeIndex = Number(event.detail.value);
    this.setData({ wristSizeIndex, 'form.wrist_size_cm': WRIST_SIZE_OPTIONS[wristSizeIndex] });
  },

  onBeadSizeChange(event) {
    const beadSizeIndex = Number(event.detail.value);
    this.setData({ beadSizeIndex, 'form.bead_size_mm': BEAD_SIZE_OPTIONS[beadSizeIndex] });
  },

  onBudgetChange(event) {
    const budgetIndex = Number(event.detail.value);
    this.setData({ budgetIndex, 'form.budget': BUDGET_OPTIONS[budgetIndex] });
  },

  async submitRequest() {
    const user = auth.getStoredUser() || {};
    const form = this.data.form;
    const wrist = Number(form.wrist_size_cm);
    if (!user.user_id || !this.data.reportId || !this.data.reportVersion) {
      wx.showToast({ title: '报告尚未准备好，请返回后重试', icon: 'none' });
      return;
    }
    if (!Number.isFinite(wrist) || wrist < 12 || wrist > 26) {
      wx.showToast({ title: '请填写 12–26cm 的手围', icon: 'none' });
      return;
    }
    this.setData({ submitting: true });
    try {
      const request = await createCustomDesignRequest({
        user_id: user.user_id,
        report_id: this.data.reportId,
        report_version: this.data.reportVersion,
        assessment_id: this.data.assessmentId || undefined,
        ...form,
        wrist_size_cm: wrist
      });
      this.setData({ request: this.decorateRequest(request) });
      wx.showToast({ title: '申请已提交', icon: 'success' });
    } catch (error) {
      wx.showToast({ title: error.message || '提交失败，请稍后重试', icon: 'none' });
    } finally {
      this.setData({ submitting: false });
    }
  },

  async confirmProposal() {
    const request = this.data.request;
    if (!request) return;
    const result = await new Promise(resolve => wx.showModal({
      title: '确认这套搭配？',
      content: '确认后会按当前材料和价格生成待支付订单，并为你保留库存 24 小时。',
      confirmText: '确认并生成订单',
      success: resolve
    }));
    if (!result.confirm) return;
    try {
      const user = auth.getStoredUser() || {};
      const updated = await confirmCustomDesignRequest(request.request_id, { user_id: user.user_id });
      this.setData({ request: this.decorateRequest(updated) });
      const orderId = updated && updated.order && updated.order.order_id;
      if (orderId) {
        wx.showToast({ title: '待支付订单已生成', icon: 'success' });
        setTimeout(() => wx.navigateTo({
          url: `/pages/order-detail/order-detail?id=${encodeURIComponent(orderId)}`
        }), 450);
      } else {
        wx.showToast({ title: '已确认方案', icon: 'success' });
      }
    } catch (error) {
      wx.showToast({ title: error.message || '操作失败', icon: 'none' });
    }
  },

  openRevision() { this.setData({ revisionOpen: true }); },
  closeRevision() { this.setData({ revisionOpen: false }); },

  async submitRevision(event) {
    const note = String((event.detail.value || {}).revision || '').trim();
    if (note.length < 5) {
      wx.showToast({ title: '请至少写 5 个字说明想调整的地方', icon: 'none' });
      return;
    }
    try {
      const user = auth.getStoredUser() || {};
      const updated = await reviseCustomDesignRequest(this.data.request.request_id, { user_id: user.user_id, note });
      this.setData({ request: this.decorateRequest(updated), revisionOpen: false });
      wx.showToast({ title: '调整说明已提交', icon: 'success' });
    } catch (error) {
      wx.showToast({ title: error.message || '提交失败', icon: 'none' });
    }
  },

  previewImage(event) {
    const current = event.currentTarget.dataset.url;
    const urls = ((this.data.request || {}).proposals || []).flatMap(item => item.image_urls || []);
    wx.previewImage({ current, urls });
  },

  openProposalInWorkspace() {
    const request = this.data.request || {};
    const proposal = request.latest_proposal || {};
    const workbench = proposal.workbench || {};
    const layout = Array.isArray(workbench.layout) ? workbench.layout : [];
    if (!layout.length) {
      wx.showToast({ title: '方案排布暂不可用', icon: 'none' });
      return;
    }
    const importId = `custom-design:${request.request_id}:${proposal.proposal_id}:${Date.now()}`;
    const payload = {
      wrist_size_cm: Number(workbench.wrist_size_cm) || 16,
      bead_size_mm: Number(workbench.bead_size_mm) || 8,
      source: 'custom_design',
      source_label: '设计师搭配',
      source_context: {
        source: 'custom_design',
        source_label: '设计师搭配',
        request_id: request.request_id,
        proposal_id: proposal.proposal_id,
        title: proposal.title || '专属手串方案'
      },
      bracelet_plan: {
        title: proposal.title || '专属手串方案',
        bead_size_mm: Number(workbench.bead_size_mm) || 8,
        items: layout.map(item => ({
          material_id: item.material_id || item.id,
          bead_size_mm: item.size || workbench.bead_size_mm
        })),
        layout: layout.map((item, index) => ({
          ...item,
          slot_index: index,
          material_id: item.material_id || item.id,
          image_url: item.selected_image_url || item.image_url || ''
        })),
        validation: {
          is_valid: true,
          source: 'designer_confirmed_layout'
        }
      }
    };
    wx.setStorageSync('recommendedWristSize', payload.wrist_size_cm);
    wx.setStorageSync('workspaceWristConfirmed', true);
    wx.setStorageSync('diyWorkbenchPayload', payload);
    wx.setStorageSync('workspaceImportIntent', {
      id: importId,
      type: 'custom-design',
      createdAt: Date.now()
    });
    wx.removeStorageSync('workspaceOpenDesign');
    wx.setStorageSync('workspacePreset', 'backend-recommended');
    wx.switchTab({ url: '/pages/workspace/workspace' });
  },

  goAssessment() {
    wx.switchTab({ url: '/pages/assessment/assessment' });
  },

  decorateRequest(request) {
    if (!request) return null;
    const proposals = (request.proposals || []).map(proposal => {
      const workbench = proposal.workbench || {};
      const layout = Array.isArray(workbench.layout) ? workbench.layout : [];
      const previewLayout = layout.map((item, index) => {
        const angle = (index / Math.max(1, layout.length)) * Math.PI * 2 - Math.PI / 2;
        return {
          ...item,
          preview_key: `${proposal.proposal_id || 'proposal'}:${index}`,
          preview_style: `left:${50 + Math.cos(angle) * 35}%;top:${50 + Math.sin(angle) * 35}%;`,
          preview_image_url: item.selected_image_url || item.image_url || ''
        };
      });
      return {
        ...proposal,
        image_urls: Array.isArray(proposal.image_urls) ? proposal.image_urls : [],
        workbench: { ...workbench, layout },
        bead_count: layout.length,
        price_text: (workbench.summary || {}).price || '0.00',
        preview_layout: previewLayout
      };
    });
    const latestProposal = proposals.find(item => item.status === 'active') || proposals[0] || null;
    return {
      ...request,
      proposals,
      latest_proposal: latestProposal,
      has_structured_proposal: !!(latestProposal && latestProposal.bead_count),
      status_text: STATUS_TEXT[request.status] || request.status || '处理中'
    };
  }
});
