import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import MaterialDetailView from './MaterialDetailView.vue'

const api = vi.hoisted(() => ({
  getMaterial: vi.fn(),
  patchMaterialSku: vi.fn(),
}))
const auth = vi.hoisted(() => ({ admin: { role: 'operator' } }))

vi.mock('@/features/materials/api', () => api)
vi.mock('@/stores/auth', () => ({ useAuthStore: () => auth }))

const material = {
  id: 'accessory-1',
  name: '幽灵随形',
  top: 'accessory',
  size: 15.2,
  weight: 2.6,
  image_urls: ['https://cdn.example.com/accessory.webp'],
  physical_specs: {
    string_axis_width_mm: 12.4,
    body_width_mm: 15.2,
    body_height_mm: 11.8,
  },
  sku: {
    size_mm: 15.2,
    weight_g: 2.6,
    price_per_bead: 16.5,
    cost_price: 8,
    stock: 12,
    safety_stock: 2,
    enabled: true,
    revision: 4,
  },
}

async function createPage() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/materials/:materialId', name: 'material-detail', component: MaterialDetailView },
      { path: '/materials', name: 'materials', component: { template: '<main>materials</main>' } },
    ],
  })
  await router.push('/materials/accessory-1')
  await router.isReady()
  const wrapper = mount({ template: '<RouterView />' }, { global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

describe('MaterialDetailView', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.clearAllMocks()
    auth.admin.role = 'operator'
    api.getMaterial.mockResolvedValue(structuredClone(material))
    api.patchMaterialSku.mockResolvedValue(structuredClone(material))
  })

  it('shows and saves SKU-level workbench physical specifications', async () => {
    const wrapper = await createPage()
    expect(wrapper.text()).toContain('工作台实物规格')
    expect((wrapper.get('input[name="physical_string_axis_width_mm"]').element as HTMLInputElement).value).toBe('12.4')

    await wrapper.get('input[name="physical_body_height_mm"]').setValue('12.1')
    await wrapper.get('input[name="physical_compatible_bead_size_mm"]').setValue('8')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(api.patchMaterialSku).toHaveBeenCalledWith('accessory-1', expect.objectContaining({
      size: 15.2,
      weight: 2.6,
      expected_revision: 4,
      physical_specs: {
        string_axis_width_mm: 12.4,
        body_width_mm: 15.2,
        body_height_mm: 12.1,
        compatible_bead_size_mm: 8,
      },
    }))
    expect(wrapper.text()).toContain('工作台实物规格已保存')
  })

  it('rejects zero physical dimensions before calling the API', async () => {
    const wrapper = await createPage()
    await wrapper.get('input[name="physical_body_width_mm"]').setValue('0')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(api.patchMaterialSku).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('外观宽度必须大于 0')
  })

  it('keeps every editable field disabled for a viewer', async () => {
    auth.admin.role = 'viewer'
    const wrapper = await createPage()

    expect(wrapper.findAll('input, select, button[type="submit"]').every((field) => field.attributes('disabled') !== undefined)).toBe(true)
    await wrapper.get('form').trigger('submit')
    expect(api.patchMaterialSku).not.toHaveBeenCalled()
  })
})
