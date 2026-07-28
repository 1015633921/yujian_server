const auth = require('../../../../utils/auth');
const { getCustomDesignRequests } = require('../../../../utils/api');

const STATUS_TEXT = {
  submitted: '等待设计',
  designing: '设计中',
  proposed: '方案待确认',
  revision_requested: '等待调整',
  confirmed: '已确认',
  closed: '已结束'
};

const FILTERS = [
  { key: 'all', label: '全部' },
  { key: 'active', label: '进行中' },
  { key: 'proposed', label: '待确认' },
  { key: 'finished', label: '已完成' }
];

function formatDateTime(value) {
  if (!value) return '';
  const text = String(value).trim();
  const hasTimezone = /T|Z|\+\d\d:\d\d$/.test(text);
  const date = hasTimezone ? new Date(text) : new Date(text.replace(/-/g, '/'));
  if (Number.isNaN(date.getTime())) {
    return text.replace('T', ' ').replace(/\+\d\d:\d\d$/, '').slice(0, 16);
  }
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hour = String(date.getHours()).padStart(2, '0');
  const minute = String(date.getMinutes()).padStart(2, '0');
  return `${year}.${month}.${day} ${hour}:${minute}`;
}

function filterKeyForStatus(status) {
  if (status === 'proposed') return 'proposed';
  if (status === 'confirmed' || status === 'closed') return 'finished';
  return 'active';
}

Page({
  data: {
    loading: true,
    refreshing: false,
    loadFailed: false,
    filters: FILTERS,
    activeFilter: 'all',
    requests: [],
    visibleRequests: [],
    isLoggedIn: true
  },

  onShow() {
    this.loadRequests({ silent: this.data.requests.length > 0 });
  },

  async onPullDownRefresh() {
    await this.loadRequests({ silent: true, refreshing: true });
    wx.stopPullDownRefresh();
  },

  async loadRequests({ silent = false, refreshing = false } = {}) {
    const user = auth.getStoredUser() || {};
    if (!user.user_id) {
      this.setData({
        loading: false,
        refreshing: false,
        loadFailed: false,
        requests: [],
        visibleRequests: [],
        isLoggedIn: false
      });
      return;
    }
    this.setData({ isLoggedIn: true });
    if (!silent) this.setData({ loading: true, loadFailed: false });
    if (refreshing) this.setData({ refreshing: true });
    try {
      const rows = await getCustomDesignRequests({ silent });
      const requests = (Array.isArray(rows) ? rows : []).map(item => this.decorateRequest(item));
      this.setData({ requests, loading: false, refreshing: false, loadFailed: false });
      this.applyFilter();
    } catch (error) {
      this.setData({ loading: false, refreshing: false, loadFailed: true });
      if (!silent) wx.showToast({ title: error.message || '人工搭配记录加载失败', icon: 'none' });
    }
  },

  decorateRequest(item = {}) {
    const request = item.request || {};
    const proposals = Array.isArray(item.proposals) ? item.proposals : [];
    const latestProposal = proposals.find(proposal => proposal.status === 'active') || proposals[0] || {};
    const workbench = latestProposal.workbench || {};
    const layout = Array.isArray(workbench.layout) ? workbench.layout : [];
    const previewMaterials = layout.slice(0, 5).map((material, index) => ({
      key: `${latestProposal.proposal_id || item.request_id || 'request'}:${index}`,
      image_url: material.selected_image_url || material.image_url || ''
    })).filter(material => material.image_url);
    const status = String(item.status || 'submitted');
    const statusText = STATUS_TEXT[status] || status || '处理中';
    const actionText = status === 'proposed'
      ? '查看并确认'
      : (status === 'confirmed' ? '查看已确认方案' : '查看详情');
    const preferences = [
      request.style_preference,
      request.wrist_size_cm ? `${request.wrist_size_cm}cm` : '',
      request.bead_size_mm ? `${request.bead_size_mm}mm` : '',
      request.budget
    ].filter(Boolean);
    return {
      ...item,
      status,
      status_text: statusText,
      filter_key: filterKeyForStatus(status),
      action_text: actionText,
      updated_at_text: formatDateTime(item.updated_at || item.created_at),
      preferences_text: preferences.join(' · ') || '等待补充搭配偏好',
      proposal_title: latestProposal.title || '专属人工搭配',
      bead_count: layout.length,
      preview_materials: previewMaterials,
      has_proposal: !!latestProposal.proposal_id,
      order_id: latestProposal.order_id || ''
    };
  },

  chooseFilter(event) {
    const key = String(event.currentTarget.dataset.key || 'all');
    if (key === this.data.activeFilter) return;
    this.setData({ activeFilter: key });
    this.applyFilter();
  },

  applyFilter() {
    const activeFilter = this.data.activeFilter;
    const visibleRequests = activeFilter === 'all'
      ? this.data.requests
      : this.data.requests.filter(item => item.filter_key === activeFilter);
    this.setData({ visibleRequests });
  },

  openRequest(event) {
    const requestId = String(event.currentTarget.dataset.id || '');
    if (!requestId) return;
    wx.navigateTo({
      url: `/pages/design-service/design-service?request_id=${encodeURIComponent(requestId)}`
    });
  },

  onPreviewImageError(event) {
    const requestId = String(event.currentTarget.dataset.requestId || '');
    const materialKey = String(event.currentTarget.dataset.materialKey || '');
    if (!requestId || !materialKey) return;
    const requests = this.data.requests.map(request => (
      request.request_id === requestId
        ? {
          ...request,
          preview_materials: request.preview_materials.filter(material => material.key !== materialKey)
        }
        : request
    ));
    this.setData({ requests });
    this.applyFilter();
  },

  goAssessment() {
    wx.switchTab({ url: '/pages/assessment/assessment' });
  },

  goProfile() {
    wx.switchTab({ url: '/pages/profile/profile' });
  },

  retry() {
    this.loadRequests();
  }
});
