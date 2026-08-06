<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import PageErrorState from '@/components/ui/PageErrorState.vue'
import {
  getCustomDesignAssessmentEvidence,
  getCustomDesignMaterialPreviews,
  getCustomDesignOverview,
  getCustomDesignProposalComposition,
  listCustomDesignEvents,
  listCustomDesignProposals,
} from '@/features/custom-design/api'
import {
  customDesignStatusLabel,
  customDesignStatusTone,
  formatAdminDate,
  preferenceMeasurement,
} from '@/features/custom-design/presentation'
import type {
  CustomDesignComposition,
  CustomDesignEvent,
  CustomDesignMaterialPreview,
  CustomDesignOverview,
  CustomDesignProposal,
} from '@/features/custom-design/types'
import { legacyDesignRequestPath } from '@/runtime/environment'

type Region = 'evidence' | 'proposals' | 'events'

const route = useRoute()
const overview = ref<CustomDesignOverview | null>(null)
const loading = ref(true)
const error = ref('')
const openRegions = reactive<Record<Region, boolean>>({
  evidence: false,
  proposals: false,
  events: false,
})
const regionLoading = reactive<Record<Region, boolean>>({
  evidence: false,
  proposals: false,
  events: false,
})
const regionErrors = reactive<Record<Region, string>>({
  evidence: '',
  proposals: '',
  events: '',
})
const evidence = ref<Record<string, unknown> | null>(null)
const proposals = ref<CustomDesignProposal[]>([])
const events = ref<CustomDesignEvent[]>([])
const compositions = ref<Record<string, CustomDesignComposition>>({})
const compositionLoading = ref<Record<string, boolean>>({})
const compositionErrors = ref<Record<string, string>>({})
const materials = ref<Record<string, CustomDesignMaterialPreview>>({})
let controller: AbortController | null = null
let loadVersion = 0

const requestId = computed(() => String(route.params.requestId || '').trim())
const brief = computed(() => overview.value?.design_brief || {})
const returnLocation = computed(() => ({
  name: 'design-requests',
  query: {
    status: typeof route.query.queueStatus === 'string' ? route.query.queueStatus : undefined,
    page: typeof route.query.queuePage === 'string' ? route.query.queuePage : undefined,
  },
}))
const legacyUrl = computed(() => legacyDesignRequestPath(requestId.value))
const canEdit = computed(() => ['submitted', 'designing', 'revision_requested'].includes(overview.value?.status || ''))
const briefConstraints = computed(() => brief.value.hard_constraints || [])
const paletteGroups = computed(() => [
  ['base', '主色'] as const,
  ['support', '辅助色'] as const,
  ['accent', '点缀色'] as const,
  ['avoid', '避免'] as const,
].map(([key, label]) => ({ key, label, colors: brief.value.palette?.[key] || [] })).filter((item) => item.colors.length))

