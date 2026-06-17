const { getCommunityPosts } = require('../../utils/communityData');

Page({
  data: {
    posts: getCommunityPosts().slice(0, 3),
    lessons: [
      { title: '第一次戴水晶需要消磁吗？', desc: '清水、月光、白水晶碎石的适用场景。' },
      { title: '如何根据手围选择珠径？', desc: '8mm 更日常，10mm 存在感更强。' },
      { title: '五行缺什么就戴什么吗？', desc: '更建议补弱项，同时压住过强项。' }
    ]
  },

  openPost(e) {
    const id = e.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({ url: `/pages/community-detail/community-detail?id=${id}` });
  },

  useSame(e) {
    const id = e.currentTarget.dataset.id;
    const post = this.data.posts.find(item => item.id === id);
    if (!post) return;
    wx.setStorageSync('recommendedRecipe', post.recipe);
    wx.setStorageSync('workspacePreset', 'recommended');
    wx.switchTab({ url: '/pages/workspace/workspace' });
  }
});
