App({
  onLaunch() {
    const { cloudEnvId, useAnyService } = require('./config/env');
    const auth = require('./utils/auth');
    if (useAnyService && wx.cloud) {
      const cloudOptions = { traceUser: true };
      if (cloudEnvId) {
        cloudOptions.env = cloudEnvId;
      }
      wx.cloud.init(cloudOptions);
    }

    const storedSessionUser = auth.getStoredUser && auth.getStoredUser();
    if (storedSessionUser && !auth.hasUsableSession()) {
      auth.clearPrivateCaches();
    }

    if (!wx.getStorageSync('energyProfile')) {
      wx.setStorageSync('energyProfile', {
        name: '新朋友',
        mbti: 'INFP',
        title: '温柔直觉型守护者',
        luckyColor: '海盐蓝',
        luckyNumber: 7,
        luckyStone: '海蓝宝',
        vitality: 82,
        inspiration: 94
      });
    }

    // Let the first screen render before refreshing an existing login session.
    // New users log in only when they tap a feature that needs identity.
    setTimeout(() => {
      const storedUser = auth.getStoredUser && auth.getStoredUser();
      if (
        !storedUser
        || !storedUser.user_id
        || !auth.hasUsableSession()
      ) return;
      auth.silentLogin().catch((error) => {
        console.warn('silent login skipped:', error.message || error);
      });
    }, 1200);
  },
  globalData: {
    userInfo: null
  }
});
