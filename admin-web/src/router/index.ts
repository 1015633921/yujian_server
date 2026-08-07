import { createRouter, createWebHistory } from 'vue-router'

import { pinia } from '@/app/pinia'
import { adminRouterBase } from '@/runtime/environment'
import { useAuthStore } from '@/stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    public?: boolean
    title?: string
  }
}

const router = createRouter({
  history: createWebHistory(adminRouterBase()),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true, title: '登录' },
    },
    {
      path: '/',
      component: () => import('@/layouts/AdminLayout.vue'),
      children: [
        {
          path: '',
          redirect: { name: 'overview' },
        },
        {
          path: 'overview',
          name: 'overview',
          component: () => import('@/views/OverviewView.vue'),
          meta: { title: '经营概览' },
        },
        {
          path: 'design-requests',
          name: 'design-requests',
          component: () => import('@/views/CustomDesignRequestsView.vue'),
          meta: { title: '人工搭配' },
        },
        {
          path: 'design-requests/:requestId',
          name: 'design-request-detail',
          component: () => import('@/views/CustomDesignRequestDetailView.vue'),
          meta: { title: '人工搭配工单' },
        },
        {
          path: 'design-requests/:requestId/workbench',
          name: 'design-request-workbench',
          component: () => import('@/views/CustomDesignWorkbenchView.vue'),
          meta: { title: '设计师工作台' },
        },
        {
          path: 'orders',
          name: 'orders',
          component: () => import('@/views/OrdersView.vue'),
          meta: { title: '订单履约' },
        },
        {
          path: 'orders/:orderId',
          name: 'order-detail',
          component: () => import('@/views/OrderDetailView.vue'),
          meta: { title: '订单履约详情' },
        },
        {
          path: 'after-sales',
          name: 'after-sales',
          component: () => import('@/views/AfterSalesView.vue'),
          meta: { title: '售后服务' },
        },
        {
          path: 'after-sales/:caseId',
          name: 'after-sale-detail',
          component: () => import('@/views/AfterSaleDetailView.vue'),
          meta: { title: '售后工单' },
        },
        {
          path: 'material-directory',
          name: 'material-directory',
          component: () => import('@/views/MaterialDirectoryView.vue'),
          meta: { title: '材料三级目录' },
        },
        {
          path: 'material-directory/series/:seriesId',
          name: 'material-series-profile',
          component: () => import('@/views/MaterialSeriesProfileView.vue'),
          meta: { title: '品种资料' },
        },
        {
          path: 'material-assets',
          name: 'material-assets',
          component: () => import('@/views/MaterialAssetsView.vue'),
          meta: { title: '素材处理' },
        },
        {
          path: 'ai-material-tags',
          name: 'ai-material-tags',
          component: () => import('@/views/AiMaterialTagsView.vue'),
          meta: { title: 'AI 打标审核' },
        },
        {
          path: 'warehouse',
          name: 'warehouse',
          component: () => import('@/views/WarehouseView.vue'),
          meta: { title: '仓库库存' },
        },
        {
          path: 'home-banners',
          name: 'home-banners',
          component: () => import('@/views/HomeBannersView.vue'),
          meta: { title: '首页 Banner' },
        },
        {
          path: 'community-posts',
          name: 'community-posts',
          component: () => import('@/views/CommunityPostsView.vue'),
          meta: { title: '社区灵感' },
        },
        {
          path: 'content-blocks',
          name: 'content-blocks',
          component: () => import('@/views/ContentBlocksView.vue'),
          meta: { title: '内容板块' },
        },
        { path: 'users', name: 'users', component: () => import('@/views/UsersView.vue'), meta: { title: '用户中心' } },
        { path: 'users/:userId', name: 'user-detail', component: () => import('@/views/UserDetailView.vue'), meta: { title: '用户详情' } },
        { path: 'energy-insights/assessment/:assessmentId', name: 'energy-assessment-detail', component: () => import('@/views/EnergyDetailView.vue'), meta: { title: '测算记录详情', energyKind: 'assessment' } },
        { path: 'energy-insights/daily/:userId/:energyDate', name: 'energy-daily-detail', component: () => import('@/views/EnergyDetailView.vue'), meta: { title: '每日能量详情', energyKind: 'daily' } },
        { path: 'energy-insights/checkin/:userId/:checkinDate', name: 'energy-checkin-detail', component: () => import('@/views/EnergyDetailView.vue'), meta: { title: '签到记录详情', energyKind: 'checkin' } },
        { path: 'energy-insights', name: 'energy-insights', component: () => import('@/views/EnergyInsightsView.vue'), meta: { title: '能量数据' } },
        { path: 'daily-energy-rules', name: 'daily-energy-rules', component: () => import('@/views/DailyRulesView.vue'), meta: { title: '每日能量规则' } },
        { path: 'system-status', name: 'system-status', component: () => import('@/views/SystemStatusView.vue'), meta: { title: '系统配置' } },
        { path: 'admin-accounts', name: 'admin-accounts', component: () => import('@/views/AdminAccountsView.vue'), meta: { title: '管理员账号' } },
        { path: 'materials', name: 'materials', component: () => import('@/views/MaterialsView.vue'), meta: { title: '材料 SKU' } },
        { path: 'materials/:materialId', name: 'material-detail', component: () => import('@/views/MaterialDetailView.vue'), meta: { title: '材料 SKU 详情' } },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFoundView.vue'),
      meta: { public: true, title: '页面不存在' },
    },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async (to) => {
  const auth = useAuthStore(pinia)
  await auth.bootstrap()

  document.title = `${to.meta.title || '运营后台'} · 宇涧`

  if (to.meta.public) {
    if (to.name === 'login' && auth.authenticated) return { name: 'overview' }
    return true
  }
  if (!auth.authenticated) {
    return {
      name: 'login',
      query: { redirect: to.fullPath },
    }
  }
  return true
})

export default router
