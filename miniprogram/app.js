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

    // 先让首页完成首屏绘制，再刷新登录态，避免新用户首次进入时
    // 登录请求和图片、页面脚本同时争用网络与主线程。
    setTimeout(() => {
      auth.silentLogin().catch((error) => {
        console.warn('silent login skipped:', error.message || error);
      });
    }, 1200);
  },
  globalData: {
    userInfo: null
  }
});
