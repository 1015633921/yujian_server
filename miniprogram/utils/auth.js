const api = require('./api');

const USER_KEY = 'currentUser';
const USER_ID_KEY = 'userId';

function getStoredUser() {
  return wx.getStorageSync(USER_KEY) || null;
}

function getUserId() {
  const user = getStoredUser();
  const userId = (user && user.user_id) || wx.getStorageSync(USER_ID_KEY) || '';
  return String(userId).startsWith('dev_') ? '' : userId;
}

function isRealWechatUser(user) {
  return !!(
    user
    && user.user_id
    && user.openid
    && !String(user.user_id).startsWith('dev_')
    && !String(user.openid).startsWith('dev_')
  );
}

function saveUser(user) {
  if (!user || !user.user_id) return null;
  wx.setStorageSync(USER_KEY, user);
  wx.setStorageSync(USER_ID_KEY, user.user_id);
  getApp().globalData.userInfo = user;
  return user;
}

function isLocalAvatarPath(value) {
  const avatarUrl = String(value || '').trim();
  if (!avatarUrl) return false;
  const lower = avatarUrl.toLowerCase();
  return (
    lower.indexOf('wxfile://') === 0
    || lower.indexOf('file://') === 0
    || lower.indexOf('http://tmp/') === 0
    || lower.indexOf('https://tmp/') === 0
    || lower.indexOf('/tmp/') === 0
  );
}

function logout() {
  wx.removeStorageSync(USER_KEY);
  wx.removeStorageSync(USER_ID_KEY);
  wx.removeStorageSync('orders');
  wx.removeStorageSync('communityFavorites');
  wx.removeStorageSync('diyDesignCart');
  wx.removeStorageSync('inspirationCart');
  try {
    const app = getApp();
    if (app && app.globalData) app.globalData.userInfo = null;
  } catch (error) {
    // The local login state has already been cleared.
  }
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
  const storedUserId = wx.getStorageSync(USER_ID_KEY) || '';
  if (isRealWechatUser(cached)) return cached;
  if (
    (cached && String(cached.user_id || '').startsWith('dev_'))
    || String(storedUserId).startsWith('dev_')
  ) {
    wx.removeStorageSync(USER_KEY);
    wx.removeStorageSync(USER_ID_KEY);
  }
  const code = await wxLoginCode();
  const user = await api.wechatLogin({ code }, { silent: true, timeout: 8000 });
  return saveUser(user);
}

async function loginWithWechatProfile() {
  return silentLogin();
}

async function updateBasicProfile(profile) {
  const user = await silentLogin();
  let avatarUrl = profile.avatar_url || '';
  const avatarChanged = !!profile.avatar_changed;
  if (avatarUrl && isLocalAvatarPath(avatarUrl)) {
    const uploaded = await api.uploadAvatar(avatarUrl, user.user_id);
    avatarUrl = uploaded.avatar_url;
  }
  const payload = {
    user_id: user.user_id,
    nickname: profile.nickname,
    gender: profile.gender
  };
  if (avatarChanged) {
    payload.avatar_url = avatarUrl;
  }
  const saved = await api.saveUserProfile(payload);
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

  if (!detail.code) {
    throw new Error(explainPhoneAuthFailure(detail));
  }

  const saved = await api.bindPhone({ user_id: user.user_id, code: detail.code });
  return saveUser(saved);
}

async function requireLogin(message = '请先登录后继续') {
  const user = getStoredUser();
  if (isRealWechatUser(user)) return user;
  try {
    return await silentLogin();
  } catch (error) {
    console.warn('refresh wechat login failed:', error.message || error);
  }
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
  logout,
  silentLogin,
  loginWithWechatProfile,
  bindWechatPhone,
  requireLogin,
  updateBasicProfile
};
