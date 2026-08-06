import { describe, expect, it } from 'vitest'

import { orderStatusLabel, receiverAddress } from './presentation'

describe('order presentation', () => {
  it('keeps admin status values out of the operator-facing interface', () => {
    expect(orderStatusLabel('pending_ship')).toBe('待发货')
    expect(orderStatusLabel('not-a-status')).toBe('状态更新')
  })

  it('formats a structured receiver address without leaking raw JSON', () => {
    expect(receiverAddress({ region: ['广东省', '广州市', '天河区'], detailAddress: '珠江新城 8 号' })).toBe('广东省 广州市 天河区 珠江新城 8 号')
  })
})
