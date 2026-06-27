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
const ORDER_RING_LIMIT = 18;

Page({
  data: {
    status: 'all',
    title: '全部订单',
    orders: [],
    filteredOrders: [],
    showListCount: true,
    loading: false
  },

  onLoad(options) {
    const status = options.status || 'all';
    this.setData({
      status,
      title: STATUS_TITLE[status] || '全部订单',
      showListCount: status !== 'done'
    });
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
      const cachedOrders = wx.getStorageSync('orders') || [];
      const orders = cachedOrders.map(item => this.normalizeOrder(item));
      this.setData({ orders });
      this.applyFilter();
      wx.showToast({ title: error.message || '订单加载失败', icon: 'none' });
    } finally {
      this.setData({ loading: false });
    }
  },

  normalizeOrder(item) {
    const sequence = Array.isArray(item.sequence) ? item.sequence : [];
    const bom = Array.isArray(item.bom) ? item.bom : [];
    const rawStatus = item.rawStatus || item.raw_status || item.status;
    const paymentStatus = item.payment_status || item.paymentStatus;
    const createdAt = item.created_at || item.createdAt || '';
    const design = item.design || {};
    const previewImage = design.preview_image || design.previewImage || design.image_url || item.preview_image || item.previewImage || '';
    const statusText = item.status_text
      || item.statusText
      || (/[\u4e00-\u9fff]/.test(String(item.status || '')) ? item.status : this.statusText(rawStatus));
    return {
      id: item.order_id || item.id,
      createdAt,
      createdAtText: this.formatDateTime(createdAt),
      status: statusText,
      statusKey: this.statusKey({ ...item, rawStatus, paymentStatus }),
      totalAmount: item.total_amount !== undefined ? item.total_amount : item.totalAmount,
      receiver: item.receiver || {},
      design,
      sequence,
      bom,
      materialCount: sequence.length || bom.reduce((sum, row) => sum + Number(row.qty || row.quantity || 1), 0),
      previewImage,
      previewBeads: this.buildPreviewBeads(
        sequence.length ? sequence : bom,
        (design && design.placements) || item.placements || []
      ),
      rawStatus,
      paymentStatus,
      logistics: item.logistics || {},
      statusHistory: item.status_history || [],
      remark: item.remark || '',
      afterSaleStatus: item.after_sale_status || '',
      refundStatus: item.refund_status || ''
    };
  },

  firstImageUrl(item = {}) {
    const urls = (item.image_urls || item.image_pool || [])
      .concat(item.image_url || item.image || item.cover || []);
    return urls.find(url => typeof url === 'string' && url.trim()) || '';
  },

  buildPreviewBeads(sequence = [], placements = []) {
    const beads = sequence.slice(0, ORDER_RING_LIMIT);
    const count = Math.max(beads.length, 1);
    return beads.map((item, index) => {
      const placement = placements[index] || item.placement || {};
      const imageUrl = this.firstImageUrl(item);
      const src = placement.image_url || imageUrl;
      const angle = (360 / count) * index;
      const size = 24;
      const radius = 46;
      const color = item.color || '#d8ddd4';
      const shine = item.shine || '#ffffff';
      return {
        key: `${item.id || item.sku || item.skuId || item.name || 'bead'}-${index}`,
        image_url: src,
        style: src
          ? `width:${size}rpx;height:${size}rpx;transform:rotate(${angle}deg) translateY(-${radius}rpx) rotate(${-angle}deg);`
          : `width:${size}rpx;height:${size}rpx;transform:rotate(${angle}deg) translateY(-${radius}rpx) rotate(${-angle}deg);background: radial-gradient(circle at 32% 24%, ${shine} 0 12%, ${color} 18% 62%, rgba(0,0,0,.18) 100%);`
      };
    });
  },

  statusKey(order) {
    const status = order.rawStatus || order.status;
    if (status === 'pending_ship') return 'ship';
    if (status === 'shipped') return 'receive';
    if (status === 'after_sale' || status === 'refund_requested') return 'after';
    if (status === '待付款') return 'pay';
    if (status === '待发货') return 'ship';
    if (status === '待收货') return 'receive';
    if (status === '售后中' || status === '退款中') return 'after';
    if (status === '已完成' || status === '已退款' || status === '已关闭') return 'done';
    if (order.payment_status === 'unpaid' || order.paymentStatus === 'unpaid' || status === 'pending_payment') return 'pay';
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
      refunded: '已退款',
      closed: '已关闭'
    }[status] || '处理中';
  },

  formatDateTime(value) {
    if (!value) return '';
    const text = String(value).trim();
    const hasTimezone = /T|Z|\+\d\d:\d\d$/.test(text);
    const date = hasTimezone ? new Date(text) : new Date(text.replace(/-/g, '/'));
    if (Number.isNaN(date.getTime())) return text.replace('T', ' ').replace(/\+\d\d:\d\d$/, '').slice(0, 19);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hour = String(date.getHours()).padStart(2, '0');
    const minute = String(date.getMinutes()).padStart(2, '0');
    const second = String(date.getSeconds()).padStart(2, '0');
    return `${year}年${month}月${day}日 ${hour}:${minute}:${second}`;
  },

  applyFilter() {
    const status = this.data.status;
    const orders = (this.data.orders || []).map(order => ({
      ...order,
      statusKey: this.statusKey(order)
    }));
    const filteredOrders = status === 'all'
      ? orders
      : orders.filter(order => order.statusKey === status);
    this.setData({ filteredOrders });
  },

  onPreviewImageError(e) {
    const id = e.currentTarget.dataset.id;
    const orders = (this.data.orders || []).map(order => (
      order.id === id ? { ...order, previewImage: '' } : order
    ));
    this.setData({ orders });
    this.applyFilter();
  },

  goDetail(e) {
    wx.navigateTo({ url: `/pages/order-detail/order-detail?id=${e.currentTarget.dataset.id}` });
  },

  copyOrderId(e) {
    const id = e.currentTarget.dataset.id;
    if (!id) return;
    wx.setClipboardData({
      data: String(id),
      success: () => wx.showToast({ title: '订单号已复制', icon: 'success' })
    });
  },

  goWorkspace() {
    wx.switchTab({ url: '/pages/workspace/workspace' });
  }
});
