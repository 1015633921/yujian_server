const auth = require('../../utils/auth');
const env = require('../../config/env');
const {
  getOrder,
  payOrder,
  mockPayOrder,
  mockShipOrder,
  confirmReceipt,
  cancelOrder,
  updateOrderReceiver,
  requestAfterSale,
  refundOrder,
  getOrderLogistics
} = require('../../utils/api');

const STATUS_META = {
  pay: {
    title: '待付款',
    hint: '订单待支付',
    tone: 'warm',
    eta: '请尽快完成支付，库存将为你短暂保留'
  },
  ship: {
    title: '待发货',
    hint: '订单已支付',
    tone: 'green',
    eta: '预计 3-7 个工作日内完成制作并发出'
  },
  receive: {
    title: '待收货',
    hint: '订单已发货',
    tone: 'green',
    eta: '请留意物流动态，收到后可确认收货'
  },
  done: {
    title: '已完成',
    hint: '订单已完成',
    tone: 'dark',
    eta: '感谢你的定制，愿这串手作陪你安稳向前'
  },
  after: {
    title: '售后中',
    hint: '',
    tone: 'warm',
    eta: '我们会尽快处理你的售后申请'
  },
  refunded: {
    title: '已退款',
    hint: '退款已完成',
    tone: 'dark',
    eta: '款项已按原支付路径退回，这笔订单已结束'
  },
  closed: {
    title: '已取消',
    hint: '订单已关闭',
    tone: 'dark',
    eta: '这笔订单已关闭，可重新定制后下单'
  }
};

