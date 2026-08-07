<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import {
  getAssessmentDetail,
  getCheckinDetail,
  getDailyEnergyDetail,
  type AssessmentDetail,
  type CheckinDetail,
  type DailyEnergyDetail,
} from '@/features/users/api'

type Detail = AssessmentDetail | DailyEnergyDetail | CheckinDetail
type DetailKind = 'assessment' | 'daily' | 'checkin'

const route = useRoute()
const router = useRouter()
const detail = ref<Detail | null>(null)
const loading = ref(true)
const error = ref('')
let controller: AbortController | null = null

const kind = computed<DetailKind>(() => String(route.meta.energyKind || 'assessment') as DetailKind)
const title = computed(() => ({ assessment: '测算记录详情', daily: '每日能量详情', checkin: '签到记录详情' })[kind.value])
const eyebrow = computed(() => ({ assessment: 'ASSESSMENT DETAIL', daily: 'DAILY ENERGY DETAIL', checkin: 'CHECK-IN DETAIL' })[kind.value])
const profile = computed(() => kind.value === 'assessment'
  ? (detail.value as AssessmentDetail | null)?.energy.profile || {}
  : kind.value === 'daily'
    ? (detail.value as DailyEnergyDetail | null)?.energy_profile || {}
    : {})
const keywordText = computed(() => {
  const values = kind.value === 'assessment'
    ? (detail.value as AssessmentDetail | null)?.energy.keywords || []
    : kind.value === 'daily'
      ? (detail.value as DailyEnergyDetail | null)?.keywords || []
      : []
  return values.map((value) => typeof value === 'string' ? value : String((value as Record<string, unknown>).label || (value as Record<string, unknown>).name || '')).filter(Boolean)
})

function score(value: unknown): string {
  const number = Number(value)
  return Number.isFinite(number) ? number.toFixed(1) : '—'
}

function crystalName(item: Record<string, unknown>): string {
  return String(item.name || item.title || item.code || '—')
}

async function load(): Promise<void> {
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  detail.value = null
  try {
    if (kind.value === 'assessment') {
      detail.value = await getAssessmentDetail(String(route.params.assessmentId || ''), controller.signal)
    } else if (kind.value === 'daily') {
      detail.value = await getDailyEnergyDetail(String(route.params.userId || ''), String(route.params.energyDate || ''), controller.signal)
    } else {
      detail.value = await getCheckinDetail(String(route.params.userId || ''), String(route.params.checkinDate || ''), controller.signal)
    }
  } catch (cause) {
    if (!(cause instanceof DOMException && cause.name === 'AbortError')) error.value = cause instanceof Error ? cause.message : '能量详情加载失败'
  } finally {
    loading.value = false
  }
}

