<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import PageEmptyState from '@/components/ui/PageEmptyState.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import { listUsers, type AdminUser } from '@/features/users/api'
const router = useRouter(); const rows = ref<AdminUser[]>([]); const keyword = ref(''); const profileStatus = ref(''); const energyTag = ref(''); const spendLevel = ref(''); const startDate = ref(''); const endDate = ref(''); const loading = ref(true); const error = ref(''); let controller: AbortController | null = null; let debounceTimer: ReturnType<typeof setTimeout> | null = null
const money = (value = 0) => new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY', maximumFractionDigits: 0 }).format(value)
function maskedIdentity(item: AdminUser): string { const phone = String(item.phone_number || '').trim(); if (/^\d{11}$/.test(phone)) return `${phone.slice(0, 3)}****${phone.slice(-4)}`; const id = String(item.user_id || ''); return id.length > 8 ? `用户 ID · ${id.slice(0, 3)}…${id.slice(-4)}` : '未绑定手机号' }
async function load(): Promise<void> { controller?.abort(); controller = new AbortController(); loading.value = true; error.value = ''; try { rows.value = await listUsers({ keyword: keyword.value, profileStatus: profileStatus.value, energyTag: energyTag.value, spendLevel: spendLevel.value, startDate: startDate.value, endDate: endDate.value }, controller.signal) } catch (cause) { if (!(cause instanceof DOMException && cause.name === 'AbortError')) error.value = cause instanceof Error ? cause.message : '用户列表加载失败' } finally { loading.value = false } }
watch([keyword, profileStatus, energyTag, spendLevel, startDate, endDate], () => { if (debounceTimer) clearTimeout(debounceTimer); debounceTimer = setTimeout(() => void load(), 260) }); onBeforeUnmount(() => { controller?.abort(); if (debounceTimer) clearTimeout(debounceTimer) }); void load()
</script>
<template>
  <section class="workspace-page users-page">
    <PageHeading
      eyebrow="CUSTOMER CENTER"
      title="用户中心"
      description="查看小程序用户资料、最近能量画像与消费概览。"
    >
      <template #actions>
        <button
          class="heading-link"
          type="button"
          @click="load"
        >
          刷新数据
        </button>
      </template>
    </PageHeading><div class="warehouse-filter users-filter">
      <input
        v-model.trim="keyword"
        placeholder="搜索昵称或手机号"
      ><select v-model="profileStatus">
        <option value="">
          全部资料
        </option><option value="complete">
          资料完整
        </option><option value="incomplete">
          待完善
        </option>
      </select><select v-model="energyTag">
        <option value="">
          全部能量
        </option><option
          v-for="tag in ['喜金','喜木','喜水','喜火','喜土']"
          :key="tag"
          :value="tag"
        >
          {{ tag }}
        </option>
      </select><select v-model="spendLevel">
        <option value="">
          全部消费
        </option><option value="none">
          未消费
        </option><option value="paid">
          已消费
        </option><option value="high">
          高客单
        </option>
      </select><input
        v-model="startDate"
        type="date"
      ><input
        v-model="endDate"
        type="date"
      >
    </div><PageErrorState
      v-if="error&&!loading"
      title="用户数据暂时无法读取"
      :message="error"
      eyebrow="CUSTOMERS UNAVAILABLE"
      @retry="load"
    /><div
      v-else-if="loading"
      class="warehouse-skeleton"
    >
      <i
        v-for="item in 8"
        :key="item"
      />
    </div><PageEmptyState
      v-else-if="!rows.length"
      title="没有符合条件的用户"
      message="调整筛选条件后重试。"
    /><div
      v-else
      class="users-ledger"
    >
      <div><span>用户</span><span>能量画像</span><span>消费</span><span>资料</span><span>更新时间</span></div><button
        v-for="item in rows"
        :key="item.user_id"
        type="button"
        @click="router.push({ name: 'user-detail', params: { userId: item.user_id } })"
      >
        <p>
          <img
            v-if="item.avatar_url"
            :src="item.avatar_url"
            :alt="item.nickname"
          ><i v-else>{{ (item.nickname||'宇').slice(0,1) }}</i><strong>{{ item.nickname||'未设置昵称' }}</strong><small>{{ maskedIdentity(item) }}</small>
        </p><em>{{ item.energy_tags.join(' · ')||'暂无测算' }}</em><p><strong>{{ item.spend_level_text }}</strong><small>{{ money(item.paid_amount) }} · {{ item.order_count }} 单</small></p><span>{{ item.profile_status_text }}</span><small>{{ item.updated_at||'—' }}</small>
      </button>
    </div>
  </section>
</template>
