const auth = require('../../utils/auth');
const env = require('../../config/env');
const {
  getOrders,
  payOrder,
  mockPayOrder,
  mockShipOrder,
  confirmReceipt,
  requestAfterSale,
  refundOrder,
  getOrderLogistics
} = require('../../utils/api');

const ORDER_TABS = [
  { key: 'pay', icon: '¥', label: '待付款', count: 0 },
  { key: 'ship', icon: '发', label: '待发货', count: 0 },
  { key: 'receive', icon: '收', label: '待收货', count: 0 },
  { key: 'after', icon: '售', label: '售后退款', count: 0 }
];

Page({
  data: {
    user: null,
    isLoggedIn: false,
    hasProfile: false,
    hasPhone: false,
    authLoading: false,
    savingProfile: false,
    phoneLoading: false,
    isLocalApi: env.isLocalApi,
    nicknameFocus: false,
    showProfileModal: false,
    showLogisticsModal: false,
    logisticsDetail: null,
    profileDraft: { nickname: '', avatar_url: '' },
    phoneDraft: '',
    profile: {},
    draft: null,
    avatarChar: '星',
    draftCount: 0,
    couponCount: 0,
    inspirationCartCount: 0,
    communityFavoriteCount: 0,
    inspirationStats: [],
    orders: [],
    filteredOrders: [],
    activeOrderStatus: 'all',
    orderStats: ORDER_TABS
  },

  onShow() {
    this.refreshPage();
    this.refreshOrdersFromServer();
  },

  refreshPage() {
    const user = auth.getStoredUser();
    const profile = wx.getStorageSync('energyProfile') || {};
    const draft = wx.getStorageSync('currentDesign') || null;
    const draftCount = draft && draft.summary ? draft.summary.count : 0;
    const inspirationCart = wx.getStorageSync('inspirationCart') || [];
    const communityFavorites = wx.getStorageSync('communityFavorites') || [];
    this.setData({
      user,
      isLoggedIn: !!(user && user.user_id),
      hasProfile: !!(user && user.has_profile),
      hasPhone: !!(user && user.has_phone),
      profileDraft: {
        nickname: (user && user.nickname) || '',
        avatar_url: (user && user.avatar_url) || ''
      },
      phoneDraft: (user && user.phone_number) || '',
      profile,
      draft,
      avatarChar: this.avatarChar(user, profile),
      draftCount,
      couponCount: wx.getStorageSync('couponCount') || 0,
      inspirationCartCount: inspirationCart.length,
      communityFavoriteCount: communityFavorites.length,
      inspirationStats: [
        { key: 'draft', icon: 'DIY', title: '我的 DIY', desc: draftCount ? '继续编辑最近的手串草稿' : '还没有草稿，去做第一条手串', count: draftCount ? `${draftCount} 颗` : '去创建' },
        { key: 'cart', icon: '收', title: '灵感单收藏', desc: inspirationCart.length ? '首页加入的推荐和每日水晶' : '首页加号收藏后会出现在这里', count: `${inspirationCart.length} 件` },
        { key: 'community', icon: '社', title: '社区收藏', desc: communityFavorites.length ? '你收藏过的搭配灵感' : '看到喜欢的作品可以先收藏', count: `${communityFavorites.length} 篇` }
      ],
      orders: wx.getStorageSync('orders') || []
    });
    this.refreshOrderView();
  },

  async refreshOrdersFromServer() {
    const user = auth.getStoredUser();
    if (!user || !user.user_id) return;
    try {
      const rows = await getOrders(user.user_id);
      const orders = rows.map(item => this.normalizeOrder(item));
      wx.setStorageSync('orders', orders);
      this.setData({ orders });
      this.refreshOrderView();
    } catch (error) {
      console.warn('load orders fallback:', error.message || error);
    }
  },

  normalizeOrder(item) {
    return {
      id: item.order_id,
      createdAt: item.created_at,
      status: item.status_text || this.statusText(item),
      statusKey: this.statusKey(item),
      totalAmount: item.total_amount,
      receiver: item.receiver,
      design: item.design,
      sequence: item.sequence,
      bom: item.bom,
      rawStatus: item.status,
      paymentStatus: item.payment_status,
      logistics: item.logistics || {},
      statusHistory: item.status_history || [],
      afterSaleStatus: item.after_sale_status || '',
      refundStatus: item.refund_status || ''
    };
  },

  statusKey(order) {
    const status = order.status || order.rawStatus;
    if (status === 'pending_ship') return 'ship';
    if (status === 'shipped') return 'receive';
    if (status === 'after_sale' || status === 'refund_requested' || status === 'refunded') return 'after';
    if (order.payment_status === 'unpaid' || order.paymentStatus === 'unpaid' || status === 'pending_payment') return 'pay';
    return 'done';
  },

  statusText(order) {
    const map = {
      pending_payment: '待付款',
      pending_ship: '待发货',
      shipped: '待收货',
      completed: '已完成',
      after_sale: '售后中',
      refund_requested: '退款中',
      refunded: '已退款',
      closed: '已关闭'
    };
    return map[order.status || order.rawStatus] || '处理中';
  },

  refreshOrderView() {
    const orders = (this.data.orders || []).map(order => ({
      ...order,
      statusKey: order.statusKey || this.statusKey(order),
      status: order.status || this.statusText(order)
    }));
    const counts = { all: orders.length, pay: 0, ship: 0, receive: 0, after: 0 };
    orders.forEach(order => {
      if (counts[order.statusKey] !== undefined) counts[order.statusKey] += 1;
    });
    const active = this.data.activeOrderStatus;
    const filteredOrders = active === 'all' ? orders : orders.filter(order => order.statusKey === active);
    this.setData({
      filteredOrders,
      orderStats: ORDER_TABS.map(item => ({ ...item, count: counts[item.key] || 0 }))
    });
  },

  avatarChar(user, profile) {
    if (user && user.nickname) return user.nickname.slice(0, 1);
    if (profile && profile.name) return profile.name.slice(0, 1);
    return '星';
  },

  async loginWithWechat() {
    this.setData({ authLoading: true });
    wx.showLoading({ title: '正在登录' });
    try {
      const user = await auth.loginWithWechatProfile();
      this.setData({
        user,
        isLoggedIn: !!user.user_id,
        hasProfile: !!user.has_profile,
        hasPhone: !!user.has_phone,
        avatarChar: this.avatarChar(user, this.data.profile),
        profileDraft: {
          nickname: user.nickname || '',
          avatar_url: user.avatar_url || ''
        }
      });
      wx.showToast({ title: '登录成功', icon: 'success' });
      this.refreshOrdersFromServer();
    } catch (error) {
      console.error('loginWithWechat failed:', error);
      wx.showToast({ title: error.message || '登录失败', icon: 'none' });
    } finally {
      wx.hideLoading();
      this.setData({ authLoading: false });
    }
  },

  onProfileInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [`profileDraft.${field}`]: e.detail.value });
  },

  openProfileModal() {
    this.setData({ showProfileModal: true });
  },

  closeProfileModal() {
    this.setData({ showProfileModal: false, nicknameFocus: false });
  },

  noop() {},

  focusNicknameInput() {
    this.setData({ nicknameFocus: true });
  },

  onNicknameBlur() {
    this.setData({ nicknameFocus: false });
  },

  onPhoneInput(e) {
    this.setData({ phoneDraft: e.detail.value });
  },

  onChooseAvatar(e) {
    this.setData({ 'profileDraft.avatar_url': e.detail.avatarUrl });
  },

  async saveBasicProfile() {
    if (!this.data.isLoggedIn) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    const draft = this.data.profileDraft;
    if (!draft.nickname.trim()) {
      wx.showToast({ title: '请填写昵称', icon: 'none' });
      return;
    }
    this.setData({ savingProfile: true });
    wx.showLoading({ title: '保存资料' });
    try {
      const user = await auth.updateBasicProfile({
        nickname: draft.nickname.trim(),
        avatar_url: draft.avatar_url
      });
      this.setData({
        user,
        hasProfile: !!user.has_profile,
        hasPhone: !!user.has_phone,
        avatarChar: this.avatarChar(user, this.data.profile),
        profileDraft: {
          nickname: user.nickname || draft.nickname,
          avatar_url: user.avatar_url || draft.avatar_url
        }
      });
      wx.showToast({ title: '资料已保存', icon: 'success' });
    } catch (error) {
      console.error('saveBasicProfile failed:', error);
      wx.showToast({ title: error.message || '保存失败', icon: 'none' });
    } finally {
      wx.hideLoading();
      this.setData({ savingProfile: false });
    }
  },

  async onGetPhoneNumber(e) {
    if (!this.data.isLoggedIn) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    this.setData({ phoneLoading: true });
    wx.showLoading({ title: '绑定手机号' });
    try {
      const user = await auth.bindWechatPhone(e);
      this.setData({ user, hasPhone: !!user.has_phone });
      wx.showToast({ title: '手机号已绑定', icon: 'success' });
    } catch (error) {
      console.error('bind phone failed:', error);
      wx.showToast({ title: error.message || '绑定失败', icon: 'none' });
    } finally {
      wx.hideLoading();
      this.setData({ phoneLoading: false });
    }
  },

  async saveManualPhone() {
    if (!this.data.isLoggedIn) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    const phoneNumber = this.data.phoneDraft.trim();
    if (!/^1\d{10}$/.test(phoneNumber)) {
      wx.showToast({ title: '请填写 11 位手机号', icon: 'none' });
      return;
    }
    this.setData({ phoneLoading: true });
    wx.showLoading({ title: '保存手机号' });
    try {
      const user = await auth.bindManualPhone(phoneNumber);
      this.setData({ user, hasPhone: !!user.has_phone, phoneDraft: user.phone_number || phoneNumber });
      wx.showToast({ title: '手机号已保存', icon: 'success' });
    } catch (error) {
      wx.showToast({ title: error.message || '保存失败', icon: 'none' });
    } finally {
      wx.hideLoading();
      this.setData({ phoneLoading: false });
    }
  },

  handleOrderStatus(e) {
    const key = e.currentTarget.dataset.key || 'all';
    wx.navigateTo({ url: `/pages/order-list/order-list?status=${key}` });
  },

  showAllOrders() {
    wx.navigateTo({ url: '/pages/order-list/order-list?status=all' });
  },

  async handleOrderAction(e) {
    const { id, action } = e.currentTarget.dataset;
    const user = auth.getStoredUser();
    if (!user || !user.user_id) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    if (action === 'pay') return this.continuePay(id, user.user_id);
    if (action === 'mockShip') {
      const order = (this.data.orders || []).find(item => item.id === id) || {};
      const phone = (order.receiver && order.receiver.phone) || '';
      return this.runOrderAction(() => mockShipOrder(id, user.user_id, {
        carrier: '顺丰速运',
        carrier_code: 'shunfeng',
        phone_tail: phone ? phone.slice(-4) : ''
      }), '已发货');
    }
    if (action === 'receive') return this.runOrderAction(() => confirmReceipt(id, user.user_id), '已确认收货');
    if (action === 'logistics') return this.showLogistics(id, user.user_id);
    if (action === 'afterSale') return this.confirmAfterSale(id, user.user_id);
    if (action === 'refund') return this.confirmRefund(id, user.user_id);
  },

  confirmAfterSale(orderId, userId) {
    wx.showModal({
      title: '申请售后',
      content: '提交后订单会进入售后中，后台可继续处理退换货。',
      confirmText: '提交',
      success: async res => {
        if (res.confirm) {
          await this.runOrderAction(() => requestAfterSale(orderId, userId, '用户在小程序发起售后'), '售后已提交');
        }
      }
    });
  },

  confirmRefund(orderId, userId) {
    wx.showModal({
      title: '申请退款',
      content: '提交后订单会进入退款中，待商家审核后原路退款。',
      confirmText: '提交',
      success: async res => {
        if (res.confirm) {
          await this.runOrderAction(() => refundOrder(orderId, userId, '用户在小程序发起退款'), '退款已提交');
        }
      }
    });
  },

  async showLogistics(orderId, userId) {
    wx.showLoading({ title: '查询物流' });
    try {
      const result = await getOrderLogistics(orderId, userId);
      wx.hideLoading();
      const logistics = result.logistics || {};
      const traces = logistics.traces || [];
      this.setData({
        showLogisticsModal: true,
        logisticsDetail: {
          orderId,
          carrier: logistics.carrier || '物流信息',
          trackingNo: logistics.tracking_no || '',
          statusText: logistics.status_text || '待更新',
          source: logistics.source === 'kuaidi100' ? '快递100实时查询' : '本地物流记录',
          message: logistics.message || '',
          traces: traces.length ? traces : [
            { time: '', location: '', desc: '商家尚未发货，暂时没有物流轨迹。' }
          ],
          statusHistory: result.status_history || []
        }
      });
    } catch (error) {
      wx.hideLoading();
      wx.showToast({ title: error.message || '物流查询失败', icon: 'none' });
    }
  },

  closeLogisticsModal() {
    this.setData({ showLogisticsModal: false, logisticsDetail: null });
  },

  async continuePay(orderId, userId) {
    wx.showLoading({ title: '准备支付' });
    try {
      const result = await payOrder(orderId, userId);
      wx.hideLoading();
      const payment = result.payment || {};
      if (payment.available && payment.pay_params) {
        await this.requestWechatPayment(payment.pay_params);
        await this.runOrderAction(() => mockPayOrder(orderId, userId), '支付完成');
        return;
      }
      if (this.data.isLocalApi) {
        wx.showModal({
          title: '无法调起真实支付',
          content: `${payment.message || '当前环境不支持真实支付'}\n\n是否模拟支付成功，继续测试订单流程？`,
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

  requestWechatPayment(payParams) {
    return new Promise((resolve, reject) => {
      wx.requestPayment({ ...payParams, success: resolve, fail: reject });
    });
  },

  async runOrderAction(action, toastTitle) {
    wx.showLoading({ title: '处理订单' });
    try {
      await action();
      await this.refreshOrdersFromServer();
      wx.hideLoading();
      wx.showToast({ title: toastTitle, icon: 'success' });
    } catch (error) {
      wx.hideLoading();
      wx.showToast({ title: error.message || '操作失败', icon: 'none' });
    }
  },

  goCoupons() {
    wx.showToast({ title: '优惠券功能准备中', icon: 'none' });
  },

  handleInspiration(e) {
    const type = e.currentTarget.dataset.type;
    if (type === 'draft') return this.goWorkspace();
    if (type === 'cart') return this.viewInspirationCart();
    this.goCommunity();
  },

  viewInspirationCart() {
    const cart = wx.getStorageSync('inspirationCart') || [];
    if (!cart.length) {
      wx.showToast({ title: '先去首页收藏灵感', icon: 'none' });
      return;
    }
    wx.showModal({
      title: `灵感单 ${cart.length} 件`,
      content: cart.map(item => item.name).join('、'),
      confirmText: '带入 DIY',
      cancelText: '知道了',
      success: res => {
        if (res.confirm) {
          const first = cart[0];
          wx.setStorageSync('recommendedRecipe', first.recipe || ['clearQuartz']);
          wx.setStorageSync('workspacePreset', 'recommended');
          this.goWorkspace();
        }
      }
    });
  },

  goAssessment() {
    if (!this.data.isLoggedIn) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    wx.navigateTo({ url: '/pages/assessment/assessment' });
  },

  goWorkspace() {
    wx.switchTab({ url: '/pages/workspace/workspace' });
  },

  goCommunity() {
    wx.switchTab({ url: '/pages/community/community' });
  }
});
