<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import { createCommunityPost, deleteCommunityPost, listCommunityPosts, updateCommunityPost, uploadAdminMedia, type CommunityPost, type ContentStatus } from '@/features/content/api'
import { getMaterialPreviews, listMaterials, type Material, type MaterialPreview } from '@/features/materials/api'
import { useAuthStore } from '@/stores/auth'

interface Editor { id: string; title: string; author: string; desc: string; story: string; sceneTags: string[]; authorNote: string; likes: number; tone: string; recipeText: string; tagsText: string; imageUrls: string[]; homeHot: boolean; status: ContentStatus; sortOrder: number }
interface SelectedMaterial { id: string; name: string; series: string; imageUrl: string; size?: number; unresolved: boolean }

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const loading = ref(true)
const saving = ref(false)
const uploading = ref(false)
const materialLoading = ref(false)
const materialKeyword = ref('')
const materialRows = ref<Material[]>([])
const selectedMaterialRows = ref<MaterialPreview[]>([])
const sceneDraft = ref('')
const imageDraft = ref('')
const error = ref('')
const notice = ref('')
const file = ref<HTMLInputElement | null>(null)
let controller: AbortController | null = null
let materialController: AbortController | null = null
let selectedMaterialController: AbortController | null = null
let skipNextRouteLoad = false
const editor = reactive<Editor>({ id: '', title: '', author: '宇涧主理人', desc: '', story: '', sceneTags: [], authorNote: '', likes: 0, tone: 'clear', recipeText: '', tagsText: '', imageUrls: [], homeHot: false, status: 'draft', sortOrder: 0 })

const isNew = computed(() => route.name === 'community-post-new')
const currentPostId = computed(() => String(route.params.postId || ''))
const canManage = computed(() => auth.admin?.role !== 'viewer')
const split = (value: string) => value.split(/[\n,，、；;]/).map((item) => item.trim()).filter(Boolean)
const unique = (values: string[]) => [...new Set(values)]
const selectedMaterialIds = computed(() => unique(split(editor.recipeText)))

function materialReferenceId(item: Material | MaterialPreview): string { return ('sku' in item ? item.sku?.sku_id : (item as MaterialPreview).sku_id || (item as MaterialPreview).skuId) || item.id }
function materialId(item: Material | MaterialPreview): string { return materialReferenceId(item) }
function materialAliases(item: Material | MaterialPreview): string[] { return unique([item.id, materialReferenceId(item)].filter(Boolean)) }
function materialLabel(item: Material | MaterialPreview): string { return item.name || item.series || '未命名材料' }
function materialSize(item: Material | MaterialPreview): number | undefined { return item.size || ('sku' in item ? item.sku?.size_mm : undefined) }
const selectedMaterials = computed<SelectedMaterial[]>(() => selectedMaterialIds.value.map((id) => {
  const material = [...materialRows.value, ...selectedMaterialRows.value].find((item) => materialAliases(item).includes(id))
  return material ? { id, name: materialLabel(material), series: material.series || '', imageUrl: material.image_url || '', size: materialSize(material), unresolved: false } : { id, name: id, series: '未能读取材料详情', imageUrl: '', unresolved: true }
}))

function cleanImageUrls(values: string[]): string[] { return unique(values.map((value) => value.trim()).filter(Boolean)).slice(0, 12) }
function reset(): void {
  selectedMaterialRows.value = []
  sceneDraft.value = ''
  imageDraft.value = ''
  Object.assign(editor, { id: '', title: '', author: '宇涧主理人', desc: '', story: '', sceneTags: [], authorNote: '', likes: 0, tone: 'clear', recipeText: '', tagsText: '', imageUrls: [], homeHot: false, status: 'draft', sortOrder: 0 })
}
function populate(item: CommunityPost): void {
  sceneDraft.value = ''
  imageDraft.value = ''
  Object.assign(editor, { id: item.id, title: item.title, author: item.author, desc: item.desc, story: item.story, sceneTags: unique(split(item.scene)), authorNote: item.authorNote, likes: item.likes, tone: item.tone, recipeText: item.recipe.join('\n'), tagsText: item.tags.join('\n'), imageUrls: cleanImageUrls(item.image_urls?.length ? item.image_urls : [item.image_url]), homeHot: item.is_home_hot, status: item.status, sortOrder: item.sort_order })
}

