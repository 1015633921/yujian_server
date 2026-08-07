<script setup lang="ts">
import { computed, ref } from 'vue'

import ActionConfirmDialog from '@/components/ui/ActionConfirmDialog.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import { getDailyRules, saveDailyRules, type DailyRules } from '@/features/users/api'
import { useAuthStore } from '@/stores/auth'

type RuleRecord = Record<string, unknown>
type RuleOption = { key?: string; label?: string; desc?: string; group?: string; score_delta?: number; crystal_codes?: string[] }

const auth = useAuthStore()
const data = ref<DailyRules | null>(null)
const text = ref('')
const loading = ref(true)
const saving = ref(false)
const message = ref('')
const error = ref('')
const resetConfirmOpen = ref(false)
const restoreVersion = ref('')
const changeNote = ref('')
const canManage = computed(() => auth.admin?.role !== 'viewer')
const history = computed(() => data.value?.history || [])
const restoreTarget = computed(() => history.value.find((item) => item.version === restoreVersion.value))

function parseRules(): RuleRecord | null {
  try {
    const value: unknown = JSON.parse(text.value)
    return value && typeof value === 'object' && !Array.isArray(value) ? value as RuleRecord : null
  } catch {
    return null
  }
}

const rules = computed(() => parseRules())
const scoring = computed(() => {
  const value = rules.value?.scoring
  return value && typeof value === 'object' && !Array.isArray(value) ? value as RuleRecord : {}
})
const statusGroups = computed(() => Array.isArray(rules.value?.status_groups) ? rules.value?.status_groups as RuleOption[] : [])
const statusTags = computed(() => Array.isArray(rules.value?.status_tags) ? rules.value?.status_tags as RuleOption[] : [])
const scenes = computed(() => Array.isArray(rules.value?.scenes) ? rules.value?.scenes as RuleOption[] : [])
const goals = computed(() => Array.isArray(rules.value?.goals) ? rules.value?.goals as RuleOption[] : [])

function mutate(mutator: (draft: RuleRecord) => void): void {
  if (!canManage.value) return
  const draft = parseRules()
  if (!draft) {
    message.value = '规则 JSON 格式错误，无法应用修改。请先在高级编辑中修复格式。'
    return
  }
  mutator(draft)
  text.value = JSON.stringify(draft, null, 2)
  message.value = '已修改，尚未发布。'
}

function setScore(key: string, event: Event): void {
  const value = Number((event.target as HTMLInputElement).value)
  if (!Number.isFinite(value)) return
  mutate((draft) => {
    const next = { ...((draft.scoring as RuleRecord) || {}) }
    next[key] = value
    draft.scoring = next
  })
}

function setOption(collection: 'status_tags' | 'scenes' | 'goals', index: number, field: keyof RuleOption, event: Event): void {
  const raw = (event.target as HTMLInputElement | HTMLSelectElement).value
  mutate((draft) => {
    const source = Array.isArray(draft[collection]) ? [...draft[collection] as RuleOption[]] : []
    const item = { ...(source[index] || {}) }
    if (field === 'score_delta') item[field] = Number(raw) || 0
    else if (field === 'crystal_codes') item[field] = raw.split(/[，,]/).map((value) => value.trim()).filter(Boolean)
    else item[field] = raw
    source[index] = item
    draft[collection] = source
  })
}

function format(): void {
  const value = parseRules()
  if (!value) {
    message.value = 'JSON 格式错误，未格式化。'
    return
  }
  text.value = JSON.stringify(value, null, 2)
  message.value = '高级配置已格式化。'
}

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    data.value = await getDailyRules()
    text.value = JSON.stringify(data.value.rules || {}, null, 2)
    message.value = ''
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '规则加载失败'
  } finally {
    loading.value = false
  }
}

async function save(reset = false, restore = ''): Promise<void> {
  if (!canManage.value || saving.value) return
  const value = reset ? {} : parseRules()
  if (!reset && !value) {
    message.value = '高级配置 JSON 格式错误，未提交。'
    return
  }
  saving.value = true
  message.value = ''
  try {
    data.value = await saveDailyRules(value || {}, { resetToDefault: reset, restoreVersion: restore, changeNote: changeNote.value.trim() })
    text.value = JSON.stringify(data.value.rules || {}, null, 2)
    resetConfirmOpen.value = false
    restoreVersion.value = ''
    changeNote.value = ''
    message.value = restore ? '已恢复指定历史版本。' : reset ? '已恢复系统默认规则。' : '每日能量规则已发布。'
  } catch (cause) {
    message.value = cause instanceof Error ? cause.message : '保存失败。'
  } finally {
    saving.value = false
  }
}

