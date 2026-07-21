const auth = require('../../utils/auth');
const {
  getOrder,
  getAfterSaleCases,
  createAfterSaleCase,
  submitAfterSaleReturnShipment,
  cancelAfterSaleCase
} = require('../../utils/api');

const SERVICE_TYPES = [
  {
    key: 'return_refund',
    index: '01',
    title: '退货退款',
    desc: '商品存在问题，希望审核后退回并原路退款',
    reasons: [
      { key: 'quality_issue', label: '质量问题' },
      { key: 'damaged', label: '收到时破损' },
      { key: 'not_as_expected', label: '与确认方案不符' },
      { key: 'other', label: '其他退款原因' }
    ]
  },
  {
    key: 'resize',
    index: '02',
    title: '修改手围',
    desc: '成品尺寸不合适，希望重新调整佩戴长度',
    reasons: [
      { key: 'size_large', label: '手围偏大' },
      { key: 'size_small', label: '手围偏小' },
      { key: 'wearing_uncomfortable', label: '佩戴不舒适' },
      { key: 'other', label: '其他尺寸问题' }
    ]
  },
  {
    key: 'repair',
    index: '03',
    title: '重新穿制／维修',
    desc: '线材、珠体或配件需要检查并重新处理',
    reasons: [
      { key: 'cord_loose', label: '线材松动或断裂' },
      { key: 'bead_damaged', label: '珠体损坏' },
      { key: 'accessory_issue', label: '配件问题' },
      { key: 'other', label: '其他维修问题' }
    ]
  },
  {
    key: 'resend',
    index: '04',
    title: '缺件／补发',
    desc: '包裹缺少内容、物流破损或收到错误商品',
    reasons: [
      { key: 'item_missing', label: '包裹缺件' },
      { key: 'logistics_damage', label: '物流破损' },
      { key: 'wrong_item', label: '收到错误商品' },
      { key: 'other', label: '其他补发问题' }
    ]
  },
  {
    key: 'other',
    index: '05',
    title: '其他问题',
    desc: '养护、使用或其他需要工作室协助的问题',
    reasons: [
      { key: 'care_question', label: '佩戴与养护' },
      { key: 'service_consulting', label: '服务咨询' },
      { key: 'other', label: '其他问题' }
    ]
  }
];

const ACTIVE_CASE_STATUSES = [
  'requested', 'approved', 'awaiting_return', 'returning', 'service_processing',
  'refund_pending', 'refund_submitting', 'refunding'
];

function createIdempotencyKey(orderId) {
  const random = Math.random().toString(36).slice(2, 10);
  return `after_sale_${orderId}_${Date.now().toString(36)}_${random}`.slice(0, 128);
}