async function load(): Promise<void> {
  controller?.abort()
  loading.value = true
  error.value = ''
  notice.value = ''
  if (isNew.value) {
    reset()
    loading.value = false
    return
  }
  controller = new AbortController()
  try {
    const rows = await listCommunityPosts({ keyword: '', status: '', homeHot: '' }, controller.signal)
    const item = rows.find((post) => post.id === currentPostId.value)
    if (!item) throw new Error('未找到该灵感内容，可能已被删除。')
    populate(item)
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') return
    error.value = cause instanceof Error ? cause.message : '社区灵感加载失败'
  } finally {
    loading.value = false
  }
}

function addSceneTags(): void {
  const next = unique([...editor.sceneTags, ...split(sceneDraft.value)])
  if (!next.length || next.length === editor.sceneTags.length) { sceneDraft.value = ''; return }
  if (next.join('、').length > 255) { notice.value = '适用场景标签合计不能超过 255 个字符。'; return }
  editor.sceneTags = next
  sceneDraft.value = ''
}
function removeSceneTag(tag: string): void { editor.sceneTags = editor.sceneTags.filter((item) => item !== tag) }
function addImageUrl(): void {
  const next = cleanImageUrls([...editor.imageUrls, imageDraft.value])
  if (next.length === editor.imageUrls.length && imageDraft.value.trim()) { notice.value = editor.imageUrls.length >= 12 ? '封面图片最多 12 张。' : '该图片已添加。'; return }
  editor.imageUrls = next
  imageDraft.value = ''
}
function removeImage(index: number): void { editor.imageUrls.splice(index, 1) }
function moveImage(index: number, direction: -1 | 1): void {
  const target = index + direction
  const current = editor.imageUrls[index]
  const adjacent = editor.imageUrls[target]
  if (!current || !adjacent || target < 0 || target >= editor.imageUrls.length) return
  const next = [...editor.imageUrls]
  next[index] = adjacent
  next[target] = current
  editor.imageUrls = next
}
function payload() {
  const recipe = selectedMaterialIds.value
  const imageUrls = cleanImageUrls(editor.imageUrls)
  return { title: editor.title.trim(), author: editor.author.trim() || '宇涧主理人', desc: editor.desc.trim(), story: editor.story.trim(), scene: editor.sceneTags.join('、'), authorNote: editor.authorNote.trim(), likes: Math.max(0, Number(editor.likes) || 0), tone: editor.tone, recipe, materials: recipe, tags: split(editor.tagsText), image_url: imageUrls[0] || '', image_urls: imageUrls, is_home_hot: editor.homeHot, status: editor.status, sort_order: Math.max(0, Number(editor.sortOrder) || 0) }
}
async function save(): Promise<void> {
  if (!canManage.value || saving.value) return
  const data = payload()
  if (!data.title) { notice.value = '请填写标题。'; return }
  if (!data.image_urls.length) { notice.value = '请至少上传或填写一张封面图片。'; return }
  saving.value = true
  notice.value = ''
  try {
    const saved = editor.id ? await updateCommunityPost(editor.id, data) : await createCommunityPost(data)
    populate(saved)
    if (isNew.value) {
      skipNextRouteLoad = true
      await router.replace({ name: 'community-post-detail', params: { postId: saved.id } })
    }
    notice.value = '灵感内容已保存。'
  } catch (cause) {
    notice.value = cause instanceof Error ? cause.message : '保存失败。'
  } finally {
    saving.value = false
  }
}
async function remove(): Promise<void> {
  if (!canManage.value || !editor.id || saving.value || !window.confirm(`删除「${editor.title}」后无法恢复，确定继续吗？`)) return
  saving.value = true
  try {
    await deleteCommunityPost(editor.id)
    await router.replace({ name: 'community-posts' })
  } catch (cause) {
    notice.value = cause instanceof Error ? cause.message : '删除失败。'
  } finally {
    saving.value = false
  }
}
async function upload(event: Event): Promise<void> {
  const files = Array.from((event.target as HTMLInputElement).files || []).filter((item) => item.type.startsWith('image/'))
  if (!files.length) { notice.value = '请选择图片文件。'; return }
  const remaining = 12 - editor.imageUrls.length
  if (remaining <= 0) { notice.value = '封面图片最多 12 张。'; return }
  uploading.value = true
  try {
    const uploaded = await Promise.all(files.slice(0, remaining).map(async (item) => (await uploadAdminMedia(item, 'community')).image_url))
    editor.imageUrls = cleanImageUrls([...editor.imageUrls, ...uploaded])
    notice.value = `已上传 ${uploaded.length} 张封面图片。`
  } catch (cause) {
    notice.value = cause instanceof Error ? cause.message : '图片上传失败。'
  } finally {
    uploading.value = false
    if (file.value) file.value.value = ''
  }
}
async function searchMaterials(): Promise<void> {
  materialController?.abort()
  materialController = new AbortController()
  materialLoading.value = true
  try {
    materialRows.value = (await listMaterials({ keyword: materialKeyword.value, top: '', status: 'enabled', page: 1, pageSize: 12 }, materialController.signal)).items
  } catch (cause) {
    if (!(cause instanceof DOMException && cause.name === 'AbortError')) notice.value = cause instanceof Error ? cause.message : '材料搜索失败。'
  } finally {
    materialLoading.value = false
  }
}
async function loadSelectedMaterials(ids: string[]): Promise<void> {
  selectedMaterialController?.abort()
  if (!ids.length) { selectedMaterialRows.value = []; return }
  selectedMaterialController = new AbortController()
  try {
    const chunks = Array.from({ length: Math.ceil(ids.length / 20) }, (_, index) => ids.slice(index * 20, index * 20 + 20))
    selectedMaterialRows.value = (await Promise.all(chunks.map((chunk) => getMaterialPreviews(chunk, selectedMaterialController?.signal)))).flat()
  } catch (cause) {
    if (!(cause instanceof DOMException && cause.name === 'AbortError')) selectedMaterialRows.value = []
  }
}
function isMaterialSelected(item: Material): boolean { return selectedMaterialIds.value.includes(materialId(item)) }
function toggleMaterial(item: Material): void { const id = materialId(item); editor.recipeText = (isMaterialSelected(item) ? selectedMaterialIds.value.filter((value) => value !== id) : [...selectedMaterialIds.value, id]).join('\n') }
function removeMaterial(id: string): void { editor.recipeText = selectedMaterialIds.value.filter((value) => value !== id).join('\n') }
function goBack(): void { void router.push({ name: 'community-posts' }) }

