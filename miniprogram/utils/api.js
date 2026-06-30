const env = require('../config/env');

function getBaseUrl() {
  const info = wx.getSystemInfoSync ? wx.getSystemInfoSync() : {};
  if (info.platform && info.platform !== 'devtools' && env.deviceBaseUrl) {
    return env.deviceBaseUrl;
  }
  return env.fallbackBaseUrl;
}

function getErrorMessage(error, fallback = '接口连接失败') {
  return (error && (error.errMsg || error.message)) || fallback;
}

function isTimeoutMessage(message = '') {
  return String(message).toLowerCase().indexOf('timeout') > -1;
}

function buildRequestError(path, method, message) {
  const friendly = isTimeoutMessage(message)
    ? `${method} ${path} 请求超时，请稍后重试`
    : `${method} ${path} ${message}`;
  const error = new Error(friendly);
  error.requestPath = path;
  error.requestMethod = method;
  error.rawMessage = message;
  return error;
}

function logRequestFailure(label, payload, options = {}) {
  const data = {
    path: payload.path,
    url: payload.url,
    method: payload.method,
    statusCode: payload.statusCode,
    message: payload.message
  };
  if (options.silent) {
    console.warn(label, data);
    return;
  }
  console.error(label, data);
}

function request(path, options = {}) {
  if (env.useAnyService && wx.cloud && wx.cloud.callContainer) {
    return requestByAnyService(path, options);
  }

  return requestByUrl(path, options);
}

function requestByAnyService(path, options = {}) {
  const method = options.method || 'GET';
  return wx.cloud.callContainer({
    path,
    method,
    data: options.data || {},
    header: {
      ...(options.header || {}),
      'Content-Type': 'application/json',
      'X-WX-SERVICE': 'tcbanyservice',
      'X-AnyService-Name': env.anyServiceName
    },
    timeout: options.timeout || 10000
  }).then((res) => unwrapResponse(res.statusCode, res.data)).catch((error) => {
    const accountInfo = wx.getAccountInfoSync ? wx.getAccountInfoSync() : {};
    const message = getErrorMessage(error);
    logRequestFailure('AnyService request failed:', {
      path,
      method,
      environment: env.cloudEnvId,
      service: env.anyServiceName,
      appId: accountInfo.miniProgram && accountInfo.miniProgram.appId,
      message
    }, options);
    throw buildRequestError(path, method, message);
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
      timeout: options.timeout || 10000,
      success(res) {
        try {
          resolve(unwrapResponse(res.statusCode, res.data));
        } catch (error) {
          logRequestFailure('api response failed:', {
            path,
            url,
            method,
            statusCode: res.statusCode,
            message: error.message || 'response_unwrap_failed'
          }, options);
          reject(error);
        }
      },
      fail(error) {
        const errMsg = error.errMsg || '无法连接接口服务';
        const requestError = buildRequestError(path, method, errMsg);
        logRequestFailure('wx.request failed:', {
          path,
          url,
          method,
          message: errMsg
        }, options);
        if (!options.silent && options.showModal !== false) {
          wx.showModal({
          title: '接口连接失败',
          content: `${url}\n${errMsg}`,
          showCancel: false
          });
        }
        reject(requestError);
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

function calculateEnergy(payload, options = {}) {
  return request('/api/v1/assessment/energy', { ...options, method: 'POST', data: payload });
}

function getAssessmentOptions(options = {}) {
  return request('/api/v1/assessment/options', options);
}

function checkAnyService() {
  return request('/health');
}

function createDIYRecommendation(assessmentId, payload, options = {}) {
  return request(`/api/v1/assessment/${assessmentId}/diy-recommendation`, { ...options, method: 'POST', data: payload });
}

function wechatLogin(payload, options = {}) {
  return request('/api/v1/auth/wechat-login', { ...options, method: 'POST', data: payload });
}

function getUserProfile(userId, options = {}) {
  return request(`/api/v1/auth/profile?user_id=${encodeURIComponent(userId)}`, options);
}

function saveUserProfile(payload, options = {}) {
  return request('/api/v1/auth/profile', { ...options, method: 'POST', data: payload });
}

function isDomainListError(errMsg = '') {
  return errMsg.indexOf('url not in domain list') > -1 || errMsg.indexOf('domain list') > -1;
}

function inferAvatarFileName(filePath = '') {
  const clean = String(filePath).split('?')[0].split('#')[0];
  const name = clean.split('/').pop() || 'avatar.jpg';
  return /\.[a-z0-9]+$/i.test(name) ? name : 'avatar.jpg';
}

function inferAvatarContentType(filePath = '') {
  const lower = String(filePath).toLowerCase();
  if (lower.indexOf('.png') > -1) return 'image/png';
  if (lower.indexOf('.webp') > -1) return 'image/webp';
  if (lower.indexOf('.gif') > -1) return 'image/gif';
  return 'image/jpeg';
}

function readFileBase64(filePath) {
  return new Promise((resolve, reject) => {
    const fs = wx.getFileSystemManager && wx.getFileSystemManager();
    if (!fs || !fs.readFile) {
      reject(new Error('当前微信版本不支持读取头像文件'));
      return;
    }
    fs.readFile({
      filePath,
      encoding: 'base64',
      success(res) {
        resolve(res.data);
      },
      fail(error) {
        reject(new Error(error.errMsg || '读取头像文件失败'));
      }
    });
  });
}

async function uploadAvatarByBase64(filePath, userId) {
  const contentBase64 = await readFileBase64(filePath);
  return request('/api/v1/auth/avatar-base64', {
    method: 'POST',
    data: {
      user_id: userId,
      content_base64: contentBase64,
      content_type: inferAvatarContentType(filePath),
      filename: inferAvatarFileName(filePath)
    }
  });
}

function uploadAvatar(filePath, userId) {
  if (!filePath) return Promise.reject(new Error('请选择头像'));
  if (env.useAnyService && wx.cloud && wx.cloud.uploadFile) {
    return uploadAvatarByBase64(filePath, userId);
  }
  const url = `${getBaseUrl()}/api/v1/auth/avatar`;
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url,
      filePath,
      name: 'file',
      formData: { user_id: userId },
      timeout: 15000,
      success(res) {
        try {
          const body = typeof res.data === 'string' ? JSON.parse(res.data) : res.data;
          resolve(unwrapResponse(res.statusCode, body));
        } catch (error) {
          logRequestFailure('avatar upload response failed:', {
            path: '/api/v1/auth/avatar',
            url,
            method: 'UPLOAD',
            statusCode: res.statusCode,
            message: error.message || 'upload_response_unwrap_failed'
          });
          reject(error);
        }
      },
      fail(error) {
        let errMsg = error.errMsg || '头像上传失败';
        if (isDomainListError(errMsg)) {
          uploadAvatarByBase64(filePath, userId).then(resolve).catch(reject);
          return;
        }
        logRequestFailure('wx.uploadFile failed:', {
          path: '/api/v1/auth/avatar',
          url,
          method: 'UPLOAD',
          message: errMsg
        });
        reject(buildRequestError('/api/v1/auth/avatar', 'UPLOAD', errMsg));
      }
    });
  });
}

