import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import CustomDesignWorkbenchView from './CustomDesignWorkbenchView.vue'

const api = vi.hoisted(() => ({
  getCustomDesignWorkbench: vi.fn(),
  listCustomDesignMaterials: vi.fn(),
  getCustomDesignCandidates: vi.fn(),
  saveCustomDesignDraft: vi.fn(),
  publishCustomDesignProposal: vi.fn(),
}))

vi.mock('@/features/custom-design/api', () => api)

function source() {
  return {
    overview: {
      request_id: 'CD-001',
      report_id: 'report-001',
      report_code: 'RPT-20260806-0001',
      report_version: 1,
      status: 'designing',
      request: { wrist_size_cm: 16, bead_size_mm: 8, budget: '300–500 元' },
      design_brief: {
        design_goal: { title: '清透自然' },
        material_roles: [{ key: 'primary', label: '主材', element: '水', reason: '承接主色。' }],
      },
    },
    source_kind: 'draft',
    workbench: {
      wrist_size_cm: 16,
      bead_size_mm: 8,
      notes: '已有结构',
      layout: [
        { id: 'M1', material_id: 'M1', name: '海蓝宝', price: 12, size_mm: 8, top: 'bead', stock: 10, image_urls: ['https://cdn.example.com/m1.webp'], selected_image_url: 'https://cdn.example.com/m1.webp' },
        { id: 'M2', material_id: 'M2', name: '月光石', price: 10, size_mm: 8, top: 'bead', stock: 10, image_urls: ['https://cdn.example.com/m2.webp'], selected_image_url: 'https://cdn.example.com/m2.webp' },
      ],
    },
    proposal: null,
  }
}

async function createPage() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/design-requests/:requestId/workbench', name: 'design-request-workbench', component: CustomDesignWorkbenchView },
      { path: '/design-requests/:requestId', name: 'design-request-detail', component: { template: '<main>detail</main>' } },
    ],
  })
  await router.push('/design-requests/CD-001/workbench')
  await router.isReady()
  const wrapper = mount({ template: '<RouterView />' }, { global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

describe('CustomDesignWorkbenchView', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    api.getCustomDesignWorkbench.mockResolvedValue(source())
    api.listCustomDesignMaterials.mockResolvedValue({ items: [], pagination: { total: 0, has_next: false } })
    api.getCustomDesignCandidates.mockResolvedValue({ status: 'ready', candidate_groups: [] })
    api.saveCustomDesignDraft.mockResolvedValue(source().overview)
    api.publishCustomDesignProposal.mockResolvedValue(source().overview)
    vi.stubGlobal('confirm', vi.fn(() => true))
  })

  it('restores a draft with stable per-bead keys and reorders the same instances', async () => {
    const wrapper = await createPage()
    const before = wrapper.findAll('.workbench-sequence__list article')
    expect(before).toHaveLength(2)
    const firstId = before[0]?.attributes('data-instance-id')
    const secondId = before[1]?.attributes('data-instance-id')
    expect(firstId).not.toBe(secondId)

    await before[0]!.findAll('.sequence-actions button')[1]!.trigger('click')
    const after = wrapper.findAll('.workbench-sequence__list article')
    expect(after[0]?.attributes('data-instance-id')).toBe(secondId)
    expect(after[1]?.attributes('data-instance-id')).toBe(firstId)
    expect(after[0]?.text()).toContain('月光石')
  })

  it('prevents duplicate draft saves while the first validation request is in progress', async () => {
    let release: ((value: unknown) => void) | undefined
    api.saveCustomDesignDraft.mockImplementation(() => new Promise((resolve) => { release = resolve }))
    const wrapper = await createPage()
    const save = wrapper.findAll('.workbench-actions button')[0]!

    await save.trigger('click')
    await save.trigger('click')
    expect(api.saveCustomDesignDraft).toHaveBeenCalledTimes(1)

    release?.(source().overview)
    await flushPromises()
    expect(wrapper.text()).toContain('草稿已保存')
  })

  it('lets an operator select multiple library materials before adding them to the layout', async () => {
    api.listCustomDesignMaterials.mockResolvedValue({
      items: [
        { id: 'M3', material_id: 'M3', name: '白水晶', price: 8, size_mm: 8, top: 'bead', stock: 10, image_urls: ['https://cdn.example.com/m3.webp'] },
        { id: 'M4', material_id: 'M4', name: '黑曜石', price: 9, size_mm: 8, top: 'bead', stock: 10, image_urls: ['https://cdn.example.com/m4.webp'] },
      ],
      pagination: { total: 2, has_next: false },
    })
    const wrapper = await createPage()
    const choices = wrapper.findAll('.workbench-materials button')
    expect(choices).toHaveLength(2)
    await choices[0]!.trigger('click')
    await choices[1]!.trigger('click')
    expect(wrapper.text()).toContain('已选 2 种材料')
    const requestsBeforeBatchAdd = api.getCustomDesignCandidates.mock.calls.length
    const add = wrapper.findAll('button').find((item) => item.text() === '加入逐颗排布')
    await add!.trigger('click')
    expect(wrapper.findAll('.workbench-sequence__list article')).toHaveLength(4)
    expect(wrapper.text()).toContain('白水晶')
    expect(wrapper.text()).toContain('黑曜石')
    expect(api.getCustomDesignCandidates).toHaveBeenCalledTimes(requestsBeforeBatchAdd + 1)
  })
})