watch(selectedMaterialIds, (ids) => void loadSelectedMaterials(ids))
watch([isNew, currentPostId], () => {
  if (skipNextRouteLoad) {
    skipNextRouteLoad = false
    return
  }
  void load()
}, { immediate: true })
onBeforeUnmount(() => { controller?.abort(); materialController?.abort(); selectedMaterialController?.abort() })
</script>

<template>
  <section class="workspace-page community-post-detail">
    <PageHeading
      :eyebrow="isNew ? 'NEW INSPIRATION' : 'INSPIRATION DETAIL'"
      :title="isNew ? '新增社区灵感' : '灵感详情'"
      :description="isNew ? '以真实图片、适用场景和配方材料建立一条可发布的灵感内容。' : '在同一处核对展示内容、图片顺序和配方材料。'"
    >
      <template #actions>
        <button
          class="heading-link"
          type="button"
          @click="goBack"
        >
          返回列表
        </button>
        <button
          v-if="editor.id"
          class="heading-link heading-link--danger"
          type="button"
          :disabled="!canManage || saving"
          @click="remove"
        >
          删除灵感
        </button>
      </template>
    </PageHeading>

    <PageErrorState
      v-if="error && !loading"
      title="社区灵感暂时无法读取"
      :message="error"
      eyebrow="CONTENT UNAVAILABLE"
      @retry="load"
    />
    <form
      v-else
      class="content-banners__editor community-post-detail__form"
      :aria-busy="loading"
      @submit.prevent="save"
    >
      <div
        v-if="loading"
        class="community-post-detail__loading content-banners__full"
      >
        正在加载灵感详情…
      </div>
      <template v-else>
        <section class="community-post-detail__summary content-banners__full">
          <span>{{ editor.id ? `内容编号 · ${editor.id}` : 'DRAFT CONTENT' }}</span>
          <p>首图作为列表与首页展示封面；其余图片、场景标签和配方材料均在详情页维护。</p>
        </section>
        <label class="content-banners__full">标题<input
          v-model.trim="editor.title"
          required
          :disabled="!canManage"
        ></label>
        <label>作者<input
          v-model.trim="editor.author"
          :disabled="!canManage"
        ></label>
        <label>排序<input
          v-model.number="editor.sortOrder"
          min="0"
          type="number"
          :disabled="!canManage"
        ></label>
        <label class="content-banners__full">列表摘要<textarea
          v-model.trim="editor.desc"
          :disabled="!canManage"
        /></label>

        <section class="community-cover-gallery content-banners__full">
          <header><div><span>灵感封面</span><small>首图用于列表和首页展示；详情页支持左右滑动查看全部图片。</small></div><strong>{{ editor.imageUrls.length }}/12</strong></header>
          <input
            ref="file"
            accept="image/*"
            multiple
            type="file"
            :disabled="!canManage || uploading"
            @change="upload"
          >
          <div class="community-cover-gallery__url">
            <input
              v-model.trim="imageDraft"
              type="url"
              placeholder="https://"
              :disabled="!canManage"
              @keyup.enter.prevent="addImageUrl"
            >
            <button
              type="button"
              :disabled="!canManage || !imageDraft.trim() || editor.imageUrls.length >= 12"
              @click="addImageUrl"
            >
              添加图片
            </button>
          </div>
          <p
            v-if="!editor.imageUrls.length"
            class="community-cover-gallery__empty"
          >
            尚未设置封面图片。
          </p>
          <ol v-else>
            <li
              v-for="(url, index) in editor.imageUrls"
              :key="url"
            >
              <img
                :src="url"
                :alt="`封面图片 ${index + 1}`"
              >
              <strong>{{ index === 0 ? '主封面' : `图片 ${index + 1}` }}</strong>
              <div>
                <button
                  type="button"
                  :disabled="!canManage || index === 0"
                  @click="moveImage(index, -1)"
                >
                  前移
                </button>
                <button
                  type="button"
                  :disabled="!canManage || index === editor.imageUrls.length - 1"
                  @click="moveImage(index, 1)"
                >
                  后移
                </button>
                <button
                  type="button"
                  :disabled="!canManage"
                  @click="removeImage(index)"
                >
                  移除
                </button>
              </div>
            </li>
          </ol>
        </section>

        <section class="community-scene-tags">
          <header><span>适用场景</span><small>输入后按回车或点击添加，可配置多个场景标签。</small></header>
          <div>
            <input
              v-model="sceneDraft"
              placeholder="例如：通勤、会议、约会"
              :disabled="!canManage"
              @keyup.enter.prevent="addSceneTags"
            >
            <button
              type="button"
              :disabled="!canManage || !sceneDraft.trim()"
              @click="addSceneTags"
            >
              添加
            </button>
          </div>
          <ul
            v-if="editor.sceneTags.length"
            aria-label="已添加的适用场景"
          >
            <li
              v-for="tag in editor.sceneTags"
              :key="tag"
            >
              <span>{{ tag }}</span>
              <button
                type="button"
                :aria-label="`移除场景标签 ${tag}`"
                :disabled="!canManage"
                @click="removeSceneTag(tag)"
              >
                移除
              </button>
            </li>
          </ul>
          <p v-else>
            暂未添加场景标签。
          </p>
        </section>
        <label>色调<select
          v-model="editor.tone"
          :disabled="!canManage"
        ><option value="clear">清透白</option><option value="gold">暖金</option><option value="zen">禅意灰绿</option><option value="dark">深色</option><option value="rose">柔粉</option><option value="earth">大地色</option></select></label>
        <label>点赞数<input
          v-model.number="editor.likes"
          min="0"
          type="number"
          :disabled="!canManage"
        ></label>
        <label>状态<select
          v-model="editor.status"
          :disabled="!canManage"
        ><option value="draft">草稿</option><option value="published">已发布</option><option value="hidden">隐藏</option></select></label>

        <section class="community-material-picker content-banners__full">
          <header><span>配方材料</span><small>可多选；已选材料会跟随配方保存。</small></header>
          <div>
            <input
              v-model.trim="materialKeyword"
              placeholder="搜索材料名称、SKU 或品种后多选"
              :disabled="!canManage || materialLoading"
              @keyup.enter.prevent="searchMaterials"
            >
            <button
              type="button"
              :disabled="!canManage || materialLoading"
              @click="searchMaterials"
            >
              {{ materialLoading ? '搜索中…' : '搜索材料' }}
            </button>
          </div>
          <section
            v-if="selectedMaterials.length"
            class="community-material-picker__selected"
            aria-live="polite"
          >
            <header><strong>已选 {{ selectedMaterials.length }} 项</strong><small>点击“移除”可取消选择</small></header>
            <ul>
              <li
                v-for="item in selectedMaterials"
                :key="item.id"
                :class="{ 'is-unresolved': item.unresolved }"
              >
                <img
                  v-if="item.imageUrl"
                  :src="item.imageUrl"
                  :alt="item.name"
                ><i v-else />
                <p><strong>{{ item.name }}</strong><small>{{ item.unresolved ? item.series : `${item.series || '材料规格'}${item.size ? ` · ${item.size}mm` : ''}` }}</small></p>
                <button
                  type="button"
                  :disabled="!canManage"
                  @click="removeMaterial(item.id)"
                >
                  移除
                </button>
              </li>
            </ul>
          </section>
          <p
            v-else
            class="community-material-picker__empty"
          >
            尚未选择材料。搜索后可连续勾选多个材料。
          </p>
          <ol
            v-if="materialRows.length"
            class="community-material-picker__results"
          >
            <li
              v-for="item in materialRows"
              :key="item.id"
              :class="{ 'is-selected': isMaterialSelected(item) }"
            >
              <img
                v-if="item.image_url"
                :src="item.image_url"
                :alt="item.name || item.series"
              ><i v-else />
              <p><strong>{{ item.name || item.series || '未命名材料' }}</strong><small>{{ item.series || '材料规格' }} · {{ item.size || item.sku?.size_mm || '—' }}mm</small></p>
              <button
                type="button"
                :disabled="!canManage"
                :aria-pressed="isMaterialSelected(item)"
                @click="toggleMaterial(item)"
              >
                {{ isMaterialSelected(item) ? '已选' : '选择' }}
              </button>
            </li>
          </ol>
        </section>
        <details class="content-banners__full">
          <summary>内部配方标识（仅技术排查）</summary>
          <label>已选配方材料标识（每行一个）<textarea
            v-model="editor.recipeText"
            placeholder="由搜索材料自动填入"
            :disabled="!canManage"
          /></label>
        </details>
        <label class="content-banners__full">标签（逗号或换行）<textarea
          v-model="editor.tagsText"
          :disabled="!canManage"
        /></label>
        <label class="content-banners__full">故事正文<textarea
          v-model.trim="editor.story"
          :disabled="!canManage"
        /></label>
        <label class="content-banners__full">主理人注释<textarea
          v-model.trim="editor.authorNote"
          :disabled="!canManage"
        /></label>
        <label class="content-banners__full community-post-detail__hot"><input
          v-model="editor.homeHot"
          type="checkbox"
          :disabled="!canManage"
        > 设为首页热门展示</label>
        <footer>
          <button
            class="primary-action"
            :disabled="!canManage || saving || uploading"
            type="submit"
          >
            {{ saving ? '保存中…' : '保存灵感' }}
          </button>
          <p>{{ notice || (!canManage ? '当前账号为只读，不能修改内容。' : '') }}</p>
        </footer>
      </template>
    </form>
  </section>
</template>
