<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref } from 'vue'

import PageEmptyState from '@/components/ui/PageEmptyState.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import ActionConfirmDialog from '@/components/ui/ActionConfirmDialog.vue'
import {
  createAdmin,
  disableAdmin,
  listAdmins,
  listLoginLogs,
  updateAdmin,
  type AdminAccountInput,
  type LoginLog,
  type ManagedAdmin,
} from '@/features/users/api'
import { useAuthStore } from '@/stores/auth'

interface AdminEditor {
  adminId: string
  username: string
  displayName: string
  role: ManagedAdmin['role']
  status: ManagedAdmin['status']
  password: string
}

const auth = useAuthStore()
const accounts = ref<ManagedAdmin[]>([])
const loginLogs = ref<LoginLog[]>([])
const keyword = ref('')
const selectedId = ref('')
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const notice = ref('')
const disableConfirmOpen = ref(false)
const editor = reactive<AdminEditor>({ adminId: '', username: '', displayName: '', role: 'operator', status: 'active', password: '' })
let controller: AbortController | null = null

const canManage = computed(() => ['admin', 'super_admin', 'owner'].includes(auth.admin?.role || ''))
const currentAdminId = computed(() => auth.admin?.admin_id || '')
const selected = computed(() => accounts.value.find((item) => item.admin_id === selectedId.value) || null)
const visibleAccounts = computed(() => {
  const term = keyword.value.trim().toLowerCase()
  if (!term) return accounts.value
  return accounts.value.filter((item) => [item.username, item.display_name, item.role, item.status, item.last_login_ip].some((value) => String(value || '').toLowerCase().includes(term)))
})
const visibleLogs = computed(() => {
  const term = keyword.value.trim().toLowerCase()
  if (!term) return loginLogs.value
  return loginLogs.value.filter((item) => [item.username, item.ip, item.user_agent, item.reason].some((value) => String(value || '').toLowerCase().includes(term)))
})

function roleLabel(value: string): string { return ({ admin: '管理员', operator: '运营', viewer: '只读' })[value] || value || '—' }
function statusLabel(value: string): string { return ({ active: '启用', disabled: '停用' })[value] || value || '—' }
function reasonLabel(value: string): string { return ({ success: '登录成功', invalid_payload: '参数异常', unknown_user: '账号不存在', bad_password: '密码错误', locked_bad_password: '失败过多已锁定', locked: '账号锁定中', disabled: '账号已停用' })[value] || value || '—' }
function timeLabel(value?: string): string { return value ? value.replace('T', ' ').slice(0, 16) : '—' }
function maskedIp(value?: string): string { const ip = String(value || '').trim(); const parts = ip.split('.'); return parts.length === 4 ? `${parts[0]}.${parts[1]}.*.*` : ip ? '已记录' : '—' }
function deviceLabel(value?: string): string { const agent = String(value || ''); if (!agent) return '—'; const platform = /Windows/i.test(agent) ? 'Windows' : /Macintosh|Mac OS/i.test(agent) ? 'Mac' : /iPhone|iPad/i.test(agent) ? 'iOS' : /Android/i.test(agent) ? 'Android' : '其他设备'; const client = /MicroMessenger/i.test(agent) ? '微信' : /Chrome/i.test(agent) ? 'Chrome' : /Safari/i.test(agent) ? 'Safari' : '浏览器'; return `${platform} · ${client}` }

function resetEditor(): void {
  selectedId.value = ''
  Object.assign(editor, { adminId: '', username: '', displayName: '', role: 'operator', status: 'active', password: '' })
  notice.value = ''
}

function editAccount(item: ManagedAdmin): void {
  selectedId.value = item.admin_id
  Object.assign(editor, { adminId: item.admin_id, username: item.username, displayName: item.display_name || item.username, role: item.role, status: item.status, password: '' })
  notice.value = ''
}

async function load(): Promise<void> {
  if (!canManage.value) { loading.value = false; return }
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  try {
    const [nextAccounts, nextLogs] = await Promise.all([listAdmins(controller.signal), listLoginLogs(controller.signal)])
    accounts.value = nextAccounts
    loginLogs.value = nextLogs
    if (selectedId.value && !nextAccounts.some((item) => item.admin_id === selectedId.value)) resetEditor()
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') return
    error.value = cause instanceof Error ? cause.message : '管理员资料加载失败'
  } finally {
    loading.value = false
  }
}

