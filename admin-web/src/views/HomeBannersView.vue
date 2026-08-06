<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'

import PageEmptyState from '@/components/ui/PageEmptyState.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import {
  createHomeBanner,
  deleteHomeBanner,
  listHomeBanners,
  updateHomeBanner,
  uploadAdminMedia,
  type BannerTheme,
  type ContentStatus,
  type HomeBanner,
} from '@/features/content/api'
import { useAuthStore } from '@/stores/auth'

interface BannerEditor { id: string; title: string; subtitle: string; eyebrow: string; imageUrl: string; actionText: string; actionUrl: string; theme: BannerTheme; status: ContentStatus; sortOrder: number }

const auth = useAuthStore()
const banners = ref<HomeBanner[]>([])
const keyword = ref('')
const status = ref('')
const selectedId = ref('')
const loading = ref(true)
const saving = ref(false)
const uploading = ref(false)
const error = ref('')
const notice = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const editor = reactive<BannerEditor>({ id: '', title: '', subtitle: '', eyebrow: '', imageUrl: '', actionText: '', actionUrl: '', theme: 'clear', status: 'draft', sortOrder: 0 })
let controller: AbortController | null = null

const canManage = computed(() => auth.admin?.role !== 'viewer')
const statusLabel = (value: string): string => ({ draft: '草稿', published: '已发布', hidden: '隐藏' })[value] || value
const themeLabel = (value: string): string => ({ dark: '深色质感', warm: '暖白柔光', green: '草木绿', gold: '暖金高级', clear: '清透白' })[value] || value

function resetEditor(): void {
  selectedId.value = ''
  Object.assign(editor, { id: '', title: '', subtitle: '', eyebrow: '宇涧水晶手作', imageUrl: '', actionText: '开始定制 →', actionUrl: '/pages/custom-mode/custom-mode', theme: 'clear', status: 'draft', sortOrder: 0 })
  notice.value = ''
}

function editBanner(item: HomeBanner): void {
  selectedId.value = item.id
  Object.assign(editor, { id: item.id, title: item.title, subtitle: item.subtitle, eyebrow: item.eyebrow, imageUrl: item.image_url, actionText: item.actionText, actionUrl: item.actionUrl, theme: item.theme, status: item.status, sortOrder: item.sort_order })
  notice.value = ''
}

function payload() {
  return { title: editor.title.trim(), subtitle: editor.subtitle.trim(), eyebrow: editor.eyebrow.trim(), image_url: editor.imageUrl.trim(), actionText: editor.actionText.trim(), actionUrl: editor.actionUrl.trim(), theme: editor.theme, status: editor.status, sort_order: Math.max(0, Number(editor.sortOrder) || 0) }
}

async function load(): Promise<void> {
  controller?.abort(); controller = new AbortController(); loading.value = true; error.value = ''
  try {
    const rows = await listHomeBanners({ keyword: keyword.value, status: status.value }, controller.signal)
    banners.value = rows
    if (selectedId.value && !rows.some((item) => item.id === selectedId.value)) resetEditor()
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') return
    error.value = cause instanceof Error ? cause.message : '首页 Banner 加载失败'
  } finally { loading.value = false }
}

async function save(): Promise<void> {
  if (!canManage.value || saving.value) return
  const input = payload()
  if (!input.title) { notice.value = '请填写主标题。'; return }
  if (!input.image_url) { notice.value = '请上传或填写 Banner 图片。'; return }
  saving.value = true; notice.value = ''
  try {
    const saved = editor.id ? await updateHomeBanner(editor.id, input) : await createHomeBanner(input)
    await load(); editBanner(saved); notice.value = 'Banner 已保存。'
  } catch (cause) { notice.value = cause instanceof Error ? cause.message : 'Banner 保存失败。' } finally { saving.value = false }
}

async function remove(): Promise<void> {
  if (!canManage.value || !editor.id || saving.value) return
  if (!window.confirm(`删除「${editor.title || '此 Banner'}」后无法恢复，确定继续吗？`)) return
  saving.value = true; notice.value = ''
  try { await deleteHomeBanner(editor.id); resetEditor(); await load(); notice.value = 'Banner 已删除。' } catch (cause) { notice.value = cause instanceof Error ? cause.message : 'Banner 删除失败。' } finally { saving.value = false }
}

async function chooseFile(event: Event): Promise<void> {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file || !canManage.value) return
  if (!file.type.startsWith('image/')) { notice.value = '请选择图片文件。'; return }
  uploading.value = true; notice.value = ''
  try { editor.imageUrl = (await uploadAdminMedia(file)).image_url; notice.value = '图片已上传，可继续保存 Banner。' } catch (cause) { notice.value = cause instanceof Error ? cause.message : '图片上传失败。' } finally { uploading.value = false; if (fileInput.value) fileInput.value.value = '' }
}

watch([keyword, status], () => { void load() })
onBeforeUnmount(() => controller?.abort())
void load()
</script>

