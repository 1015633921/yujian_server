import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import MaterialAssetsView from './MaterialAssetsView.vue'

const api = vi.hoisted(() => ({
  bindMaterialAssets: vi.fn(), uploadMaterialAsset: vi.fn(), listMaterialTypes: vi.fn(), listMaterialTaxonomy: vi.fn(),
}))
vi.mock('@/features/materials/api', () => api)
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ admin: { role: 'operator' } }) }))

describe('MaterialAssetsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.listMaterialTypes.mockResolvedValue([{ id: 'type-bead', code: 'bead', name: '珠子', enabled: true }])
    api.listMaterialTaxonomy.mockResolvedValue([{
      id: 'category-1', parent_id: 'bead', kind: 'category', top: 'bead', name: '白水晶', sort_order: 1, enabled: true,
      series: [{ id: 'series-1', parent_id: 'category-1', kind: 'series', top: 'bead', name: '白水晶', sort_order: 1, enabled: true, image_urls: ['old.webp'] }],
    }])
  })

  it('defaults to append and explains the risk before replacement', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/material-assets', name: 'material-assets', component: MaterialAssetsView },
        { path: '/material-directory', name: 'material-directory', component: { template: '<main />' } },
        { path: '/material-directory/series/:seriesId', name: 'material-series-profile', component: { template: '<main />' } },
      ],
    })
    await router.push('/material-assets?top=bead&series_id=series-1')
    await router.isReady()
    const wrapper = mount({ template: '<RouterView />' }, { global: { plugins: [router] } })
    await flushPromises()

    const mode = wrapper.findAll('select')[3]!
    expect((mode.element as HTMLSelectElement).value).toBe('append')
    expect(wrapper.text()).not.toContain('替换会让现有图库停止引用')
    await mode.setValue('replace')
    expect(wrapper.text()).toContain('替换会让现有图库停止引用')
    expect(wrapper.get('input[placeholder="输入品种名称快速筛选"]')).toBeTruthy()
  })
})
