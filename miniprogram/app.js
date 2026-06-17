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

    const logs = wx.getStorageSync('logs') || [];
    logs.unshift(Date.now());
    wx.setStorageSync('logs', logs);

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

    auth.silentLogin().catch((error) => {
      console.warn('silent login skipped:', error.message || error);
    });
  },
  globalData: {
    userInfo: null
  }
});
