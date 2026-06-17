const auth = require('../../utils/auth');
const { getOrders } = require('../../utils/api');

const STATUS_TITLE = {
  all: '全部订单',
  pay: '待付款',
  ship: '待发货',
  receive: '待收货',
  after: '售后退款',
  done: '已完成'
};

Page({
  data: {
    status: 'all',
    title: '全部订单',
    orders: [],
    filteredOrders: [],
    loading: false
  },

  onLoad(options) {
    const status = options.status || 'all';
    this.setData({ status, title: STATUS_TITLE[status] || '全部订单' });
    wx.setNavigationBarTitle({ title: STATUS_TITLE[status] || '全部订单' });
  },

  onShow() {
    this.loadOrders();
  },

  async loadOrders() {
    const user = auth.getStoredUser();
    if (!user || !user.user_id) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    this.setData({ loading: true });
    try {
      const rows = await getOrders(user.user_id);
      const orders = rows.map(item => this.normalizeOrder(item));
      wx.setStorageSync('orders', orders);
      this.setData({ orders });
      this.applyFilter();
    } catch (error) {
      const orders = wx.getStorageSync('orders') || [];
      this.setData({ orders });
      this.applyFilter();
      wx.showToast({ title: error.message || '订单加载失败', icon: 'none' });
    } finally {
      this.setData({ loading: false });
    }
  },

  normalizeOrder(item) {
    return {
      id: item.order_id,
      createdAt: item.created_at,
      status: item.status_text || this.statusText(item.status),
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
    if (order.status === 'pending_ship') return 'ship';
    if (order.status === 'shipped') return 'receive';
    if (order.status === 'after_sale' || order.status === 'refund_requested' || order.status === 'refunded') return 'after';
    if (order.payment_status === 'unpaid' || order.status === 'pending_payment') return 'pay';
    return 'done';
  },

  statusText(status) {
    return {
      pending_payment: '待付款',
      pending_ship: '待发货',
      shipped: '待收货',
      completed: '已完成',
      after_sale: '售后中',
      refund_requested: '退款中',
      refunded: '已退款'
    }[status] || '处理中';
  },

  applyFilter() {
    const status = this.data.status;
    const filteredOrders = status === 'all'
      ? this.data.orders
      : this.data.orders.filter(order => order.statusKey === status);
    this.setData({ filteredOrders });
  },

  goDetail(e) {
    wx.navigateTo({ url: `/pages/order-detail/order-detail?id=${e.currentTarget.dataset.id}` });
  },

  goWorkspace() {
    wx.switchTab({ url: '/pages/workspace/workspace' });
  }
});
