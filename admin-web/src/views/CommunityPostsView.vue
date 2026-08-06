<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'

import PageEmptyState from '@/components/ui/PageEmptyState.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import { createCommunityPost, deleteCommunityPost, listCommunityPosts, updateCommunityPost, uploadAdminMedia, type CommunityPost, type ContentStatus } from '@/features/content/api'
import { listMaterials, type Material } from '@/features/materials/api'
import { useAuthStore } from '@/stores/auth'

interface Editor { id: string; title: string; author: string; desc: string; story: string; scene: string; authorNote: string; likes: number; tone: string; recipeText: string; tagsText: string; imageUrl: string; homeHot: boolean; status: ContentStatus; sortOrder: number }
const auth = useAuthStore(); const rows = ref<CommunityPost[]>([]); const keyword = ref(''); const status = ref(''); const homeHot = ref(''); const selectedId = ref(''); const loading = ref(true); const saving = ref(false); const uploading = ref(false); const materialLoading = ref(false); const materialKeyword = ref(''); const materialRows = ref<Material[]>([]); const error = ref(''); const notice = ref(''); const file = ref<HTMLInputElement | null>(null); let controller: AbortController | null = null; let materialController: AbortController | null = null
const editor = reactive<Editor>({ id: '', title: '', author: '宇涧主理人', desc: '', story: '', scene: '', authorNote: '', likes: 0, tone: 'clear', recipeText: '', tagsText: '', imageUrl: '', homeHot: false, status: 'draft', sortOrder: 0 })
const canManage = computed(() => auth.admin?.role !== 'viewer'); const split = (value: string) => value.split(/[\n,，、]/).map((item) => item.trim()).filter(Boolean); const statusLabel = (value: string) => ({ draft: '草稿', published: '已发布', hidden: '隐藏' })[value] || value
function reset(): void { selectedId.value = ''; Object.assign(editor, { id: '', title: '', author: '宇涧主理人', desc: '', story: '', scene: '', authorNote: '', likes: 0, tone: 'clear', recipeText: '', tagsText: '', imageUrl: '', homeHot: false, status: 'draft', sortOrder: 0 }); notice.value = '' }
function edit(item: CommunityPost): void { selectedId.value = item.id; Object.assign(editor, { id: item.id, title: item.title, author: item.author, desc: item.desc, story: item.story, scene: item.scene, authorNote: item.authorNote, likes: item.likes, tone: item.tone, recipeText: item.recipe.join('\n'), tagsText: item.tags.join('\n'), imageUrl: item.image_url, homeHot: item.is_home_hot, status: item.status, sortOrder: item.sort_order }); notice.value = '' }
function payload() { const recipe = split(editor.recipeText); return { title: editor.title.trim(), author: editor.author.trim() || '宇涧主理人', desc: editor.desc.trim(), story: editor.story.trim(), scene: editor.scene.trim(), authorNote: editor.authorNote.trim(), likes: Math.max(0, Number(editor.likes) || 0), tone: editor.tone, recipe, materials: recipe, tags: split(editor.tagsText), image_url: editor.imageUrl.trim(), is_home_hot: editor.homeHot, status: editor.status, sort_order: Math.max(0, Number(editor.sortOrder) || 0) } }
async function load(): Promise<void> { controller?.abort(); controller = new AbortController(); loading.value = true; error.value = ''; try { rows.value = await listCommunityPosts({ keyword: keyword.value, status: status.value, homeHot: homeHot.value }, controller.signal); if (selectedId.value && !rows.value.some((item) => item.id === selectedId.value)) reset() } catch (cause) { if (cause instanceof DOMException && cause.name === 'AbortError') return; error.value = cause instanceof Error ? cause.message : '社区灵感加载失败' } finally { loading.value = false } }
async function save(): Promise<void> { if (!canManage.value || saving.value) return; const data = payload(); if (!data.title) { notice.value = '请填写标题。'; return }; if (!data.image_url) { notice.value = '请上传或填写封面图片。'; return }; saving.value = true; notice.value = ''; try { const saved = editor.id ? await updateCommunityPost(editor.id, data) : await createCommunityPost(data); await load(); edit(saved); notice.value = '灵感内容已保存。' } catch (cause) { notice.value = cause instanceof Error ? cause.message : '保存失败。' } finally { saving.value = false } }
async function remove(): Promise<void> { if (!canManage.value || !editor.id || saving.value || !window.confirm(`删除「${editor.title}」后无法恢复，确定继续吗？`)) return; saving.value = true; try { await deleteCommunityPost(editor.id); reset(); await load(); notice.value = '灵感内容已删除。' } catch (cause) { notice.value = cause instanceof Error ? cause.message : '删除失败。' } finally { saving.value = false } }
async function upload(event: Event): Promise<void> { const next = (event.target as HTMLInputElement).files?.[0]; if (!next || !next.type.startsWith('image/')) { notice.value = '请选择图片文件。'; return }; uploading.value = true; try { editor.imageUrl = (await uploadAdminMedia(next, 'community')).image_url; notice.value = '封面已上传。' } catch (cause) { notice.value = cause instanceof Error ? cause.message : '图片上传失败。' } finally { uploading.value = false; if (file.value) file.value.value = '' } }
async function searchMaterials(): Promise<void> { materialController?.abort(); materialController = new AbortController(); materialLoading.value = true; try { materialRows.value = (await listMaterials({ keyword: materialKeyword.value, top: '', status: 'enabled', page: 1, pageSize: 12 }, materialController.signal)).items } catch (cause) { if (!(cause instanceof DOMException && cause.name === 'AbortError')) notice.value = cause instanceof Error ? cause.message : '材料搜索失败。' } finally { materialLoading.value = false } }
function addMaterial(item: Material): void { const id = item.sku?.sku_id || item.id; const recipe = split(editor.recipeText); if (!recipe.includes(id)) editor.recipeText = [...recipe, id].join('\n'); notice.value = `已加入 ${item.name || item.series || '材料规格'}。` }
watch([keyword, status, homeHot], () => void load()); onBeforeUnmount(() => { controller?.abort(); materialController?.abort() }); void load()
</script>