function uploadDesignPreview(filePath, userId) {
  if (!filePath) return Promise.reject(new Error('请选择方案预览图'));
  const url = `${getBaseUrl()}/api/v1/diy-designs/preview`;
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url,
      filePath,
      name: 'file',
      formData: { user_id: userId },
      timeout: 15000,
      success(res) {
        try {
          const body = typeof res.data === 'string' ? JSON.parse(res.data) : res.data;
          resolve(unwrapResponse(res.statusCode, body));
        } catch (error) {
          logRequestFailure('design preview upload response failed:', {
            path: '/api/v1/diy-designs/preview',
            url,
            method: 'UPLOAD',
            statusCode: res.statusCode,
            message: error.message || 'upload_response_unwrap_failed'
          });
          reject(error);
        }
      },
      fail(error) {
        const errMsg = getErrorMessage(error, '方案预览图上传失败');
        logRequestFailure('wx.uploadFile design preview failed:', {
          path: '/api/v1/diy-designs/preview',
          url,
          method: 'UPLOAD',
          message: errMsg
        });
        reject(new Error(error.errMsg || '方案预览图上传失败'));
      }
    });
  });
}

function bindPhone(payload) {
  return request('/api/v1/auth/phone', { method: 'POST', data: payload });
}

function getTodayDailyEnergy(userId, options = {}) {
  const query = [`user_id=${encodeURIComponent(userId)}`];
  if (options.initialWish) query.push(`initial_wish=${encodeURIComponent(options.initialWish)}`);
  (options.statusTags || []).forEach(key => query.push(`status_tags=${encodeURIComponent(key)}`));
  if (options.sceneKey) query.push(`scene_key=${encodeURIComponent(options.sceneKey)}`);
  (options.goalKeys || []).forEach(key => query.push(`goal_keys=${encodeURIComponent(key)}`));
  if (options.forceRecalculate) query.push('force_recalculate=true');
  return request(`/api/v1/daily-energy/today?${query.join('&')}`, {
    silent: !!options.silent,
    timeout: options.timeout
  });
}

function getDailyEnergyOptions() {
  return request('/api/v1/daily-energy/options');
}

function checkInDailyEnergy(payload) {
  return request('/api/v1/daily-energy/check-in', { method: 'POST', data: payload });
}

function getMaterials(options = {}) {
  const query = [];
  if (options.top) query.push(`top=${encodeURIComponent(options.top)}`);
  if (options.keyword) query.push(`keyword=${encodeURIComponent(options.keyword)}`);
  if (options.compact) query.push('compact=true');
  if (options.limit) query.push(`limit=${encodeURIComponent(options.limit)}`);
  return request(`/api/v1/materials${query.length ? `?${query.join('&')}` : ''}`, {
    silent: !!options.silent,
    timeout: options.timeout
  });
}

