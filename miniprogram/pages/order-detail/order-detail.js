const auth = require('../../utils/auth');
const env = require('../../config/env');
const {
  getOrder,
  getOrderPaymentStatus,
  payOrder,
  mockPayOrder,
  mockShipOrder,
  confirmReceipt,
  cancelOrder,
  updateOrderReceiver,
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
    hint: '工作室正在制作与打包',
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
    paymentConfirming: false,
    showAllMaterials: false,
    showLogisticsModal: false
  },

  onLoad(options = {}) {
    this.setData({ id: decodeURIComponent(options.id || options.order_id || '') });
  },

  onShow() {
    this.loadOrder();
  },

  onUnload() {
    this.stopLogisticsRefresh();
    this.stopPaymentConfirmation();
  },

  async loadOrder(options = {}) {
    if (!this.data.id || this.data.loading) return null;
    this.setData({ loading: true });
    let activeUserId = '';
    try {
      let user = auth.getStoredUser();
      if (!user || !user.user_id) {
        user = await auth.silentLogin();
      }
      activeUserId = user.user_id;
      const row = await getOrder(this.data.id, user.user_id);
      const order = this.normalizeOrder(row);
      this.updateOrderCache(order);
      this.setData({
        order,
        logisticsDetail: order.logisticsCard
      });
      if (this.shouldAutoLoadLogistics(order)) {
        await this.loadLogistics(order.id, activeUserId, { silent: true });
      }
      return this.data.order || order;
    } catch (error) {
      const orders = wx.getStorageSync('orders') || [];
      const currentUser = auth.getStoredUser();
      const currentUserId = activeUserId || (currentUser && currentUser.user_id) || '';
      const cachedOrder = orders.find(item => item.id === this.data.id && item.userId === currentUserId) || null;
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
    const signedAwaitingReceipt = statusKey === 'receive' && logisticsCard.isSigned;
    const afterSaleStatus = item.after_sale_status || item.afterSaleStatus || '';
    const refundStatus = item.refund_status || item.refundStatus || '';
    const actionState = this.buildFooterActions({
      statusKey,
      paymentStatus,
      logisticsCard,
      afterSaleStatus,
      refundStatus
    });
    const statusSteps = this.buildStatusSteps(statusKey, {
      createdAt: item.created_at || item.createdAt,
      updatedAt: item.updated_at || item.updatedAt,
      paidAt,
      rawStatus,
      afterSaleStatus,
      refundStatus,
      statusHistory,
      logistics,
      logisticsCard
    });
    const statusStepsLayout = this.buildStatusStepsLayout(statusSteps);
    const displayMaterials = this.data.showAllMaterials ? materials : materials.slice(0, 3);
    const materialCount = sequence.length || materials.reduce((sum, row) => sum + Number(row.qty || 1), 0);

    return {
      id: item.order_id || item.id || this.data.id,
      userId: item.user_id || item.userId || '',
      outTradeNo: item.out_trade_no || item.outTradeNo || '',
      createdAt: item.created_at || item.createdAt || '',
      createdAtText: this.formatDateTime(item.created_at || item.createdAt || ''),
      updatedAt: item.updated_at || item.updatedAt || '',
      status: meta.title,
      statusTitle: meta.title,
      statusHint: meta.hint,
      statusDisplayText: signedAwaitingReceipt ? '快递已签收' : (meta.hint || meta.title),
      statusTone: meta.tone,
      etaText: signedAwaitingReceipt ? logisticsCard.receiptHint : (logisticsCard.etaText || meta.eta),
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
      ...statusStepsLayout,
      statusHistory,
      remark: item.remark || '',
      afterSaleStatus,
      refundStatus,
      ...actionState
    };
  },

  buildFooterActions({ statusKey, paymentStatus, logisticsCard, afterSaleStatus, refundStatus }) {
    const activeAfterSaleValues = [
      'requested', 'approved', 'awaiting_return', 'returning', 'service_processing',
      'refund_pending', 'refund_submitting', 'refunding', 'processing'
    ];
    const hasActiveAfterSale = statusKey === 'after'
      || activeAfterSaleValues.includes(afterSaleStatus)
      || activeAfterSaleValues.includes(refundStatus);
    const paymentInProgress = paymentStatus === 'processing';
    const canCancel = statusKey === 'pay' && !paymentInProgress;
    const canRefund = statusKey === 'ship' && !hasActiveAfterSale;
    const canAfterSale = ['receive', 'done'].includes(statusKey) && !hasActiveAfterSale;
    const canViewAfterSale = hasActiveAfterSale;
    const canViewLogistics = Boolean(logisticsCard && logisticsCard.show);
    const canPay = statusKey === 'pay' && !paymentInProgress;
    const canMockShip = statusKey === 'ship' && this.data.isLocalApi;
    const canReceive = statusKey === 'receive' && !hasActiveAfterSale;
    const hasSecondaryAction = canCancel || canRefund || canAfterSale || canViewAfterSale;
    const hasPrimaryAction = canPay || canMockShip || canReceive || canViewLogistics;
    const actionCount = ['closed', 'refunded'].includes(statusKey)
      ? 0
      : (hasSecondaryAction ? 1 : 0) + 1 + (hasPrimaryAction ? 1 : 0);

    return {
      hasActiveAfterSale,
      canCancel,
      canRefund,
      canAfterSale,
      canViewAfterSale,
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
    if (rawStatus === 'refund_requested') return 'after';
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
      const sku = item.sku || item.skuId || item.id || '';
      return {
        key: `${sku || name}-${size || 'na'}-${index}`,
        positionLabel: useSequence ? `第 ${Number(item.index || index + 1)} 颗` : `共 ${qty} 件`,
        name,
        detail: [sizeText ? `珠径 ${sizeText}` : '', type].filter(Boolean).join(' · '),
        sizeText,
        type,
        sku,
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
    const rawTraces = (logistics.traces || []).map((trace, index) => ({
      id: `${trace.time || ''}-${index}`,
      desc: trace.desc || trace.context || trace.status || '物流状态更新',
      location: trace.location || '',
      time: this.formatDateTime(trace.time || trace.ftime || ''),
      active: index === 0
    }));
    const trackingNo = logistics.tracking_no || logistics.trackingNo || '';
    const hasTracking = Boolean(trackingNo);
    const isSigned = logistics.status === 'signed'
      || String(logistics.status_text || logistics.statusText || '').includes('签收');
    const autoCompleteAt = logistics.auto_complete_at || logistics.autoCompleteAt || '';
    const autoCompleteAtText = this.formatDateTime(autoCompleteAt);
    const localTracePattern = /商家已打包|商家已填写发货信息|等待物流公司更新轨迹|商家已发货，等待快递揽收/;
    const carrierTraces = rawTraces.filter(trace => !localTracePattern.test(trace.desc));
    const shippedAt = this.findHistoryTime(statusHistory, 'shipped') || logistics.shipped_at || '';
    const merchantTraces = [];
    if (shippedAt || hasTracking) {
      merchantTraces.push({
        id: 'merchant-waiting-pickup',
        desc: '商家已发货，等待快递揽收',
        location: '宇涧水晶工作室',
        time: this.formatDateTime(shippedAt || logistics.updated_at || ''),
        active: carrierTraces.length === 0
      });
    }
    const traces = [...carrierTraces, ...merchantTraces];
    const hasCarrierUpdates = logistics.source === 'kuaidi100' && carrierTraces.length > 0;
    const hasTraces = traces.length > 0;
    const isAwaitingShipment = statusKey === 'ship' && !hasTracking;
    const latestTrace = carrierTraces[0] || merchantTraces[0] || {
      id: 'awaiting-shipment',
      desc: hasTracking ? '商家已发货，等待快递揽收。' : '工作室正在制作与打包，完成后将填写快递单号。',
      location: '',
      time: '',
      active: true
    };
    const statusText = isAwaitingShipment
      ? '待发货'
      : (hasTracking && !hasCarrierUpdates
        ? '已发货待揽收'
        : (logistics.status_text || logistics.statusText || (hasTraces ? '物流运输中' : '暂无物流轨迹')));
    return {
      show: ['ship', 'receive'].includes(statusKey) || hasTracking || hasTraces,
      isFulfillmentProgress: isAwaitingShipment,
      hasTracking,
      hasTraces,
      hasCarrierUpdates,
      isSigned,
      autoCompleteAt,
      autoCompleteAtText,
      carrier: logistics.carrier || '物流信息',
      carrierCode: logistics.carrier_code || logistics.carrierCode || '',
      carrierShort: this.carrierShort(logistics.carrier || ''),
      trackingNo,
      statusText,
      source: logistics.source === 'kuaidi100'
        ? '物流轨迹已更新'
        : (hasTracking ? '商家发货记录' : '订单进度'),
      message: logistics.message || '',
      traces: hasTraces ? traces : [latestTrace],
      latestTrace,
      summaryTitle: statusText,
      summaryDesc: latestTrace.desc,
      receiptHint: autoCompleteAtText
        ? `请确认收货；若未操作，${autoCompleteAtText} 后自动完成`
        : '请确认收货；签收满 7 天后订单将自动完成',
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

  buildStatusStepsLayout(statusSteps = []) {
    const count = statusSteps.length;
    const scrollable = count > 5;
    return {
      statusStepsClass: `steps-${count}`,
      statusStepsScrollable: scrollable,
      statusStepsScrollLeft: scrollable ? 99999 : 0,
      statusStepsStyle: scrollable
        ? `min-width:${count * 132}rpx;grid-template-columns:repeat(${count},minmax(132rpx,1fr));`
        : ''
    };
  },

  buildStatusSteps(statusKey, context) {
    const history = context.statusHistory || [];
    const createdAt = context.createdAt || this.findHistoryTime(history, 'pending_payment') || '';
    const shippedAt = this.findHistoryTime(history, 'shipped') || (context.logistics && context.logistics.shipped_at) || '';
    const completedAt = this.findHistoryTime(history, 'completed') || '';
    const closedAt = this.findHistoryTime(history, 'closed') || context.updatedAt || '';
    const paidAt = context.paidAt || '';
    const logistics = context.logistics || {};
    const logisticsCard = context.logisticsCard || {};
    const transitAt = (logisticsCard.hasCarrierUpdates && logisticsCard.traces[0] && logisticsCard.traces[0].time) || '';
    if (statusKey === 'closed') {
      return [
        { key: 'created', label: '订单创建', time: this.formatDateTime(createdAt), active: true },
        { key: 'closed', label: '已取消', time: this.formatDateTime(closedAt), active: true }
      ];
    }
    if (['after', 'refunded'].includes(statusKey)) {
      return this.buildAfterSaleStatusSteps(statusKey, context);
    }
    const paid = ['ship', 'receive', 'done', 'after'].includes(statusKey);
    const shipped = ['receive', 'done', 'after'].includes(statusKey) || Boolean(logisticsCard.hasTracking);
    const completed = statusKey === 'done';
    const signed = logistics.status === 'signed' || String(logisticsCard.statusText || '').includes('签收');
    const carrierUpdated = Boolean(logisticsCard.hasCarrierUpdates);
    const steps = [
      { key: 'paid', label: paid ? '已支付' : '待支付', time: this.formatDateTime(paidAt), active: paid },
      {
        key: 'fulfillment',
        label: '待发货',
        time: this.formatDateTime(paidAt),
        active: paid
      },
      {
        key: 'pickup',
        label: (carrierUpdated || signed) ? '已揽收' : '已发货待揽收',
        time: this.formatDateTime(shippedAt),
        active: shipped
      },
      { key: 'transit', label: '运输中', time: transitAt, active: carrierUpdated || signed }
    ];
    if (signed) {
      steps.push({
        key: 'signed',
        label: '已签收',
        time: this.formatDateTime(logistics.signed_at || logistics.signedAt || '') || transitAt,
        active: true
      });
      steps.push({
        key: 'done',
        label: completed ? '已完成' : '待确认收货',
        time: this.formatDateTime(completedAt),
        active: completed
      });
      return steps;
    }
    steps.push({
      key: 'done',
      label: completed ? '已完成' : '待签收',
      time: this.formatDateTime(completedAt),
      active: completed
    });
    return steps;
  },

  buildAfterSaleStatusSteps(statusKey, context = {}) {
    const history = Array.isArray(context.statusHistory) ? context.statusHistory : [];
    const aliases = {
      pay: 'pending_payment',
      paid: 'pending_ship',
      ship: 'pending_ship',
      receive: 'shipped',
      done: 'completed',
      refund: 'refund_requested'
    };
    const labels = {
      pending_payment: '订单创建',
      pending_ship: '已支付',
      shipped: '已发货',
      completed: '已完成',
      refund_requested: '退款申请',
      refunded: '已退款'
    };
    const supportedStatuses = Object.keys(labels);
    const timeline = [];
    const appendStatus = (status, time = '') => {
      if (!supportedStatuses.includes(status)) return;
      const previous = timeline[timeline.length - 1];
      if (previous && previous.status === status) {
        if (!previous.time && time) previous.time = time;
        return;
      }
      timeline.push({ status, time: time || '' });
    };
    history.forEach(item => {
      const status = aliases[item.status] || item.status;
      appendStatus(status, item.time || '');
    });
    const hasStatus = status => timeline.some(item => item.status === status);
    const insertStatus = (status, time = '', beforeStatuses = []) => {
      if (hasStatus(status)) return;
      const targetIndex = timeline.findIndex(item => beforeStatuses.includes(item.status));
      timeline.splice(targetIndex < 0 ? timeline.length : targetIndex, 0, {
        status,
        time: time || ''
      });
    };
    const logistics = context.logistics || {};
    const rawStatus = aliases[context.rawStatus] || context.rawStatus || '';

    insertStatus('pending_payment', context.createdAt || '', supportedStatuses.slice(1));
    if (context.paidAt || hasStatus('pending_ship')) {
      insertStatus('pending_ship', context.paidAt || '', [
        'shipped', 'completed', 'refund_requested', 'refunded'
      ]);
    }
    if (logistics.tracking_no || logistics.trackingNo) {
      insertStatus('shipped', logistics.shipped_at || context.updatedAt || '', [
        'completed', 'refund_requested', 'refunded'
      ]);
    }
    const lastStatus = timeline.length ? timeline[timeline.length - 1].status : '';
    if (rawStatus && rawStatus !== lastStatus) appendStatus(rawStatus, context.updatedAt || '');
    if (statusKey === 'after' && !hasStatus('refund_requested')) {
      appendStatus('refund_requested', context.updatedAt || '');
    }
    if (statusKey === 'refunded') {
      if (!hasStatus('refund_requested')) {
        insertStatus('refund_requested', '', ['refunded']);
      }
      if (!hasStatus('refunded')) appendStatus('refunded', context.updatedAt || '');
    }

    return timeline.map((item, index) => ({
      key: `${item.status}-${index}`,
      label: labels[item.status],
      time: this.formatDateTime(item.time),
      active: true
    }));
  },

  buildAmountRows(totalAmount) {
    return [
      { label: '商品金额', value: `¥${this.formatAmount(totalAmount)}` },
      { label: '定制服务费', value: '¥0.00' },
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
    if (action === 'afterSale' && !order.canAfterSale && !order.canViewAfterSale) {
      wx.showToast({ title: '当前订单暂不能申请售后', icon: 'none' });
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

  shouldAutoLoadLogistics(order = {}) {
    return ['ship', 'receive', 'done', 'after'].includes(order.statusKey)
      || Boolean(order.logisticsCard && order.logisticsCard.hasTracking);
  },

  stopLogisticsRefresh() {
    this._logisticsRequestToken = (this._logisticsRequestToken || 0) + 1;
  },

  async loadLogistics(orderId, userId, options = {}) {
    const silent = options.silent === true;
    const requestToken = (this._logisticsRequestToken || 0) + 1;
    this._logisticsRequestToken = requestToken;
    if (!silent) wx.showLoading({ title: '查询物流' });
    try {
      const result = await getOrderLogistics(orderId, userId, { silent });
      const currentOrder = this.data.order;
      if (requestToken !== this._logisticsRequestToken || !currentOrder || currentOrder.id !== orderId) {
        return null;
      }
      const logistics = result.logistics || {};
      const traces = logistics.traces || [];
      const statusHistory = result.status_history || currentOrder.statusHistory || [];
      const rawStatus = result.order_status || currentOrder.rawStatus;
      const statusKey = this.statusKey(rawStatus, currentOrder.paymentStatus, currentOrder.statusKey);
      const meta = STATUS_META[statusKey] || STATUS_META.done;
      const logisticsDetail = this.normalizeLogistics({ ...logistics, traces }, statusHistory, statusKey);
      const statusSteps = this.buildStatusSteps(statusKey, {
        createdAt: currentOrder.createdAt,
        updatedAt: currentOrder.updatedAt,
        paidAt: currentOrder.paidAt,
        rawStatus,
        afterSaleStatus: currentOrder.afterSaleStatus,
        refundStatus: currentOrder.refundStatus,
        statusHistory,
        logistics,
        logisticsCard: logisticsDetail
      });
      const statusStepsLayout = this.buildStatusStepsLayout(statusSteps);
      const actionState = this.buildFooterActions({
        statusKey,
        paymentStatus: currentOrder.paymentStatus,
        logisticsCard: logisticsDetail,
        afterSaleStatus: currentOrder.afterSaleStatus,
        refundStatus: currentOrder.refundStatus
      });
      const nextOrder = {
        ...currentOrder,
        status: meta.title,
        statusTitle: meta.title,
        statusHint: meta.hint,
        statusDisplayText: statusKey === 'receive' && logisticsDetail.isSigned
          ? '快递已签收'
          : (meta.hint || meta.title),
        statusTone: meta.tone,
        etaText: statusKey === 'receive' && logisticsDetail.isSigned
          ? logisticsDetail.receiptHint
          : (logisticsDetail.etaText || meta.eta),
        statusKey,
        rawStatus,
        canEditAddress: ['pay', 'ship'].includes(statusKey),
        logistics,
        logisticsCard: logisticsDetail,
        logisticsDetail,
        statusHistory,
        statusSteps,
        ...statusStepsLayout,
        ...actionState
      };
      this.updateOrderCache(nextOrder);
      this.setData({
        logisticsDetail,
        order: nextOrder
      });
      if (!logisticsDetail.show && !silent) {
        wx.showToast({ title: '暂无物流轨迹', icon: 'none' });
      }
      return logisticsDetail;
    } catch (error) {
      if (!silent) wx.showToast({ title: error.message || '物流查询失败', icon: 'none' });
      return null;
    } finally {
      if (!silent) wx.hideLoading();
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
    wx.navigateTo({
      url: `/pages/after-sale-apply/after-sale-apply?id=${encodeURIComponent(orderId)}`
    });
  },

  confirmRefund(orderId, userId) {
    wx.showModal({
      title: '申请退款',
      content: '待发货订单可申请退款；如商品已经发出，请改为申请退货退款。',
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
    if (this._paymentActionRunning) return;
    this._paymentActionRunning = true;
    this.setData({ paymentConfirming: false });
    wx.showLoading({ title: '准备支付' });
    try {
      const result = await payOrder(orderId, userId);
      const payment = result.payment || {};
      wx.hideLoading();
      if (payment.available && payment.pay_params) {
        let clientPaymentUnknown = false;
        try {
          await new Promise((resolve, reject) => wx.requestPayment({ ...payment.pay_params, success: resolve, fail: reject }));
        } catch (paymentError) {
          const cancelled = String(paymentError && paymentError.errMsg || '').includes('cancel');
          if (cancelled) {
            wx.showToast({ title: '已取消支付', icon: 'none' });
            return;
          }
          clientPaymentUnknown = true;
        }
        this.setData({ paymentConfirming: true });
        wx.showLoading({ title: '正在确认支付结果' });
        const confirmation = await this.confirmPaymentResult(orderId, userId);
        wx.hideLoading();
        this.setData({ paymentConfirming: false });
        if (confirmation.state === 'paid') {
          await this.loadOrder({ silent: true });
          wx.showToast({ title: '支付成功', icon: 'success' });
        } else if (confirmation.state === 'pending') {
          wx.showModal({
            title: clientPaymentUnknown ? '支付状态待确认' : '支付结果确认中',
            content: clientPaymentUnknown
              ? '客户端未能确认支付结果，服务端也暂未收到最终状态。可稍后在订单列表查看。'
              : '服务端尚未确认支付结果，可稍后在订单列表查看。',
            showCancel: false,
            confirmText: '我知道了'
          });
        } else if (confirmation.state === 'terminal') {
          await this.loadOrder({ silent: true });
          wx.showToast({ title: '支付未完成', icon: 'none' });
        }
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
    } finally {
      this._paymentActionRunning = false;
      this.setData({ paymentConfirming: false });
    }
  },

  stopPaymentConfirmation() {
    this._paymentPollToken = (this._paymentPollToken || 0) + 1;
    if (this._paymentPollTimer) clearTimeout(this._paymentPollTimer);
    if (this._paymentPollResolve) this._paymentPollResolve(false);
    this._paymentPollTimer = null;
    this._paymentPollResolve = null;
  },

  waitForPaymentPoll(delay, token) {
    return new Promise(resolve => {
      this._paymentPollResolve = resolve;
      this._paymentPollTimer = setTimeout(() => {
        this._paymentPollTimer = null;
        this._paymentPollResolve = null;
        resolve(this._paymentPollToken === token);
      }, delay);
    });
  },

  async confirmPaymentResult(orderId, userId) {
    this.stopPaymentConfirmation();
    const token = this._paymentPollToken;
    const delays = [0, 800, 1500, 2500, 4000, 6000];
    for (const delay of delays) {
      if (delay && !await this.waitForPaymentPoll(delay, token)) return { state: 'stopped' };
      const currentUser = auth.getStoredUser();
      if (!currentUser || currentUser.user_id !== userId) {
        this.stopPaymentConfirmation();
        return { state: 'account_changed' };
      }
      try {
        const status = await getOrderPaymentStatus(orderId, { silent: true });
        if (status.paid) return { state: 'paid', status };
        if (status.terminal) return { state: 'terminal', status };
      } catch (error) {
        if (this._paymentPollToken !== token) return { state: 'stopped' };
      }
    }
    return { state: 'pending' };
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
