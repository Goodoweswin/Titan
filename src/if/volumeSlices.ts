export type Triple = readonly [number, number, number]
export type SliceMode = 'XY' | 'XZ' | 'YZ'
export type VolumeGeometry = { dimensions: Triple; spacing: Triple }
export type ChannelDisplay = { visible: boolean; color: string; min: number; max: number; opacity: number }

export function rgb(color: string): [number, number, number] {
  const number = parseInt(color.slice(1), 16)
  return [(number >> 16) & 255, (number >> 8) & 255, number & 255]
}

export function sliceGeometry(info: VolumeGeometry, mode: SliceMode) {
  const [a, b, fixed] = mode === 'XY' ? [0, 1, 2] : mode === 'XZ' ? [0, 2, 1] : [1, 2, 0]
  const width = info.dimensions[a], height = info.dimensions[b]
  return { width, height, count: info.dimensions[fixed], aspect: width * info.spacing[a] / (height * info.spacing[b]) }
}

export function createSlice(values: Uint16Array, info: VolumeGeometry, mode: SliceMode,
                            index: number, channels: ChannelDisplay[]) {
  const [nx, ny, nz] = info.dimensions
  const { width, height } = sliceGeometry(info, mode)
  const pixels = new Uint8ClampedArray(width * height * 4)
  const visible = channels.flatMap((channel, i) => {
    if (!channel.visible || !channel.opacity) return []
    return [{ i, color: rgb(channel.color), min: channel.min, span: Math.max(1, channel.max - channel.min), opacity: channel.opacity }]
  })
  for (let v = 0; v < height; v++) {
    for (let u = 0; u < width; u++) {
      const z = mode === 'XY' ? index : nz - 1 - v
      const y = mode === 'XY' ? v : mode === 'XZ' ? index : u
      const x = mode === 'YZ' ? index : u
      const start = ((z * ny + y) * nx + x) * channels.length
      const dest = (v * width + u) * 4
      let red = 0, green = 0, blue = 0
      for (const channel of visible) {
        const weight = Math.max(0, Math.min(1, (values[start + channel.i] - channel.min) / channel.span)) * channel.opacity
        red += channel.color[0] * weight
        green += channel.color[1] * weight
        blue += channel.color[2] * weight
      }
      pixels[dest] = red
      pixels[dest + 1] = green
      pixels[dest + 2] = blue
      pixels[dest + 3] = 255
    }
  }
  return pixels
}
