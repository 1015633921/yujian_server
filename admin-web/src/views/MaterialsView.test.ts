import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import MaterialsView from './MaterialsView.vue'

const api = vi.hoisted(() => ({
  listMaterialSpus: vi.fn(),
  listMaterialTypes: vi.fn(),
}))

vi.mock('@/features/materials/api', () => api)

describe('MaterialsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.listMaterialTypes.mockResolvedValue([])
    api.listMaterialSpus.mockResolvedValue({
      items: [{
        id: 'series-1',
        series_id: 'series-1',
        spu: {
          series: '幽灵随形',
          category: '随形',
          sku_count: 2,
          min_price: 16,
          max_price: 18,
          size_values: [12.4, 15.2],
          sku_options: [
            { id: 'sku-12', size_mm: 12.4 },
            { id: 'sku-15', size_mm: 15.2, grade: 'AAA' },
          ],
        },
      }],
      pagination: { total: 1, has_next: false },
    })
  })

  it('links every displayed size to its SKU physical specification editor', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/materials', name: 'materials', component: MaterialsView },
        { path: '/materials/:materialId', name: 'material-detail', component: { template: '<main>detail</main>' } },
        { path: '/material-directory', name: 'material-directory', component: { template: '<main>directory</main>' } },
        { path: '/material-assets', name: 'material-assets', component: { template: '<main>assets</main>' } },
        { path: '/material-directory/series/:seriesId', name: 'material-series-profile', component: { template: '<main>series</main>' } },
      ],
    })
    await router.push('/materials')
    await router.isReady()
    const wrapper = mount({ template: '<RouterView />' }, { global: { plugins: [router] } })
    await flushPromises()

    const links = wrapper.findAll('.material-lookup-row__specs a')
    expect(links.map(link => link.text())).toEqual(['12.4 mm', '15.2 mm · AAA'])
    expect(links[0]?.attributes('href')).toBe('/materials/sku-12')
    expect(links[1]?.attributes('title')).toContain('编辑 15.2mm SKU 实物规格')
  })
})
