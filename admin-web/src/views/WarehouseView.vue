<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import PageEmptyState from '@/components/ui/PageEmptyState.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import {
  createWarehouseInbound,
  createWarehouseOutbound,
  listWarehouseMovements,
  listWarehouseItems,
  listWarehouseBatches,
  saveWarehouseChannel,
  saveWarehouseLocation,
  saveWarehouseSupplier,
  warehouseOptions,
  warehouseOverview,
  type WarehouseItem,
  type WarehouseBatch,
  type WarehouseChannel,
  type WarehouseLocation,
  type WarehouseMovement,
  type WarehouseOptions,
  type WarehouseOverview,
  type WarehouseSupplier,
} from '@/features/warehouse/api'

const tab = ref<'overview' | 'items'>('overview')
type LedgerTab = 'overview' | 'items' | 'batches' | 'movements' | 'inbound' | 'outbound' | 'settings'
type SettingKind = 'supplier' | 'location' | 'channel'
type BasicSetting = WarehouseSupplier | WarehouseLocation | WarehouseChannel
interface BasicSettingForm { id: string; code: string; name: string; contactName: string; phone: string; address: string; area: string; shelf: string; boxNo: string; channelType: string; remark: string; enabled: boolean }

const ledgerTab = ref<LedgerTab>('overview')
const overview = ref<WarehouseOverview | null>(null)
const options = ref<WarehouseOptions | null>(null)
const items = ref<WarehouseItem[]>([])
const keyword = ref('')
const category = ref('')
const itemType = ref('')
const enabled = ref('')
const batches = ref<WarehouseBatch[]>([])
const batchRows = ref<WarehouseBatch[]>([])
const movements = ref<WarehouseMovement[]>([])
const batchKeyword = ref('')
const batchItemId = ref('')
const batchStatus = ref('')
const movementKeyword = ref('')
const movementItemId = ref('')
const movementType = ref('')
const movementChannelId = ref('')
const movementStartDate = ref('')
const movementEndDate = ref('')
const settingKind = ref<SettingKind>('supplier')
const settingNotice = ref('')
const savingSetting = ref(false)
const settingForm = ref<BasicSettingForm>({ id: '', code: '', name: '', contactName: '', phone: '', address: '', area: '', shelf: '', boxNo: '', channelType: 'manual', remark: '', enabled: true })
const busy = ref(false)
const notice = ref('')
const inbound = ref({ item_id: '', supplier_id: '', location_id: '', quantity: 1, unit_cost: 0, purchase_date: '', quality_note: '', remark: '' })
const outbound = ref({ item_id: '', batch_id: '', movement_type: 'sale_out', channel_id: '', quantity: 1, external_order_no: '', reason: '', remark: '' })
const loading = ref(true)
const error = ref('')
let controller: AbortController | null = null

