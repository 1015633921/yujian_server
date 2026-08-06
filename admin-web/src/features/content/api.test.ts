import { beforeEach, describe, expect, it, vi } from 'vitest'

import { storeToken } from '@/api/client'

import { createCommunityPost, createContentBlock, createHomeBanner, deleteCommunityPost, deleteContentBlock, deleteHomeBanner, listCommunityPosts, listContentBlocks, listHomeBanners, updateCommunityPost, updateContentBlock, updateHomeBanner } from './api'

describe('home banner api', () => {
  beforeEach(() => { window.history.replaceState({}, '', '/admin-v2/home-banners'); storeToken('operator-token'); vi.restoreAllMocks() })

  it('uses the banner list filters and the dedicated write endpoints', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ code: 0, data: [] }), { status: 200, headers: { 'content-type': 'application/json' } })))
    vi.stubGlobal('fetch', fetchMock)
    const payload = { title: '夏日清透', subtitle: '', eyebrow: '', image_url: 'https://example.com/banner.webp', actionText: '开始定制', actionUrl: '/pages/custom-mode/custom-mode', theme: 'clear' as const, status: 'draft' as const, sort_order: 1 }
    await listHomeBanners({ keyword: '夏日', status: 'draft' })
    await createHomeBanner(payload)
    await updateHomeBanner('banner-1', payload)
    await deleteHomeBanner('banner-1')
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('home-banners?keyword=%E5%A4%8F%E6%97%A5&status=draft&limit=200')
    expect(fetchMock.mock.calls.slice(1).map(([url]) => String(url))).toEqual([
      expect.stringContaining('home-banners'), expect.stringContaining('home-banners/banner-1'), expect.stringContaining('home-banners/banner-1'),
    ])
    expect(fetchMock.mock.calls.slice(1).map(([, init]) => (init as RequestInit).method)).toEqual(['POST', 'PUT', 'DELETE'])
  })

  it('keeps community posts and the home-hot flag on the same content resource', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ code: 0, data: [] }), { status: 200, headers: { 'content-type': 'application/json' } })))
    vi.stubGlobal('fetch', fetchMock)
    const payload = { title: '清透通勤', author: '宇涧主理人', desc: '', story: '', scene: '通勤', authorNote: '', likes: 0, tone: 'clear', recipe: ['sku-1'], materials: ['sku-1'], tags: ['清透'], image_url: 'https://example.com/inspo.webp', is_home_hot: true, status: 'published' as const, sort_order: 2 }
    await listCommunityPosts({ keyword: '通勤', status: 'published', homeHot: 'true' })
    await createCommunityPost(payload)
    await updateCommunityPost('inspo-1', { ...payload, is_home_hot: false })
    await deleteCommunityPost('inspo-1')
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('community-posts?keyword=%E9%80%9A%E5%8B%A4&status=published&limit=200&home_hot=true')
    expect(fetchMock.mock.calls.slice(1).map(([url]) => String(url))).toEqual([expect.stringContaining('community-posts'), expect.stringContaining('community-posts/inspo-1'), expect.stringContaining('community-posts/inspo-1')])
  })

  it('uses a separate content-block resource for fixed page sections', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ code: 0, data: [] }), { status: 200, headers: { 'content-type': 'application/json' } })))
    vi.stubGlobal('fetch', fetchMock)
    const payload = { section: 'home', title: '每日建议', subtitle: '', body: '', image_url: '', action_text: '', action_url: '', status: 'draft' as const, sort_order: 0 }
    await listContentBlocks('home')
    await createContentBlock(payload)
    await updateContentBlock('block-1', payload)
    await deleteContentBlock('block-1')
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('blocks?section=home')
    expect(fetchMock.mock.calls.slice(1).map(([, init]) => (init as RequestInit).method)).toEqual(['POST', 'PUT', 'DELETE'])
  })
})