void load()
</script>

<template>
  <section class="workspace-page rules-page">
    <PageHeading
      eyebrow="DAILY ENERGY RULES"
      title="每日能量规则"
      description="先用结构化配置调整常用规则；高级 JSON 仅用于完整迁移和特殊字段。"
    >
      <template #actions>
        <button
          class="heading-link"
          type="button"
          @click="load"
        >
          重新读取
        </button>
      </template>
    </PageHeading>

    <PageErrorState
      v-if="error && !loading"
      title="规则暂时无法读取"
      :message="error"
      eyebrow="RULES UNAVAILABLE"
      @retry="load"
    />
    <div
      v-else-if="loading"
      class="warehouse-skeleton"
    >
      <i
        v-for="item in 5"
        :key="item"
      />
    </div>
    <template v-else>
      <div class="rules-summary">
        <div><span>规则版本</span><strong>{{ data?.rules_version || '—' }}</strong></div>
        <div><span>状态标签</span><strong>{{ statusTags.length }}</strong></div>
        <div><span>场景</span><strong>{{ scenes.length }}</strong></div>
        <div><span>目标</span><strong>{{ goals.length }}</strong></div>
        <p>{{ data?.updated_at ? `最近发布 ${data.updated_at}` : '当前规则尚未记录发布时间。' }}</p>
      </div>

      <section class="rules-history">
        <header><div><span>VERSION HISTORY</span><h2>版本记录与回滚</h2></div><p>保留最近 20 个发布版本；回滚会生成新的当前版本，不会覆盖历史。</p></header>
        <div class="rules-history__list">
          <article
            v-for="item in history"
            :key="item.version"
            :class="{ 'is-current': item.current }"
          >
            <div><strong>{{ item.current ? '当前版本' : item.version }}</strong><small>{{ item.updated_at || '历史时间未记录' }} · {{ item.actor || '系统' }}</small></div>
            <p>{{ item.note || '未填写变更说明' }}</p>
            <button
              v-if="!item.current"
              type="button"
              :disabled="!canManage || saving"
              @click="restoreVersion = item.version"
            >
              回滚到此版本
            </button>
          </article>
          <p
            v-if="history.length <= 1"
            class="rules-history__empty"
          >
            首次发布后会自动开始保留可回滚版本。
          </p>
        </div>
      </section>

      <div class="rules-workspace">
        <section class="rules-section">
          <header><div><span>SCORING</span><h2>基础分与边界</h2></div><p>修改后可直接预览常用分数区间。</p></header>
          <div class="rules-fields">
            <label>基础模式<input
              :value="scoring.starter_base ?? ''"
              :disabled="!canManage"
              type="number"
              @change="setScore('starter_base', $event)"
            ></label>
            <label>个性化模式<input
              :value="scoring.personalized_base ?? ''"
              :disabled="!canManage"
              type="number"
              @change="setScore('personalized_base', $event)"
            ></label>
            <label>最低分<input
              :value="scoring.min_score ?? ''"
              :disabled="!canManage"
              type="number"
              @change="setScore('min_score', $event)"
            ></label>
            <label>最高分<input
              :value="scoring.max_score ?? ''"
              :disabled="!canManage"
              type="number"
              @change="setScore('max_score', $event)"
            ></label>
          </div>
        </section>

        <section class="rules-section">
          <header><div><span>STATUS TAGS</span><h2>状态标签</h2></div><p>状态会参与每日建议的推荐逻辑。</p></header>
          <div class="rules-option-list">
            <article
              v-for="(tag, index) in statusTags"
              :key="tag.key || index"
            >
              <label>名称<input
                :value="tag.label || ''"
                :disabled="!canManage"
                @change="setOption('status_tags', index, 'label', $event)"
              ></label>
              <label>分组<select
                :value="tag.group || ''"
                :disabled="!canManage"
                @change="setOption('status_tags', index, 'group', $event)"
              ><option value="">未分组</option><option
                v-for="group in statusGroups"
                :key="group.key"
                :value="group.key"
              >{{ group.label || group.key }}</option></select></label>
              <label>分数变化<input
                :value="tag.score_delta ?? 0"
                :disabled="!canManage"
                type="number"
                @change="setOption('status_tags', index, 'score_delta', $event)"
              ></label>
              <label>推荐晶石编码<input
                :value="(tag.crystal_codes || []).join(', ')"
                :disabled="!canManage"
                @change="setOption('status_tags', index, 'crystal_codes', $event)"
              ></label>
              <label class="rules-option-list__wide">说明<input
                :value="tag.desc || ''"
                :disabled="!canManage"
                @change="setOption('status_tags', index, 'desc', $event)"
              ></label>
            </article>
          </div>
        </section>

        <section class="rules-section rules-section--compact">
          <header><div><span>SCENES & GOALS</span><h2>场景与目标</h2></div><p>保留业务语言，避免在运营端暴露技术键值。</p></header>
          <div class="rules-simple-list">
            <article
              v-for="(scene, index) in scenes"
              :key="scene.key || index"
            >
              <label>场景名称<input
                :value="scene.label || ''"
                :disabled="!canManage"
                @change="setOption('scenes', index, 'label', $event)"
              ></label><label>说明<input
                :value="scene.desc || ''"
                :disabled="!canManage"
                @change="setOption('scenes', index, 'desc', $event)"
              ></label>
            </article>
            <article
              v-for="(goal, index) in goals"
              :key="goal.key || index"
            >
              <label>目标名称<input
                :value="goal.label || ''"
                :disabled="!canManage"
                @change="setOption('goals', index, 'label', $event)"
              ></label><label>说明<input
                :value="goal.desc || ''"
                :disabled="!canManage"
                @change="setOption('goals', index, 'desc', $event)"
              ></label>
            </article>
          </div>
        </section>

        <details class="rules-advanced">
          <summary>高级 JSON 编辑</summary>
          <p>用于完整迁移、批量维护和暂未结构化的字段。格式错误时无法发布。</p>
          <textarea
            v-model="text"
            :disabled="!canManage"
            spellcheck="false"
          />
          <button
            type="button"
            :disabled="!canManage"
            @click="format"
          >
            格式化 JSON
          </button>
        </details>
      </div>

      <footer class="rules-actions">
        <p role="status">
          {{ message || (!canManage ? '当前账号为只读，不能修改规则。' : '所有修改均需点击“发布规则”后才对用户生效。') }}
        </p>
        <label class="rules-change-note">变更说明<input
          v-model.trim="changeNote"
          :disabled="!canManage || saving"
          maxlength="300"
          placeholder="例如：提高专注场景基础分"
        ></label>
        <button
          type="button"
          :disabled="!canManage || saving"
          @click="resetConfirmOpen = true"
        >
          恢复默认
        </button>
        <button
          class="primary-action"
          type="button"
          :disabled="!canManage || saving"
          @click="save()"
        >
          {{ saving ? '发布中…' : '发布规则' }}
        </button>
      </footer>

      <ActionConfirmDialog
        :open="resetConfirmOpen"
        title="恢复默认每日能量规则"
        description="这会覆盖当前自定义规则，并立即生成一个新的规则版本。"
        confirm-label="确认恢复默认"
        tone="danger"
        :busy="saving"
        @close="resetConfirmOpen = false"
        @confirm="save(true)"
      >
        <p class="action-confirm__note">
          建议先在高级 JSON 中复制当前版本，或记录本次变更说明后再继续。
        </p>
      </ActionConfirmDialog>

      <ActionConfirmDialog
        :open="Boolean(restoreVersion)"
        title="回滚每日能量规则"
        :description="`将恢复至 ${restoreTarget?.version || '所选'} 版本，并把当前版本保留在历史记录中。`"
        confirm-label="确认回滚"
        tone="danger"
        :busy="saving"
        @close="restoreVersion = ''"
        @confirm="save(false, restoreVersion)"
      >
        <p class="action-confirm__note">
          {{ restoreTarget?.note || '该版本没有填写变更说明。' }}
        </p>
      </ActionConfirmDialog>
    </template>
  </section>
</template>
