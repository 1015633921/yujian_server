<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import PageErrorState from '@/components/ui/PageErrorState.vue'
import { getMaterial, patchMaterialSku, type Material } from '@/features/materials/api'
import { useAuthStore } from '@/stores/auth'

const physicalFields = [
  { key: 'string_axis_width_mm', label: '穿线方向占位', suffix: 'mm', kind: 'geometry' },
  { key: 'body_width_mm', label: '外观宽度', suffix: 'mm', kind: 'geometry' },
  { key: 'body_height_mm', label: '外观高度', suffix: 'mm', kind: 'geometry' },
  { key: 'radial_depth_mm', label: '径向厚度', suffix: 'mm', kind: 'geometry' },
  { key: 'compatible_bead_size_mm', label: '适配主珠珠径', suffix: 'mm', kind: 'bead_cap' },
  { key: 'compatible_size_tolerance_mm', label: '适配误差 ±', suffix: 'mm', kind: 'bead_cap' },
] as const

const shapeLabels: Record<string, string> = {
  round: '圆珠', faceted_round: '切面圆珠', rondelle: '算盘珠', barrel: '桶珠', cube: '方糖', nugget: '随形',
  double_terminated: '双尖', single_terminated: '单尖', triangle: '三角形', disc: '隔片', bead_cap: '包珠隔片 / 花托',
  curved_tube: '弯管', connector: '连接扣', clasp: '扣件', charm: '挂坠', special: '异形',
}

const route = useRoute()
const auth = useAuthStore()
const item = ref<Material | null>(null)
const loading = ref(true)
const error = ref('')
const saving = ref(false)
const message = ref('')
let controller: AbortController | null = null

const id = computed(() => String(route.params.materialId || ''))
const canManage = computed(() => auth.admin?.role !== 'viewer')
const resolvedShape = computed(() => {
  const stored = String(item.value?.material_params?.bead_shape || '')
  if (stored) return stored
  if (item.value?.top === 'bead' || item.value?.top === 'incense') return 'round'
  if (String(item.value?.category || '').includes('花托')) return 'bead_cap'
  if (item.value?.top === 'pendant' || String(item.value?.category || '').includes('吊坠')) return 'charm'
  return 'special'
})
const visiblePhysicalFields = computed(() => {
  if (['round', 'faceted_round'].includes(resolvedShape.value)) return []
  return physicalFields.filter((field) => field.kind === 'geometry' || resolvedShape.value === 'bead_cap')
})
const shapeLabel = computed(() => shapeLabels[resolvedShape.value] || '异形材料')
const commercialWarnings = computed(() => {
  if (!item.value?.sku) return []
  const warnings: string[] = []
  if (Number(item.value.sku.cost_price || 0) <= 0) warnings.push('成本价尚未维护，毛利数据会失真')
  if (Number(item.value.sku.safety_stock || 0) <= 0) warnings.push('安全库存为 0，无法提前提示补货')
  if (item.value.sku.enabled && Number(item.value.sku.price_per_bead || 0) <= 0.01) warnings.push('启用中的 SKU 售价异常，请确认是否为测试价格')
  return warnings
})

function displayNumber(value: unknown): number | string {
  const number = Number(value)
  return Number.isFinite(number) && number > 0 ? number : ''
}

function requiredPositive(data: FormData, name: string, label: string): number {
  const value = Number(data.get(name))
  if (!Number.isFinite(value) || value <= 0) throw new Error(`${label}必须大于 0。`)
  return value
}

function optionalPositive(data: FormData, name: string, label: string): number | undefined {
  const raw = String(data.get(name) || '').trim()
  if (!raw) return undefined
  const value = Number(raw)
  if (!Number.isFinite(value) || value <= 0) throw new Error(`${label}必须大于 0，或留空。`)
  return value
}

