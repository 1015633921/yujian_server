import { apiRequest } from '@/api/client'

export type ContentStatus = 'draft' | 'published' | 'hidden'
export type BannerTheme = 'dark' | 'warm' | 'green' | 'gold' | 'clear'

export interface HomeBanner {
  id: string
  title: string
  subtitle: string
  eyebrow: string
  image_url: string
  actionText: string
  actionUrl: string
  theme: BannerTheme
  status: ContentStatus
  sort_order: number
  updated_at?: string
}

export interface HomeBannerInput {
  title: string
  subtitle: string
  eyebrow: string
  image_url: string
  actionText: string
  actionUrl: string
  theme: BannerTheme
  status: ContentStatus
  sort_order: number
}

export interface AdminMediaUpload { image_url: string; url: string; key: string }
export interface CommunityPost { id: string; title: string; author: string; desc: string; story: string; scene: string; authorNote: string; likes: number; tone: string; recipe: string[]; materials: Array<string | Record<string, unknown>>; tags: string[]; image_url: string; is_home_hot: boolean; status: ContentStatus; sort_order: number; updated_at?: string }
export interface CommunityPostInput { title: string; author: string; desc: string; story: string; scene: string; authorNote: string; likes: number; tone: string; recipe: string[]; materials: string[]; tags: string[]; image_url: string; is_home_hot: boolean; status: ContentStatus; sort_order: number }
export interface ContentBlock { block_id: string; section: string; title: string; subtitle: string; body: string; image_url: string; action_text: string; action_url: string; status: ContentStatus; sort_order: number }
export type ContentBlockInput = Omit<ContentBlock, 'block_id'>

export function listHomeBanners(query: { keyword: string; status: string }, signal?: AbortSignal): Promise<HomeBanner[]> {
  const params = new URLSearchParams({ keyword: query.keyword, status: query.status, limit: '200' })
  return apiRequest(`/api/v1/admin/home-banners?${params}`, { signal })
}

export function createHomeBanner(input: HomeBannerInput): Promise<HomeBanner> {
  return apiRequest('/api/v1/admin/home-banners', { method: 'POST', body: JSON.stringify(input) })
}

export function updateHomeBanner(bannerId: string, input: HomeBannerInput): Promise<HomeBanner> {
  return apiRequest(`/api/v1/admin/home-banners/${encodeURIComponent(bannerId)}`, { method: 'PUT', body: JSON.stringify(input) })
}

export function deleteHomeBanner(bannerId: string): Promise<void> {
  return apiRequest(`/api/v1/admin/home-banners/${encodeURIComponent(bannerId)}`, { method: 'DELETE' })
}

export function uploadAdminMedia(file: File, category = 'home-banner'): Promise<AdminMediaUpload> {
  const body = new FormData()
  body.append('category', category)
  body.append('file', file, file.name)
  return apiRequest('/api/v1/admin/media/upload', { method: 'POST', body })
}

export function listCommunityPosts(query: { keyword: string; status: string; homeHot: string }, signal?: AbortSignal): Promise<CommunityPost[]> {
  const params = new URLSearchParams({ keyword: query.keyword, status: query.status, limit: '200' })
  if (query.homeHot) params.set('home_hot', query.homeHot)
  return apiRequest(`/api/v1/admin/community-posts?${params}`, { signal })
}

export function createCommunityPost(input: CommunityPostInput): Promise<CommunityPost> { return apiRequest('/api/v1/admin/community-posts', { method: 'POST', body: JSON.stringify(input) }) }
export function updateCommunityPost(postId: string, input: CommunityPostInput): Promise<CommunityPost> { return apiRequest(`/api/v1/admin/community-posts/${encodeURIComponent(postId)}`, { method: 'PUT', body: JSON.stringify(input) }) }
export function deleteCommunityPost(postId: string): Promise<void> { return apiRequest(`/api/v1/admin/community-posts/${encodeURIComponent(postId)}`, { method: 'DELETE' }) }
export function listContentBlocks(section = '', signal?: AbortSignal): Promise<ContentBlock[]> { return apiRequest(`/api/v1/admin/blocks?${new URLSearchParams({ section })}`, { signal }) }
export function createContentBlock(input: ContentBlockInput): Promise<ContentBlock> { return apiRequest('/api/v1/admin/blocks', { method: 'POST', body: JSON.stringify(input) }) }
export function updateContentBlock(blockId: string, input: ContentBlockInput): Promise<ContentBlock> { return apiRequest(`/api/v1/admin/blocks/${encodeURIComponent(blockId)}`, { method: 'PUT', body: JSON.stringify(input) }) }
export function deleteContentBlock(blockId: string): Promise<void> { return apiRequest(`/api/v1/admin/blocks/${encodeURIComponent(blockId)}`, { method: 'DELETE' }) }
