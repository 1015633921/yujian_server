const api = require('./api');

const USER_KEY = 'currentUser';
const USER_ID_KEY = 'userId';

function getStoredUser() {
  return wx.getStorageSync(USER_KEY) || null;
}

function getUserId() {
  const user = getStoredUser();
  return (user && user.user_id) || wx.getStorageSync(USER_ID_KEY) || '';
}

function saveUser(user) {
  if (!user || !user.user_id) return null;
  wx.setStorageSync(USER_KEY, user);
  wx.setStorageSync(USER_ID_KEY, user.user_id);
  getApp().globalData.userInfo = user;
  return user;
}

function wxLoginCode() {
  return new Promise((resolve, reject) => {
    wx.login({
      success(res) {
        if (res.code) {
          resolve(res.code);
          return;
        }
        reject(new Error('wx.login 没有返回 code'));
      },
      fail: reject
    });
  });
}

async function silentLogin() {
  const cached = getStoredUser();
  if (cached && cached.user_id) return cached;
  const code = await wxLoginCode();
  const user = await api.wechatLogin({ code });
  return saveUser(user);
}

async function loginWithWechatProfile() {
  return silentLogin();
}

async function updateBasicProfile(profile) {
  const user = await silentLogin();
  const saved = await api.saveUserProfile({
    user_id: user.user_id,
    nickname: profile.nickname,
    avatar_url: profile.avatar_url,
    gender: profile.gender
  });
  return saveUser(saved);
}

function explainPhoneAuthFailure(detail) {
  const errMsg = detail && detail.errMsg ? detail.errMsg : '';
  if (errMsg.indexOf('deny') > -1 || errMsg.indexOf('cancel') > -1 || errMsg.indexOf('fail user deny') > -1) {
    return '你取消了手机号授权';
  }
  if (errMsg.indexOf('no permission') > -1 || errMsg.indexOf('permission') > -1) {
    return '小程序还没有开通手机号快速验证能力';
  }
  if (errMsg && errMsg.indexOf(':ok') === -1) {
    return `微信手机号授权失败：${errMsg}`;
  }
  return '微信没有返回手机号授权码，请用真机或体验版测试，并确认已开通手机号快速验证能力';
}

async function bindWechatPhone(event) {
  const user = await silentLogin();
  const detail = (event && event.detail) || {};
  console.log('getPhoneNumber detail:', detail);

  if (!detail.code) {
    throw new Error(explainPhoneAuthFailure(detail));
  }

  const saved = await api.bindPhone({ user_id: user.user_id, code: detail.code });
  return saveUser(saved);
}

async function bindManualPhone(phoneNumber) {
  const user = await silentLogin();
  const saved = await api.bindPhone({ user_id: user.user_id, phone_number: phoneNumber });
  return saveUser(saved);
}

async function requireLogin(message = '请先登录后继续') {
  const user = getStoredUser();
  if (user && user.user_id) return user;
  const confirmed = await new Promise((resolve) => {
    wx.showModal({
      title: '需要登录',
      content: message,
      confirmText: '去登录',
      success(res) {
        resolve(res.confirm);
      },
      fail() {
        resolve(false);
      }
    });
  });
  if (confirmed) {
    wx.switchTab({ url: '/pages/profile/profile' });
  }
  throw new Error('login_required');
}

module.exports = {
  getStoredUser,
  getUserId,
  saveUser,
  silentLogin,
  loginWithWechatProfile,
  bindWechatPhone,
  bindManualPhone,
  requireLogin,
  updateBasicProfile
};
