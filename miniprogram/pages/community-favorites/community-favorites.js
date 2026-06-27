const { getCommunityPosts, getCommunityPost } = require('../../utils/communityData');

Page({
  data: {
    posts: []
  },

  onShow() {
    this.loadFavorites();
  },

  loadFavorites() {
    const stored = wx.getStorageSync('communityFavorites') || [];
    const seen = new Set();
    const favorites = stored.filter(item => {
      if (!item || !item.id || seen.has(item.id)) return false;
      seen.add(item.id);
      return true;
    });
    const postMap = new Map(getCommunityPosts().map(post => [post.id, post]));
    const validFavorites = favorites.filter(item => postMap.has(item.id));
    const posts = validFavorites.map(item => {
      const post = postMap.get(item.id);
      return {
        ...post,
        addedAt: item.addedAt || 0
      };
    });

    if (validFavorites.length !== stored.length) {
      wx.setStorageSync('communityFavorites', validFavorites);
    }
    this.setData({ posts });
  },

  openPost(e) {
    const id = e.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({
      url: `/pages/community-detail/community-detail?id=${id}&from=favorites`
    });
  },

  useSame(e) {
    const post = getCommunityPost(e.currentTarget.dataset.id);
    if (!post) return;
    wx.setStorageSync('recommendedRecipe', post.recipe);
    wx.setStorageSync('workspacePreset', 'recommended');
    wx.switchTab({ url: '/pages/workspace/workspace' });
  },

  removeFavorite(e) {
    const id = e.currentTarget.dataset.id;
    const post = this.data.posts.find(item => item.id === id);
    if (!post) return;
    wx.showModal({
      title: '取消收藏？',
      content: post.title,
      confirmText: '取消收藏',
      confirmColor: '#7A4E3A',
      success: res => {
        if (!res.confirm) return;
        const favorites = (wx.getStorageSync('communityFavorites') || [])
          .filter(item => item.id !== id);
        wx.setStorageSync('communityFavorites', favorites);
        this.loadFavorites();
      }
    });
  },

  goCommunity() {
    wx.navigateTo({ url: '/pages/community/community' });
  }
});
