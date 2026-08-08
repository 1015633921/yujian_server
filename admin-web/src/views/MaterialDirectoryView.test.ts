import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import MaterialDirectoryView from './MaterialDirectoryView.vue'

const api = vi.hoisted(() => ({
  deleteEmptyMaterialCategory: vi.fn(), deleteEmptyMaterialSeries: vi.fn(), deleteEmptyMaterialType: vi.fn(),
  disableMaterialTaxonomyItem: vi.fn(), disableMaterialType: vi.fn(), saveMaterialCategory: vi.fn(),
  saveMaterialSeries: vi.fn(), saveMaterialType: vi.fn(), updateMaterialSeries: vi.fn(),
  listMaterialOptions: vi.fn(), listMaterialTaxonomyPage: vi.fn(), listMaterialTypes: vi.fn(),
}))

vi.mock('@/features/materials/api', () => api)
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ admin: { role: 'operator' } }) }))

describe('MaterialDirectoryView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.sessionStorage.clear()
    api.listMaterialTypes.mockResolvedValue([
      { id: 'type-accessory', code: 'accessory', name: '配饰', description: '', sort_order: 1, enabled: true, category_count: 2, variety_count: 3, sku_count: 10 },
      { id: 'type-bead', code: 'bead', name: '珠子', description: '', sort_order: 2, enabled: true, category_count: 4, variety_count: 8, sku_count: 64 },
    ])
    api.listMaterialTaxonomyPage.mockResolvedValue({ items: [], categories: [], pagination: { total: 0, has_next: false } })
    api.listMaterialOptions.mockResolvedValue({ elements: [], wish_pools: [], chakras: [], color_families: [] })
  })

  it('opens the common bead workflow, defaults to enabled records, and keeps editing opt-in', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/material-directory', name: 'material-directory', component: MaterialDirectoryView },
        { path: '/materials', name: 'materials', component: { template: '<main />' } },
        { path: '/material-directory/series/:seriesId', name: 'material-series-profile', component: { template: '<main />' } },
      ],
    })
    await router.push('/material-directory')
    await router.isReady()
    const wrapper = mount({ template: '<RouterView />' }, { global: { plugins: [router] } })
    await flushPromises()
    await flushPromises()

    expect(router.currentRoute.value.query.top).toBe('bead')
    expect(api.listMaterialTaxonomyPage).toHaveBeenCalledWith(expect.objectContaining({ top: 'bead', status: 'enabled' }), expect.any(AbortSignal))
    expect(wrapper.text()).toContain('材料类型')
    expect(wrapper.text()).toContain('一级类目')
    expect(wrapper.text()).toContain('品种资料')
    expect(wrapper.text()).toContain('可售 SKU')
    expect(wrapper.text()).toContain('选择一项管理任务')
  })
})