<template>
  <section class="workspace-page content-banners">
    <PageHeading
      eyebrow="HOME CONTENT"
      title="首页 Banner"
      description="管理小程序首页的轮播内容、跳转路径与发布状态。图片会保存到运营素材存储。"
    >
      <template #actions>
        <button
          class="heading-link"
          type="button"
          @click="resetEditor"
        >
          新增 Banner
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
    <div class="content-banners__filters">
      <input
        v-model.trim="keyword"
        placeholder="搜索标题、顶部小字或副标题"
      >
      <select v-model="status">
        <option value="">
          全部状态
        </option><option value="draft">
          草稿
        </option><option value="published">
          已发布
        </option><option value="hidden">
          隐藏
        </option>
      </select>
      <small>{{ banners.length }} 条内容 · 按排序号升序展示</small>
    </div>
    <PageErrorState
      v-if="error && !loading"
      title="Banner 暂时无法读取"
      :message="error"
      eyebrow="CONTENT UNAVAILABLE"
      @retry="load"
    />
    <div
      v-else
      class="content-banners__workspace"
    >
      <div class="content-banners__list">
        <div class="content-banners__list-head">
          <span>预览 / 内容</span><span>主题</span><span>状态</span><span>排序</span>
        </div>
        <div
          v-if="loading"
          class="content-banners__skeleton"
        >
          <i
            v-for="item in 6"
            :key="item"
          />
        </div>
        <PageEmptyState
          v-else-if="!banners.length"
          title="没有符合条件的 Banner"
          message="可以新建一条首页轮播内容。"
        />
        <button
          v-for="item in banners"
          v-else
          :key="item.id"
          class="content-banners__item"
          :class="{ 'is-current': selectedId === item.id }"
          type="button"
          @click="editBanner(item)"
        >
          <img
            v-if="item.image_url"
            :src="item.image_url"
            :alt="item.title"
          ><i v-else />
          <p><strong>{{ item.title }}</strong><small>{{ item.eyebrow || '未设顶部小字' }} · {{ item.subtitle || '未设副标题' }}</small></p><span>{{ themeLabel(item.theme) }}</span><b :class="`status-${item.status}`">{{ statusLabel(item.status) }}</b><em>{{ item.sort_order }}</em>
        </button>
      </div>
      <form
        class="content-banners__editor"
        @submit.prevent="save"
      >
        <header>
          <div><span>{{ editor.id ? 'EDIT BANNER' : 'NEW BANNER' }}</span><h2>{{ editor.id ? '编辑首页 Banner' : '新增首页 Banner' }}</h2></div><button
            v-if="editor.id"
            type="button"
            :disabled="saving"
            @click="remove"
          >
            删除
          </button>
        </header>
        <label class="content-banners__full">主标题<input
          v-model.trim="editor.title"
          :disabled="!canManage"
          required
        ></label><label>顶部小字<input
          v-model.trim="editor.eyebrow"
          :disabled="!canManage"
        ></label><label>排序<input
          v-model.number="editor.sortOrder"
          min="0"
          type="number"
          :disabled="!canManage"
        ></label>
        <label class="content-banners__full">副标题<textarea
          v-model.trim="editor.subtitle"
          :disabled="!canManage"
        /></label>
        <section class="content-banners__image content-banners__full">
          <div>
            <img
              v-if="editor.imageUrl"
              :src="editor.imageUrl"
              alt="Banner 预览"
            ><span v-else>尚未设置图片</span>
          </div><p><strong>Banner 图片</strong><small>支持上传 JPG、PNG、WebP，或直接填写 URL。</small></p><input
            ref="fileInput"
            accept="image/*"
            type="file"
            :disabled="!canManage || uploading"
            @change="chooseFile"
          ><input
            v-model.trim="editor.imageUrl"
            type="url"
            placeholder="https://"
            :disabled="!canManage"
          ><small v-if="uploading">图片上传中…</small>
        </section>
        <label>按钮文案<input
          v-model.trim="editor.actionText"
          :disabled="!canManage"
        ></label><label>小程序跳转路径<input
          v-model.trim="editor.actionUrl"
          :disabled="!canManage"
        ></label><label>主题风格<select
          v-model="editor.theme"
          :disabled="!canManage"
        ><option value="clear">清透白</option><option value="warm">暖白柔光</option><option value="green">草木绿</option><option value="gold">暖金高级</option><option value="dark">深色质感</option></select></label><label>发布状态<select
          v-model="editor.status"
          :disabled="!canManage"
        ><option value="draft">草稿</option><option value="published">已发布</option><option value="hidden">隐藏</option></select></label>
        <footer>
          <button
            class="primary-action"
            :disabled="!canManage || saving || uploading"
            type="submit"
          >
            {{ saving ? '保存中…' : '保存 Banner' }}
          </button><p>{{ notice || (!canManage ? '当前账号为只读，不能修改内容。' : '') }}</p>
        </footer>
      </form>
    </div>
  </section>
</template>
