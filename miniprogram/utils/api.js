const env = require('../config/env');

function getBaseUrl() {
  return env.fallbackBaseUrl;
}

function request(path, options = {}) {
  if (env.useAnyService && wx.cloud && wx.cloud.callContainer) {
    return requestByAnyService(path, options);
  }

  return requestByUrl(path, options);
}

function requestByAnyService(path, options = {}) {
  return wx.cloud.callContainer({
    path,
    method: options.method || 'GET',
    data: options.data || {},
    header: {
      ...(options.header || {}),
      'Content-Type': 'application/json',
      'X-WX-SERVICE': 'tcbanyservice',
      'X-AnyService-Name': env.anyServiceName
    },
    timeout: 10000
  }).then((res) => unwrapResponse(res.statusCode, res.data)).catch((error) => {
    const accountInfo = wx.getAccountInfoSync ? wx.getAccountInfoSync() : {};
    console.error('AnyService request failed:', {
      path,
      environment: env.cloudEnvId,
      service: env.anyServiceName,
      appId: accountInfo.miniProgram && accountInfo.miniProgram.appId,
      error
    });
    throw error;
  });
}

function requestByUrl(path, options = {}) {
  const url = `${getBaseUrl()}${path}`;
  const method = options.method || 'GET';
  return new Promise((resolve, reject) => {
    wx.request({
      url,
      method,
      data: options.data || {},
      header: { 'content-type': 'application/json', ...(options.header || {}) },
      timeout: 10000,
      success(res) {
        try {
          resolve(unwrapResponse(res.statusCode, res.data));
        } catch (error) {
          console.error('api response failed:', { url, statusCode: res.statusCode, data: res.data, error });
          reject(error);
        }
      },
      fail(error) {
        const errMsg = error.errMsg || '无法连接接口服务';
        console.error('wx.request failed:', { url, method, error });
        wx.showModal({
          title: '接口连接失败',
          content: `${url}\n${errMsg}`,
          showCancel: false
        });
        reject(new Error(errMsg));
      }
    });
  });
}

function unwrapResponse(statusCode, body) {
  if (statusCode >= 200 && statusCode < 300 && body && body.code === 0) {
    return body.data;
  }

  throw new Error((body && (body.message || body.detail)) || `请求失败 (${statusCode})`);
}

function calculateEnergy(payload) {
  return request('/api/v1/assessment/energy', { method: 'POST', data: payload });
}

function checkAnyService() {
  return request('/health');
}

function createDIYRecommendation(assessmentId, payload) {
  return request(`/api/v1/assessment/${assessmentId}/diy-recommendation`, { method: 'POST', data: payload });
}

function wechatLogin(payload) {
  return request('/api/v1/auth/wechat-login', { method: 'POST', data: payload });
}

function getUserProfile(userId) {
  return request(`/api/v1/auth/profile?user_id=${encodeURIComponent(userId)}`);
}

function saveUserProfile(payload) {
  return request('/api/v1/auth/profile', { method: 'POST', data: payload });
}

function bindPhone(payload) {
  return request('/api/v1/auth/phone', { method: 'POST', data: payload });
}

function getTodayDailyEnergy(userId, options = {}) {
  const query = [`user_id=${encodeURIComponent(userId)}`];
  if (options.initialWish) query.push(`initial_wish=${encodeURIComponent(options.initialWish)}`);
  if (options.forceRecalculate) query.push('force_recalculate=true');
  return request(`/api/v1/daily-energy/today?${query.join('&')}`);
}

function getMaterials(options = {}) {
  const query = [];
  if (options.top) query.push(`top=${encodeURIComponent(options.top)}`);
  if (options.keyword) query.push(`keyword=${encodeURIComponent(options.keyword)}`);
  return request(`/api/v1/materials${query.length ? `?${query.join('&')}` : ''}`);
}

function createOrder(payload) {
  return request('/api/v1/orders', { method: 'POST', data: payload });
}

function getOrders(userId) {
  return request(`/api/v1/orders?user_id=${encodeURIComponent(userId)}`);
}

function payOrder(orderId, userId) {
  return request(`/api/v1/orders/${encodeURIComponent(orderId)}/pay`, {
    method: 'POST',
    data: { user_id: userId }
  });
}

function mockPayOrder(orderId, userId) {
  return request(`/api/v1/orders/${encodeURIComponent(orderId)}/mock-pay`, {
    method: 'POST',
    data: { user_id: userId }
  });
}

function mockShipOrder(orderId, userId, options = {}) {
  return request(`/api/v1/orders/${encodeURIComponent(orderId)}/mock-ship`, {
    method: 'POST',
    data: {
      user_id: userId,
      carrier: options.carrier || '顺丰速运',
      carrier_code: options.carrier_code || 'shunfeng',
      tracking_no: options.tracking_no || '',
      phone_tail: options.phone_tail || ''
    }
  });
}

function confirmReceipt(orderId, userId) {
  return request(`/api/v1/orders/${encodeURIComponent(orderId)}/confirm-receipt`, {
    method: 'POST',
    data: { user_id: userId }
  });
}

function requestAfterSale(orderId, userId, reason = '') {
  return request(`/api/v1/orders/${encodeURIComponent(orderId)}/after-sale`, {
    method: 'POST',
    data: { user_id: userId, reason }
  });
}

function refundOrder(orderId, userId, reason = '') {
  return request(`/api/v1/orders/${encodeURIComponent(orderId)}/refund`, {
    method: 'POST',
    data: { user_id: userId, reason }
  });
}

function getOrderLogistics(orderId, userId) {
  return request(`/api/v1/orders/${encodeURIComponent(orderId)}/logistics?user_id=${encodeURIComponent(userId)}`);
}

module.exports = {
  getBaseUrl,
  request,
  checkAnyService,
  calculateEnergy,
  createDIYRecommendation,
  wechatLogin,
  getUserProfile,
  saveUserProfile,
  bindPhone,
  getTodayDailyEnergy,
  getMaterials,
  createOrder,
  getOrders,
  payOrder,
  mockPayOrder,
  mockShipOrder,
  confirmReceipt,
  requestAfterSale,
  refundOrder,
  getOrderLogistics
};
