const { getCommunityPost } = require('../../utils/communityData');

Page({
  data: {
    post: null,
    isFavorite: false
  },

  onLoad(options) {
    const post = getCommunityPost(options.id);
    const favorites = wx.getStorageSync('communityFavorites') || [];
    this.setData({
      post,
      isFavorite: favorites.some(item => item.id === post.id)
    });
    wx.setNavigationBarTitle({ title: post.title });
  },

  toggleFavorite() {
    const post = this.data.post;
    if (!post) return;
    const favorites = wx.getStorageSync('communityFavorites') || [];
    const isFavorite = favorites.some(item => item.id === post.id);
    const nextFavorites = isFavorite
      ? favorites.filter(item => item.id !== post.id)
      : [{ id: post.id, title: post.title, tone: post.tone, recipe: post.recipe, addedAt: Date.now() }, ...favorites];
    wx.setStorageSync('communityFavorites', nextFavorites);
    this.setData({ isFavorite: !isFavorite });
    wx.showToast({ title: isFavorite ? '已取消收藏' : '已收藏', icon: 'none' });
  },

  useSame() {
    const post = this.data.post;
    if (!post) return;
    wx.setStorageSync('recommendedRecipe', post.recipe);
    wx.setStorageSync('workspacePreset', 'recommended');
    wx.switchTab({ url: '/pages/workspace/workspace' });
  }
});