<template>
  <section class="workspace-page community-posts">
    <PageHeading
      eyebrow="COMMUNITY CONTENT"
      title="社区灵感"
      description="管理社区灵感与首页热门展示；配方材料会由系统自动关联。"
    >
      <template #actions>
        <button
          class="heading-link"
          type="button"
          @click="reset"
        >
          新增灵感
        </button><button
          class="heading-link"
          type="button"
          @click="load"
        >
          刷新数据
        </button>
      </template>
    </PageHeading><div class="content-banners__filters">
      <input
        v-model.trim="keyword"
        placeholder="搜索标题、作者、摘要或标签"
      ><select v-model="status">
        <option value="">
          全部状态
        </option><option value="draft">
          草稿
        </option><option value="published">
          已发布
        </option><option value="hidden">
          隐藏
        </option>
      </select><select v-model="homeHot">
        <option value="">
          全部首页状态
        </option><option value="true">
          仅首页热门
        </option><option value="false">
          未设首页热门
        </option>
      </select>
    </div><PageErrorState
      v-if="error && !loading"
      title="社区灵感暂时无法读取"
      :message="error"
      eyebrow="CONTENT UNAVAILABLE"
      @retry="load"
    /><div
      v-else
      class="content-banners__workspace"
    >
      <div class="content-banners__list">
        <div class="content-banners__list-head">
          <span>封面 / 内容</span><span>色调</span><span>状态</span><span>排序</span>
        </div><div
          v-if="loading"
          class="content-banners__skeleton"
        >
          <i
            v-for="item in 6"
            :key="item"
          />
        </div><PageEmptyState
          v-else-if="!rows.length"
          title="没有符合条件的灵感内容"
          message="可新建一条社区灵感。"
        /><button
          v-for="item in rows"
          v-else
          :key="item.id"
          class="content-banners__item"
          :class="{ 'is-current': selectedId === item.id }"
          type="button"
          @click="edit(item)"
        >
          <img
            v-if="item.image_url"
            :src="item.image_url"
            :alt="item.title"
          ><i v-else /><p><strong>{{ item.title }}</strong><small>{{ item.author }} · {{ item.is_home_hot ? '首页热门' : item.scene || '未设场景' }}</small></p><span>{{ item.tone }}</span><b :class="`status-${item.status}`">{{ statusLabel(item.status) }}</b><em>{{ item.sort_order }}</em>
        </button>
      </div><form
        class="content-banners__editor"
        @submit.prevent="save"
      >
        <header>
          <div><span>{{ editor.id ? 'EDIT INSPIRATION' : 'NEW INSPIRATION' }}</span><h2>{{ editor.id ? '编辑社区灵感' : '新增社区灵感' }}</h2></div><button
            v-if="editor.id"
            type="button"
            :disabled="saving"
            @click="remove"
          >
            删除
          </button>
        </header><label class="content-banners__full">标题<input
          v-model.trim="editor.title"
          required
          :disabled="!canManage"
        ></label><label>作者<input
          v-model.trim="editor.author"
          :disabled="!canManage"
        ></label><label>排序<input
          v-model.number="editor.sortOrder"
          min="0"
          type="number"
          :disabled="!canManage"
        ></label><label class="content-banners__full">列表摘要<textarea
          v-model.trim="editor.desc"
          :disabled="!canManage"
        /></label><section class="content-banners__image content-banners__full">
          <div>
            <img
              v-if="editor.imageUrl"
              :src="editor.imageUrl"
              alt="灵感封面"
            ><span v-else>尚未设置封面</span>
          </div><p><strong>灵感封面</strong><small>上传图片或粘贴 URL。</small></p><input
            ref="file"
            accept="image/*"
            type="file"
            :disabled="!canManage || uploading"
            @change="upload"
          ><input
            v-model.trim="editor.imageUrl"
            type="url"
            placeholder="https://"
            :disabled="!canManage"
          >
        </section><label>适用场景<input
          v-model.trim="editor.scene"
          :disabled="!canManage"
        ></label><label>色调<select
          v-model="editor.tone"
          :disabled="!canManage"
        ><option value="clear">清透白</option><option value="gold">暖金</option><option value="zen">禅意灰绿</option><option value="dark">深色</option><option value="rose">柔粉</option><option value="earth">大地色</option></select></label><label>点赞数<input
          v-model.number="editor.likes"
          min="0"
          type="number"
          :disabled="!canManage"
        ></label><label>状态<select
          v-model="editor.status"
          :disabled="!canManage"
        ><option value="draft">草稿</option><option value="published">已发布</option><option value="hidden">隐藏</option></select></label><section class="community-material-picker content-banners__full">
          <header><span>配方材料</span><small>搜索后添加真实材料规格；不会加载整库。</small></header><div>
            <input
              v-model.trim="materialKeyword"
              placeholder="搜索材料名称、SKU 或品种"
              :disabled="!canManage || materialLoading"
              @keyup.enter.prevent="searchMaterials"
            ><button
              type="button"
              :disabled="!canManage || materialLoading"
              @click="searchMaterials"
            >
              {{ materialLoading ? '搜索中…' : '搜索材料' }}
            </button>
          </div><ol v-if="materialRows.length">
            <li
              v-for="item in materialRows"
              :key="item.id"
            >
              <img
                v-if="item.image_url"
                :src="item.image_url"
                :alt="item.name || item.series"
              ><i v-else /><p><strong>{{ item.name || item.series || '未命名材料' }}</strong><small>{{ item.series || '材料规格' }} · {{ item.size || item.sku?.size_mm || '—' }}mm</small></p><button
                type="button"
                :disabled="!canManage"
                @click="addMaterial(item)"
              >
                添加
              </button>
            </li>
          </ol>
        </section><details class="content-banners__full">
          <summary>内部配方标识（仅技术排查）</summary><label>已选配方材料标识（每行一个）<textarea
            v-model="editor.recipeText"
            placeholder="由搜索材料自动填入"
            :disabled="!canManage"
          /></label>
        </details><label class="content-banners__full">标签（逗号或换行）<textarea
          v-model="editor.tagsText"
          :disabled="!canManage"
        /></label><label class="content-banners__full">故事正文<textarea
          v-model.trim="editor.story"
          :disabled="!canManage"
        /></label><label class="content-banners__full">主理人注释<textarea
          v-model.trim="editor.authorNote"
          :disabled="!canManage"
        /></label><label class="content-banners__full"><input
          v-model="editor.homeHot"
          type="checkbox"
          :disabled="!canManage"
        > 设为首页热门展示</label><footer>
          <button
            class="primary-action"
            :disabled="!canManage || saving || uploading"
            type="submit"
          >
            {{ saving ? '保存中…' : '保存灵感' }}
          </button><p>{{ notice || (!canManage ? '当前账号为只读，不能修改内容。' : '') }}</p>
        </footer>
      </form>
    </div>
  </section>
</template>