Page({
  data: {
    id: '',
    order: null,
    isLocalApi: env.isLocalApi,
    logisticsDetail: null,
    loading: false,
    showAllMaterials: false,
    showLogisticsModal: false
  },

  onLoad(options = {}) {
    this.setData({ id: decodeURIComponent(options.id || options.order_id || '') });
  },

  onShow() {
    this.loadOrder();
  },

  async loadOrder(options = {}) {
    if (!this.data.id || this.data.loading) return null;
    this.setData({ loading: true });
    try {
      let user = auth.getStoredUser();
      if (!user || !user.user_id) {
        user = await auth.silentLogin();
      }
      const row = await getOrder(this.data.id, user.user_id);
      const order = this.normalizeOrder(row);
      this.updateOrderCache(order);
      this.setData({
        order,
        logisticsDetail: order.logisticsCard
      });
      return order;
    } catch (error) {
      const orders = wx.getStorageSync('orders') || [];
      const cachedOrder = orders.find(item => item.id === this.data.id) || null;
      const order = cachedOrder ? this.normalizeOrder(cachedOrder) : null;
      this.setData({
        order,
        logisticsDetail: order ? order.logisticsCard : null
      });
      if (!order && !options.silent) {
        wx.showToast({ title: error.message || '订单不存在', icon: 'none' });
      }
      return order;
    } finally {
      this.setData({ loading: false });
    }
  },

  normalizeOrder(item = {}) {
    const rawStatus = item.status || item.rawStatus || '';
    const paymentStatus = item.payment_status || item.paymentStatus || '';
    const statusKey = this.statusKey(rawStatus, paymentStatus, item.statusKey);
    const meta = STATUS_META[statusKey] || STATUS_META.done;
    const receiver = this.normalizeReceiver(item.receiver || {});
    const sequence = item.sequence || [];
    const bom = item.bom || [];
    const statusHistory = item.status_history || item.statusHistory || [];
    const logistics = item.logistics || {};
    const totalAmount = Number(item.total_amount ?? item.totalAmount ?? 0);
    const paidAt = item.paid_at || item.paidAt || this.findHistoryTime(statusHistory, 'pending_ship');
    const materials = this.normalizeMaterials(bom, sequence);
    const logisticsCard = this.normalizeLogistics(logistics, statusHistory, statusKey);
    const afterSaleStatus = item.after_sale_status || item.afterSaleStatus || '';
    const refundStatus = item.refund_status || item.refundStatus || '';
    const actionState = this.buildFooterActions({
      statusKey,
      logisticsCard,
      afterSaleStatus,
      refundStatus
    });
    const statusSteps = this.buildStatusSteps(statusKey, {
      createdAt: item.created_at || item.createdAt,
      updatedAt: item.updated_at || item.updatedAt,
      paidAt,
      statusHistory,
      logistics,
      logisticsCard
    });
    const displayMaterials = this.data.showAllMaterials ? materials : materials.slice(0, 3);
    const materialCount = sequence.length || materials.reduce((sum, row) => sum + Number(row.qty || 1), 0);

    return {
      id: item.order_id || item.id || this.data.id,
      outTradeNo: item.out_trade_no || item.outTradeNo || '',
      createdAt: item.created_at || item.createdAt || '',
      createdAtText: this.formatDateTime(item.created_at || item.createdAt || ''),
      updatedAt: item.updated_at || item.updatedAt || '',
      status: meta.title,
      statusTitle: meta.title,
      statusHint: meta.hint,
      statusDisplayText: meta.hint || meta.title,
      statusTone: meta.tone,
      etaText: logisticsCard.etaText || meta.eta,
      statusKey,
      rawStatus,
      paymentStatus,
      paidAt,
      totalAmount,
      totalAmountText: this.formatAmount(totalAmount),
      amountRows: this.buildAmountRows(totalAmount),
      receiver,
      design: item.design || {},
      sequence,
      bom,
      materials,
      displayMaterials,
      materialCount,
      materialKindCount: materials.length,
      hasMoreMaterials: materials.length > 3,
      canEditAddress: ['pay', 'ship'].includes(statusKey),
      logistics,
      logisticsCard,
      statusSteps,
      statusHistory,
      remark: item.remark || '',
      afterSaleStatus,
      refundStatus,
      ...actionState
    };
  },

  buildFooterActions({ statusKey, logisticsCard, afterSaleStatus, refundStatus }) {
    const activeAfterSaleValues = ['requested', 'processing', 'approved', 'after_sale', 'refund_requested', 'refunding'];
    const hasActiveAfterSale = statusKey === 'after'
      || activeAfterSaleValues.includes(afterSaleStatus)
      || activeAfterSaleValues.includes(refundStatus);
    const canCancel = statusKey === 'pay';
    const canRefund = ['ship', 'receive'].includes(statusKey) && !hasActiveAfterSale;
    const canAfterSale = ['receive', 'done'].includes(statusKey) && !hasActiveAfterSale;
    const canViewLogistics = Boolean(logisticsCard && logisticsCard.show);
    const canPay = statusKey === 'pay';
    const canMockShip = statusKey === 'ship' && this.data.isLocalApi;
    const canReceive = statusKey === 'receive' && !hasActiveAfterSale;
    const hasSecondaryAction = canCancel || canRefund || canAfterSale;
    const hasPrimaryAction = canPay || canMockShip || canReceive || canViewLogistics;
    const actionCount = ['closed', 'refunded'].includes(statusKey)
      ? 0
      : (hasSecondaryAction ? 1 : 0) + 1 + (hasPrimaryAction ? 1 : 0);

    return {
      hasActiveAfterSale,
      canCancel,
      canRefund,
      canAfterSale,
      canViewLogistics,
      canPay,
      canMockShip,
      canReceive,
      hasFooterAction: actionCount > 0,
      actionBarClass: `actions-${actionCount}`
    };
  },

  statusKey(rawStatus = '', paymentStatus = '', cachedKey = '') {
    if (['closed', 'cancelled', 'canceled'].includes(rawStatus)) return 'closed';
    if (rawStatus === 'refunded' || paymentStatus === 'refunded') return 'refunded';
    if (rawStatus === 'pending_ship') return 'ship';
    if (rawStatus === 'shipped') return 'receive';
    if (['after_sale', 'refund_requested'].includes(rawStatus)) return 'after';
    if (paymentStatus === 'unpaid' || rawStatus === 'pending_payment') return 'pay';
    if (cachedKey && ['pay', 'ship', 'receive', 'done', 'after', 'closed', 'refunded'].includes(cachedKey)) {
      return cachedKey;
    }
    return 'done';
  },

  normalizeReceiver(receiver = {}) {
    const region = receiver.region || [];
    const regionText = receiver.regionText || (Array.isArray(region) ? region.join(' ') : String(region || ''));
    const detail = receiver.detailAddress || receiver.detail_address || receiver.detail || '';
    const address = receiver.address || [regionText, detail].filter(Boolean).join(' ');
    return {
      name: receiver.name || receiver.receiver || '',
      phone: receiver.phone || receiver.mobile || '',
      address,
      regionText,
      detailAddress: detail
    };
  },

  normalizeMaterials(bom = [], sequence = []) {
    const useSequence = Array.isArray(sequence) && sequence.length;
    const source = useSequence ? sequence : bom;
    return source.map((item, index) => {
      const price = Number(item.price || 0);
      const qty = useSequence ? 1 : Number(item.qty || item.quantity || 1);
      const size = item.size || item.diameter || item.bead_size_mm || item.beadSizeMm || '';
      const sizeText = size ? `${this.formatSpecValue(size)}mm` : '';
      const name = item.name || item.material_name || item.materialId || item.id || '定制材料';
      const top = item.top || '';
      const type = item.type || item.shape || (top === 'accessory' ? '配件' : top === 'pendant' ? '吊坠' : '圆珠');
      const imageUrl = item.image_url || item.image || item.cover || '';
      const tags = [
        item.category ? { label: '品类', value: item.category } : null,
        item.series && item.series !== item.category ? { label: '系列', value: item.series } : null,
        item.grade ? { label: '等级', value: item.grade } : null,
        item.element ? { label: '五行', value: item.element } : null,
        item.weight ? { label: '单重', value: `${this.formatSpecValue(item.weight)}g` } : null
      ].filter(Boolean);
      const sku = item.sku || item.skuId || item.id || '';
      return {
        key: `${sku || name}-${size || 'na'}-${index}`,
        positionLabel: useSequence ? `第 ${Number(item.index || index + 1)} 颗` : `共 ${qty} 件`,
        name,
        effect: item.effect || item.subtitle || '',
        detail: [sizeText ? `珠径 ${sizeText}` : '', type].filter(Boolean).join(' · '),
        sizeText,
        type,
        sku,
        tags,
        priceText: this.formatAmount(price),
        qty,
        qtyText: useSequence ? '单颗' : `× ${qty}`,
        totalText: this.formatAmount(item.total ?? price * qty),
        imageUrl,
        colorStyle: `background:${item.color || '#b95858'};`
      };
    });
  },

  normalizeLogistics(logistics = {}, statusHistory = [], statusKey = '') {
    const traces = (logistics.traces || []).map((trace, index) => ({
      id: `${trace.time || ''}-${index}`,
      desc: trace.desc || trace.context || trace.status || '物流状态更新',
      location: trace.location || '',
      time: this.formatDateTime(trace.time || trace.ftime || ''),
      active: index === 0
    }));
    const trackingNo = logistics.tracking_no || logistics.trackingNo || '';
    const hasTracking = Boolean(trackingNo);
    const hasTraces = traces.length > 0;
    const latestTrace = traces[0] || {
      id: 'waiting-pickup',
      desc: hasTracking ? '商家已打包，等待快递揽收或物流更新。' : '商家尚未填写快递单号。',
      location: '',
      time: '',
      active: true
    };
    const statusText = logistics.status_text || logistics.statusText || (hasTraces ? '物流运输中' : (hasTracking ? '待揽收' : '暂无物流轨迹'));
    return {
      show: hasTraces,
      hasTracking,
      hasTraces,
      carrier: logistics.carrier || '物流信息',
      carrierCode: logistics.carrier_code || logistics.carrierCode || '',
      carrierShort: this.carrierShort(logistics.carrier || ''),
      trackingNo,
      statusText,
      source: logistics.source === 'kuaidi100' ? '物流轨迹已更新' : '商家发货记录',
      message: logistics.message || '',
      traces: hasTraces ? traces : [latestTrace],
      latestTrace,
      summaryTitle: statusText,
      summaryDesc: latestTrace.desc,
      etaText: logistics.eta_text || logistics.estimated_delivery || ''
    };
  },

  carrierShort(carrier = '') {
    if (carrier.includes('顺丰')) return 'SF';
    if (carrier.includes('京东')) return 'JD';
    if (carrier.includes('中通')) return 'ZT';
    if (carrier.includes('圆通')) return 'YT';
    if (carrier.includes('韵达')) return 'YD';
    return '物';
  },

  buildStatusSteps(statusKey, context) {
    const history = context.statusHistory || [];
    const createdAt = context.createdAt || this.findHistoryTime(history, 'pending_payment') || '';
    const shippedAt = this.findHistoryTime(history, 'shipped') || (context.logistics && context.logistics.shipped_at) || '';
    const completedAt = this.findHistoryTime(history, 'completed') || '';
    const closedAt = this.findHistoryTime(history, 'closed') || context.updatedAt || '';
    const refundRequestedAt = this.findHistoryTime(history, 'refund_requested') || this.findHistoryTime(history, 'after_sale') || '';
    const refundedAt = this.findHistoryTime(history, 'refunded') || context.updatedAt || '';
    const paidAt = context.paidAt || '';
    const transitAt = (context.logisticsCard && context.logisticsCard.traces[0] && context.logisticsCard.traces[0].time) || '';
    if (statusKey === 'closed') {
      return [
        { key: 'created', label: '订单创建', time: this.formatDateTime(createdAt), active: true },
        { key: 'closed', label: '已取消', time: this.formatDateTime(closedAt), active: true }
      ];
    }
    if (statusKey === 'refunded') {
      return [
        { key: 'paid', label: '已支付', time: this.formatDateTime(paidAt), active: Boolean(paidAt) },
        { key: 'refund', label: '退款申请', time: this.formatDateTime(refundRequestedAt), active: true },
        { key: 'refunded', label: '已退款', time: this.formatDateTime(refundedAt), active: true }
      ];
    }
    const paid = ['ship', 'receive', 'done', 'after'].includes(statusKey);
    const shipped = ['receive', 'done', 'after'].includes(statusKey);
    const completed = statusKey === 'done';
    return [
      { key: 'paid', label: paid ? '已支付' : '待支付', time: this.formatDateTime(paidAt), active: paid },
      { key: 'ship', label: shipped ? '已发货' : '待发货', time: this.formatDateTime(shippedAt), active: shipped },
      { key: 'transit', label: '运输中', time: transitAt, active: false },
      { key: 'done', label: '已完成', time: this.formatDateTime(completedAt), active: completed }
    ];
  },

  buildAmountRows(totalAmount) {
    return [
      { label: '商品金额', value: `¥${this.formatAmount(totalAmount)}` },
      { label: '定制服务费', value: '¥0.00' },
      { label: '优惠券', value: '- ¥0.00', danger: true },
      { label: '运费', value: '¥0.00' }
    ];
  },

  findHistoryTime(history = [], status) {
    const row = history.find(item => item.status === status);
    return row ? row.time : '';
  },

  updateOrderCache(order) {
    const orders = wx.getStorageSync('orders') || [];
    const index = orders.findIndex(item => item.id === order.id);
    if (index >= 0) orders[index] = order;
    else orders.unshift(order);
    wx.setStorageSync('orders', orders);
  },

  async handleAction(e) {
    const action = e.currentTarget.dataset.action;
    const user = auth.getStoredUser();
    const order = this.data.order;
    if (!order) return;
    if (action === 'logistics' && !order.canViewLogistics) {
      wx.showToast({ title: '暂无物流轨迹', icon: 'none' });
      return;
    }
    if (action === 'afterSale' && !order.canAfterSale) {
      wx.showToast({ title: '订单已在售后处理中', icon: 'none' });
      return;
    }
    if (action === 'refund' && !order.canRefund) {
      wx.showToast({ title: '当前订单暂不能申请退款', icon: 'none' });
      return;
    }
    if (!user || !user.user_id) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    if (action === 'pay') return this.continuePay(order.id, user.user_id);
    if (action === 'cancel') return this.confirmCancel(order.id, user.user_id);
    if (action === 'mockShip') {
      const phone = (order.receiver && order.receiver.phone) || '';
      return this.runOrderAction(() => mockShipOrder(order.id, user.user_id, {
        carrier: '顺丰速运',
        carrier_code: 'shunfeng',
        phone_tail: phone ? phone.slice(-4) : ''
      }), '已发货');
    }
    if (action === 'receive') return this.runOrderAction(() => confirmReceipt(order.id, user.user_id), '已确认收货');
    if (action === 'logistics') return this.openLogistics(order.id, user.user_id);
    if (action === 'afterSale') return this.confirmAfterSale(order.id, user.user_id);
    if (action === 'refund') return this.confirmRefund(order.id, user.user_id);
  },

  async loadLogistics(orderId, userId) {
    wx.showLoading({ title: '查询物流' });
    try {
      const result = await getOrderLogistics(orderId, userId);
      const logistics = result.logistics || {};
      const traces = logistics.traces || [];
      const logisticsDetail = this.normalizeLogistics({ ...logistics, traces }, result.status_history || [], this.data.order.statusKey);
      const actionState = this.buildFooterActions({
        statusKey: this.data.order.statusKey,
        logisticsCard: logisticsDetail,
        afterSaleStatus: this.data.order.afterSaleStatus,
        refundStatus: this.data.order.refundStatus
      });
      this.setData({
        logisticsDetail,
        'order.logisticsCard': logisticsDetail,
        'order.canViewLogistics': actionState.canViewLogistics,
        'order.hasFooterAction': actionState.hasFooterAction,
        'order.actionBarClass': actionState.actionBarClass
      });
      if (!logisticsDetail.show) {
        wx.showToast({ title: '暂无物流轨迹', icon: 'none' });
      }
    } catch (error) {
      wx.showToast({ title: error.message || '物流查询失败', icon: 'none' });
    } finally {
      wx.hideLoading();
    }
  },

  async openLogistics(orderId, userId) {
    await this.loadLogistics(orderId, userId);
    if (this.data.logisticsDetail && this.data.logisticsDetail.show) {
      this.setData({ showLogisticsModal: true });
    }
  },

  closeLogisticsModal() {
    this.setData({ showLogisticsModal: false });
  },

  noop() {},

  confirmAfterSale(orderId, userId) {
    wx.showModal({
      title: '申请售后',
      content: '提交后订单会进入售后处理中，客服会尽快与你联系。',
      confirmText: '提交',
      success: async res => {
        if (res.confirm) {
          await this.runOrderAction(() => requestAfterSale(orderId, userId, '用户在小程序订单详情中发起售后'), '售后已提交');
        }
      }
    });
  },

  confirmRefund(orderId, userId) {
    wx.showModal({
      title: '申请退款',
      content: '提交后订单会进入退款审核，已制作或已发货订单需客服确认后处理。',
      confirmText: '提交',
      success: async res => {
        if (res.confirm) {
          await this.runOrderAction(() => refundOrder(orderId, userId, '用户在小程序订单详情中发起退款'), '退款已提交');
        }
      }
    });
  },

  confirmCancel(orderId, userId) {
    wx.showModal({
      title: '取消订单',
      content: '确定取消这笔待付款订单吗？取消后不能继续支付。',
      confirmText: '取消订单',
      confirmColor: '#b35f34',
      success: async res => {
        if (res.confirm) {
          await this.runOrderAction(
            () => cancelOrder(orderId, userId, '用户在小程序订单详情中取消'),
            '订单已取消'
          );
        }
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
        wx.showLoading({ title: '确认支付结果' });
        const paid = await this.waitForPaidStatus();
        wx.hideLoading();
        wx.showToast({
          title: paid ? '支付成功' : '支付结果确认中',
          icon: paid ? 'success' : 'none'
        });
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

  async waitForPaidStatus() {
    for (let attempt = 0; attempt < 6; attempt += 1) {
      if (attempt > 0) {
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
      const order = await this.loadOrder({ silent: true });
      if (order && order.paymentStatus === 'paid') return true;
    }
    return false;
  },

  async runOrderAction(action, title) {
    wx.showLoading({ title: '处理订单' });
    try {
      await action();
      await this.loadOrder({ silent: true });
      wx.hideLoading();
      wx.showToast({ title, icon: 'success' });
    } catch (error) {
      wx.hideLoading();
      wx.showToast({ title: error.message || '操作失败', icon: 'none' });
    }
  },

  toggleMaterials() {
    const showAllMaterials = !this.data.showAllMaterials;
    const order = this.normalizeOrder(this.data.order);
    this.setData({
      showAllMaterials,
      order: {
        ...order,
        displayMaterials: showAllMaterials ? order.materials : order.materials.slice(0, 3)
      }
    });
  },

  copyOrderId() {
    const id = this.data.order && this.data.order.id;
    if (!id) return;
    wx.setClipboardData({
      data: id,
      success: () => wx.showToast({ title: '订单号已复制', icon: 'success' })
    });
  },

  copyTrackingNo() {
    const trackingNo = this.data.logisticsDetail && this.data.logisticsDetail.trackingNo;
    if (!trackingNo) return;
    wx.setClipboardData({
      data: trackingNo,
      success: () => wx.showToast({ title: '物流单号已复制', icon: 'success' })
    });
  },

  editAddress() {
    const order = this.data.order;
    const user = auth.getStoredUser();
    if (!order || !order.canEditAddress) {
      wx.showToast({ title: '订单已发货，不能修改地址', icon: 'none' });
      return;
    }
    if (!user || !user.user_id) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    wx.chooseAddress({
      success: async res => {
        const region = [res.provinceName, res.cityName, res.countyName].filter(Boolean);
        const receiver = {
          name: res.userName || '',
          phone: res.telNumber || '',
          region,
          regionText: region.join(' '),
          detailAddress: res.detailInfo || '',
          address: [region.join(' '), res.detailInfo || ''].filter(Boolean).join(' ')
        };
        wx.showLoading({ title: '更新地址' });
        try {
          const updated = await updateOrderReceiver(order.id, user.user_id, receiver);
          const nextOrder = this.normalizeOrder(updated);
          this.updateOrderCache(nextOrder);
          this.setData({
            order: nextOrder,
            logisticsDetail: nextOrder.logisticsCard
          });
          wx.hideLoading();
          wx.showToast({ title: '地址已更新', icon: 'success' });
        } catch (error) {
          wx.hideLoading();
          wx.showToast({ title: error.message || '地址更新失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.showToast({ title: '可在发货前修改地址', icon: 'none' });
      }
    });
  },

  formatSpecValue(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return String(value || '');
    return Number.isInteger(number) ? String(number) : number.toFixed(1).replace(/\.0$/, '');
  },

  formatAmount(value) {
    const amount = Number(value || 0);
    return Number.isFinite(amount) ? amount.toFixed(2) : '0.00';
  },

  formatDateTime(value) {
    if (!value) return '';
    const text = String(value);
    const hasTimezone = /T|Z|\+\d\d:\d\d$/.test(text);
    const date = hasTimezone ? new Date(text) : new Date(text.replace(/-/g, '/'));
    if (Number.isNaN(date.getTime())) return String(value).slice(0, 16);
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hour = String(date.getHours()).padStart(2, '0');
    const minute = String(date.getMinutes()).padStart(2, '0');
    return `${month}-${day} ${hour}:${minute}`;
  }
});
