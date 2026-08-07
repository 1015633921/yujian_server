<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { environmentLabel, legacyAdminPath } from '@/runtime/environment'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const navigationOpen = ref(false)
const legacyUrl = legacyAdminPath()
const navigationGroups = [
  {
    label: '工作台',
    items: [{ to: { name: 'overview' }, label: '经营概览' }],
  },
  {
    label: '履约服务',
    items: [
      { to: { name: 'design-requests' }, label: '人工搭配' },
      { to: { name: 'orders' }, label: '订单履约' },
      { to: { name: 'after-sales' }, label: '售后服务' },
    ],
  },
  {
    label: '材料中心',
    items: [
      { to: { name: 'materials' }, label: '珠材管理' },
      { to: { name: 'material-directory' }, label: '材料目录' },
      { to: { name: 'material-assets' }, label: '素材处理' },
      { to: { name: 'ai-material-tags' }, label: 'AI 打标审核' },
    ],
  },
  {
    label: '用户与洞察',
    items: [
      { to: { name: 'users' }, label: '用户中心' },
      { to: { name: 'energy-insights' }, label: '能量数据' },
    ],
  },
  {
    label: '平台治理',
    items: [
      { to: { name: 'daily-energy-rules' }, label: '每日能量规则' },
      { to: { name: 'admin-accounts' }, label: '管理员账号' },
      { to: { name: 'system-status' }, label: '系统配置' },
    ],
  },
  {
    label: '其他功能',
    items: [
      { to: { name: 'warehouse' }, label: '仓库库存' },
      { to: { name: 'home-banners' }, label: '首页 Banner' },
      { to: { name: 'community-posts' }, label: '社区灵感' },
      { to: { name: 'content-blocks' }, label: '内容板块' },
    ],
  },
]
const roleLabel = computed(() => {
  const labels: Record<string, string> = {
    admin: '管理员',
    super_admin: '超级管理员',
    operator: '运营管理员',
    viewer: '只读账号',
  }
  return labels[auth.admin?.role || ''] || auth.admin?.role || '管理员'
})

async function logout(): Promise<void> {
  await auth.logout()
  await router.replace({ name: 'login' })
}
</script>

<template>
  <div
    class="admin-shell"
    :class="{ 'admin-shell--nav-open': navigationOpen }"
  >
    <button
      v-if="navigationOpen"
      class="admin-nav-mask"
      type="button"
      aria-label="关闭导航"
      @click="navigationOpen = false"
    />

    <aside class="admin-sidebar">
      <div class="admin-brand">
        <span class="admin-brand__seal">涧</span>
        <span>
          <strong>宇涧运营后台</strong>
          <small>YUJIAN OPERATIONS</small>
        </span>
      </div>

      <nav
        class="admin-navigation"
        aria-label="新版后台导航"
      >
        <template
          v-for="group in navigationGroups"
          :key="group.label"
        >
          <span class="admin-navigation__label">{{ group.label }}</span>
          <RouterLink
            v-for="item in group.items"
            :key="item.label"
            :to="item.to"
            @click="navigationOpen = false"
          >
            {{ item.label }}
          </RouterLink>
        </template>
      </nav>

      <div class="admin-sidebar__foot">
        <a :href="legacyUrl">进入当前正式后台 <span>↗</span></a>
        <div class="admin-profile">
          <span>{{ auth.displayName.slice(0, 1) }}</span>
          <div>
            <strong>{{ auth.displayName }}</strong>
            <small>{{ roleLabel }}</small>
          </div>
          <button
            type="button"
            title="退出登录"
            @click="logout"
          >
            退出
          </button>
        </div>
      </div>
    </aside>

    <main class="admin-main">
      <header class="admin-topbar">
        <button
          class="admin-menu-button"
          type="button"
          @click="navigationOpen = true"
        >
          导航
        </button>
        <div>
          <span>运营工作台</span>
          <strong>{{ environmentLabel() }}</strong>
        </div>
      </header>
      <RouterView />
    </main>
  </div>
</template>
