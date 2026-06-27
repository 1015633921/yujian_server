Page({
  data: {
    orderId: '',
    order: null,
    display: {
      orderId: '',
      createdAt: '',
      deliveryText: '预计 3-7 个工作日内完成制作并发出',
      amount: '0.00',
      receiverName: ''
    }
  },

  onLoad(options = {}) {
    const orderId = decodeURIComponent(options.id || options.order_id || '');
    this.setData({ orderId });
    this.loadOrder(orderId);
  },

  loadOrder(orderId) {
    const orders = wx.getStorageSync('orders') || [];
    const order = orders.find(item => item.id === orderId) || null;
    if (!order) {
      this.setData({
        display: {
          orderId: orderId || '待同步',
          createdAt: '',
          deliveryText: '订单已提交，详情同步后可在订单列表查看',
          amount: '0.00',
          receiverName: ''
        }
      });
      return;
    }
    this.setData({
      order,
      display: {
        orderId: order.id,
        createdAt: order.createdAt || '',
        deliveryText: this.deliveryText(order),
        amount: this.formatAmount(order.totalAmount),
        receiverName: order.receiver && order.receiver.name ? order.receiver.name : ''
      }
    });
  },

  deliveryText(order) {
    if (order.statusKey === 'pay') return '订单已创建，支付后将进入定制制作流程';
    if (order.statusKey === 'ship') return '预计 3-7 个工作日内完成制作并发出';
    if (order.statusKey === 'receive') return '订单已发货，可在详情页查看物流进度';
    return '可在订单详情页查看后续进度';
  },

  formatAmount(value) {
    const amount = Number(value || 0);
    return Number.isFinite(amount) ? amount.toFixed(2) : '0.00';
  },

  viewDetail() {
    const orderId = this.data.display.orderId;
    if (!orderId || orderId === '待同步') {
      wx.navigateTo({ url: '/pages/order-list/order-list?status=all' });
      return;
    }
    wx.navigateTo({ url: `/pages/order-detail/order-detail?id=${encodeURIComponent(orderId)}` });
  },

  continueShopping() {
    wx.switchTab({ url: '/pages/home/home' });
  },

  goOrders() {
    wx.navigateTo({ url: '/pages/order-list/order-list?status=all' });
  }
});
