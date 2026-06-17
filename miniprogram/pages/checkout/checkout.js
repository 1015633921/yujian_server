const auth = require('../../utils/auth');
const env = require('../../config/env');
const { createOrder, mockPayOrder } = require('../../utils/api');

const MATERIALS = {
  clearQuartz8: { name: '喜马拉雅白水晶 8mm', sku: 'SKU_CLEAR_8MM', price: 5 },
  clearQuartz10: { name: '喜马拉雅白水晶 10mm', sku: 'SKU_CLEAR_10MM', price: 10 },
  clearQuartz12: { name: '喜马拉雅白水晶 12mm', sku: 'SKU_CLEAR_12MM', price: 15 },
  clearQuartz14: { name: '喜马拉雅白水晶 14mm', sku: 'SKU_CLEAR_14MM', price: 18 },
  amethyst8: { name: '乌拉圭紫水晶 8mm', sku: 'SKU_AMETHYST_8MM', price: 12 },
  amethyst10: { name: '乌拉圭紫水晶 10mm', sku: 'SKU_AMETHYST_10MM', price: 18 },
  citrine8: { name: '巴西黄水晶 8mm', sku: 'SKU_CITRINE_8MM', price: 16 },
  citrine10: { name: '巴西黄水晶 10mm', sku: 'SKU_CITRINE_10MM', price: 22 },
  obsidian10: { name: '冰种黑曜石 10mm', sku: 'SKU_OBSIDIAN_10MM', price: 14 },
  tigerEye8: { name: '南非虎眼石 8mm', sku: 'SKU_TIGER_8MM', price: 13 },
  moonstone6: { name: '雪花幽灵 6mm', sku: 'SKU_MOON_6MM', price: 4 },
  moonstone8: { name: '雪花幽灵 8mm', sku: 'SKU_MOON_8MM', price: 8 },
  aquamarine8: { name: '巴西海蓝宝 8mm', sku: 'SKU_AQUA_8MM', price: 25 },
  roseQuartz8: { name: '马达加斯加粉晶 8mm', sku: 'SKU_ROSE_8MM', price: 11 },
  silverSpacer: { name: '纯银隔片', sku: 'SKU_SILVER_SPACER', price: 18 },
  goldSpacer: { name: '镀金隔片', sku: 'SKU_GOLD_SPACER', price: 16 },
  foxPendant: { name: '粉晶狐狸吊坠', sku: 'SKU_FOX_PENDANT', price: 88 }
};

const ADDRESS_KEY = 'checkoutReceiver';