function text(value: unknown, fallback = '未提供'): string {
  if (typeof value === 'string' || typeof value === 'number') return String(value).trim() || fallback
  return fallback
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function arrayText(value: unknown): string {
  if (!Array.isArray(value)) return '未提供'
  return value.map((item) => text(typeof item === 'object' ? record(item).label || record(item).element : item, '')).filter(Boolean).join('、') || '未提供'
}

function materialId(item: Record<string, unknown>): string {
  return text(item.material_id || item.sku_id || item.skuId || item.id, '')
}

function materialImage(item: Record<string, unknown>, material?: CustomDesignMaterialPreview): string {
  return text(item.selected_image_url || item.image_url || material?.image_urls?.[0] || material?.image_url, '')
}

function compositionFor(proposalId?: string): CustomDesignComposition | undefined {
  return proposalId ? compositions.value[proposalId] : undefined
}

function compositionSummary(proposalId?: string): string {
  const composition = compositionFor(proposalId)
  if (!composition) return ''
  return `${preferenceMeasurement(composition.wrist_size_cm || undefined, 'cm')} · ${preferenceMeasurement(composition.bead_size_mm || undefined, 'mm')} · ${composition.layout?.length || 0} 颗`
}

function compositionLayout(proposalId?: string): Array<Record<string, unknown>> {
  return compositionFor(proposalId)?.layout || []
}

function eventLabel(event: CustomDesignEvent): string {
  const labels: Record<string, string> = {
    deposit_created: '已创建保证金',
    deposit_paid: '保证金已支付',
    draft_saved: '设计草稿已保存',
    proposal_published: '方案已提交',
    proposal_confirmed: '用户已确认方案',
    revision_requested: '用户提出调整',
    order_created: '订单已生成',
  }
  return labels[event.event_type || ''] || '服务状态已更新'
}

const evidenceRows = computed(() => {
  const summary = evidence.value || {}
  const conclusion = record(summary.core_conclusion)
  const balance = record(summary.balance)
  const ranking = record(summary.ranking)
  return [
    ['测算结论', text(conclusion.summary || conclusion.title)],
    ['平衡状态', text(balance.label || balance.status || balance.score)],
    ['重点方向', arrayText(summary.adjustment_strategy || summary.useful_elements)],
    ['现有气质', text(ranking.dominant || summary.strongest_element)],
    ['设计关键词', arrayText(summary.keywords)],
  ].filter(([, value]) => value !== '未提供')
})

function resetRegions(): void {
  evidence.value = null
  proposals.value = []
  events.value = []
  compositions.value = {}
  materials.value = {}
  for (const region of ['evidence', 'proposals', 'events'] as Region[]) {
    openRegions[region] = false
    regionLoading[region] = false
    regionErrors[region] = ''
  }
}

async function loadOverview(): Promise<void> {
  const version = ++loadVersion
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  overview.value = null
  resetRegions()
  try {
    const result = await getCustomDesignOverview(requestId.value, controller.signal)
    if (version !== loadVersion) return
    overview.value = result
  } catch (cause) {
    if (version !== loadVersion || (cause instanceof DOMException && cause.name === 'AbortError')) return
    error.value = cause instanceof Error ? cause.message : '工单详情加载失败'
  } finally {
    if (version === loadVersion) loading.value = false
  }
}

async function toggleRegion(region: Region): Promise<void> {
  openRegions[region] = !openRegions[region]
  if (!openRegions[region] || regionLoading[region] || regionErrors[region] === '__loaded__') return
  regionLoading[region] = true
  regionErrors[region] = ''
  try {
    if (region === 'evidence') evidence.value = (await getCustomDesignAssessmentEvidence(requestId.value)).report_summary || {}
    if (region === 'proposals') proposals.value = await listCustomDesignProposals(requestId.value)
    if (region === 'events') events.value = await listCustomDesignEvents(requestId.value)
    regionErrors[region] = '__loaded__'
  } catch (cause) {
    regionErrors[region] = cause instanceof Error ? cause.message : '资料加载失败'
  } finally {
    regionLoading[region] = false
  }
}

async function loadComposition(proposal: CustomDesignProposal): Promise<void> {
  const proposalId = proposal.proposal_id || ''
  if (!proposalId || compositions.value[proposalId] || compositionLoading.value[proposalId]) return
  compositionLoading.value[proposalId] = true
  compositionErrors.value[proposalId] = ''
  try {
    const composition = await getCustomDesignProposalComposition(requestId.value, proposalId)
    compositions.value = { ...compositions.value, [proposalId]: composition }
    const ids = (composition.layout || []).map(materialId).filter(Boolean)
    const previews = await getCustomDesignMaterialPreviews(ids)
    materials.value = {
      ...materials.value,
      ...Object.fromEntries(previews.map((item) => [item.id, item])),
    }
  } catch (cause) {
    compositionErrors.value[proposalId] = cause instanceof Error ? cause.message : '方案材料读取失败'
  } finally {
    compositionLoading.value[proposalId] = false
  }
}

watch(requestId, () => void loadOverview(), { immediate: true })
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <section class="workspace-page design-detail-page">
    <RouterLink
      class="detail-back"
      :to="returnLocation"
    >
      ← 返回人工搭配
    </RouterLink>

    <div
      v-if="loading"
      class="design-detail-skeleton"
      aria-label="正在加载工单详情"
    >
      <i /><i /><i />
    </div>

    <PageErrorState
      v-else-if="error"
      eyebrow="WORK ORDER UNAVAILABLE"
      title="工单详情暂时无法读取"
      :message="error"
      @retry="loadOverview"
    />

    <template v-else-if="overview">
      <header class="detail-heading">
        <div>
          <span>DESIGN WORK ORDER · {{ overview.report_code || overview.report_id }}</span>
          <h1>{{ brief.design_goal?.title || '人工搭配服务单' }}</h1>
          <p>{{ brief.design_goal?.summary || '以用户偏好、佩戴规格和可用材料完成设计。' }}</p>
        </div>
        <div class="detail-heading__actions">
          <b
            class="status-label"
            :data-tone="customDesignStatusTone(overview.status)"
          >{{ customDesignStatusLabel(overview.status) }}</b>
          <RouterLink
            v-if="canEdit"
            :to="{ name: 'design-request-workbench', params: { requestId } }"
          >
            进入设计工作台 →
          </RouterLink>
          <a
            v-else
            :href="legacyUrl"
          >在当前后台查看完整工单 ↗</a>
        </div>
      </header>

      <div class="detail-meta-strip">
        <div><span>服务单</span><strong>{{ overview.request_id }}</strong></div>
        <div><span>测算报告</span><strong>{{ overview.report_code || overview.report_id }} · 第 {{ overview.report_version || 1 }} 版</strong></div>
        <div><span>首稿时限</span><strong>{{ overview.first_draft_due_at ? formatAdminDate(overview.first_draft_due_at) : '待排期' }}</strong></div>
        <div><span>最近更新</span><strong>{{ formatAdminDate(overview.updated_at) }}</strong></div>
      </div>

      <div class="detail-main-grid">
        <section class="detail-section detail-section--brief">
          <div class="detail-section__eyebrow">
            DESIGN BRIEF
          </div>
          <h2>设计方向</h2>
          <div class="detail-intervention">
            <span>{{ brief.intervention?.label || '审美优先' }}</span>
            <strong v-if="brief.intervention?.score !== undefined">{{ brief.intervention.score }}<small>分</small></strong>
            <p>{{ brief.intervention?.reason || '先以用户审美和佩戴场景为中心完成设计。' }}</p>
          </div>
          <div class="detail-brief-list">
            <div
              v-for="role in brief.material_roles || []"
              :key="role.key || role.label"
            >
              <span>{{ role.label || '材料角色' }}<b v-if="role.element"> · {{ role.element }}</b></span>
              <p>{{ role.reason || role.purpose }}</p>
            </div>
          </div>
          <div
            v-if="brief.structure?.direction"
            class="detail-structure"
          >
            <span>结构建议</span><p>{{ brief.structure.direction }}</p>
            <small>珠材不超过 {{ brief.structure.max_bead_materials || 3 }} 种；配饰不超过 {{ brief.structure.max_accessories || 2 }} 处。</small>
          </div>
        </section>

        <aside class="detail-aside">
          <section class="detail-section">
            <div class="detail-section__eyebrow">
              USER CONSTRAINTS
            </div>
            <h2>佩戴与偏好</h2>
            <dl class="detail-constraints">
              <template
                v-for="constraint in briefConstraints"
                :key="constraint.key || constraint.label"
              >
                <dt>{{ constraint.label }}</dt><dd>{{ constraint.value }}</dd>
              </template>
              <dt>配饰偏好</dt><dd>{{ overview.request?.accessory_preference || brief.preferences?.accessory || '未指定' }}</dd>
              <dt>佩戴场景</dt><dd>{{ overview.request?.wear_scene || brief.preferences?.wear_scene || '未指定' }}</dd>
            </dl>
          </section>
          <section
            v-if="paletteGroups.length"
            class="detail-section"
          >
            <div class="detail-section__eyebrow">
              COLOR LANGUAGE
            </div>
            <h2>色彩语言</h2>
            <div class="detail-palette">
              <div
                v-for="group in paletteGroups"
                :key="group.key"
              >
                <span>{{ group.label }}</span>
                <p>
                  <i
                    v-for="color in group.colors"
                    :key="color.key || color.label"
                    :style="{ background: color.hex || '#dedfd9' }"
                  />{{ group.colors.map((color) => color.label).filter(Boolean).join(' · ') }}
                </p>
              </div>
            </div>
          </section>
        </aside>
      </div>

      <section class="detail-section detail-section--latest">
        <div class="detail-latest-head">
          <div>
            <div class="detail-section__eyebrow">
              CURRENT DELIVERY
            </div>
            <h2>{{ overview.latest_proposal?.title || (overview.draft ? '设计草稿进行中' : '尚未提交设计方案') }}</h2>
          </div>
          <span>{{ overview.proposal_count || 0 }} 版方案 · {{ overview.deposit?.amount_text ? `保证金 ¥${overview.deposit.amount_text}` : '保证金待核对' }}</span>
        </div>
        <p v-if="overview.latest_proposal">
          最近一版于 {{ formatAdminDate(overview.latest_proposal.created_at) }} 创建；方案图片和材料组成在需要查看时才加载。
        </p>
        <p v-else-if="overview.draft">
          草稿第 {{ overview.draft.draft_version || 1 }} 版，最近编辑 {{ formatAdminDate(overview.draft.updated_at) }}。
        </p>
        <p v-else>
          可先根据上方 Brief 进入当前设计工作台完成首稿。
        </p>
      </section>

      <div class="detail-disclosure-list">
        <section class="detail-disclosure">
          <button
            type="button"
            :aria-expanded="openRegions.evidence"
            @click="toggleRegion('evidence')"
          >
            <span><small>REPORT EVIDENCE</small><strong>查看测算依据</strong></span><i>{{ openRegions.evidence ? '−' : '+' }}</i>
          </button>
          <div
            v-if="openRegions.evidence"
            class="detail-disclosure__body"
          >
            <p v-if="regionLoading.evidence">
              正在读取设计相关测算依据…
            </p>
            <p
              v-else-if="regionErrors.evidence && regionErrors.evidence !== '__loaded__'"
              class="detail-region-error"
            >
              {{ regionErrors.evidence }}
            </p>
            <dl
              v-else
              class="detail-evidence-list"
            >
              <template
                v-for="row in evidenceRows"
                :key="row[0]"
              >
                <dt>{{ row[0] }}</dt><dd>{{ row[1] }}</dd>
              </template>
            </dl>
          </div>
        </section>

        <section class="detail-disclosure">
          <button
            type="button"
            :aria-expanded="openRegions.proposals"
            @click="toggleRegion('proposals')"
          >
            <span><small>PROPOSAL HISTORY</small><strong>查看方案与真实材料</strong></span><i>{{ openRegions.proposals ? '−' : '+' }}</i>
          </button>
          <div
            v-if="openRegions.proposals"
            class="detail-disclosure__body"
          >
            <p v-if="regionLoading.proposals">
              正在读取方案记录…
            </p>
            <p
              v-else-if="regionErrors.proposals && regionErrors.proposals !== '__loaded__'"
              class="detail-region-error"
            >
              {{ regionErrors.proposals }}
            </p>
            <div
              v-else-if="!proposals.length"
              class="detail-empty-inline"
            >
              尚未发布方案。
            </div>
            <article
              v-for="proposal in proposals"
              :key="proposal.proposal_id"
              class="detail-proposal"
            >
              <header><span>第 {{ proposal.proposal_version || 1 }} 版 · {{ formatAdminDate(proposal.created_at) }}</span><strong>{{ proposal.title || '未命名方案' }}</strong></header>
              <p v-if="proposal.description">
                {{ proposal.description }}
              </p>
              <div
                v-if="proposal.image_urls?.length"
                class="detail-proposal__images"
              >
                <img
                  v-for="url in proposal.image_urls"
                  :key="url"
                  :src="url"
                  alt="方案参考图"
                >
              </div>
              <button
                type="button"
                :disabled="!proposal.proposal_id || compositionLoading[proposal.proposal_id]"
                @click="loadComposition(proposal)"
              >
                {{ compositions[proposal.proposal_id || ''] ? '已展开材料组成' : compositionLoading[proposal.proposal_id || ''] ? '读取材料中' : '查看材料组成' }}
              </button>
              <p
                v-if="compositionErrors[proposal.proposal_id || '']"
                class="detail-region-error"
              >
                {{ compositionErrors[proposal.proposal_id || ''] }}
              </p>
              <div
                v-if="compositionFor(proposal.proposal_id)"
                class="detail-composition"
              >
                <span>{{ compositionSummary(proposal.proposal_id) }}</span>
                <div>
                  <figure
                    v-for="(item, index) in compositionLayout(proposal.proposal_id)"
                    :key="`${proposal.proposal_id}-${index}`"
                  >
                    <img
                      v-if="materialImage(item, materials[materialId(item)])"
                      :src="materialImage(item, materials[materialId(item)])"
                      :alt="materials[materialId(item)]?.name || materialId(item)"
                    >
                    <i v-else>{{ index + 1 }}</i>
                    <figcaption>{{ materials[materialId(item)]?.name || materialId(item) || '材料待同步' }}</figcaption>
                  </figure>
                </div>
              </div>
            </article>
          </div>
        </section>

        <section class="detail-disclosure">
          <button
            type="button"
            :aria-expanded="openRegions.events"
            @click="toggleRegion('events')"
          >
            <span><small>SERVICE HISTORY</small><strong>查看服务记录</strong></span><i>{{ openRegions.events ? '−' : '+' }}</i>
          </button>
          <div
            v-if="openRegions.events"
            class="detail-disclosure__body"
          >
            <p v-if="regionLoading.events">
              正在读取服务记录…
            </p>
            <p
              v-else-if="regionErrors.events && regionErrors.events !== '__loaded__'"
              class="detail-region-error"
            >
              {{ regionErrors.events }}
            </p>
            <ol
              v-else-if="events.length"
              class="detail-event-list"
            >
              <li
                v-for="event in events"
                :key="`${event.event_type}-${event.created_at}`"
              >
                <time>{{ formatAdminDate(event.created_at) }}</time><div>
                  <strong>{{ eventLabel(event) }}</strong><p v-if="event.note">
                    {{ event.note }}
                  </p>
                </div>
              </li>
            </ol>
            <div
              v-else
              class="detail-empty-inline"
            >
              暂无服务记录。
            </div>
          </div>
        </section>
      </div>
    </template>
  </section>
</template>
