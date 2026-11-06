import { describe, expect, it } from 'vitest'
import { createSlice, sliceGeometry } from './volumeSlices'

describe('orthogonal fluorescence slices', () => {
  const info = { dimensions: [3, 2, 2], spacing: [.25, .5, 2] } as const
  const values = new Uint16Array(3 * 2 * 2 * 2)
  values[((1 * 2 + 0) * 3 + 2) * 2] = 4096
  values[((1 * 2 + 0) * 3 + 2) * 2 + 1] = 4096
  const red = { visible: true, color: '#ff0000', min: 0, max: 4096, opacity: .5 }
  const green = { ...red, visible: false, color: '#00ff00' }

  it('keeps the same voxel registered through all three views', () => {
    const pixel = (slice: Uint8ClampedArray, index: number) => [...slice.slice(index * 4, index * 4 + 4)]
    expect(pixel(createSlice(values, info, 'XY', 1, [red, green]), 2)).toEqual([128, 0, 0, 255])
    expect(pixel(createSlice(values, info, 'XZ', 0, [red, green]), 2)).toEqual([128, 0, 0, 255])
    expect(pixel(createSlice(values, info, 'YZ', 2, [red, green]), 0)).toEqual([128, 0, 0, 255])
    expect(sliceGeometry(info, 'XZ').aspect).toBeCloseTo(.75 / 4)
  })
})
