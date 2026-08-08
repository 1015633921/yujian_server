import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import MaterialSeriesProfileView from './MaterialSeriesProfileView.vue'

const api = vi.hoisted(() => ({ getMaterialSeries: vi.fn(), listMaterialOptions: vi.fn(), updateMaterialSeries: vi.fn() }))
vi.mock('@/features/materials/api', () => api)
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ admin: { role: 'operator' } }) }))

const options = {
  elements: [], wish_pools: [], chakras: [], color_families: [], grades: [], effects: [], mood_tags: [], visual_tags: [], roles: [], match_rules: [], care_tags: [],
  bead_shapes: [{ key: 'round', label: '圆珠' }, { key: 'charm', label: '挂坠' }],
  placement_modes: [{ key: 'threaded', label: '穿线串珠' }, { key: 'hanging', label: '悬挂' }],
  visual_axes: [{ key: 'radial', label: '环绕' }, { key: 'vertical', label: '纵向' }],
  surface_finishes: [], transparency_levels: [], texture_features: [], batch_variation_levels: [], option_items: [],
}

describe('MaterialSeriesProfileView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.getMaterialSeries.mockResolvedValue({
      id: 'series-pendant', parent_id: 'category-pendant', category_name: '吊坠', kind: 'series', top: 'pendant', name: '银色条型吊坠',
      sort_order: 1, enabled: true, image_url: '', image_urls: [], energy: {}, rules: {},
      material_params: { bead_shape: 'round', placement_mode: 'threaded', visual_axis: 'radial' }, asset: {},
    })
    api.listMaterialOptions.mockResolvedValue(options)
    api.updateMaterialSeries.mockResolvedValue({})
  })

  it('hides irrelevant energy fields and repairs an incompatible pendant geometry before save', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/material-directory/series/:seriesId', name: 'material-series-profile', component: MaterialSeriesProfileView },
        { path: '/material-directory', name: 'material-directory', component: { template: '<main />' } },
        { path: '/material-assets', name: 'material-assets', component: { template: '<main />' } },
      ],
    })
    await router.push('/material-directory/series/series-pendant')
    await router.isReady()
    const wrapper = mount({ template: '<RouterView />' }, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('五行与推荐已按类型隐藏')
    expect(wrapper.text()).toContain('当前形制与“悬挂吊坠”不一致')
    const preset = wrapper.findAll('button').find((button) => button.text().includes('套用“悬挂吊坠”建议'))
    expect(preset).toBeTruthy()
    await preset!.trigger('click')

    const geometrySelects = wrapper.findAll('#profile-geometry select')
    expect((geometrySelects[0]!.element as HTMLSelectElement).value).toBe('charm')
    expect((geometrySelects[1]!.element as HTMLSelectElement).value).toBe('hanging')
    expect((geometrySelects[2]!.element as HTMLSelectElement).value).toBe('vertical')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(api.updateMaterialSeries).toHaveBeenCalledWith('series-pendant', expect.objectContaining({
      material_params: expect.objectContaining({ bead_shape: 'charm', placement_mode: 'hanging', visual_axis: 'vertical' }),
    }))
  })
})
