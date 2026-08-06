<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageEmptyState from '@/components/ui/PageEmptyState.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import { getUser, type UserDetail } from '@/features/users/api'
const route = useRoute(); const router = useRouter(); const detail = ref<UserDetail | null>(null); const loading = ref(true); const error = ref(''); let controller: AbortController | null = null
const userId = computed(() => String(route.params.userId || '')); const money = (value = 0) => new Intl.NumberFormat('zh-CN', { style:'currency',currency:'CNY',maximumFractionDigits:0 }).format(value)
async function load(): Promise<void> { controller?.abort(); controller = new AbortController(); loading.value = true; error.value = ''; try { detail.value = await getUser(userId.value, controller.signal) } catch (cause) { if (!(cause instanceof DOMException && cause.name === 'AbortError')) error.value = cause instanceof Error ? cause.message : '用户详情加载失败' } finally { loading.value = false } }
onBeforeUnmount(() => controller?.abort()); void load()
</script>
<template>
  <section class="workspace-page user-detail">
    <PageHeading
      eyebrow="CUSTOMER PROFILE"
      :title="detail?.user.nickname || '用户详情'"
      description="查看用户资料、能量画像与消费记录。"
    >
      <template #actions>
        <button
          class="heading-link"
          type="button"
          @click="router.push({ name:'users' })"
        >
          返回用户中心
        </button><button
          class="heading-link"
          type="button"
          @click="load"
        >
          刷新数据
        </button>
      </template>
    </PageHeading><PageErrorState
      v-if="error&&!loading"
      title="用户详情暂时无法读取"
      :message="error"
      eyebrow="CUSTOMER UNAVAILABLE"
      @retry="load"
    /><div
      v-else-if="loading"
      class="warehouse-skeleton"
    >
      <i
        v-for="item in 8"
        :key="item"
      />
    </div><template v-else-if="detail">
      <div class="user-detail__metrics">
        <div><span>订单</span><strong>{{ detail.stats.order_count }}</strong></div><div><span>累计消费</span><strong>{{ money(detail.stats.paid_amount) }}</strong></div><div><span>DIY 设计</span><strong>{{ detail.stats.design_count }}</strong></div><div><span>测算记录</span><strong>{{ detail.stats.assessment_count }}</strong></div>
      </div><div class="user-detail__grid">
        <section>
          <header><span>ENERGY PROFILE</span><h2>能量画像</h2></header><p class="user-detail__tags">
            {{ detail.energy.tags.join(' · ') || '暂无测算标签' }}
          </p><dl>
            <div
              v-for="(value,key) in detail.energy.energy_profile"
              :key="key"
            >
              <dt>{{ key }}</dt><dd><i :style="{ width: `${Math.min(100, Number(value)*3)}%` }" /><b>{{ Number(value).toFixed(1) }}</b></dd>
            </div>
          </dl>
        </section><section>
          <header><span>ASSESSMENTS</span><h2>最近测算</h2></header><PageEmptyState
            v-if="!detail.assessments.length"
            title="暂无测算记录"
            message="该用户尚未完成测算。"
          /><article
            v-for="item in detail.assessments"
            v-else
            :key="item.assessment_id"
          >
            <strong>{{ item.core_wish || '未设愿望' }}</strong><p>{{ item.summary || '暂无测算摘要' }}</p><small>{{ item.created_at || '—' }}</small>
          </article>
        </section><section>
          <header><span>ORDERS</span><h2>历史订单</h2></header><PageEmptyState
            v-if="!detail.orders.length"
            title="暂无订单"
            message="该用户暂未下单。"
          /><article
            v-for="item in detail.orders"
            v-else
            :key="item.order_id"
          >
            <strong>{{ item.order_id }}</strong><span>{{ item.status || '—' }} · {{ money(item.total_amount) }}</span><small>{{ item.created_at || '—' }}</small>
          </article>
        </section><section>
          <header><span>DAILY ENERGY</span><h2>每日能量</h2></header><PageEmptyState
            v-if="!detail.daily_energies.length"
            title="暂无每日能量记录"
            message="暂无可展示的建议。"
          /><article
            v-for="item in detail.daily_energies"
            v-else
            :key="item.energy_date"
          >
            <strong>{{ item.energy_date }}</strong><p>{{ item.title || '今日建议' }} · {{ item.recommended_stone || '—' }}</p><small>{{ item.lucky_color || '—' }} · {{ item.score ?? '—' }} 分</small>
          </article>
        </section>
      </div>
    </template>
  </section>
</template>
