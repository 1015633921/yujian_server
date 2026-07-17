const auth = require('../../utils/auth');
const { confirmWebLoginPairing } = require('../../utils/api');

const PAIRING_ID_PATTERN = /^wp_[A-Za-z0-9_-]{20,80}$/;
const VERIFICATION_CODE_PATTERN = /^[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{8}$/;

function currentSession() {
  const user = auth.getStoredUser();
  const isLoggedIn = !!(user && user.user_id && auth.hasUsableSession());
  return { user: isLoggedIn ? user : null, isLoggedIn };
}

function errorState(error) {
  if (error && error.statusCode === 410) {
    return {
      status: 'expired',
      errorText: '这组登录信息已过期，请回到电脑端重新获取。'
    };
  }
  if (error && error.statusCode === 409) {
    return {
      status: 'error',
      errorText: '这组登录信息已确认或已使用，请回到电脑端查看。'
    };
  }
  if (error && error.statusCode === 404) {
    return {
      status: 'error',
      errorText: '配对编号或验证码不正确，请核对后重试。'
    };
  }
  if (error && error.statusCode === 503) {
    return {
      status: 'error',
      errorText: '网页登录确认暂未开放，请稍后再试。'
    };
  }
  if (error && (error.statusCode === 401 || error.message === 'login_required')) {
    return {
      status: 'error',
      errorText: '登录状态已失效，请重新登录后再确认。'
    };
  }
  return {
    status: 'error',
    errorText: '确认失败，请检查网络后重试。'
  };
}

Page({
  data: {
    user: null,
    isLoggedIn: false,
    authLoading: false,
    submitting: false,
    pairingId: '',
    verificationCode: '',
    status: 'idle',
    errorText: ''
  },

  onShow() {
    this.setData(currentSession());
  },

  onPairingIdInput(e) {
    this.setData({
      pairingId: String(e.detail.value || '').trim(),
      status: 'idle',
      errorText: ''
    });
  },

  onVerificationCodeInput(e) {
    const verificationCode = String(e.detail.value || '')
      .toUpperCase()
      .replace(/[^A-Z0-9]/g, '')
      .slice(0, 8);
    this.setData({ verificationCode, status: 'idle', errorText: '' });
  },

  async loginWithWechat() {
    if (this.data.authLoading) return;
    this.setData({ authLoading: true, status: 'idle', errorText: '' });
    try {
      await auth.loginWithWechatProfile();
      this.setData(currentSession());
      wx.showToast({ title: '登录成功', icon: 'success' });
    } catch (error) {
      this.setData(errorState(error));
    } finally {
      this.setData({ authLoading: false });
    }
  },

  validateInput() {
    if (!PAIRING_ID_PATTERN.test(this.data.pairingId)) {
      return '请输入电脑端完整显示的 pairing_id。';
    }
    if (!VERIFICATION_CODE_PATTERN.test(this.data.verificationCode)) {
      return '请输入电脑端显示的 8 位验证码。';
    }
    return '';
  },

  confirmIntent() {
    return new Promise(resolve => {
      wx.showModal({
        title: '确认网页登录',
        content: '仅当你本人刚刚在宇涧网站发起登录时确认。不要替他人输入，也不要把验证码发送给别人。',
        confirmText: '确认登录',
        cancelText: '取消',
        success: result => resolve(!!result.confirm),
        fail: () => resolve(false)
      });
    });
  },

  async submitConfirmation() {
    if (this.data.submitting) return;
    const inputError = this.validateInput();
    if (inputError) {
      this.setData({ status: 'error', errorText: inputError });
      return;
    }

    if (!this.data.isLoggedIn) {
      this.setData({
        status: 'error',
        errorText: '请先登录当前微信账号，再确认网页登录。'
      });
      return;
    }

    const confirmed = await this.confirmIntent();
    if (!confirmed) return;

    this.setData({ submitting: true, status: 'loading', errorText: '' });
    try {
      await auth.requireLogin('登录后才能确认网页登录。');
      await confirmWebLoginPairing(
        this.data.pairingId,
        this.data.verificationCode,
        { silent: true, showModal: false, timeout: 8000 }
      );
      this.setData({
        pairingId: '',
        verificationCode: '',
        status: 'success',
        errorText: ''
      });
    } catch (error) {
      this.setData(errorState(error));
    } finally {
      this.setData({ submitting: false });
    }
  },

  resetForm() {
    this.setData({
      pairingId: '',
      verificationCode: '',
      status: 'idle',
      errorText: ''
    });
  },

  goBack() {
    if (getCurrentPages().length > 1) {
      wx.navigateBack();
      return;
    }
    wx.switchTab({ url: '/pages/profile/profile' });
  }
});