Page({
  data: {
    orderId: '',
    order: null,
    orderSummary: null,
    serviceTypes: SERVICE_TYPES,
    selectedType: '',
    selectedTypeTitle: '',
    reasonOptions: [],
    selectedReason: '',
    selectedReasonLabel: '',
    detail: '',
    detailCount: 0,
    agreementChecked: false,
    canSubmit: false,
    loading: true,
    submitting: false,
    loadError: '',
    submitError: '',
    submittedCase: null,
    isExistingCase: false,
    returnCarrier: '顺丰速运',
    returnTrackingNo: '',
    returnSubmitting: false,
    canceling: false
  },

  onLoad(options = {}) {
    const orderId = decodeURIComponent(options.id || options.order_id || '');
    this.idempotencyKey = createIdempotencyKey(orderId || 'unknown');
    this.setData({ orderId });
    this.loadPage();
  },

  async loadPage() {
    if (!this.data.orderId) {
      this.setData({ loading: false, loadError: '缺少订单信息，请从订单详情重新进入' });
      return;
    }
    this.setData({ loading: true, loadError: '' });
    try {
      let user = auth.getStoredUser();
      if (!user || !user.user_id) user = await auth.silentLogin();
      this.activeUser = user;
      const [order, cases] = await Promise.all([
        getOrder(this.data.orderId, user.user_id),
        getAfterSaleCases(this.data.orderId, user.user_id, { silent: true, showModal: false })
      ]);
      const activeCase = (cases || []).find(item => ACTIVE_CASE_STATUSES.includes(item.status));
      this.setData({
        order,
        orderSummary: this.buildOrderSummary(order),
        submittedCase: activeCase ? this.buildCaseDisplay(activeCase) : null,
        isExistingCase: !!activeCase
      });
    } catch (error) {
      this.setData({ loadError: error.message || '售后信息加载失败，请稍后重试' });
    } finally {
      this.setData({ loading: false });
    }
  },

  buildOrderSummary(order = {}) {
    const sequence = order.sequence || [];
    const amount = Number(order.total_amount || 0);
    return {
      orderId: order.order_id || this.data.orderId,
      amountText: Number.isFinite(amount) ? amount.toFixed(2) : '0.00',
      statusText: order.status_text || order.status || '-',
      materialCount: sequence.length,
      eligible: order.payment_status === 'paid' && ['shipped', 'completed'].includes(order.status),
      eligibilityText: order.payment_status !== 'paid'
        ? '订单尚未支付，不能申请售后'
        : (!['shipped', 'completed'].includes(order.status) ? '当前订单状态暂不能申请售后' : '')
    };
  },

  buildCaseDisplay(item = {}) {
    const nextSteps = {
      requested: '工作室审核中，请先不要自行寄回商品。',
      awaiting_return: '审核已通过，请填写退回快递公司和单号。',
      returning: '退回物流已提交，工作室收货核验后会继续处理。',
      service_processing: '工作室正在处理本次服务，请留意后续通知。',
      refund_pending: '退款已审核通过，等待运营复核并提交微信。',
      refund_submitting: '退款指令已登记，正在核对微信接口结果。',
      refunding: '微信退款处理中，请留意原支付账户。'
    };
    return {
      ...item,
      createdAtText: this.formatDateTime(item.created_at),
      returnSubmittedAtText: this.formatDateTime(item.return_submitted_at),
      canSubmitReturn: item.status === 'awaiting_return',
      canCancel: ['requested', 'awaiting_return'].includes(item.status),
      nextStepText: nextSteps[item.status] || (item.type === 'return_refund'
        ? '工作室会根据售后状态继续安排退回与退款。'
        : '工作室会通过售后记录或客服告知具体处理方式。')
    };
  },

  onReturnCarrierInput(event) {
    this.setData({ returnCarrier: String(event.detail.value || '').slice(0, 50) });
  },

  onReturnTrackingInput(event) {
    this.setData({ returnTrackingNo: String(event.detail.value || '').trim().slice(0, 80) });
  },

  async submitReturnShipment() {
    const activeCase = this.data.submittedCase;
    const user = this.activeUser || auth.getStoredUser();
    if (!activeCase || !activeCase.canSubmitReturn || this.data.returnSubmitting) return;
    if (!user || !user.user_id) {
      wx.showToast({ title: '请重新登录后提交', icon: 'none' });
      return;
    }
    if (!this.data.returnCarrier.trim() || this.data.returnTrackingNo.trim().length < 6) {
      wx.showToast({ title: '请填写有效的退回物流信息', icon: 'none' });
      return;
    }
    this.setData({ returnSubmitting: true });
    try {
      const updated = await submitAfterSaleReturnShipment(
        this.data.orderId,
        activeCase.case_id,
        {
          user_id: user.user_id,
          carrier: this.data.returnCarrier.trim(),
          tracking_no: this.data.returnTrackingNo.trim()
        },
        { showModal: false }
      );
      this.setData({ submittedCase: this.buildCaseDisplay(updated) });
      wx.showToast({ title: '退回物流已提交', icon: 'success' });
    } catch (error) {
      wx.showToast({ title: error.message || '退回物流提交失败', icon: 'none' });
    } finally {
      this.setData({ returnSubmitting: false });
    }
  },

  cancelApplication() {
    const activeCase = this.data.submittedCase;
    const user = this.activeUser || auth.getStoredUser();
    if (!activeCase || !activeCase.canCancel || this.data.canceling || !user || !user.user_id) return;
    wx.showModal({
      title: '取消售后申请',
      content: '取消后，本次售后将停止处理。确认继续吗？',
      confirmText: '确认取消',
      confirmColor: '#b35f34',
      success: async result => {
        if (!result.confirm) return;
        this.setData({ canceling: true });
        try {
          await cancelAfterSaleCase(
            this.data.orderId,
            activeCase.case_id,
            user.user_id,
            '用户在小程序主动取消售后',
            { showModal: false }
          );
          wx.showToast({ title: '售后申请已取消', icon: 'success' });
          this.setData({ submittedCase: null, isExistingCase: false });
          await this.loadPage();
        } catch (error) {
          wx.showToast({ title: error.message || '取消失败，请稍后重试', icon: 'none' });
        } finally {
          this.setData({ canceling: false });
        }
      }
    });
  },

  selectType(event) {
    const key = event.currentTarget.dataset.key;
    const selected = SERVICE_TYPES.find(item => item.key === key);
    if (!selected || this.data.submitting) return;
    this.setData({
      selectedType: selected.key,
      selectedTypeTitle: selected.title,
      reasonOptions: selected.reasons,
      selectedReason: '',
      selectedReasonLabel: '',
      submitError: ''
    });
    this.updateCanSubmit();
  },

  selectReason(event) {
    const key = event.currentTarget.dataset.key;
    const selected = this.data.reasonOptions.find(item => item.key === key);
    if (!selected || this.data.submitting) return;
    this.setData({ selectedReason: selected.key, selectedReasonLabel: selected.label, submitError: '' });
    this.updateCanSubmit();
  },

  onDetailInput(event) {
    const detail = String(event.detail.value || '').slice(0, 500);
    this.setData({ detail, detailCount: detail.length, submitError: '' });
    this.updateCanSubmit();
  },

  toggleAgreement() {
    if (this.data.submitting) return;
    this.setData({ agreementChecked: !this.data.agreementChecked, submitError: '' });
    this.updateCanSubmit();
  },

  updateCanSubmit() {
    const summary = this.data.orderSummary;
    const canSubmit = !!(
      summary && summary.eligible
      && this.data.selectedType
      && this.data.selectedReason
      && this.data.detail.trim().length >= 5
      && this.data.agreementChecked
      && !this.data.submitting
      && !this.data.submittedCase
    );
    this.setData({ canSubmit });
  },

  async submitApplication() {
    this.updateCanSubmit();
    if (!this.data.canSubmit || this.data.submitting) {
      wx.showToast({ title: '请完成售后类型、原因和问题说明', icon: 'none' });
      return;
    }
    const user = this.activeUser || auth.getStoredUser();
    if (!user || !user.user_id) {
      wx.showToast({ title: '请重新登录后提交', icon: 'none' });
      return;
    }
    this.setData({ submitting: true, canSubmit: false, submitError: '' });
    try {
      const created = await createAfterSaleCase(this.data.orderId, {
        user_id: user.user_id,
        type: this.data.selectedType,
        reason_code: this.data.selectedReason,
        reason: this.data.detail.trim(),
        evidence_urls: [],
        idempotency_key: this.idempotencyKey
      }, { showModal: false });
      this.setData({ submittedCase: this.buildCaseDisplay(created), isExistingCase: false });
      wx.showToast({ title: '售后申请已提交', icon: 'success' });
    } catch (error) {
      if (error && error.statusCode === 409) {
        await this.loadExistingCaseAfterConflict(user.user_id);
      } else {
        this.setData({ submitError: error.message || '提交失败，请稍后重试' });
      }
    } finally {
      this.setData({ submitting: false });
      this.updateCanSubmit();
    }
  },

  async loadExistingCaseAfterConflict(userId) {
    try {
      const cases = await getAfterSaleCases(this.data.orderId, userId, { silent: true, showModal: false });
      const activeCase = (cases || []).find(item => ACTIVE_CASE_STATUSES.includes(item.status));
      if (activeCase) {
        this.setData({ submittedCase: this.buildCaseDisplay(activeCase), isExistingCase: true });
        return;
      }
    } catch (error) {
      // Fall through to the conflict message below.
    }
    this.setData({ submitError: '该订单已有进行中的售后申请，请返回订单详情查看' });
  },

  retryLoad() {
    this.loadPage();
  },

  goOrderDetail() {
    const pages = getCurrentPages();
    if (pages.length > 1) {
      wx.navigateBack();
      return;
    }
    wx.redirectTo({ url: `/pages/order-detail/order-detail?id=${encodeURIComponent(this.data.orderId)}` });
  },

  formatDateTime(value) {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    const pad = number => String(number).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }
});