function requiredNonNegative(data: FormData, name: string, label: string, integer = false): number {
  const value = Number(data.get(name))
  if (!Number.isFinite(value) || value < 0 || (integer && !Number.isInteger(value))) {
    throw new Error(`${label}必须是${integer ? '非负整数' : '大于或等于 0 的数字'}。`)
  }
  return value
}

function moneyInput(value: unknown): string {
  const number = Number(value || 0)
  return Number.isFinite(number) ? number.toFixed(2) : '0.00'
}

function typeLabel(value?: string): string {
  return ({ bead: '珠子', accessory: '配饰', pendant: '花托/吊坠', incense: '合香珠' } as Record<string, string>)[value || ''] || value || '材料'
}

async function load(): Promise<void> {
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  try {
    item.value = await getMaterial(id.value, controller.signal)
  } catch (cause) {
    if (!(cause instanceof DOMException && cause.name === 'AbortError')) {
      error.value = cause instanceof Error ? cause.message : '材料读取失败'
    }
  } finally {
    loading.value = false
  }
}

async function save(event: Event): Promise<void> {
  if (!item.value || saving.value || !canManage.value) return
  const data = new FormData(event.target as HTMLFormElement)
  message.value = ''
  let size: number
  let weight: number
  const physicalSpecs: Record<string, number> = Object.fromEntries(
    Object.entries(item.value.physical_specs || {}).filter((entry): entry is [string, number] => Number.isFinite(Number(entry[1]))).map(([key, value]) => [key, Number(value)]),
  )
  let price: number
  let cost: number
  let stock: number
  let safety: number
  try {
    size = requiredPositive(data, 'size', '珠径 / 外观最大尺寸')
    weight = requiredPositive(data, 'weight', '重量')
    for (const field of visiblePhysicalFields.value) {
      const value = optionalPositive(data, `physical_${field.key}`, field.label)
      if (value !== undefined) physicalSpecs[field.key] = value
      else delete physicalSpecs[field.key]
    }
    price = requiredNonNegative(data, 'price', '单颗售价')
    cost = requiredNonNegative(data, 'cost', '成本价')
    stock = requiredNonNegative(data, 'stock', '库存', true)
    safety = requiredNonNegative(data, 'safety', '安全库存', true)
  } catch (cause) {
    message.value = cause instanceof Error ? cause.message : '请检查实物规格。'
    return
  }
  const payload = {
    price,
    cost_price: cost,
    size,
    weight,
    stock,
    safety_stock: safety,
    enabled: data.get('enabled') === 'true',
    physical_specs: physicalSpecs,
    expected_revision: item.value.sku?.revision,
  }
  saving.value = true
  try {
    item.value = await patchMaterialSku(item.value.id, payload)
    message.value = 'SKU 商业资料与工作台实物规格已保存。'
  } catch (cause) {
    message.value = cause instanceof Error ? cause.message : '保存失败'
  } finally {
    saving.value = false
  }
}

