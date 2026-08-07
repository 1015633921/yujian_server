<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import PageEmptyState from '@/components/ui/PageEmptyState.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import { listCommunityPosts, type CommunityPost } from '@/features/content/api'

const router = useRouter()
const rows = ref<CommunityPost[]>([])
const keyword = ref('')
const status = ref('')
const homeHot = ref('')
const loading = ref(true)
const error = ref('')
let controller: AbortController | null = null

const statusLabel = (value: string) => ({ draft: '草稿', published: '已发布', hidden: '隐藏' })[value] || value

async function load(): Promise<void> {
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  try {
    rows.value = await listCommunityPosts({ keyword: keyword.value, status: status.value, homeHot: homeHot.value }, controller.signal)
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') return
    error.value = cause instanceof Error ? cause.message : '社区灵感加载失败'
  } finally {
    loading.value = false
  }
}

function openPost(postId: string): void {
  void router.push({ name: 'community-post-detail', params: { postId } })
}

function createPost(): void {
  void router.push({ name: 'community-post-new' })
}

watch([keyword, status, homeHot], () => void load())
onBeforeUnmount(() => controller?.abort())
void load()
</script>

<template>
  <section class="workspace-page community-posts">
    <PageHeading
      eyebrow="COMMUNITY CONTENT"
      title="社区灵感"
      description="按内容状态与首页展示统一查看灵感；进入详情页可维护图片、场景、配方和文案。"
    >
      <template #actions>
        <button
          class="heading-link"
          type="button"
          @click="createPost"
        >
          新增灵感
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

    <div class="content-banners__filters community-posts__filters">
      <input
        v-model.trim="keyword"
        placeholder="搜索标题、作者、摘要或标签"
      >
      <select v-model="status">
        <option value="">
          全部状态
        </option>
        <option value="draft">
          草稿
        </option>
        <option value="published">
          已发布
        </option>
        <option value="hidden">
          隐藏
        </option>
      </select>
      <select v-model="homeHot">
        <option value="">
          全部首页状态
        </option>
        <option value="true">
          仅首页热门
        </option>
        <option value="false">
          未设首页热门
        </option>
      </select>
      <small>{{ loading ? '正在同步内容…' : `共 ${rows.length} 条灵感` }}</small>
    </div>

    <PageErrorState
      v-if="error && !loading"
      title="社区灵感暂时无法读取"
      :message="error"
      eyebrow="CONTENT UNAVAILABLE"
      @retry="load"
    />
    <section
      v-else
      class="community-posts__ledger"
      aria-label="社区灵感列表"
    >
      <div class="content-banners__list-head community-posts__list-head">
        <span>封面 / 内容</span>
        <span>适用场景</span>
        <span>状态</span>
        <span>排序</span>
        <span aria-hidden="true" />
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
        v-else-if="!rows.length"
        title="没有符合条件的灵感内容"
        message="可新建一条社区灵感。"
      />
      <button
        v-for="item in rows"
        v-else
        :key="item.id"
        class="community-posts__item"
        type="button"
        @click="openPost(item.id)"
      >
        <img
          v-if="item.image_urls?.[0] || item.image_url"
          :src="item.image_urls?.[0] || item.image_url"
          :alt="item.title"
        >
        <i v-else />
        <p>
          <strong>{{ item.title }}</strong>
          <small>{{ item.author }} · {{ item.is_home_hot ? '首页热门' : '常规展示' }}</small>
        </p>
        <span>{{ item.scene || '未设场景' }}</span>
        <b :class="`status-${item.status}`">{{ statusLabel(item.status) }}</b>
        <em>{{ item.sort_order }}</em>
        <mark>查看详情</mark>
      </button>
    </section>
  </section>
</template>
