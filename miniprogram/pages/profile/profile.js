const auth = require('../../utils/auth');
const env = require('../../config/env');
const {
  getOrders,
  getOrder,
  payOrder,
  mockPayOrder,
  mockShipOrder,
  confirmReceipt,
  requestAfterSale,
  refundOrder,
  getOrderLogistics,
  getCartItems,
  getCommunityFavorites
} = require('../../utils/api');

const ORDER_TABS = [
  { key: 'pay', icon: '¥', label: '待付款', count: 0 },
  { key: 'ship', icon: '发', label: '待发货', count: 0 },
  { key: 'receive', icon: '收', label: '待收货', count: 0 },
  { key: 'done', icon: '✓', label: '已完成', count: 0, showCount: false },
  { key: 'after', icon: '售', label: '售后退款', count: 0 }
];
const TAB_BAR_PAGES = ['/pages/home/home', '/pages/assessment/assessment', '/pages/workspace/workspace', '/pages/profile/profile'];

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
    profileAvatarChanged: false,
    profile: {},
    draft: null,
    avatarChar: '',
    draftCount: 0,
    shoppingCartCount: 0,
    communityFavoriteCount: 0,
    profileStats: [],
    orders: [],
    filteredOrders: [],
    activeOrderStatus: 'all',
    orderStats: ORDER_TABS,
    labTabbarClass: ''
  },

  onShow() {
    this.hideNativeTabBar();
    this.lastProfileScrollTop = 0;
    if (this.data.labTabbarClass) {
      this.setData({ labTabbarClass: '' });
    }
    this.refreshPage();
    this.refreshOrdersFromServer();
  },

  onHide() {
    clearTimeout(this.tabbarSetDataTimer);
    this.restoreNativeTabBar();
  },

  onUnload() {
    clearTimeout(this.tabbarSetDataTimer);
    this.restoreNativeTabBar();
  },

  onPageScroll(e) {
    const currentTop = Number(e.scrollTop) || 0;
    const previousTop = this.lastProfileScrollTop || 0;
    const delta = currentTop - previousTop;
    this.lastProfileScrollTop = currentTop;

    if (Math.abs(delta) < 12) return;

    const shouldHide = delta > 0 && currentTop > 80;
    const nextClass = shouldHide ? 'is-hidden' : '';
    if (nextClass === this.data.labTabbarClass) return;

    clearTimeout(this.tabbarSetDataTimer);
    this.tabbarSetDataTimer = setTimeout(() => {
      this.setData({ labTabbarClass: nextClass });
    }, 16);
  },

  hideNativeTabBar() {
    if (!wx.hideTabBar) return;
    wx.hideTabBar({ animation: false, fail: () => {} });
  },

  restoreNativeTabBar() {
    if (!wx.showTabBar) return;
    wx.showTabBar({ animation: false, fail: () => {} });
  },

  refreshPage() {
    const user = auth.getStoredUser();
    const profile = wx.getStorageSync('energyProfile') || {};
    const draft = wx.getStorageSync('currentDesign') || null;
    const draftCount = draft && Array.isArray(draft.selected) ? draft.selected.length : 0;
    const shoppingCart = wx.getStorageSync('diyDesignCart') || [];
    const storedCommunityFavorites = wx.getStorageSync('communityFavorites') || [];
    const favoriteIds = new Set();
    const communityFavorites = storedCommunityFavorites.filter(item => {
      if (!item || !item.id || favoriteIds.has(item.id)) return false;
      favoriteIds.add(item.id);
      return true;
    });
    if (communityFavorites.length !== storedCommunityFavorites.length) {
      wx.setStorageSync('communityFavorites', communityFavorites);
    }
    const localOrders = wx.getStorageSync('orders') || [];
    const favoriteCount = communityFavorites.length;
    this.setData({
      user,
      isLoggedIn: !!(user && user.user_id),
      hasProfile: !!(user && user.has_profile),
      hasPhone: !!(user && user.has_phone),
      profileDraft: {
        nickname: (user && user.nickname) || '',
        avatar_url: (user && user.avatar_url) || ''
      },
      profileAvatarChanged: false,
      profile,
      draft,
      avatarChar: this.avatarChar(user, profile),
      draftCount,
      shoppingCartCount: shoppingCart.length,
      communityFavoriteCount: communityFavorites.length,
      profileStats: [
        { key: 'plans', value: draftCount, label: '我的方案' },
        { key: 'orders', value: localOrders.length, label: '我的订单' },
        { key: 'cart', value: shoppingCart.length, label: '购物车' },
        { key: 'energy', value: profile && Object.keys(profile).length ? Object.keys(profile).length : 0, label: '能量记录' }
      ],
      orders: localOrders
    });
    this.refreshOrderView();
    this.refreshUserAssetCounts();
  },

  async refreshUserAssetCounts() {
    const user = auth.getStoredUser();
    if (!user || !user.user_id) return;
    try {
      const [cartRows, favoriteRows] = await Promise.all([
        getCartItems(user.user_id, { silent: true, timeout: 8000 }),
        getCommunityFavorites(user.user_id, { silent: true, timeout: 8000 })
      ]);
      const shoppingCart = cartRows
        .filter(row => (row.item_type || 'diy_design') === 'diy_design')
        .map(row => ({
          ...(row.item || {}),
          id: row.cart_item_id,
          key: row.cart_item_id,
          cart_item_id: row.cart_item_id,
          quantity: row.quantity,
          qty: row.quantity
        }));
      wx.setStorageSync('diyDesignCart', shoppingCart);
      wx.setStorageSync('communityFavorites', favoriteRows);
      this.setData({
        shoppingCartCount: shoppingCart.length,
        communityFavoriteCount: favoriteRows.length,
        profileStats: this.data.profileStats.map(item => (
          item.key === 'cart' ? { ...item, value: shoppingCart.length } : item
        ))
      });
    } catch (error) {
      console.warn('refresh user assets fallback:', error.message || error);
    }
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
    const status = order.rawStatus || order.status;
    if (status === 'pending_ship') return 'ship';
    if (status === 'shipped') return 'receive';
    if (status === 'after_sale' || status === 'refund_requested') return 'after';
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
      statusKey: this.statusKey(order),
      status: order.status || this.statusText(order)
    }));
    const counts = { all: orders.length, pay: 0, ship: 0, receive: 0, done: 0, after: 0 };
    orders.forEach(order => {
      if (counts[order.statusKey] !== undefined) counts[order.statusKey] += 1;
    });
    const active = this.data.activeOrderStatus;
    const filteredOrders = active === 'all' ? orders : orders.filter(order => order.statusKey === active);
    this.setData({
      filteredOrders,
      orderStats: ORDER_TABS.map(item => ({ ...item, count: counts[item.key] || 0 })),
      profileStats: (this.data.profileStats || []).map(item => (
        item.key === 'orders' ? { ...item, value: orders.length } : item
      ))
    });
  },

  avatarChar(user, profile) {
    if (!user || !user.user_id) return '';
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
        },
        profileAvatarChanged: false
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

  confirmLogout() {
    wx.showModal({
      title: '退出登录',
      content: '退出后，当前设备上的账号信息和订单缓存将被清除。',
      confirmText: '退出',
      confirmColor: '#C65B55',
      success: result => {
        if (!result.confirm) return;
        auth.logout();
        this.setData({
          user: null,
          isLoggedIn: false,
          hasProfile: false,
          hasPhone: false,
          showProfileModal: false,
          profileDraft: { nickname: '', avatar_url: '' },
          profileAvatarChanged: false,
          avatarChar: '',
          orders: [],
          filteredOrders: [],
          activeOrderStatus: 'all',
          orderStats: ORDER_TABS.map(item => ({ ...item, count: 0 }))
        });
        wx.showToast({ title: '已退出登录', icon: 'success' });
      }
    });
  },

  noop() {},

  focusNicknameInput() {
    this.setData({ nicknameFocus: true });
  },

  onNicknameBlur() {
    this.setData({ nicknameFocus: false });
  },

  onChooseAvatar(e) {
    this.setData({
      'profileDraft.avatar_url': e.detail.avatarUrl,
      profileAvatarChanged: true
    });
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
        avatar_url: draft.avatar_url,
        avatar_changed: this.data.profileAvatarChanged
      });
      this.setData({
        user,
        hasProfile: !!user.has_profile,
        hasPhone: !!user.has_phone,
        avatarChar: this.avatarChar(user, this.data.profile),
        profileDraft: {
          nickname: user.nickname || draft.nickname,
          avatar_url: user.avatar_url || draft.avatar_url
        },
        profileAvatarChanged: false
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
    wx.showLoading({ title: '微信快捷绑定' });
    try {
      const user = await auth.bindWechatPhone(e);
      this.setData({ user, hasPhone: !!user.has_phone });
      wx.showToast({ title: '微信手机号已绑定', icon: 'success' });
    } catch (error) {
      console.error('bind phone failed:', error);
      wx.showModal({
        title: '手机号授权失败',
        content: error.message || '微信未能完成手机号授权，请确认小程序已开通手机号快速验证能力后重试。',
        showCancel: false,
        confirmText: '知道了'
      });
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
          source: logistics.source === 'kuaidi100' ? '物流轨迹已更新' : '商家发货记录',
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
        wx.showLoading({ title: '确认支付结果' });
        const paid = await this.waitForPaidStatus(orderId, userId);
        wx.hideLoading();
        wx.showToast({
          title: paid ? '支付成功' : '支付结果确认中',
          icon: paid ? 'success' : 'none'
        });
        await this.refreshOrdersFromServer();
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

  async waitForPaidStatus(orderId, userId) {
    for (let attempt = 0; attempt < 6; attempt += 1) {
      if (attempt > 0) {
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
      try {
        const order = await getOrder(orderId, userId);
        if (order.payment_status === 'paid') return true;
      } catch (error) {
        console.warn('payment status refresh failed:', error.message || error);
      }
    }
    return false;
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

  openPrivacyContract() {
    if (!wx.openPrivacyContract) {
      wx.showToast({ title: '请升级微信后查看隐私指引', icon: 'none' });
      return;
    }
    wx.openPrivacyContract({
      fail(error) {
        wx.showToast({ title: error.errMsg || '隐私指引暂不可用', icon: 'none' });
      }
    });
  },

  handleInspiration(e) {
    const type = e.currentTarget.dataset.type;
    if (type === 'draft') return this.viewMyPlans();
    if (type === 'cart') return this.viewShoppingCart();
    this.viewCommunityFavorites();
  },

  viewMyPlans() {
    wx.navigateTo({ url: '/pages/my-plans/my-plans' });
  },

  viewShoppingCart() {
    wx.navigateTo({ url: '/pages/inspiration-cart/inspiration-cart' });
  },

  viewCommunityFavorites() {
    wx.navigateTo({ url: '/pages/community-favorites/community-favorites' });
  },

  viewAddress() {
    wx.showToast({ title: '收货地址会在下单时填写', icon: 'none' });
  },

  viewCoupons() {
    wx.showToast({ title: '优惠券功能准备中', icon: 'none' });
  },

  contactCustomer() {
    wx.showToast({ title: '可通过订单详情联系商家', icon: 'none' });
  },

  openSettings() {
    this.openPrivacyContract();
  },

  goToPage(e) {
    const url = e.currentTarget.dataset.url;
    if (!url) return;
    if (url === '/pages/assessment/assessment') {
      wx.setStorageSync('customMode', {
        id: 'wuxing',
        title: '五行定制',
        selectedAt: Date.now()
      });
    }
    if (TAB_BAR_PAGES.includes(url)) {
      wx.switchTab({ url });
      return;
    }
    wx.navigateTo({ url });
  },

  goAssessment() {
    if (!this.data.isLoggedIn) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    wx.switchTab({ url: '/pages/assessment/assessment' });
  },

  goWorkspace() {
    wx.switchTab({ url: '/pages/workspace/workspace' });
  },

  goCommunity() {
    wx.navigateTo({ url: '/pages/community/community' });
  }
});
