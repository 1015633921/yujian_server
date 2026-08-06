<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const username = ref('')
const password = ref('')
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

async function submit(): Promise<void> {
  if (!username.value.trim() || !password.value) return
  try {
    await auth.login(username.value.trim(), password.value)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/overview'
    await router.replace(redirect)
  } catch {
    // The store exposes a safe user-facing message without logging credentials.
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-brand">
      <div class="login-brand__mark">
        涧
      </div>
      <div>
        <span>YUJIAN CRYSTAL STUDIO</span>
        <h1>把复杂运营，整理成清晰秩序。</h1>
        <p>新版后台采用独立路由与模块化工作区，当前与旧版并行验证。</p>
      </div>
      <small>LIGHT STUDIO LAB · 2026</small>
    </section>

    <section class="login-panel">
      <form @submit.prevent="submit">
        <div class="login-panel__heading">
          <span>OPERATIONS CENTER</span>
          <h2>登录运营后台</h2>
          <p>使用现有管理员账号，权限和数据均来自当前后端。</p>
        </div>

        <label>
          <span>管理员账号</span>
          <input
            v-model="username"
            name="username"
            autocomplete="username"
            autofocus
          >
        </label>
        <label>
          <span>密码</span>
          <input
            v-model="password"
            name="password"
            type="password"
            autocomplete="current-password"
          >
        </label>

        <p
          v-if="auth.error"
          class="form-error"
          role="alert"
        >
          {{ auth.error }}
        </p>
        <button
          type="submit"
          :disabled="auth.busy || !username.trim() || !password"
        >
          <span>{{ auth.busy ? '正在验证' : '进入后台' }}</span>
          <i aria-hidden="true">→</i>
        </button>
      </form>
    </section>
  </main>
</template>
