<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageEmptyState from '@/components/ui/PageEmptyState.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import { listMaterials, listMaterialTypes, type Material, type MaterialType } from '@/features/materials/api'
import { legacyAdminPath } from '@/runtime/environment'
const route = useRoute(); const router = useRouter(); const items = ref<Material[]>([]); const types = ref<MaterialType[]>([]); const loading = ref(true); const error = ref(''); const total = ref(0); const hasNext = ref(false); let controller: AbortController | null = null
const keyword = computed(() => typeof route.query.keyword === 'string' ? route.query.keyword : ''); const top = computed(() => typeof route.query.top === 'string' ? route.query.top : ''); const status = computed(() => typeof route.query.status === 'string' ? route.query.status : ''); const page = computed(() => Math.max(1, Number(route.query.page) || 1))
function updateQuery(updates: Record<string, string | undefined>) { const query = { ...route.query }; Object.entries(updates).forEach(([key, value]) => value ? query[key] = value : delete query[key]); void router.replace({ query }) }
async function load() { controller?.abort(); controller = new AbortController(); loading.value = true; error.value = ''; try { const [result, materialTypes] = await Promise.all([listMaterials({ keyword: keyword.value, top: top.value, status: status.value, page: page.value, pageSize: 30 }, controller.signal), types.value.length ? Promise.resolve(types.value) : listMaterialTypes(false, controller.signal)]); items.value = result.items; total.value = result.pagination.total; hasNext.value = result.pagination.has_next; types.value = materialTypes } catch (cause) { if (cause instanceof DOMException && cause.name === 'AbortError') return; error.value = cause instanceof Error ? cause.message : '材料目录加载失败' } finally { loading.value = false } }
function search(event: Event) { const value = new FormData(event.target as HTMLFormElement).get('keyword'); updateQuery({ keyword: typeof value === 'string' ? value.trim() || undefined : undefined, page: undefined }) }
watch(() => [keyword.value, top.value, status.value, page.value], () => void load(), { immediate: true }); onBeforeUnmount(() => controller?.abort())
</script>
<template>
  <section class="workspace-page materials-page">
    <PageHeading
      eyebrow="MATERIAL CATALOG"
      title="材料 SKU"
      description="维护价格、库存、规格与图库；销售和工作台均使用此目录。"
    >
      <template #actions>
        <a
          class="heading-link"
          :href="`${legacyAdminPath()}?page=materials`"
        >当前后台完整编辑 ↗</a>
      </template>
    </PageHeading><div class="materials-toolbar">
      <form @submit.prevent="search">
        <input
          name="keyword"
          :value="keyword"
          placeholder="搜索名称、SKU 或材料编码"
        ><button>查询</button>
      </form><select
        :value="top"
        @change="updateQuery({ top: ($event.target as HTMLSelectElement).value || undefined, page: undefined })"
      >
        <option value="">
          全部类型
        </option><option
          v-for="type in types"
          :key="type.code"
          :value="type.code"
        >
          {{ type.name }}
        </option>
      </select><select
        :value="status"
        @change="updateQuery({ status: ($event.target as HTMLSelectElement).value || undefined, page: undefined })"
      >
        <option value="">
          全部状态
        </option><option value="enabled">
          已启用
        </option><option value="disabled">
          已停用
        </option>
      </select><span>{{ total }} 个 SKU</span>
    </div><div
      v-if="loading"
      class="order-list-skeleton"
    >
      <i /><i /><i />
    </div><PageErrorState
      v-else-if="error"
      eyebrow="CATALOG UNAVAILABLE"
      title="材料目录暂时无法读取"
      :message="error"
      @retry="load"
    /><PageEmptyState
      v-else-if="!items.length"
      title="暂无符合条件的材料"
      message="调整筛选或前往当前后台新增材料。"
      @clear="updateQuery({ keyword: undefined, top: undefined, status: undefined })"
    /><template v-else>
      <div class="materials-grid">
        <article
          v-for="item in items"
          :key="item.id"
        >
          <RouterLink :to="{ name: 'material-detail', params: { materialId: item.id } }">
            <img
              v-if="item.image_url || item.image_urls?.[0]"
              :src="item.image_url || item.image_urls?.[0]"
              alt=""
            ><i v-else />
          </RouterLink><div>
            <RouterLink :to="{ name: 'material-detail', params: { materialId: item.id } }">
              <strong>{{ item.name || item.id }}</strong>
            </RouterLink><span>{{ item.sku?.sku_id || item.id }} · {{ item.sku?.size_mm || item.size || '-' }}mm</span><small>¥{{ Number(item.sku?.price_per_bead || 0).toFixed(2) }} · 库存 {{ item.sku?.stock || 0 }}</small>
          </div><b :class="item.sku?.enabled ? 'material-live' : ''">{{ item.sku?.enabled ? '启用' : '停用' }}</b>
        </article>
      </div><nav class="design-pagination">
        <button
          :disabled="page === 1"
          @click="updateQuery({ page: page > 2 ? String(page - 1) : undefined })"
        >
          ← 上一页
        </button><span>第 {{ page }} 页</span><button
          :disabled="!hasNext"
          @click="updateQuery({ page: String(page + 1) })"
        >
          下一页 →
        </button>
      </nav>
    </template>
  </section>
</template>
