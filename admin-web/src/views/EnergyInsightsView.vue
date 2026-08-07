<script setup lang="ts">
import { ref, watch } from 'vue'
import PageEmptyState from '@/components/ui/PageEmptyState.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import { listAssessments, listCheckins, listDailyEnergies, type Assessment, type Checkin, type DailyEnergy } from '@/features/users/api'
type Tab = 'assessments'|'daily'|'checkins'; const tab=ref<Tab>('assessments'); const keyword=ref(''); const wish=ref(''); const hideTests=ref(true); const rows=ref<Array<Assessment|DailyEnergy|Checkin>>([]); const loading=ref(true); const error=ref('')
async function load(): Promise<void> { loading.value=true; error.value=''; try { rows.value=tab.value==='assessments'?await listAssessments({keyword:keyword.value,wish:wish.value,hideTests:hideTests.value}):tab.value==='daily'?await listDailyEnergies(keyword.value):await listCheckins(keyword.value) } catch(cause) { error.value=cause instanceof Error?cause.message:'能量数据加载失败' } finally { loading.value=false } }
function switchTab(next:Tab):void { tab.value=next; void load() }; watch([keyword,wish,hideTests],()=>void load()); void load()
</script>
<template>
  <section class="workspace-page insights-page">
    <PageHeading
      eyebrow="ENERGY INSIGHTS"
      title="能量数据"
      description="只读查看测算、每日建议与签到数据，作为运营分析依据。"
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
    </PageHeading><nav class="warehouse-tabs">
      <button
        :class="{'is-current':tab==='assessments'}"
        type="button"
        @click="switchTab('assessments')"
      >
        测算记录
      </button><button
        :class="{'is-current':tab==='daily'}"
        type="button"
        @click="switchTab('daily')"
      >
        每日能量
      </button><button
        :class="{'is-current':tab==='checkins'}"
        type="button"
        @click="switchTab('checkins')"
      >
        签到记录
      </button>
    </nav><div class="warehouse-filter">
      <input
        v-model.trim="keyword"
        placeholder="搜索用户、日期、愿望或测算编号"
      ><select
        v-if="tab==='assessments'"
        v-model="wish"
      >
        <option value="">
          全部愿望
        </option><option
          v-for="item in ['招财','桃花','辟邪','健康']"
          :key="item"
        >
          {{ item }}
        </option>
      </select><label v-if="tab==='assessments'"><input
        v-model="hideTests"
        type="checkbox"
      > 隐藏测试数据</label>
    </div><PageErrorState
      v-if="error&&!loading"
      title="能量数据暂时无法读取"
      :message="error"
      eyebrow="INSIGHTS UNAVAILABLE"
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
      title="暂无符合条件的数据"
      message="调整筛选条件后重试。"
    /><div
      v-else
      class="insights-ledger"
    >
      <article
        v-for="item in rows"
        :key="('assessment_id'in item?item.assessment_id:'energy_date'in item?`${item.user_id}-${item.energy_date}`:`${item.user_id}-${item.checkin_date}`)"
      >
        <template v-if="'assessment_id'in item">
          <strong>{{ item.name||item.user_id }} · {{ item.core_wish||'未设愿望' }}</strong><p>{{ item.formula?.tags?.map(x=>`${x.role||'珠材'} ${x.name||''}`).join(' · ')||'暂无配方' }}</p><small>{{ item.summary||'暂无摘要' }} · {{ item.created_at||'—' }}</small>
          <RouterLink :to="{ name: 'energy-assessment-detail', params: { assessmentId: item.assessment_id } }">
            查看详情
          </RouterLink>
        </template><template v-else-if="'energy_date'in item">
          <strong>{{ item.energy_date }} · {{ item.user_id }}</strong><p>{{ item.title||'今日能量' }} · {{ item.recommended_stone||'—' }}</p><small>{{ item.lucky_color||'—' }} · {{ item.score??'—' }} 分</small>
          <RouterLink :to="{ name: 'energy-daily-detail', params: { userId: item.user_id, energyDate: item.energy_date } }">
            查看详情
          </RouterLink>
        </template><template v-else>
          <strong>{{ item.checkin_date }} · {{ item.user_id }}</strong><p>心情 {{ item.mood??'—' }} · 睡眠 {{ item.sleep??'—' }} · 压力 {{ item.stress??'—' }}</p><small>{{ item.updated_at||'—' }}</small>
          <RouterLink :to="{ name: 'energy-checkin-detail', params: { userId: item.user_id, checkinDate: item.checkin_date } }">
            查看详情
          </RouterLink>
        </template>
      </article>
    </div>
  </section>
</template>