watch(() => route.fullPath, () => void load(), { immediate: true })
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <section class="workspace-page energy-detail-page">
    <PageHeading
      :eyebrow="eyebrow"
      :title="title"
      description="查看单条能量记录的来源、五行画像与推荐结果。"
    >
      <template #actions>
        <button
          class="heading-link"
          type="button"
          @click="router.push({ name: 'energy-insights' })"
        >
          返回能量数据
        </button>
        <button
          class="heading-link"
          type="button"
          @click="load"
        >
          刷新数据
        </button>
      </template>
    </PageHeading>

    <PageErrorState
      v-if="error && !loading"
      title="能量详情暂时无法读取"
      :message="error"
      eyebrow="DETAIL UNAVAILABLE"
      @retry="load"
    />
    <div
      v-else-if="loading"
      class="warehouse-skeleton"
    >
      <i
        v-for="item in 6"
        :key="item"
      />
    </div>

    <template v-else-if="detail">
      <div class="energy-detail__meta">
        <span>用户：{{ detail.user_id }}</span>
        <span v-if="kind === 'assessment'">测算编号：{{ (detail as AssessmentDetail).assessment_id }}</span>
        <span v-else-if="kind === 'daily'">日期：{{ (detail as DailyEnergyDetail).energy_date }}</span>
        <span v-else>签到日期：{{ (detail as CheckinDetail).checkin_date }}</span>
        <span>{{ 'created_at' in detail ? detail.created_at || detail.updated_at || '—' : detail.updated_at || '—' }}</span>
      </div>

      <div
        v-if="kind !== 'checkin'"
        class="energy-detail__profile"
      >
        <section>
          <header><span>FIVE ELEMENTS</span><h2>五行画像</h2></header>
          <div
            v-if="Object.keys(profile).length"
            class="energy-detail__bars"
          >
            <div
              v-for="(value, key) in profile"
              :key="key"
            >
              <span>{{ key }}</span><i><b :style="{ width: `${Math.min(100, Number(value) * 3)}%` }" /></i><strong>{{ score(value) }}</strong>
            </div>
          </div>
          <p
            v-else
            class="energy-detail__empty"
          >
            该记录未保留五行占比。
          </p>
        </section>
        <section>
          <header><span>KEYWORDS</span><h2>能量提示</h2></header>
          <p class="energy-detail__keywords">
            {{ keywordText.join(' · ') || '暂无能量标签' }}
          </p>
          <p
            v-if="kind === 'assessment'"
            class="energy-detail__copy"
          >
            {{ (detail as AssessmentDetail).energy.interpretation || (detail as AssessmentDetail).summary || '暂无文字解读。' }}
          </p>
          <p
            v-else
            class="energy-detail__copy"
          >
            {{ (detail as DailyEnergyDetail).advice || '暂无今日建议。' }}
          </p>
        </section>
      </div>

      <div
        v-if="kind === 'assessment'"
        class="energy-detail__grid"
      >
        <section>
          <header><span>ASSESSMENT</span><h2>测算概览</h2></header>
          <dl><div><dt>姓名</dt><dd>{{ (detail as AssessmentDetail).name || '—' }}</dd></div><div><dt>核心愿望</dt><dd>{{ (detail as AssessmentDetail).core_wish || '—' }}</dd></div><div><dt>优势五行</dt><dd>{{ (detail as AssessmentDetail).energy.strongest_element || '—' }}</dd></div><div><dt>待补五行</dt><dd>{{ (detail as AssessmentDetail).energy.weakest_element || '—' }}</dd></div></dl>
        </section>
        <section>
          <header><span>RECOMMENDATION</span><h2>推荐方案</h2></header>
          <p class="energy-detail__copy">
            {{ (detail as AssessmentDetail).recommendation.copy || '暂无推荐文案。' }}
          </p>
          <p>主石：{{ crystalName((detail as AssessmentDetail).recommendation.primary_crystal) }}</p>
          <p>副石：{{ (detail as AssessmentDetail).recommendation.supporting_crystals.map(crystalName).join('、') || '—' }}</p>
        </section>
        <section class="energy-detail__wide">
          <header><span>RECOMMENDATION BASIS</span><h2>配方构成</h2></header>
          <p class="energy-detail__keywords">
            {{ (detail as AssessmentDetail).formula?.tags?.map((item) => `${item.role || '珠材'} ${item.name || ''}`).join(' · ') || '暂无配方信息' }}
          </p>
        </section>
      </div>

      <div
        v-else-if="kind === 'daily'"
        class="energy-detail__grid"
      >
        <section><header><span>DAILY SUMMARY</span><h2>今日建议</h2></header><dl><div><dt>能量分</dt><dd>{{ (detail as DailyEnergyDetail).score ?? '—' }}</dd></div><div><dt>幸运色</dt><dd>{{ (detail as DailyEnergyDetail).lucky_color || '—' }}</dd></div><div><dt>推荐材料</dt><dd>{{ (detail as DailyEnergyDetail).recommended_stone || '—' }}</dd></div><div><dt>幸运时段</dt><dd>{{ (detail as DailyEnergyDetail).lucky_time || '—' }}</dd></div></dl></section>
      </div>

      <div
        v-else
        class="energy-detail__grid"
      >
        <section><header><span>CHECK-IN</span><h2>当日状态</h2></header><dl><div><dt>心情</dt><dd>{{ (detail as CheckinDetail).mood ?? '—' }}</dd></div><div><dt>睡眠</dt><dd>{{ (detail as CheckinDetail).sleep ?? '—' }}</dd></div><div><dt>压力</dt><dd>{{ (detail as CheckinDetail).stress ?? '—' }}</dd></div></dl></section>
      </div>
    </template>
  </section>
</template>