watch(id, () => void load(), { immediate: true })
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <section class="workspace-page material-detail-page">
    <RouterLink
      class="detail-back"
      :to="{ name: 'materials' }"
    >
      ← 返回珠材管理
    </RouterLink>
    <div
      v-if="loading"
      class="design-detail-skeleton"
    >
      <i /><i /><i />
    </div>
    <PageErrorState
      v-else-if="error"
      eyebrow="MATERIAL UNAVAILABLE"
      title="材料详情暂时无法读取"
      :message="error"
      @retry="load"
    />
    <template v-else-if="item">
      <header class="detail-heading">
        <div>
          <span>材料规格</span>
          <h1>{{ item.name || '未命名材料' }}</h1>
          <p>{{ typeLabel(item.top) }} / {{ item.category || '未分类' }} · {{ item.sku?.size_mm || item.size || '-' }} mm · ¥{{ Number(item.sku?.price_per_bead || 0).toFixed(2) }}</p>
        </div>
      </header>
      <p
        v-if="message"
        class="order-action-message"
        role="status"
      >
        {{ message }}
      </p>
      <form
        class="order-detail-grid material-edit-form"
        @submit.prevent="save"
      >
        <div>
          <section class="order-detail-section">
            <div class="detail-section-head">
              <div><span>VISUAL</span><h3>图库</h3></div>
            </div>
            <div class="evidence-strip">
              <a
                v-for="url in item.image_urls || []"
                :key="url"
                :href="url"
                target="_blank"
              ><img
                :src="url"
                alt="材料图库"
              ></a>
              <p v-if="!item.image_urls?.length">
                该品种暂无图库图片
              </p>
            </div>
          </section>
          <section class="order-detail-section material-physical-section">
            <div class="detail-section-head">
              <div><span>WORKBENCH GEOMETRY</span><h3>工作台实物规格</h3></div><b class="material-shape-badge">{{ shapeLabel }}</b>
            </div>
            <p class="material-physical-section__intro">
              {{ visiblePhysicalFields.length ? '已根据品种形制显示需要测量的字段；请按卡尺实测，不相关字段已自动隐藏。' : '圆珠只需要确认珠径和重量，不再展示无意义的异形尺寸。' }}
            </p>
            <div class="material-physical-fields">
              <label><span>珠径 / 外观最大尺寸 <b>*</b></span><div><input
                name="size"
                type="number"
                min="0.001"
                max="1000"
                step="0.001"
                required
                :disabled="saving || !canManage"
                :value="displayNumber(item.sku?.size_mm || item.size)"
              ><small>mm</small></div></label>
              <label><span>重量 <b>*</b></span><div><input
                name="weight"
                type="number"
                min="0.001"
                max="100000"
                step="0.001"
                required
                :disabled="saving || !canManage"
                :value="displayNumber(item.sku?.weight_g || item.weight)"
              ><small>g</small></div></label>
              <label
                v-for="field in visiblePhysicalFields"
                :key="field.key"
              ><span>{{ field.label }}</span><div><input
                :name="`physical_${field.key}`"
                type="number"
                min="0.001"
                max="1000"
                step="0.001"
                :disabled="saving || !canManage"
                :value="displayNumber(item.physical_specs?.[field.key])"
              ><small>{{ field.suffix }}</small></div></label>
            </div>
          </section>
        </div>
        <aside>
          <section class="order-detail-section">
            <div class="detail-section-head">
              <div><span>COMMERCIAL</span><h3>价格与库存</h3></div>
            </div>
            <ul
              v-if="commercialWarnings.length"
              class="material-commercial-warnings"
            >
              <li
                v-for="warning in commercialWarnings"
                :key="warning"
              >
                {{ warning }}
              </li>
            </ul>
            <div class="shipment-form material-commercial-fields">
              <label><span>单颗售价</span><input
                name="price"
                type="number"
                min="0"
                step="0.01"
                :disabled="saving || !canManage"
                :value="moneyInput(item.sku?.price_per_bead)"
              ></label>
              <label><span>成本价</span><input
                name="cost"
                type="number"
                min="0"
                step="0.01"
                :disabled="saving || !canManage"
                :value="moneyInput(item.sku?.cost_price)"
              ></label>
              <label><span>库存</span><input
                name="stock"
                type="number"
                min="0"
                :disabled="saving || !canManage"
                :value="item.sku?.stock || 0"
              ></label>
              <label><span>安全库存</span><input
                name="safety"
                type="number"
                min="0"
                :disabled="saving || !canManage"
                :value="item.sku?.safety_stock || 0"
              ></label>
              <label><span>状态</span><select
                name="enabled"
                :disabled="saving || !canManage"
                :value="String(!!item.sku?.enabled)"
              ><option value="true">启用</option><option value="false">停用</option></select></label>
              <button
                class="primary-action"
                type="submit"
                :disabled="saving || !canManage"
              >
                {{ saving ? '保存中…' : '保存 SKU 资料' }}
              </button>
            </div>
          </section>
        </aside>
      </form>
    </template>
  </section>
</template>