Page({
  data: {
    design: null,
    sequence: [],
    bom: [],
    receiver: {
      name: '',
      phone: '',
      region: [],
      regionText: '',
      detailAddress: '',
      address: ''
    },
    fullAddress: '',
    hasAddress: false,
    addressError: '',
    submitting: false
  },

  onLoad() {
    this.loadDesign();
    this.loadReceiver();
  },

  loadReceiver() {
    const user = auth.getStoredUser();
    const cached = wx.getStorageSync(ADDRESS_KEY) || {};
    const receiver = {
      name: cached.name || '',
      phone: cached.phone || (user && user.phone_number) || '',
      region: cached.region || [],
      regionText: cached.regionText || '',
      detailAddress: cached.detailAddress || '',
      address: cached.address || ''
    };
    this.setReceiver(receiver);
  },

  loadDesign() {
    const design = wx.getStorageSync('currentDesign');
    if (!design || !design.selected || !design.selected.length) return;
    const sequence = design.selected.map((id, index) => ({
      index: index + 1,
      id,
      name: MATERIALS[id] ? MATERIALS[id].name : id,
      sku: MATERIALS[id] ? MATERIALS[id].sku : id,
      price: MATERIALS[id] ? MATERIALS[id].price : 0
    }));
    const bomMap = {};
    sequence.forEach(item => {
      if (!bomMap[item.sku]) {
        bomMap[item.sku] = { sku: item.sku, name: item.name, qty: 0 };
      }
      bomMap[item.sku].qty += 1;
    });
    this.setData({ design, sequence, bom: Object.values(bomMap) });
  },

  setReceiver(receiver) {
    const regionText = receiver.regionText || (receiver.region || []).join(' ');
    const fullAddress = [regionText, receiver.detailAddress].filter(Boolean).join(' ');
    this.setData({
      receiver: { ...receiver, regionText, address: fullAddress },
      fullAddress,
      hasAddress: !!(receiver.name && receiver.phone && fullAddress)
    });
  },

  onInput(e) {
    const field = e.currentTarget.dataset.field;
    const receiver = { ...this.data.receiver, [field]: e.detail.value };
    this.setReceiver(receiver);
    if (this.data.addressError) this.setData({ addressError: '' });
  },

  onRegionChange(e) {
    const region = e.detail.value || [];
    this.setReceiver({
      ...this.data.receiver,
      region,
      regionText: region.join(' ')
    });
    if (this.data.addressError) this.setData({ addressError: '' });
  },

  chooseWechatAddress() {
    wx.chooseAddress({
      success: res => {
        const region = [res.provinceName, res.cityName, res.countyName].filter(Boolean);
        this.setReceiver({
          name: res.userName || '',
          phone: res.telNumber || '',
          region,
          regionText: region.join(' '),
          detailAddress: res.detailInfo || '',
          address: ''
        });
        wx.showToast({ title: '地址已导入', icon: 'success' });
      },
      fail: err => {
        console.warn('chooseAddress failed:', err);
        wx.showToast({ title: '可手动填写地址', icon: 'none' });
      }
    });
  },

  focusAddressForm() {
    wx.pageScrollTo({ selector: '#addressForm', duration: 250 });
  },

  validateReceiver() {
    const receiver = this.data.receiver;
    if (!receiver.name || receiver.name.trim().length < 2) return '请填写至少 2 个字的收货人姓名';
    if (!/^1\d{10}$/.test(receiver.phone || '')) return '请填写正确的 11 位手机号';
    if (!receiver.region || receiver.region.length < 3) return '请选择省 / 市 / 区';
    if (!receiver.detailAddress || receiver.detailAddress.trim().length < 5) return '请填写详细地址，至少 5 个字';
    return '';
  },

  async submitOrder() {
    if (this.data.submitting) return;
    let user;
    try {
      user = await auth.requireLogin('登录后才能提交订单和查看履约进度。');
    } catch (error) {
      return;
    }
    if (!this.data.design) {
      wx.showToast({ title: '暂无可提交设计', icon: 'none' });
      return;
    }
    const error = this.validateReceiver();
    if (error) {
      this.setData({ addressError: error });
      wx.showToast({ title: error, icon: 'none' });
      this.focusAddressForm();
      return;
    }

    const receiver = {
      name: this.data.receiver.name.trim(),
      phone: this.data.receiver.phone,
      region: this.data.receiver.region,
      detailAddress: this.data.receiver.detailAddress.trim(),
      address: this.data.fullAddress
    };
    wx.setStorageSync(ADDRESS_KEY, receiver);

    this.setData({ submitting: true });
    wx.showLoading({ title: '生成订单' });
    try {
      const result = await createOrder({
        user_id: user.user_id,
        receiver,
        design: this.data.design,
        sequence: this.data.sequence,
        bom: this.data.bom
      });
      this.cacheOrder(result.order);
      wx.hideLoading();

      const payment = result.payment || {};
      if (payment.available && payment.pay_params) {
        await this.requestWechatPayment(payment.pay_params);
        wx.showToast({ title: '支付完成', icon: 'success' });
        wx.navigateTo({ url: '/pages/order-list/order-list?status=all' });
        return;
      }

      wx.showModal({
        title: '订单已生成',
        content: `${payment.message || '订单已保存为待付款。'}${env.isLocalApi ? '\n\n本地调试可先模拟支付成功，继续测试后续流程。' : ''}`,
        confirmText: env.isLocalApi ? '模拟支付' : '查看订单',
        cancelText: '稍后',
        showCancel: true,
        success: async (res) => {
          if (res.confirm && env.isLocalApi) {
            await this.mockPay(result.order.order_id, user.user_id);
            return;
          }
          wx.navigateTo({ url: '/pages/order-list/order-list?status=all' });
        }
      });
    } catch (error) {
      wx.hideLoading();
      console.error('submit order failed:', error);
      wx.showToast({ title: error.message || '下单失败', icon: 'none' });
    } finally {
      this.setData({ submitting: false });
    }
  },

  async mockPay(orderId, userId) {
    wx.showLoading({ title: '模拟支付' });
    try {
      const order = await mockPayOrder(orderId, userId);
      this.cacheOrder(order);
      wx.hideLoading();
      wx.showToast({ title: '已进入待发货', icon: 'success' });
      wx.navigateTo({ url: '/pages/order-list/order-list?status=ship' });
    } catch (error) {
      wx.hideLoading();
      wx.showToast({ title: error.message || '模拟支付失败', icon: 'none' });
    }
  },

  requestWechatPayment(payParams) {
    return new Promise((resolve, reject) => {
      wx.requestPayment({ ...payParams, success: resolve, fail: reject });
    });
  },

  cacheOrder(order) {
    const orders = wx.getStorageSync('orders') || [];
    const localOrder = {
      id: order.order_id,
      userId: order.user_id,
      createdAt: order.created_at,
      receiver: order.receiver,
      design: order.design,
      sequence: order.sequence,
      bom: order.bom,
      rawStatus: order.status,
      paymentStatus: order.payment_status,
      statusKey: this.statusKey(order),
      status: order.status_text || this.statusText(order),
      totalAmount: order.total_amount,
      logistics: order.logistics || {},
      statusHistory: order.status_history || []
    };
    wx.setStorageSync('orders', [localOrder, ...orders.filter(item => item.id !== localOrder.id)]);
  },

  statusKey(order) {
    if (order.status === 'pending_ship') return 'ship';
    if (order.status === 'shipped') return 'receive';
    if (order.status === 'after_sale' || order.status === 'refund_requested' || order.status === 'refunded') return 'after';
    if (order.payment_status === 'unpaid' || order.status === 'pending_payment') return 'pay';
    return 'done';
  },

  statusText(order) {
    return {
      pending_payment: '待付款',
      pending_ship: '待发货',
      shipped: '待收货',
      completed: '已完成',
      after_sale: '售后中',
      refund_requested: '退款中',
      refunded: '已退款'
    }[order.status] || (order.payment_status === 'paid' ? '已支付' : '待付款');
  },

  goBack() {
    wx.navigateBack();
  }
});