function input(): AdminAccountInput {
  return { display_name: editor.displayName.trim(), role: editor.role, status: editor.status, password: editor.password || undefined }
}

async function save(): Promise<void> {
  if (!canManage.value || saving.value) return
  if (!editor.adminId && !editor.username.trim()) { notice.value = '请填写登录账号。'; return }
  if (!editor.adminId && !editor.password) { notice.value = '请设置初始密码。'; return }
  if (editor.password && (!/[A-Za-z]/.test(editor.password) || !/\d/.test(editor.password) || editor.password.length < 8 || editor.password.length > 80 || /\s/.test(editor.password))) { notice.value = '密码需为 8–80 位，同时含字母和数字，且不能包含空格。'; return }
  if (editor.adminId === currentAdminId.value && editor.status === 'disabled') { notice.value = '不能停用当前登录账号。'; return }
  saving.value = true
  notice.value = ''
  try {
    if (editor.adminId) {
      await updateAdmin(editor.adminId, input())
      notice.value = '管理员账号已更新。'
    } else {
      await createAdmin({ ...input(), username: editor.username.trim(), password: editor.password })
      notice.value = '管理员账号已创建。'
    }
    await load()
  } catch (cause) {
    notice.value = cause instanceof Error ? cause.message : '管理员账号保存失败。'
  } finally {
    saving.value = false
  }
}

function requestDisable(): void {
  if (!canManage.value || !selected.value || saving.value) return
  if (selected.value.admin_id === currentAdminId.value) { notice.value = '不能停用当前登录账号。'; return }
  disableConfirmOpen.value = true
}

async function disable(): Promise<void> {
  if (!canManage.value || !selected.value || saving.value) return
  saving.value = true
  notice.value = ''
  try {
    await disableAdmin(selected.value.admin_id)
    disableConfirmOpen.value = false
    resetEditor()
    await load()
    notice.value = '管理员账号已停用。'
  } catch (cause) {
    notice.value = cause instanceof Error ? cause.message : '管理员账号停用失败。'
  } finally {
    saving.value = false
  }
}

onBeforeUnmount(() => controller?.abort())
void load()
</script>

