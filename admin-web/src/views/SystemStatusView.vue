<script setup lang="ts">
import { ref } from 'vue'

import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import { getSystemStatus, type SystemStatus } from '@/features/users/api'

const data = ref<SystemStatus | null>(null)
const loading = ref(true)
const error = ref('')

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    data.value = await getSystemStatus()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '系统状态加载失败'
  } finally {
    loading.value = false
  }
}

void load()
</script>

<template>
  <section class="workspace-page system-status">
    <PageHeading
      eyebrow="SYSTEM READINESS"
      title="系统配置"
      description="只展示服务就绪状态与配置提示，不展示任何密钥或敏感配置。"
    >
      <template #actions>
        <button
          class="heading-link"
          type="button"
          :disabled="loading"
          @click="load"
        >
          {{ loading ? '检查中…' : '刷新检查' }}
        </button>
      </template>
    </PageHeading>

    <PageErrorState
      v-if="error && !loading"
      title="系统状态暂时无法读取"
      :message="error"
      eyebrow="SYSTEM UNAVAILABLE"
      @retry="load"
    />

    <template v-else>
      <div
        v-if="loading"
        class="system-status__skeleton"
      >
        <i
          v-for="item in 4"
          :key="item"
        />
      </div>

      <template v-else>
        <div class="system-status__summary">
          <span>配置就绪</span>
          <strong>{{ data?.ready_count ?? '—' }}</strong>
          <p>共 {{ data?.total_count ?? '—' }} 项服务检查已完成。</p>
        </div>

        <div class="system-status__list">
          <article
            v-for="item in data?.checks || []"
            :key="item.key"
          >
            <span :class="item.ready ? 'is-ready' : 'is-missing'">
              {{ item.ready ? '已就绪' : '待配置' }}
            </span>
            <div>
              <strong>{{ item.label }}</strong>
              <small>{{ item.hint }}</small>
            </div>
          </article>
        </div>
      </template>
    </template>
  </section>
</template>
