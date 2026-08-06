import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { apiRequest, readStoredToken, storeToken } from '@/api/client'
import type { AdminUser, LoginResult } from '@/api/types'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(readStoredToken())
  const admin = ref<AdminUser | null>(null)
  const initialized = ref(false)
  const busy = ref(false)
  const error = ref('')

  const authenticated = computed(() => Boolean(token.value && admin.value))
  const displayName = computed(() => admin.value?.display_name || admin.value?.username || '管理员')

  function clearSession(): void {
    token.value = ''
    admin.value = null
    storeToken('')
  }

  async function bootstrap(): Promise<void> {
    if (initialized.value) return
    token.value = readStoredToken()
    if (!token.value) {
      initialized.value = true
      return
    }
    try {
      admin.value = await apiRequest<AdminUser>('/api/v1/admin/me')
    } catch {
      clearSession()
    } finally {
      initialized.value = true
    }
  }

  async function login(username: string, password: string): Promise<void> {
    busy.value = true
    error.value = ''
    try {
      const result = await apiRequest<LoginResult>('/api/v1/admin/login', {
        method: 'POST',
        auth: false,
        body: JSON.stringify({ username, password }),
      })
      token.value = result.token
      admin.value = result.admin
      storeToken(result.token)
      initialized.value = true
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '登录失败，请稍后重试'
      throw cause
    } finally {
      busy.value = false
    }
  }

  async function logout(): Promise<void> {
    try {
      if (token.value) await apiRequest('/api/v1/admin/logout', { method: 'POST' })
    } finally {
      clearSession()
      initialized.value = true
    }
  }

  return {
    admin,
    authenticated,
    busy,
    clearSession,
    displayName,
    error,
    initialized,
    login,
    logout,
    bootstrap,
    token,
  }
})
