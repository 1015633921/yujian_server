import { describe, expect, it } from 'vitest'

import {
  MATERIAL_ASSET_OUTPUT_SIZE,
  materialAssetAlphaBounds,
  materialAssetMetrics,
  materialAssetPlacement,
} from './assets'

describe('material asset normalization', () => {
  it('finds the visible alpha subject and ignores transparent padding', () => {
    const pixels = new Uint8ClampedArray(4 * 4 * 4)
    const visible = [5, 6, 9, 10]
    for (const pixel of visible) pixels[pixel * 4 + 3] = 255

    const bounds = materialAssetAlphaBounds(pixels, 4, 4)

    expect(bounds).toMatchObject({ left: 1, top: 1, right: 2, bottom: 2, width: 2, height: 2 })
  })

  it('places an off-center source at the shared 512px output center', () => {
    const placement = materialAssetPlacement({ width: 100, height: 50 })

    expect(placement.width).toBe(Math.floor(MATERIAL_ASSET_OUTPUT_SIZE * 0.985))
    expect(placement.x).toBeGreaterThanOrEqual(0)
    expect(placement.y).toBeGreaterThan(placement.x)
    expect(materialAssetMetrics({ left: 3, right: 508, top: 3, bottom: 508, width: 506, height: 506 })).toMatchObject({
      fillRatio: expect.closeTo(506 / 512),
      offsetX: 0,
      offsetY: 0,
    })
  })
})