function getCommunityPosts(options = {}) {
  const query = [];
  if (options.limit) query.push(`limit=${encodeURIComponent(options.limit)}`);
  return request(`/api/v1/community-posts${query.length ? `?${query.join('&')}` : ''}`, {
    silent: !!options.silent,
    timeout: options.timeout
  });
}

function getHomeBanners(options = {}) {
  const query = [];
  if (options.limit) query.push(`limit=${encodeURIComponent(options.limit)}`);
  return request(`/api/v1/home-banners${query.length ? `?${query.join('&')}` : ''}`, {
    silent: !!options.silent,
    timeout: options.timeout
  });
}

function getCommunityPost(postId, options = {}) {
  return request(`/api/v1/community-posts/${encodeURIComponent(postId)}`, options);
}

function getCommunityFavorites(userId, options = {}) {
  return request(`/api/v1/community-favorites?user_id=${encodeURIComponent(userId)}`, {
    silent: !!options.silent,
    timeout: options.timeout
  });
}

function saveCommunityFavorite(payload, options = {}) {
  return request('/api/v1/community-favorites', {
    ...options,
    method: 'POST',
    data: payload
  });
}

function deleteCommunityFavorite(userId, postId, options = {}) {
  return request(
    `/api/v1/community-favorites/${encodeURIComponent(postId)}?user_id=${encodeURIComponent(userId)}`,
    { ...options, method: 'DELETE' }
  );
}

function getRecommendationPlans(options = {}) {
  const query = [];
  if (options.homeHot !== undefined) query.push(`home_hot=${options.homeHot ? 'true' : 'false'}`);
  if (options.limit) query.push(`limit=${encodeURIComponent(options.limit)}`);
  return request(`/api/v1/recommendation-plans${query.length ? `?${query.join('&')}` : ''}`, {
    silent: !!options.silent,
    timeout: options.timeout
  });
}

function getRecommendationPlan(planId, options = {}) {
  return request(`/api/v1/recommendation-plans/${encodeURIComponent(planId)}`, options);
}

function createOrder(payload) {
  return request('/api/v1/orders', { method: 'POST', data: payload });
}

function saveDIYDesign(payload) {
  return request('/api/v1/diy-designs', { method: 'POST', data: payload });
}

function getCartItems(userId, options = {}) {
  return request(`/api/v1/cart?user_id=${encodeURIComponent(userId)}`, {
    silent: !!options.silent,
    timeout: options.timeout
  });
}

function saveCartItem(payload, options = {}) {
  return request('/api/v1/cart/items', {
    ...options,
    method: 'POST',
    data: payload
  });
}

function updateCartItem(cartItemId, payload, options = {}) {
  return request(`/api/v1/cart/items/${encodeURIComponent(cartItemId)}`, {
    ...options,
    method: 'PATCH',
    data: payload
  });
}

function deleteCartItem(cartItemId, userId, options = {}) {
  return request(
    `/api/v1/cart/items/${encodeURIComponent(cartItemId)}?user_id=${encodeURIComponent(userId)}`,
    { ...options, method: 'DELETE' }
  );
}

function clearCart(userId, options = {}) {
  return request(`/api/v1/cart?user_id=${encodeURIComponent(userId)}`, {
    ...options,
    method: 'DELETE'
  });
}

function getOrders(userId) {
  return request(`/api/v1/orders?user_id=${encodeURIComponent(userId)}`);
}

function getOrder(orderId, userId) {
  return request(
    `/api/v1/orders/${encodeURIComponent(orderId)}?user_id=${encodeURIComponent(userId)}`
  );
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

function cancelOrder(orderId, userId, reason = '') {
  return request(`/api/v1/orders/${encodeURIComponent(orderId)}/cancel`, {
    method: 'POST',
    data: { user_id: userId, reason }
  });
}

function updateOrderReceiver(orderId, userId, receiver) {
  return request(`/api/v1/orders/${encodeURIComponent(orderId)}/receiver`, {
    method: 'PUT',
    data: { user_id: userId, receiver }
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
  getAssessmentOptions,
  createDIYRecommendation,
  wechatLogin,
  getUserProfile,
  saveUserProfile,
  uploadAvatar,
  uploadDesignPreview,
  bindPhone,
  getTodayDailyEnergy,
  getDailyEnergyOptions,
  checkInDailyEnergy,
  getMaterials,
  getHomeBanners,
  getCommunityPosts,
  getCommunityPost,
  getCommunityFavorites,
  saveCommunityFavorite,
  deleteCommunityFavorite,
  getRecommendationPlans,
  getRecommendationPlan,
  saveDIYDesign,
  getCartItems,
  saveCartItem,
  updateCartItem,
  deleteCartItem,
  clearCart,
  createOrder,
  getOrders,
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
};
