const auth = require('../../utils/auth');
const env = require('../../config/env');
const { createOrder, mockPayOrder, getMaterials } = require('../../utils/api');

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

function firstImageUrl(entry = {}) {
  const urls = (entry.image_urls || entry.image_pool || [])
    .concat(entry.image_url || [])
    .filter(Boolean);
  return urls[0] || '';
}

function moneyValue(...values) {
  for (const value of values) {
    if (value === undefined || value === null || value === '') continue;
    const amount = Number(value);
    if (Number.isFinite(amount)) return amount;
  }
  return 0;
}

function normalizeSequenceItem(entry = {}, index = 0) {
  const key = entry.id || entry.sku || entry.material_id || '';
  const fallback = MATERIALS[key] || {};
  const imageUrls = (entry.image_urls || entry.image_pool || [])
    .concat(entry.image_url || [])
    .filter(Boolean);
  const size = entry.size || entry.diameter || '';
  const name = entry.name || entry.series || entry.category || fallback.name || key || '定制珠材';
  const category = entry.category || entry.series || '';
  return {
    ...entry,
    index: Number(entry.index || index + 1),
    id: entry.id || key,
    sku: entry.sku || fallback.sku || key,
    name,
    category,
    series: entry.series || '',
    size,
    sizeText: size ? `${size}mm` : '',
    subText: [size ? `${size}mm` : '', category].filter(Boolean).join(' · '),
    price: moneyValue(entry.price, entry.priceText, entry.amount, fallback.price),
    weight: Number(entry.weight || 0),
    image_url: entry.image_url || imageUrls[0] || '',
    image_urls: imageUrls
  };
}

