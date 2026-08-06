<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import PageEmptyState from '@/components/ui/PageEmptyState.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import { createContentBlock, deleteContentBlock, listContentBlocks, updateContentBlock, uploadAdminMedia, type ContentBlock, type ContentStatus } from '@/features/content/api'
import { useAuthStore } from '@/stores/auth'
interface Editor { id: string; section: string; title: string; subtitle: string; body: string; imageUrl: string; actionText: string; actionUrl: string; status: ContentStatus; sortOrder: number }
const auth = useAuthStore(); const section = ref(''); const rows = ref<ContentBlock[]>([]); const selectedId = ref(''); const loading = ref(true); const saving = ref(false); const uploading = ref(false); const error = ref(''); const notice = ref(''); const file = ref<HTMLInputElement | null>(null); let controller: AbortController | null = null
const editor = reactive<Editor>({ id: '', section: 'home', title: '', subtitle: '', body: '', imageUrl: '', actionText: '', actionUrl: '', status: 'draft', sortOrder: 0 }); const canManage = computed(() => auth.admin?.role !== 'viewer')
function reset(): void { selectedId.value = ''; Object.assign(editor, { id: '', section: section.value || 'home', title: '', subtitle: '', body: '', imageUrl: '', actionText: '', actionUrl: '', status: 'draft', sortOrder: 0 }); notice.value = '' }
function edit(item: ContentBlock): void { selectedId.value = item.block_id; Object.assign(editor, { id: item.block_id, section: item.section, title: item.title, subtitle: item.subtitle, body: item.body, imageUrl: item.image_url, actionText: item.action_text, actionUrl: item.action_url, status: item.status, sortOrder: item.sort_order }); notice.value = '' }
function payload() { return { section: editor.section, title: editor.title.trim(), subtitle: editor.subtitle.trim(), body: editor.body.trim(), image_url: editor.imageUrl.trim(), action_text: editor.actionText.trim(), action_url: editor.actionUrl.trim(), status: editor.status, sort_order: Math.max(0, Number(editor.sortOrder) || 0) } }
async function load(): Promise<void> { controller?.abort(); controller = new AbortController(); loading.value = true; error.value = ''; try { rows.value = await listContentBlocks(section.value, controller.signal); if (selectedId.value && !rows.value.some((row) => row.block_id === selectedId.value)) reset() } catch (cause) { if (!(cause instanceof DOMException && cause.name === 'AbortError')) error.value = cause instanceof Error ? cause.message : '内容板块加载失败' } finally { loading.value = false } }
async function save(): Promise<void> { if (!canManage.value || saving.value) return; const data = payload(); if (!data.title) { notice.value = '请填写标题。'; return }; saving.value = true; try { const saved = editor.id ? await updateContentBlock(editor.id, data) : await createContentBlock(data); await load(); edit(saved); notice.value = '内容板块已保存。' } catch (cause) { notice.value = cause instanceof Error ? cause.message : '保存失败。' } finally { saving.value = false } }
async function remove(): Promise<void> { if (!editor.id || saving.value || !window.confirm(`删除「${editor.title}」后无法恢复，确定继续吗？`)) return; saving.value = true; try { await deleteContentBlock(editor.id); reset(); await load(); notice.value = '内容板块已删除。' } catch (cause) { notice.value = cause instanceof Error ? cause.message : '删除失败。' } finally { saving.value = false } }
async function upload(event: Event): Promise<void> { const next = (event.target as HTMLInputElement).files?.[0]; if (!next) return; uploading.value = true; try { editor.imageUrl = (await uploadAdminMedia(next, 'content-block')).image_url } catch (cause) { notice.value = cause instanceof Error ? cause.message : '图片上传失败。' } finally { uploading.value = false; if (file.value) file.value.value = '' } }
watch(section, () => { reset(); void load() }); onBeforeUnmount(() => controller?.abort()); void load()
</script>
<template>
  <section class="workspace-page content-blocks">
    <PageHeading
      eyebrow="CONTENT BLOCKS"
      title="内容板块"
      description="管理首页、每日建议和社区固定区域的标题、图文与跳转。"
    >
      <template #actions>
        <button
          class="heading-link"
          type="button"
          @click="reset"
        >
          新增板块
        </button><button
          class="heading-link"
          type="button"
          @click="load"
        >
          刷新数据
        </button>
      </template>
    </PageHeading><div class="content-banners__filters">
      <select v-model="section">
        <option value="">
          全部区域
        </option><option value="home">
          首页
        </option><option value="daily">
          每日
        </option><option value="community">
          社区
        </option>
      </select>
    </div><PageErrorState
      v-if="error&&!loading"
      title="内容板块暂时无法读取"
      :message="error"
      eyebrow="CONTENT UNAVAILABLE"
      @retry="load"
    /><div
      v-else
      class="content-banners__workspace"
    >
      <div class="content-banners__list">
        <div class="content-banners__list-head">
          <span>区域 / 内容</span><span>—</span><span>状态</span><span>排序</span>
        </div><div
          v-if="loading"
          class="content-banners__skeleton"
        >
          <i
            v-for="item in 4"
            :key="item"
          />
        </div><PageEmptyState
          v-else-if="!rows.length"
          title="没有内容板块"
          message="可以新增一个固定内容区域。"
        /><button
          v-for="item in rows"
          v-else
          :key="item.block_id"
          class="content-banners__item"
          :class="{ 'is-current': selectedId===item.block_id }"
          type="button"
          @click="edit(item)"
        >
          <img
            v-if="item.image_url"
            :src="item.image_url"
            :alt="item.title"
          ><i v-else /><p><strong>{{ item.title }}</strong><small>{{ item.section }} · {{ item.subtitle || item.body || '未设正文' }}</small></p><span>固定区</span><b :class="`status-${item.status}`">{{ item.status }}</b><em>{{ item.sort_order }}</em>
        </button>
      </div><form
        class="content-banners__editor"
        @submit.prevent="save"
      >
        <header>
          <div><span>{{ editor.id?'EDIT BLOCK':'NEW BLOCK' }}</span><h2>{{ editor.id?'编辑内容板块':'新增内容板块' }}</h2></div><button
            v-if="editor.id"
            type="button"
            @click="remove"
          >
            删除
          </button>
        </header><label>区域<select
          v-model="editor.section"
          :disabled="!canManage"
        ><option value="home">首页</option><option value="daily">每日</option><option value="community">社区</option></select></label><label>排序<input
          v-model.number="editor.sortOrder"
          min="0"
          type="number"
          :disabled="!canManage"
        ></label><label class="content-banners__full">标题<input
          v-model.trim="editor.title"
          required
          :disabled="!canManage"
        ></label><label class="content-banners__full">副标题<textarea
          v-model.trim="editor.subtitle"
          :disabled="!canManage"
        /></label><label class="content-banners__full">正文<textarea
          v-model.trim="editor.body"
          :disabled="!canManage"
        /></label><section class="content-banners__image content-banners__full">
          <div>
            <img
              v-if="editor.imageUrl"
              :src="editor.imageUrl"
              alt="板块图片"
            ><span v-else>可选图片</span>
          </div><p><strong>板块图片</strong><small>上传或粘贴 URL。</small></p><input
            ref="file"
            accept="image/*"
            type="file"
            :disabled="!canManage||uploading"
            @change="upload"
          ><input
            v-model.trim="editor.imageUrl"
            type="url"
            placeholder="https://"
            :disabled="!canManage"
          >
        </section><label>按钮文案<input
          v-model.trim="editor.actionText"
          :disabled="!canManage"
        ></label><label>跳转路径<input
          v-model.trim="editor.actionUrl"
          :disabled="!canManage"
        ></label><label>状态<select
          v-model="editor.status"
          :disabled="!canManage"
        ><option value="draft">草稿</option><option value="published">已发布</option><option value="hidden">隐藏</option></select></label><footer>
          <button
            class="primary-action"
            :disabled="!canManage||saving||uploading"
            type="submit"
          >
            {{ saving?'保存中…':'保存板块' }}
          </button><p>{{ notice }}</p>
        </footer>
      </form>
    </div>
  </section>
</template>
