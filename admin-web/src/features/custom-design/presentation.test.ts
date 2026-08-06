import { describe, expect, it } from 'vitest'

import {
  customDesignActionLabel,
  customDesignStatusLabel,
  depositStatusLabel,
  formatAdminDate,
  latestProposal,
  normalizeCustomDesignStatus,
  proposalCount,
} from './presentation'

describe('custom design list presentation', () => {
  it('maps operational states to Chinese and rejects invalid filters', () => {
    expect(customDesignStatusLabel('revision_requested')).toBe('待调整')
    expect(customDesignStatusLabel('future_state')).toBe('状态更新')
    expect(depositStatusLabel('refund_failed')).toBe('退款待重试')
    expect(normalizeCustomDesignStatus('designing')).toBe('designing')
    expect(normalizeCustomDesignStatus('unknown')).toBe('')
    expect(customDesignActionLabel('submitted')).toBe('开始设计')
  })

  it('supports the lightweight proposal summary and legacy proposals array', () => {
    const lightweight = {
      request_id: 'CD1',
      report_id: 'R1',
      status: 'proposed',
      proposal_count: 3,
      latest_proposal: { title: '清透款' },
    }
    expect(proposalCount(lightweight)).toBe(3)
    expect(latestProposal(lightweight)?.title).toBe('清透款')

    const legacy = {
      request_id: 'CD2',
      report_id: 'R2',
      status: 'proposed',
      proposals: [{ title: '旧版方案' }],
    }
    expect(proposalCount(legacy)).toBe(1)
    expect(latestProposal(legacy)?.title).toBe('旧版方案')
  })

  it('never renders an invalid date', () => {
    expect(formatAdminDate('not-a-date')).toBe('-')
    expect(formatAdminDate('')).toBe('-')
  })
})
