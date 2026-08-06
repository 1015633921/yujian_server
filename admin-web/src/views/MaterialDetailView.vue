<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import { getMaterial, patchMaterialSku, type Material } from '@/features/materials/api'
const route = useRoute(); const item = ref<Material | null>(null); const loading = ref(true); const error = ref(''); const saving = ref(false); const message = ref(''); let controller: AbortController | null = null
const id = computed(() => String(route.params.materialId || ''))
async function load() { controller?.abort(); controller = new AbortController(); loading.value = true; error.value = ''; try { item.value = await getMaterial(id.value, controller.signal) } catch (cause) { if (!(cause instanceof DOMException && cause.name === 'AbortError')) error.value = cause instanceof Error ? cause.message : '材料读取失败' } finally { loading.value = false } }
async function save(event: Event) { if (!item.value || saving.value) return; const data = new FormData(event.target as HTMLFormElement); const payload = { price: Number(data.get('price')), cost_price: Number(data.get('cost')), stock: Number(data.get('stock')), safety_stock: Number(data.get('safety')), enabled: data.get('enabled') === 'true', expected_revision: item.value.sku?.revision }; saving.value = true; message.value = ''; try { item.value = await patchMaterialSku(item.value.id, payload); message.value = 'SKU 商业资料已保存。' } catch (cause) { message.value = cause instanceof Error ? cause.message : '保存失败' } finally { saving.value = false } }
watch(id, () => void load(), { immediate: true }); onBeforeUnmount(() => controller?.abort())
</script>
<template>
  <section class="workspace-page">
    <RouterLink
      class="detail-back"
      :to="{ name: 'materials' }"
    >
      ← 返回材料目录
    </RouterLink><div
      v-if="loading"
      class="design-detail-skeleton"
    >
      <i /><i /><i />
    </div><PageErrorState
      v-else-if="error"
      eyebrow="MATERIAL UNAVAILABLE"
      title="材料详情暂时无法读取"
      :message="error"
      @retry="load"
    /><template v-else-if="item">
      <header class="detail-heading">
        <div><span>材料规格</span><h1>{{ item.name || '未命名材料' }}</h1><p>{{ item.top || '-' }} · {{ item.sku?.size_mm || item.size || '-' }}mm · ¥{{ Number(item.sku?.price_per_bead || 0).toFixed(2) }}</p></div>
      </header><p
        v-if="message"
        class="order-action-message"
      >
        {{ message }}
      </p><div class="order-detail-grid">
        <div>
          <section class="order-detail-section">
            <div class="detail-section-head">
              <div><span>VISUAL</span><h3>图库</h3></div>
            </div><div class="evidence-strip">
              <a
                v-for="url in item.image_urls || []"
                :key="url"
                :href="url"
                target="_blank"
              ><img
                :src="url"
                alt="材料图库"
              ></a><p v-if="!item.image_urls?.length">
                该品种暂无图库图片
              </p>
            </div>
          </section>
        </div><aside>
          <section class="order-detail-section">
            <div class="detail-section-head">
              <div><span>COMMERCIAL</span><h3>价格与库存</h3></div>
            </div><form
              class="shipment-form material-edit-form"
              @submit.prevent="save"
            >
              <label><span>单颗售价</span><input
                name="price"
                type="number"
                min="0"
                step="0.01"
                :value="item.sku?.price_per_bead || 0"
              ></label><label><span>成本价</span><input
                name="cost"
                type="number"
                min="0"
                step="0.01"
                :value="item.sku?.cost_price || 0"
              ></label><label><span>库存</span><input
                name="stock"
                type="number"
                min="0"
                :value="item.sku?.stock || 0"
              ></label><label><span>安全库存</span><input
                name="safety"
                type="number"
                min="0"
                :value="item.sku?.safety_stock || 0"
              ></label><label><span>状态</span><select
                name="enabled"
                :value="String(!!item.sku?.enabled)"
              ><option value="true">启用</option><option value="false">停用</option></select></label><button
                class="primary-action"
                :disabled="saving"
              >
                {{ saving ? '保存中…' : '保存 SKU' }}
              </button>
            </form>
          </section>
        </aside>
      </div>
    </template>
  </section>
</template>
