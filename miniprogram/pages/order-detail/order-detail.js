const auth = require('../../utils/auth');
const env = require('../../config/env');
const {
  payOrder,
  mockPayOrder,
  mockShipOrder,
  confirmReceipt,
  requestAfterSale,
  refundOrder,
  getOrderLogistics
} = require('../../utils/api');

Page({
  data: {
    id: '',
    order: null,
    isLocalApi: env.isLocalApi,
    logisticsDetail: null
  },

  onLoad(options) {
    this.setData({ id: options.id || '' });
    this.loadOrder();
  },

  onShow() {
    this.loadOrder();
  },

  loadOrder() {
    const orders = wx.getStorageSync('orders') || [];
    const order = orders.find(item => item.id === this.data.id) || null;
    this.setData({ order });
    if (!order) {
      wx.showToast({ title: '订单不存在', icon: 'none' });
    }
  },

  async handleAction(e) {
    const action = e.currentTarget.dataset.action;
    const user = auth.getStoredUser();
    const order = this.data.order;
    if (!user || !user.user_id || !order) return;
    if (action === 'pay') return this.continuePay(order.id, user.user_id);
    if (action === 'mockShip') {
      const phone = (order.receiver && order.receiver.phone) || '';
      return this.runOrderAction(() => mockShipOrder(order.id, user.user_id, {
        carrier: '顺丰速运',
        carrier_code: 'shunfeng',
        phone_tail: phone ? phone.slice(-4) : ''
      }), '已发货');
    }
    if (action === 'receive') return this.runOrderAction(() => confirmReceipt(order.id, user.user_id), '已确认收货');
    if (action === 'logistics') return this.loadLogistics(order.id, user.user_id);
    if (action === 'afterSale') return this.confirmAfterSale(order.id, user.user_id);
    if (action === 'refund') return this.confirmRefund(order.id, user.user_id);
  },

  async loadLogistics(orderId, userId) {
    wx.showLoading({ title: '查询物流' });
    try {
      const result = await getOrderLogistics(orderId, userId);
      const logistics = result.logistics || {};
      const traces = logistics.traces || [];
      this.setData({
        logisticsDetail: {
          carrier: logistics.carrier || '物流信息',
          trackingNo: logistics.tracking_no || '',
          statusText: logistics.status_text || '待更新',
          source: logistics.source === 'kuaidi100' ? '快递100实时查询' : '本地物流记录',
          message: logistics.message || '',
          traces: traces.length ? traces : [{ desc: '商家尚未发货，暂时没有物流轨迹。' }],
          statusHistory: result.status_history || []
        }
      });
    } catch (error) {
      wx.showToast({ title: error.message || '物流查询失败', icon: 'none' });
    } finally {
      wx.hideLoading();
    }
  },

  confirmAfterSale(orderId, userId) {
    wx.showModal({
      title: '申请售后',
      content: '提交后订单会进入售后中，后台可继续处理。',
      confirmText: '提交',
      success: async res => {
        if (res.confirm) await this.runOrderAction(() => requestAfterSale(orderId, userId, '用户在小程序发起售后'), '售后已提交');
      }
    });
  },

  confirmRefund(orderId, userId) {
    wx.showModal({
      title: '申请退款',
      content: '提交后订单会进入退款中，待商家审核。',
      confirmText: '提交',
      success: async res => {
        if (res.confirm) await this.runOrderAction(() => refundOrder(orderId, userId, '用户在小程序发起退款'), '退款已提交');
      }
    });
  },

  async continuePay(orderId, userId) {
    wx.showLoading({ title: '准备支付' });
    try {
      const result = await payOrder(orderId, userId);
      const payment = result.payment || {};
      wx.hideLoading();
      if (payment.available && payment.pay_params) {
        await new Promise((resolve, reject) => wx.requestPayment({ ...payment.pay_params, success: resolve, fail: reject }));
        await this.runOrderAction(() => mockPayOrder(orderId, userId), '支付完成');
        return;
      }
      if (this.data.isLocalApi) {
        wx.showModal({
          title: '无法调起真实支付',
          content: `${payment.message || '当前环境不支持真实支付'}\n\n是否模拟支付成功？`,
          confirmText: '模拟支付',
          success: async res => {
            if (res.confirm) await this.runOrderAction(() => mockPayOrder(orderId, userId), '已进入待发货');
          }
        });
        return;
      }
      wx.showToast({ title: payment.message || '支付暂不可用', icon: 'none' });
    } catch (error) {
      wx.hideLoading();
      wx.showToast({ title: error.message || '支付失败', icon: 'none' });
    }
  },

  async runOrderAction(action, title) {
    wx.showLoading({ title: '处理订单' });
    try {
      await action();
      wx.hideLoading();
      wx.showToast({ title, icon: 'success' });
      setTimeout(() => wx.navigateBack(), 500);
    } catch (error) {
      wx.hideLoading();
      wx.showToast({ title: error.message || '操作失败', icon: 'none' });
    }
  }
});