<template>
  <section class="workspace-page admin-accounts">
    <PageHeading
      eyebrow="ADMIN SECURITY"
      title="管理员账号"
      description="创建子账号、控制角色与停用状态，并查看最近的后台登录留痕。密码不会在后台展示。"
    >
      <template #actions>
        <button
          v-if="canManage"
          class="heading-link"
          type="button"
          @click="resetEditor"
        >
          新增账号
        </button>
        <button
          class="heading-link"
          type="button"
          :disabled="loading"
          @click="load"
        >
          {{ loading ? '刷新中…' : '刷新数据' }}
        </button>
      </template>
    </PageHeading>

    <div
      v-if="!canManage"
      class="admin-accounts__restricted"
    >
      <span>RESTRICTED</span>
      <h2>当前账号没有管理员账号管理权限</h2>
      <p>管理员账号、密码重置和登录留痕仅对管理员角色开放。</p>
    </div>

    <template v-else>
      <div class="admin-accounts__tools">
        <input
          v-model.trim="keyword"
          placeholder="搜索账号、角色或状态"
        >
        <small>{{ visibleAccounts.length }} 个账号 · {{ visibleLogs.length }} 条登录记录</small>
      </div>

      <PageErrorState
        v-if="error && !loading"
        title="管理员资料暂时无法读取"
        :message="error"
        eyebrow="ADMIN SECURITY UNAVAILABLE"
        @retry="load"
      />

      <div
        v-else
        class="admin-accounts__workspace"
      >
        <div class="admin-accounts__list">
          <div class="admin-accounts__list-head">
            <span>账号</span><span>角色</span><span>状态</span><span>最近登录</span>
          </div>
          <div
            v-if="loading"
            class="admin-accounts__skeleton"
          >
            <i
              v-for="item in 5"
              :key="item"
            />
          </div>
          <PageEmptyState
            v-else-if="!visibleAccounts.length"
            title="没有符合条件的管理员账号"
            message="可新增一个运营或只读子账号。"
          />
          <button
            v-for="item in visibleAccounts"
            v-else
            :key="item.admin_id"
            :class="{ 'is-current': selectedId === item.admin_id }"
            type="button"
            @click="editAccount(item)"
          >
            <p><strong>{{ item.display_name || item.username }}</strong><small>{{ item.username }}</small></p><span>{{ roleLabel(item.role) }}</span><b :class="item.status === 'active' ? 'is-active' : 'is-disabled'">{{ statusLabel(item.status) }}</b><small>{{ timeLabel(item.last_login_at) }}</small>
          </button>
        </div>

        <form
          class="admin-accounts__editor"
          @submit.prevent="save"
        >
          <header>
            <div><span>{{ editor.adminId ? 'EDIT ADMIN ACCOUNT' : 'NEW ADMIN ACCOUNT' }}</span><h2>{{ editor.adminId ? '编辑管理员账号' : '新增管理员子账号' }}</h2></div>
            <button
              v-if="editor.adminId && selected?.status === 'active' && selected.admin_id !== currentAdminId"
              type="button"
              :disabled="saving"
              @click="requestDisable"
            >
              停用账号
            </button>
          </header>
          <p class="admin-accounts__hint">
            日常运营优先使用“运营”角色；密码仅以加盐哈希保存，不会在此处回显。
          </p>
          <label>登录账号<input
            v-model.trim="editor.username"
            :disabled="Boolean(editor.adminId) || saving"
            autocomplete="username"
            maxlength="40"
            placeholder="例如 ops_01"
            required
          ></label><label>显示名称<input
            v-model.trim="editor.displayName"
            :disabled="saving"
            maxlength="120"
            placeholder="例如 日常运营"
          ></label><label>角色<select
            v-model="editor.role"
            :disabled="saving"
          ><option value="admin">管理员</option><option value="operator">运营</option><option value="viewer">只读</option></select></label><label>账号状态<select
            v-model="editor.status"
            :disabled="saving || editor.adminId === currentAdminId"
          ><option value="active">启用</option><option value="disabled">停用</option></select></label><label class="admin-accounts__full">{{ editor.adminId ? '重置密码（留空则不修改）' : '初始密码' }}<input
            v-model="editor.password"
            :disabled="saving"
            :required="!editor.adminId"
            autocomplete="new-password"
            maxlength="80"
            minlength="8"
            placeholder="8–80 位，需同时包含字母和数字"
            type="password"
          ></label>
          <footer>
            <button
              class="primary-action"
              :disabled="saving"
              type="submit"
            >
              {{ saving ? '保存中…' : editor.adminId ? '保存账号' : '创建账号' }}
            </button><p>{{ notice }}</p>
          </footer>
        </form>
      </div>

      <section class="admin-login-logs">
        <header><div><span>RECENT LOGIN TRACE</span><h2>最近登录留痕</h2></div><small>仅展示最近 120 条记录</small></header>
        <div class="admin-login-logs__list">
          <div><span>时间</span><span>账号</span><span>结果</span><span>IP</span><span>设备</span></div>
          <PageEmptyState
            v-if="!loading && !visibleLogs.length"
            title="暂无登录留痕"
            message="后台登录后会自动记录结果与设备信息。"
          />
          <article
            v-for="item in visibleLogs"
            :key="item.log_id"
          >
            <time>{{ timeLabel(item.created_at) }}</time><strong>{{ item.username || '—' }}</strong><b :class="item.success ? 'is-success' : 'is-failed'">{{ reasonLabel(item.reason) }}</b><span>{{ maskedIp(item.ip) }}</span><small>{{ deviceLabel(item.user_agent) }}</small>
          </article>
        </div>
      </section>
      <ActionConfirmDialog
        :open="disableConfirmOpen"
        title="停用管理员账号"
        :description="`账号「${selected?.display_name || selected?.username || '—'}」将立即无法登录后台；已有会话将在下次鉴权时失效。`"
        confirm-label="确认停用"
        tone="danger"
        :busy="saving"
        @close="disableConfirmOpen = false"
        @confirm="disable"
      />
    </template>
  </section>
</template>
