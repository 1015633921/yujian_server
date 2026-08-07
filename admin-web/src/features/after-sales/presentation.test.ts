import { describe, expect, it } from 'vitest'

import { afterSaleEventLabel, afterSaleEventStatusText } from './presentation'

describe('after-sale presentation', () => {
  it('converts processing event enums into operator-facing copy', () => {
    expect(afterSaleEventLabel('refund_submitted')).toBe('已提交原路退款')
    expect(afterSaleEventLabel('unrecognized_internal_event')).toBe('已记录处理动作')
  })

  it('summarizes status changes without exposing raw state values', () => {
    expect(afterSaleEventStatusText('refund_pending', 'refunding')).toBe('状态：待确认退款 → 退款处理中')
    expect(afterSaleEventStatusText(undefined, 'requested')).toBe('状态更新为「待审核」')
  })
})
