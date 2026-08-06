<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { environmentLabel, legacyAdminPath } from '@/runtime/environment'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const navigationOpen = ref(false)
const legacyUrl = legacyAdminPath()
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
        <span class="admin-navigation__label">当前阶段</span>
        <RouterLink
          to="/overview"
          @click="navigationOpen = false"
        >
          <span>01</span>
          经营概览
        </RouterLink>

        <RouterLink
          to="/design-requests"
          @click="navigationOpen = false"
        >
          <span>02</span>
          人工搭配
        </RouterLink>

        <RouterLink
          to="/orders"
          @click="navigationOpen = false"
        >
          <span>03</span>
          订单履约
        </RouterLink>

        <RouterLink
          to="/after-sales"
          @click="navigationOpen = false"
        >
          <span>04</span>
          售后服务
        </RouterLink>
        <RouterLink
          to="/materials"
          @click="navigationOpen = false"
        >
          <span>05</span>珠材管理
        </RouterLink>
        <RouterLink
          to="/material-directory"
          @click="navigationOpen = false"
        >
          <span>06</span>目录设置
        </RouterLink>
        <RouterLink
          to="/material-assets"
          @click="navigationOpen = false"
        >
          <span>07</span>图库处理
        </RouterLink>
        <RouterLink
          to="/ai-material-tags"
          @click="navigationOpen = false"
        >
          <span>08</span>AI 打标审核
        </RouterLink>
        <RouterLink
          to="/warehouse"
          @click="navigationOpen = false"
        >
          <span>09</span>仓库库存
        </RouterLink>

        <RouterLink
          to="/home-banners"
          @click="navigationOpen = false"
        >
          <span>10</span>首页 Banner
        </RouterLink>
        <RouterLink
          to="/community-posts"
          @click="navigationOpen = false"
        >
          <span>11</span>社区灵感
        </RouterLink>
        <RouterLink
          to="/content-blocks"
          @click="navigationOpen = false"
        >
          <span>12</span>内容板块
        </RouterLink>
        <RouterLink
          to="/users"
          @click="navigationOpen = false"
        >
          <span>13</span>用户中心
        </RouterLink>
        <RouterLink
          to="/energy-insights"
          @click="navigationOpen = false"
        >
          <span>14</span>能量数据
        </RouterLink>
        <RouterLink
          to="/daily-energy-rules"
          @click="navigationOpen = false"
        >
          <span>15</span>每日能量规则
        </RouterLink>
        <RouterLink
          to="/system-status"
          @click="navigationOpen = false"
        >
          <span>16</span>系统配置
        </RouterLink>

        <RouterLink
          to="/admin-accounts"
          @click="navigationOpen = false"
        >
          <span>17</span>管理员账号
        </RouterLink>
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
          <span>ADMIN WEB · V2</span>
          <strong>{{ environmentLabel() }}</strong>
        </div>
      </header>
      <RouterView />
    </main>
  </div>
</template>