Page({
  data: {
    design: null,
    sequence: [],
    bom: [],
    designPreviewImage: '',
    previewBeads: [],
    amountText: '0.00',
    couponDiscountText: '-¥0.00',
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
    remark: '',
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
    const hasSelected = Array.isArray(design && design.selected) && design.selected.length;
    const hasSequence = Array.isArray(design && design.sequence) && design.sequence.length;
    if (!design || (!hasSelected && !hasSequence)) return;
    const rawSequence = hasSequence ? design.sequence : design.selected.map((id, index) => ({
      index: index + 1,
      id,
      name: MATERIALS[id] ? MATERIALS[id].name : id,
      sku: MATERIALS[id] ? MATERIALS[id].sku : id,
      price: MATERIALS[id] ? MATERIALS[id].price : 0
    }));
    const sequence = rawSequence.map(normalizeSequenceItem);
    this.applyDesignState(design, sequence);
    this.refreshDesignPrices();
  },

  buildBom(sequence = []) {
    const bomMap = {};
    sequence.forEach(item => {
      const key = item.sku || item.id || `${item.name}-${item.size}`;
      if (!bomMap[key]) {
        bomMap[key] = {
          sku: key,
          name: item.name,
          qty: 0,
          size: item.size || '',
          sizeText: item.sizeText || '',
          subText: item.subText || item.category || '',
          category: item.category || '',
          price: Number(item.price || 0),
          image_url: item.image_url || ''
        };
      }
      bomMap[key].qty += 1;
      bomMap[key].total = Number((bomMap[key].qty * bomMap[key].price).toFixed(2));
      bomMap[key].priceText = this.formatAmount(bomMap[key].price);
      bomMap[key].totalText = this.formatAmount(bomMap[key].total);
    });
    return Object.values(bomMap);
  },

  applyDesignState(design, sequence) {
    const bom = this.buildBom(sequence);
    const fallbackAmount = sequence.reduce((sum, item) => sum + Number(item.price || 0), 0);
    const summaryAmount = Number(design.summary && (design.summary.priceText || design.summary.price));
    const amount = Number.isFinite(summaryAmount) && summaryAmount > 0 ? summaryAmount : fallbackAmount;
    const summary = {
      ...(design.summary || {}),
      count: sequence.length,
      price: amount,
      priceText: this.formatAmount(amount)
    };
    const designForView = { ...design, summary };
    this.setData({
      design: designForView,
      designPreviewImage: this.resolveDesignPreviewImage(designForView),
      sequence,
      bom,
      previewBeads: this.buildPreviewBeads(sequence, design.placements || []),
      amountText: this.formatAmount(amount)
    });
  },

  resolveDesignPreviewImage(design = {}) {
    return design.preview_image
      || design.previewImage
      || design.design_preview_url
      || design.preview_url
      || design.previewUrl
      || design.image_url
      || design.local_preview_image
      || design.localPreviewImage
      || '';
  },

  onPreviewImageError() {
    this.setData({ designPreviewImage: '' });
  },

  async refreshDesignPrices() {
    const design = this.data.design;
    const sequence = this.data.sequence || [];
    if (!design || !sequence.length) return;
    try {
      const payload = await getMaterials();
      const materials = payload.materials || [];
      if (!materials.length) return;
      const byId = {};
      const bySku = {};
      materials.forEach(material => {
        if (material.id) byId[String(material.id)] = material;
        if (material.skuId) bySku[String(material.skuId)] = material;
        if (material.sku) bySku[String(material.sku)] = material;
      });

      const changed = [];
      const refreshed = sequence.map((item, index) => {
        const material = byId[String(item.id || item.material_id || '')]
          || bySku[String(item.sku || item.skuId || '')];
        if (!material) return item;
        const currentPrice = moneyValue(material.price, material.priceText, material.amount);
        const oldPrice = moneyValue(item.price, item.priceText);
        const hasReliableSnapshot = Boolean(item.snapshot_at);
        if (hasReliableSnapshot && oldPrice !== currentPrice) {
          changed.push(`${material.name || item.name || '珠材'} ¥${this.formatAmount(oldPrice)}→¥${this.formatAmount(currentPrice)}`);
        }
        return normalizeSequenceItem({
          ...item,
          id: material.id || item.id,
          material_id: material.id || item.material_id,
          sku: material.skuId || material.sku || item.sku,
          skuId: material.skuId || item.skuId || item.sku,
          name: material.name || item.name,
          category: material.category || item.category,
          series: material.series || item.series,
          grade: material.grade || item.grade,
          effect: material.effect || item.effect,
          element: material.element || item.element,
          size: material.size || item.size,
          diameter: material.size || item.diameter,
          price: currentPrice,
          weight: material.weight || item.weight,
          image_url: item.image_url || material.image_url || firstImageUrl(material),
          image_urls: material.image_urls || material.image_pool || item.image_urls || [],
          snapshot_at: item.snapshot_at || new Date().toISOString()
        }, index);
      });

      const refreshedAmount = refreshed.reduce((sum, item) => sum + Number(item.price || 0), 0);
      const nextDesign = {
        ...design,
        summary: {
          ...(design.summary || {}),
          count: refreshed.length,
          price: refreshedAmount,
          priceText: this.formatAmount(refreshedAmount)
        },
        sequence: refreshed,
        selected: refreshed.map(item => item.id || item.sku).filter(Boolean)
      };
      this.applyDesignState(nextDesign, refreshed);
      wx.setStorageSync('currentDesign', {
        ...nextDesign,
        summary: this.data.design.summary
      });
      if (changed.length) {
        wx.showModal({
          title: '珠材价格已同步',
          content: `当前方案已按最新珠材价格刷新：${changed.slice(0, 3).join('；')}${changed.length > 3 ? '…' : ''}`,
          showCancel: false,
          confirmText: '知道了'
        });
      }
    } catch (error) {
      console.warn('refresh checkout material prices failed:', error);
    }
  },

  buildPreviewBeads(sequence, placements = []) {
    const beads = (sequence || []).slice(0, 18);
    const count = Math.max(beads.length, 1);
    return beads.map((item, index) => {
      const placement = placements[index] || item.placement || {};
      const angle = (360 / count) * index;
      const size = 26;
      return {
        ...item,
        image_url: placement.image_url || item.image_url || firstImageUrl(item),
        style: `width:${size}rpx;height:${size}rpx;transform:rotate(${angle}deg) translateY(-58rpx) rotate(${-angle}deg);`
      };
    });
  },

  formatAmount(value) {
    const amount = Number(value || 0);
    return Number.isFinite(amount) ? amount.toFixed(2) : '0.00';
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

  onRemarkInput(e) {
    this.setData({ remark: e.detail.value || '' });
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
        design_id: this.data.design.designId || this.data.design.design_id || '',
        receiver,
        remark: (this.data.remark || '').trim(),
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
        this.goSuccess(result.order.order_id);
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
          this.goOrderDetail(result.order.order_id);
        }
      });
    } catch (error) {
      wx.hideLoading();
      console.error('submit order failed:', error);
      this.handleSubmitError(error);
    } finally {
      this.setData({ submitting: false });
    }
  },

  handleSubmitError(error) {
    const message = error && error.message ? error.message : '下单失败';
    if (message.includes('珠材价格已更新') || message.includes('已下架或无库存')) {
      wx.showModal({
        title: '珠材信息已更新',
        content: message,
        confirmText: '返回工作台',
        cancelText: '稍后',
        success: (res) => {
          if (res.confirm) {
            wx.navigateBack({
              fail: () => wx.redirectTo({ url: '/pages/workspace/workspace' })
            });
          }
        }
      });
      return;
    }
    wx.showToast({ title: message, icon: 'none' });
  },

  async mockPay(orderId, userId) {
    wx.showLoading({ title: '模拟支付' });
    try {
      const order = await mockPayOrder(orderId, userId);
      this.cacheOrder(order);
      wx.hideLoading();
      wx.showToast({ title: '已进入待发货', icon: 'success' });
      this.goSuccess(order.order_id || orderId);
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
      remark: order.remark || '',
      logistics: order.logistics || {},
      statusHistory: order.status_history || []
    };
    wx.setStorageSync('orders', [localOrder, ...orders.filter(item => item.id !== localOrder.id)]);
  },

  goSuccess(orderId) {
    wx.navigateTo({ url: `/pages/order-success/order-success?id=${encodeURIComponent(orderId || '')}` });
  },

  goOrderDetail(orderId) {
    wx.redirectTo({ url: `/pages/order-detail/order-detail?id=${encodeURIComponent(orderId || '')}` });
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
