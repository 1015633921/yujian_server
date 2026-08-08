import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AiMaterialTagsView from './AiMaterialTagsView.vue'

const api = vi.hoisted(() => ({ applyAiMaterialTag: vi.fn(), listAiMaterialTags: vi.fn(), reviewAiMaterialTag: vi.fn() }))
vi.mock('@/features/ai-tags/api', () => api)
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ admin: { role: 'operator' } }) }))

function record(id: string, status: string, category: string, createdAt: string) {
  return {
    annotation_id: id, target_id: `target-${id}`, material_code: id, top: 'bead', category, series: `材料 ${id}`, status,
    model_id: 'model', image_urls: [], created_at: createdAt, known_facts: {}, parsed_response: { confidence: .75, visual: {}, design: {} },
    application: { fields: { allowed_roles: ['primary'], match_rules: ['best_as_primary'], mood_tags: ['clarity', 'softness'], color_family: 'green' } },
  }
}

describe('AiMaterialTagsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.listAiMaterialTags.mockResolvedValue([
      record('pending-old', 'pending_review', '幽灵水晶', '2026-01-01T00:00:00Z'),
      record('pending-new', 'pending_review', '白水晶', '2026-01-02T00:00:00Z'),
      record('failed', 'failed', '幽灵水晶', '2026-01-03T00:00:00Z'),
    ])
  })

  it('loads one stable queue, defaults to pending, and keeps cross-status counts visible', async () => {
    const wrapper = mount(AiMaterialTagsView)
    await flushPromises()

    expect(api.listAiMaterialTags).toHaveBeenCalledWith('', expect.any(AbortSignal))
    expect(wrapper.findAll('.ai-tags__item')).toHaveLength(2)
    expect(wrapper.text()).toContain('待审核 2')
    expect(wrapper.text()).toContain('标注失败 1')
    expect(wrapper.text()).toContain('字段级写入预览')
    expect(wrapper.text()).toContain('通过不会立即修改资料')
    expect(wrapper.text()).toContain('清晰 · 柔和')
  })
})
