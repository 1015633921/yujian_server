Page({
  data: {
    accountDeletion: false,
    sessionFrom: 'support_center'
  },

  onLoad(options = {}) {
    const accountDeletion = options.scene === 'account_deletion';
    this.setData({
      accountDeletion,
      sessionFrom: accountDeletion ? 'account_deletion' : 'support_center'
    });
  },

  onContactTap() {
    wx.showToast({ title: '正在打开微信客服', icon: 'none', duration: 1000 });
  }
});