const stockLabel = computed(() => `${overview.value?.stats.total_stock || 0}`)
function money(value = 0): string { return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY', maximumFractionDigits: 2 }).format(value) }
function typeLabel(value: string): string { return options.value?.item_types.find((item) => item.key === value)?.label as string || value || '—' }
function movementLabel(value: string): string { return options.value?.movement_types.find((item) => item.key === value)?.label as string || value || '—' }
function batchStatusLabel(value: string): string { return value === 'active' ? '可用' : value === 'empty' ? '已耗尽' : value || '—' }
const settings = computed<BasicSetting[]>(() => settingKind.value === 'supplier' ? options.value?.suppliers || [] : settingKind.value === 'location' ? options.value?.locations || [] : options.value?.channels || [])
function settingId(item: BasicSetting): string { return 'supplier_id' in item ? item.supplier_id : 'location_id' in item ? item.location_id : item.channel_id }
function settingCode(item: BasicSetting): string { return 'supplier_code' in item ? item.supplier_code : 'location_code' in item ? item.location_code : item.channel_code }
function settingMeta(item: BasicSetting): string { return 'contact_name' in item ? [item.contact_name, item.phone].filter(Boolean).join(' · ') : 'area' in item ? [item.area, item.shelf, item.box_no].filter(Boolean).join(' / ') : item.channel_type }
function resetSetting(): void { settingForm.value = { id: '', code: '', name: '', contactName: '', phone: '', address: '', area: '', shelf: '', boxNo: '', channelType: 'manual', remark: '', enabled: true }; settingNotice.value = '' }
function chooseSetting(kind: SettingKind): void { settingKind.value = kind; resetSetting() }
function editSetting(item: BasicSetting): void {
  settingForm.value = {
    id: settingId(item), code: settingCode(item), name: item.name, remark: item.remark, enabled: item.enabled,
    contactName: 'contact_name' in item ? item.contact_name : '', phone: 'phone' in item ? item.phone : '', address: 'address' in item ? item.address : '',
    area: 'area' in item ? item.area : '', shelf: 'shelf' in item ? item.shelf : '', boxNo: 'box_no' in item ? item.box_no : '', channelType: 'channel_type' in item ? item.channel_type : 'manual',
  }
  settingNotice.value = `正在编辑 ${item.name}。`
}

async function loadOverview(): Promise<void> {
  controller?.abort(); controller = new AbortController(); loading.value = true; error.value = ''
  try { const [nextOverview, nextOptions] = await Promise.all([warehouseOverview(controller.signal), options.value ? Promise.resolve(options.value) : warehouseOptions(controller.signal)]); overview.value = nextOverview; options.value = nextOptions } catch (cause) { if (cause instanceof DOMException && cause.name === 'AbortError') return; error.value = cause instanceof Error ? cause.message : '仓库概览加载失败' } finally { loading.value = false }
}
async function loadItems(): Promise<void> {
  controller?.abort(); controller = new AbortController(); loading.value = true; error.value = ''
  try { const [nextItems, nextOptions] = await Promise.all([listWarehouseItems({ keyword: keyword.value, category: category.value, itemType: itemType.value, enabled: enabled.value }, controller.signal), options.value ? Promise.resolve(options.value) : warehouseOptions(controller.signal)]); items.value = nextItems; options.value = nextOptions } catch (cause) { if (cause instanceof DOMException && cause.name === 'AbortError') return; error.value = cause instanceof Error ? cause.message : '库存品加载失败' } finally { loading.value = false }
}
async function loadBatches(): Promise<void> {
  controller?.abort(); controller = new AbortController(); loading.value = true; error.value = ''
  try { batchRows.value = await listWarehouseBatches({ keyword: batchKeyword.value, itemId: batchItemId.value, status: batchStatus.value }, controller.signal) } catch (cause) { if (cause instanceof DOMException && cause.name === 'AbortError') return; error.value = cause instanceof Error ? cause.message : '库存批次加载失败' } finally { loading.value = false }
}
async function loadMovements(): Promise<void> {
  controller?.abort(); controller = new AbortController(); loading.value = true; error.value = ''
  try { movements.value = await listWarehouseMovements({ keyword: movementKeyword.value, itemId: movementItemId.value, movementType: movementType.value, channelId: movementChannelId.value, startDate: movementStartDate.value, endDate: movementEndDate.value }, controller.signal) } catch (cause) { if (cause instanceof DOMException && cause.name === 'AbortError') return; error.value = cause instanceof Error ? cause.message : '库存流水加载失败' } finally { loading.value = false }
}
async function loadSettings(): Promise<void> { options.value = await warehouseOptions() }
async function switchTab(next: LedgerTab): Promise<void> {
  ledgerTab.value = next
  if (next === 'overview' || next === 'items') tab.value = next
  if ((next === 'inbound' || next === 'outbound' || next === 'batches' || next === 'movements') && !items.value.length) await loadItems()
  if (next === 'batches') await loadBatches()
  if (next === 'movements') await loadMovements()
  if (next === 'settings' && !options.value) await loadSettings()
}
function refresh(): void {
  if (ledgerTab.value === 'overview') void loadOverview()
  else if (ledgerTab.value === 'items') void loadItems()
  else if (ledgerTab.value === 'batches') void loadBatches()
  else if (ledgerTab.value === 'movements') void loadMovements()
  else if (ledgerTab.value === 'settings') void loadSettings()
  else void loadOverview()
}
watch(tab, () => { if (tab.value === 'overview') void loadOverview(); else void loadItems() })
watch(() => outbound.value.item_id, async (itemId) => {
  try { batches.value = itemId ? await listWarehouseBatches({ itemId }) : [] } catch (cause) { notice.value = cause instanceof Error ? cause.message : '指定批次加载失败。'; batches.value = [] }
  outbound.value.batch_id = ''
})
watch([keyword, category, itemType, enabled], () => { if (tab.value === 'items') void loadItems() })
watch([batchKeyword, batchItemId, batchStatus], () => { if (ledgerTab.value === 'batches') void loadBatches() })
watch([movementKeyword, movementItemId, movementType, movementChannelId, movementStartDate, movementEndDate], () => { if (ledgerTab.value === 'movements') void loadMovements() })
onBeforeUnmount(() => controller?.abort())
void loadOverview()

async function submitInbound(): Promise<void> { if (busy.value) return; busy.value = true; notice.value = ''; try { const saved = await createWarehouseInbound(inbound.value); notice.value = `已入库，批次号 ${saved.batch_no}。`; inbound.value = { item_id: '', supplier_id: '', location_id: '', quantity: 1, unit_cost: 0, purchase_date: '', quality_note: '', remark: '' }; await loadOverview() } catch (cause) { notice.value = cause instanceof Error ? cause.message : '入库失败。' } finally { busy.value = false } }
async function submitOutbound(): Promise<void> { if (busy.value) return; if (!window.confirm('确认出库后将按指定批次或先进先出扣减库存，确定继续吗？')) return; busy.value = true; notice.value = ''; try { const saved = await createWarehouseOutbound(outbound.value); notice.value = `已出库 ${saved.quantity} 件，已生成 ${saved.entries.length} 条库存流水。`; outbound.value = { item_id: '', batch_id: '', movement_type: 'sale_out', channel_id: '', quantity: 1, external_order_no: '', reason: '', remark: '' }; batches.value = []; await loadOverview() } catch (cause) { notice.value = cause instanceof Error ? cause.message : '出库失败。' } finally { busy.value = false } }
async function submitSetting(): Promise<void> {
  if (savingSetting.value) return
  savingSetting.value = true; settingNotice.value = ''
  try {
    const form = settingForm.value
    if (settingKind.value === 'supplier') await saveWarehouseSupplier({ supplier_id: form.id, supplier_code: form.code, name: form.name, contact_name: form.contactName, phone: form.phone, address: form.address, remark: form.remark, enabled: form.enabled })
    if (settingKind.value === 'location') await saveWarehouseLocation({ location_id: form.id, location_code: form.code, name: form.name, area: form.area, shelf: form.shelf, box_no: form.boxNo, remark: form.remark, enabled: form.enabled })
    if (settingKind.value === 'channel') await saveWarehouseChannel({ channel_id: form.id, channel_code: form.code, name: form.name, channel_type: form.channelType || 'manual', remark: form.remark, enabled: form.enabled })
    await loadSettings(); resetSetting(); settingNotice.value = '基础资料已保存。'
  } catch (cause) { settingNotice.value = cause instanceof Error ? cause.message : '基础资料保存失败。' } finally { savingSetting.value = false }
}
</script>

<template>
  <section class="workspace-page warehouse-page">
    <PageHeading
      eyebrow="WAREHOUSE LEDGER"
      title="仓库库存"
      description="独立记录散珠、配件、线材、包装等实物仓储；不自动联动小程序商品库存或外部平台订单。"
    >
      <template #actions>
        <button
          class="heading-link"
          type="button"
          @click="refresh"
        >
          刷新数据
        </button>
      </template>
    </PageHeading>
    <nav
      class="warehouse-tabs"
      aria-label="仓库功能"
    >
      <button
        :class="{ 'is-current': ledgerTab === 'overview' }"
        type="button"
        @click="switchTab('overview')"
      >
        库存概览
      </button>
      <button
        :class="{ 'is-current': ledgerTab === 'items' }"
        type="button"
        @click="switchTab('items')"
      >
        库存品
      </button>
      <button
        :class="{ 'is-current': ledgerTab === 'batches' }"
        type="button"
        @click="switchTab('batches')"
      >
        库存批次
      </button>
      <button
        :class="{ 'is-current': ledgerTab === 'movements' }"
        type="button"
        @click="switchTab('movements')"
      >
        库存流水
      </button>
      <button
        :class="{ 'is-current': ledgerTab === 'inbound' }"
        type="button"
        @click="switchTab('inbound')"
      >
        入库
      </button>
      <button
        :class="{ 'is-current': ledgerTab === 'outbound' }"
        type="button"
        @click="switchTab('outbound')"
      >
        出库
      </button>
      <button
        :class="{ 'is-current': ledgerTab === 'settings' }"
        type="button"
        @click="switchTab('settings')"
      >
        基础资料
      </button>
      <span>库存以批次账本为准，数量由服务端统一计算。</span>
    </nav>
    <PageErrorState
      v-if="error && !loading"
      title="仓库数据暂时无法读取"
      :message="error"
      eyebrow="WAREHOUSE UNAVAILABLE"
      @retry="refresh"
    />
    <template v-else-if="ledgerTab === 'overview'">
      <div
        v-if="loading || !overview"
        class="warehouse-skeleton"
      >
        <i
          v-for="item in 8"
          :key="item"
        />
      </div>
      <template v-else>
        <div class="warehouse-metrics">
          <div><span>库存品类</span><strong>{{ overview.stats.item_count }}</strong><small>已建档的仓库实物</small></div><div><span>实物库存</span><strong>{{ stockLabel }}</strong><small>当前剩余数量</small></div><div><span>库存成本</span><strong>{{ money(overview.stats.stock_value) }}</strong><small>按批次成本估算</small></div><div><span>有效批次</span><strong>{{ overview.stats.batch_count }}</strong><small>{{ overview.stats.zero_stock_items }} 个零库存品类</small></div>
        </div>
        <div class="warehouse-grid">
          <section>
            <header><span>STOCK ALERT</span><h2>低库存 / 零库存</h2><p>优先补拍、补货或下架的仓库实物。</p></header><PageEmptyState
              v-if="!overview.low_stock_items.length"
              title="暂无低库存品"
              message="当前启用库存品均有可用余额。"
            /><div
              v-else
              class="warehouse-alert-list"
            >
              <article
                v-for="item in overview.low_stock_items"
                :key="item.item_id"
              >
                <img
                  v-if="item.image_urls?.[0]"
                  :src="item.image_urls[0]"
                  :alt="item.display_name"
                ><i v-else /><div><strong>{{ item.display_name }}</strong><small>{{ item.item_code }} · {{ item.category || typeLabel(item.item_type) }}</small></div><b :class="{ 'is-danger': item.actual_stock <= 0 }">{{ item.actual_stock }} {{ item.unit_label || item.unit }}</b>
              </article>
            </div>
          </section><section>
            <header><span>RECENT MOVEMENTS</span><h2>最近库存流水</h2><p>最近入库、销售出库、损耗和人工调整。</p></header><PageEmptyState
              v-if="!overview.recent_movements.length"
              title="暂无库存流水"
              message="完成首次入库后会在这里展示。"
            /><ol
              v-else
              class="warehouse-history"
            >
              <li
                v-for="movement in overview.recent_movements"
                :key="movement.movement_id"
              >
                <small>{{ movement.occurred_at || '—' }}</small><strong>{{ movement.item_name || movement.item_code }}</strong><span>{{ movementLabel(movement.movement_type) }} · {{ movement.quantity }}</span>
              </li>
            </ol>
          </section>
        </div>
      </template>
    </template>
    <template v-else-if="ledgerTab === 'items'">
      <div class="warehouse-filter">
        <input
          v-model="keyword"
          placeholder="搜索品名、编码、分类、颜色"
        ><select v-model="itemType">
          <option value="">
            全部类型
          </option><option
            v-for="item in options?.item_types || []"
            :key="String(item.key)"
            :value="String(item.key)"
          >
            {{ item.label }}
          </option>
        </select><input
          v-model="category"
          placeholder="分类筛选"
        ><select v-model="enabled">
          <option value="">
            全部状态
          </option><option value="1">
            启用
          </option><option value="0">
            停用
          </option>
        </select>
      </div>
      <div
        v-if="loading"
        class="warehouse-skeleton"
      >
        <i
          v-for="item in 8"
          :key="item"
        />
      </div>
      <PageEmptyState
        v-else-if="!items.length"
        title="没有符合条件的库存品"
        message="调整筛选条件，或稍后从旧后台新增库存品。"
      />
      <div
        v-else
        class="warehouse-items"
      >
        <div class="warehouse-items__head">
          <span>库存品</span><span>现有库存</span><span>平均成本</span><span>状态</span>
        </div><article
          v-for="item in items"
          :key="item.item_id"
        >
          <div>
            <img
              v-if="item.image_urls?.[0]"
              :src="item.image_urls[0]"
              :alt="item.display_name"
            ><i v-else /><p><strong>{{ item.display_name }}</strong><small>{{ item.item_code }} · {{ typeLabel(item.item_type) }} · {{ item.category || '未分类' }}</small></p>
          </div><b>{{ item.actual_stock }} {{ item.unit_label || item.unit }}<small>{{ item.batch_count }} 个批次</small></b><b>{{ item.avg_cost ? money(item.avg_cost) : '—' }}<small>成本额 {{ money(item.stock_cost_value) }}</small></b><span :class="{ 'is-disabled': !item.enabled }">{{ item.enabled ? '启用' : '停用' }}</span>
        </article>
      </div>
    </template>
    <template v-else-if="ledgerTab === 'batches'">
      <div class="warehouse-filter warehouse-filter--batches">
        <input
          v-model.trim="batchKeyword"
          placeholder="搜索批次号、品名或库存编码"
        >
        <select v-model="batchItemId">
          <option value="">
            全部库存品
          </option>
          <option
            v-for="item in items"
            :key="item.item_id"
            :value="item.item_id"
          >
            {{ item.display_name }} · {{ item.item_code }}
          </option>
        </select>
        <select v-model="batchStatus">
          <option value="">
            全部批次状态
          </option>
          <option value="active">
            可用
          </option>
          <option value="empty">
            已耗尽
          </option>
        </select>
      </div>
      <div
        v-if="loading"
        class="warehouse-skeleton"
      >
        <i
          v-for="item in 8"
          :key="item"
        />
      </div>
      <PageEmptyState
        v-else-if="!batchRows.length"
        title="没有符合条件的库存批次"
        message="完成首次入库后，批次及其剩余数量会在这里展示。"
      />
      <div
        v-else
        class="warehouse-ledger"
      >
        <div class="warehouse-ledger__head warehouse-ledger__head--batch">
          <span>批次 / 库存品</span><span>入库</span><span>剩余</span><span>单位成本</span><span>来源与仓位</span><span>状态</span>
        </div>
        <article
          v-for="batch in batchRows"
          :key="batch.batch_id"
          class="warehouse-ledger__batch"
        >
          <p><strong>{{ batch.batch_no }}</strong><small>{{ batch.item_name || batch.item_code }}</small></p><b>{{ batch.inbound_quantity }}</b><b>{{ batch.remaining_quantity }}</b><b>{{ money(batch.unit_cost) }}</b><p><strong>{{ batch.supplier_name || '未指定供应商' }}</strong><small>{{ batch.location_name || '未指定仓位' }} · {{ batch.inbound_at || batch.purchase_date || '—' }}</small></p><span :class="{ 'is-disabled': batch.status !== 'active' }">{{ batchStatusLabel(batch.status) }}</span>
        </article>
      </div>
    </template>
    <template v-else-if="ledgerTab === 'movements'">
      <div class="warehouse-filter warehouse-filter--movements">
        <input
          v-model.trim="movementKeyword"
          placeholder="搜索流水号、订单号、品名或编码"
        >
        <select v-model="movementItemId">
          <option value="">
            全部库存品
          </option>
          <option
            v-for="item in items"
            :key="item.item_id"
            :value="item.item_id"
          >
            {{ item.display_name }}
          </option>
        </select>
        <select v-model="movementType">
          <option value="">
            全部流水类型
          </option>
          <option
            v-for="item in options?.movement_types || []"
            :key="String(item.key)"
            :value="String(item.key)"
          >
            {{ item.label }}
          </option>
        </select>
        <select v-model="movementChannelId">
          <option value="">
            全部渠道
          </option>
          <option
            v-for="item in options?.channels || []"
            :key="String(item.channel_id)"
            :value="String(item.channel_id)"
          >
            {{ item.name }}
          </option>
        </select>
        <input
          v-model="movementStartDate"
          aria-label="流水开始日期"
          type="date"
        >
        <input
          v-model="movementEndDate"
          aria-label="流水结束日期"
          type="date"
        >
      </div>
      <div
        v-if="loading"
        class="warehouse-skeleton"
      >
        <i
          v-for="item in 8"
          :key="item"
        />
      </div>
      <PageEmptyState
        v-else-if="!movements.length"
        title="没有符合条件的库存流水"
        message="入库、出库、退货及人工调整都会保留在这里。"
      />
      <div
        v-else
        class="warehouse-ledger"
      >
        <div class="warehouse-ledger__head warehouse-ledger__head--movement">
          <span>时间 / 流水号</span><span>库存品 / 批次</span><span>类型</span><span>变动</span><span>变动后</span><span>渠道 / 订单</span>
        </div>
        <article
          v-for="movement in movements"
          :key="movement.movement_id"
          class="warehouse-ledger__movement"
        >
          <p><strong>{{ movement.occurred_at || '—' }}</strong><small>{{ movement.movement_no || movement.movement_id }}</small></p><p><strong>{{ movement.item_name || movement.item_code }}</strong><small>{{ movement.batch_no || '未指定批次' }}</small></p><span>{{ movementLabel(movement.movement_type) }}</span><b :class="{ 'is-out': movement.quantity < 0 }">{{ movement.quantity > 0 ? '+' : '' }}{{ movement.quantity }}</b><b>{{ movement.after_quantity ?? '—' }}</b><p><strong>{{ movement.channel_name || '—' }}</strong><small>{{ movement.external_order_no || movement.reason || '—' }}</small></p>
        </article>
      </div>
    </template>
    <section
      v-else-if="ledgerTab === 'settings'"
      class="warehouse-settings"
    >
      <header>
        <div>
          <span>WAREHOUSE REFERENCES</span>
          <h2>供应商、仓位与渠道</h2>
          <p>这些资料只服务仓库出入库及流水归因，不会改变小程序商品或订单。</p>
        </div>
        <nav aria-label="基础资料类型">
          <button
            v-for="item in [{ key: 'supplier', label: '供应商' }, { key: 'location', label: '仓位' }, { key: 'channel', label: '出库渠道' }]"
            :key="item.key"
            :class="{ 'is-current': settingKind === item.key }"
            type="button"
            @click="chooseSetting(item.key as SettingKind)"
          >
            {{ item.label }}
          </button>
        </nav>
      </header>
      <div class="warehouse-settings__workspace">
        <div class="warehouse-settings__list">
          <div class="warehouse-settings__list-head">
            <span>编码 / 名称</span><span>辅助信息</span><span>状态</span>
          </div>
          <PageEmptyState
            v-if="!settings.length"
            :title="`暂无${settingKind === 'supplier' ? '供应商' : settingKind === 'location' ? '仓位' : '出库渠道'}`"
            message="可在右侧新增，系统会自动生成编码。"
          />
          <template v-else>
            <button
              v-for="item in settings"
              :key="settingId(item)"
              class="warehouse-settings__item"
              :class="{ 'is-current': settingForm.id === settingId(item) }"
              type="button"
              @click="editSetting(item)"
            >
              <p><strong>{{ item.name }}</strong><small>{{ settingCode(item) }}</small></p><small>{{ settingMeta(item) || item.remark || '—' }}</small><span :class="{ 'is-disabled': !item.enabled }">{{ item.enabled ? '启用' : '停用' }}</span>
            </button>
          </template>
        </div>
        <form
          class="warehouse-settings__form"
          @submit.prevent="submitSetting"
        >
          <div class="warehouse-settings__form-head">
            <div><span>{{ settingForm.id ? 'EDIT REFERENCE' : 'NEW REFERENCE' }}</span><h3>{{ settingForm.id ? '编辑基础资料' : `新增${settingKind === 'supplier' ? '供应商' : settingKind === 'location' ? '仓位' : '出库渠道'}` }}</h3></div>
            <button
              v-if="settingForm.id"
              type="button"
              @click="resetSetting"
            >
              新增一项
            </button>
          </div>
          <label>名称<input
            v-model.trim="settingForm.name"
            required
          ></label><label>编码（可留空）<input v-model.trim="settingForm.code"></label>
          <template v-if="settingKind === 'supplier'">
            <label>联系人<input v-model.trim="settingForm.contactName"></label><label>电话<input v-model.trim="settingForm.phone"></label><label class="warehouse-settings__full">地址<input v-model.trim="settingForm.address"></label>
          </template>
          <template v-else-if="settingKind === 'location'">
            <label>区域<input v-model.trim="settingForm.area"></label><label>货架<input v-model.trim="settingForm.shelf"></label><label>盒号<input v-model.trim="settingForm.boxNo"></label>
          </template>
          <template v-else>
            <label>渠道类型<select v-model="settingForm.channelType"><option value="manual">人工</option><option value="offline">线下</option><option value="online">线上</option></select></label>
          </template>
          <label class="warehouse-settings__full">备注<textarea v-model.trim="settingForm.remark" /></label><label class="warehouse-settings__enabled"><input
            v-model="settingForm.enabled"
            type="checkbox"
          > 启用此资料</label><footer>
            <button
              class="primary-action"
              :disabled="savingSetting"
              type="submit"
            >
              保存资料
            </button><p>{{ settingNotice }}</p>
          </footer>
        </form>
      </div>
    </section>
    <form
      v-else-if="ledgerTab === 'inbound'"
      class="warehouse-write-form"
      @submit.prevent="submitInbound"
    >
      <h2>采购 / 拍摄入库</h2><p>每次入库将生成独立批次与库存流水。</p><label>库存品<select
        v-model="inbound.item_id"
        required
      ><option value="">请选择库存品</option><option
        v-for="item in items"
        :key="item.item_id"
        :value="item.item_id"
      >{{ item.display_name }} · {{ item.item_code }}</option></select></label><label>供应商<select v-model="inbound.supplier_id"><option value="">未指定</option><option
        v-for="item in options?.suppliers || []"
        :key="String(item.supplier_id)"
        :value="String(item.supplier_id)"
      >{{ item.name }}</option></select></label><label>仓位<select v-model="inbound.location_id"><option value="">未指定</option><option
        v-for="item in options?.locations || []"
        :key="String(item.location_id)"
        :value="String(item.location_id)"
      >{{ item.name }}</option></select></label><label>数量<input
        v-model.number="inbound.quantity"
        min="1"
        type="number"
        required
      ></label><label>单位成本<input
        v-model.number="inbound.unit_cost"
        min="0"
        step="0.01"
        type="number"
      ></label><label>采购日期<input
        v-model="inbound.purchase_date"
        type="date"
      ></label><label class="warehouse-write-form__full">质量备注<textarea v-model="inbound.quality_note" /></label><label class="warehouse-write-form__full">备注<textarea v-model="inbound.remark" /></label><footer>
        <button
          class="primary-action"
          :disabled="busy"
          type="submit"
        >
          确认入库
        </button><p>{{ notice }}</p>
      </footer>
    </form>
    <form
      v-else-if="ledgerTab === 'outbound'"
      class="warehouse-write-form"
      @submit.prevent="submitOutbound"
    >
      <h2>销售 / 损耗出库</h2><p>不指定批次时由后端按先进先出扣减；库存不足将拒绝出库。</p><label>库存品<select
        v-model="outbound.item_id"
        required
      ><option value="">请选择库存品</option><option
        v-for="item in items"
        :key="item.item_id"
        :value="item.item_id"
      >{{ item.display_name }} · 可用 {{ item.actual_stock }}</option></select></label><label>指定批次<select v-model="outbound.batch_id"><option value="">自动先进先出</option><option
        v-for="item in batches"
        :key="item.batch_id"
        :value="item.batch_id"
      >{{ item.batch_no }} · 剩余 {{ item.remaining_quantity }}</option></select></label><label>出库类型<select v-model="outbound.movement_type"><option
        v-for="item in options?.movement_types || []"
        :key="String(item.key)"
        :value="String(item.key)"
      >{{ item.label }}</option></select></label><label>渠道<select v-model="outbound.channel_id"><option value="">未指定</option><option
        v-for="item in options?.channels || []"
        :key="String(item.channel_id)"
        :value="String(item.channel_id)"
      >{{ item.name }}</option></select></label><label>数量<input
        v-model.number="outbound.quantity"
        min="1"
        type="number"
        required
      ></label><label>外部订单号<input v-model.trim="outbound.external_order_no"></label><label class="warehouse-write-form__full">原因<input v-model.trim="outbound.reason"></label><label class="warehouse-write-form__full">备注<textarea v-model="outbound.remark" /></label><footer>
        <button
          class="primary-action"
          :disabled="busy"
          type="submit"
        >
          确认出库
        </button><p>{{ notice }}</p>
      </footer>
    </form>
  </section>
</template>
