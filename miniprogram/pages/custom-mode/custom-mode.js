const MODE_STORAGE_KEY = 'customMode';

const MODES = [
  {
    id: 'wuxing',
    title: '五行定制',
    desc: '根据出生信息建立五行画像，平衡能量，改善趋势',
    badge: '五',
    tone: 'green',
    type: 'switchTab',
    url: '/pages/assessment/assessment'
  },
  {
    id: 'astro',
    title: '星座灵感',
    desc: '结合星座气质与佩戴场景，发现更适合你的水晶',
    badge: '☆',
    tone: 'purple',
    type: 'switchTab',
    url: '/pages/assessment/assessment'
  },
  {
    id: 'mbti',
    title: 'MBTI 定制',
    desc: '解析性格倾向，匹配你的能量主石与配色',
    badge: 'M',
    tone: 'blue',
    type: 'switchTab',
    url: '/pages/assessment/assessment'
  },
  {
    id: 'aesthetic',
    title: '审美定制',
    desc: '先从灵感库选择喜欢的风格，再进入 DIY 调整',
    badge: '♎',
    tone: 'gold',
    type: 'navigate',
    url: '/pages/community/community'
  },
  {
    id: 'free',
    title: '自由 DIY',
    desc: '不设限制，自由搭配，创造独一无二的手串',
    badge: '□',
    tone: 'dark',
    type: 'switchTab',
    url: '/pages/workspace/workspace'
  }
];

Page({
  data: {
    modes: MODES
  },

  goBack() {
    const pages = getCurrentPages();
    if (pages.length > 1) {
      wx.navigateBack();
      return;
    }
    wx.switchTab({ url: '/pages/home/home' });
  },

  selectMode(e) {
    const id = e.currentTarget.dataset.id;
    const mode = MODES.find(item => item.id === id);
    if (!mode) return;

    wx.setStorageSync(MODE_STORAGE_KEY, {
      id: mode.id,
      title: mode.title,
      selectedAt: Date.now()
    });

    if (mode.type === 'switchTab') {
      wx.switchTab({ url: mode.url });
      return;
    }
    wx.navigateTo({ url: mode.url });
  }
});
