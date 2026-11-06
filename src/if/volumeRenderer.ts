import '@kitware/vtk.js/Rendering/Profiles/Volume'
import vtkImageData from '@kitware/vtk.js/Common/DataModel/ImageData'
import vtkDataArray from '@kitware/vtk.js/Common/Core/DataArray'
import vtkGenericRenderWindow from '@kitware/vtk.js/Rendering/Misc/GenericRenderWindow'
import vtkVolume from '@kitware/vtk.js/Rendering/Core/Volume'
import vtkVolumeMapper from '@kitware/vtk.js/Rendering/Core/VolumeMapper'
import { ColorMixPreset } from '@kitware/vtk.js/Rendering/Core/VolumeProperty/Constants'
import vtkColorTransferFunction from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction'
import vtkPiecewiseFunction from '@kitware/vtk.js/Common/DataModel/PiecewiseFunction'
import { rgb, type ChannelDisplay, type VolumeGeometry } from './volumeSlices'

export function attachVolume(host: HTMLElement, geometry: VolumeGeometry, values: Uint16Array,
                             count: number, onLost: () => void) {
  const probe = document.createElement('canvas').getContext('webgl2')
  if (!probe) throw new Error('当前设备无法启动 WebGL 2')
  const textureLimit = probe.getParameter(probe.MAX_3D_TEXTURE_SIZE)
  probe.getExtension('WEBGL_lose_context')?.loseContext()
  if (Math.max(...geometry.dimensions) > textureLimit) throw new Error('显卡的三维纹理尺寸不足')

  const window = vtkGenericRenderWindow.newInstance({ background: [0, 0, 0], listenWindowResize: false })
  const renderWindow = window.getRenderWindow()
  const renderer = window.getRenderer()
  const view = window.getApiSpecificRenderWindow()
  if (!('get3DContext' in view)) throw new Error('未能启动 WebGL 渲染器')
  const mapper = vtkVolumeMapper.newInstance()
  const actor = vtkVolume.newInstance()
  const data = vtkImageData.newInstance()
  const scalars = vtkDataArray.newInstance({ name: 'Fluorescence', numberOfComponents: count, values })
  const colors = Array.from({ length: count }, () => vtkColorTransferFunction.newInstance())
  const opacities = Array.from({ length: count }, () => vtkPiecewiseFunction.newInstance())
  const property = actor.getProperty()
  const step = Math.min(...geometry.spacing)
  let disposed = false
  let animation = 0
  let benchmarkCancel: (() => void) | undefined
  let rejectCapture: ((reason: Error) => void) | undefined

  function contextLost() {
    rejectCapture?.(new Error('GPU 渲染已中断，截图未保存'))
    onLost()
  }

  function resize() {
    if (!host.clientWidth || !host.clientHeight) return
    const scale = Math.min(1, 1280 / host.clientWidth, 960 / host.clientHeight)
    view.setSize(Math.round(host.clientWidth * scale), Math.round(host.clientHeight * scale))
    renderWindow.render()
  }
  const observer = new ResizeObserver(resize)
  function dispose() {
    if (disposed) return
    disposed = true
    observer.disconnect()
    host.removeEventListener('webglcontextlost', contextLost, true)
    cancelAnimationFrame(animation)
    benchmarkCancel?.()
    rejectCapture?.(new Error('视图已关闭'))
    renderer.removeVolume(actor)
    window.delete()
    for (const item of [...colors, ...opacities, actor, mapper, scalars, data]) item.delete()
    renderer.delete()
    renderWindow.delete()
    host.replaceChildren()
  }
  function resetCamera() {
    const camera = renderer.getActiveCamera()
    camera.setPosition(0, 0, 1)
    camera.setFocalPoint(0, 0, 0)
    camera.setViewUp(0, 1, 0)
    renderer.resetCamera()
    camera.azimuth(24)
    camera.elevation(18)
    camera.orthogonalizeViewUp()
    renderer.resetCameraClippingRange()
  }
  try {
    data.setDimensions([...geometry.dimensions])
    data.setSpacing([...geometry.spacing])
    data.getPointData().setScalars(scalars)
    mapper.setInputData(data)
    mapper.setSampleDistance(step * .8)
    mapper.setAutoAdjustSampleDistances(true)
    mapper.setInitialInteractionScale(2)
    mapper.setInteractionSampleDistanceFactor(2)
    // The VTK default sums channel tints even when a channel is transparent.
    // Weight each tint by its own local opacity so only visible signal adds color.
    mapper.setViewSpecificProperties({ OpenGL: { ShaderReplacements: [{
      shaderType: 'Fragment', originalValue: '//VTK::CustomColorMix', replaceFirst: true, replaceAll: false,
      replacementValue: `
        vec3 mixedTint = vec3(0.0);
        float totalOpacity = 0.0;
        for (int i = 0; i < vtkNumberOfComponents; ++i) {
          float lookupY = volume.transferFunctionsSampleHeight[i];
          float alpha = getOpacityFromTexture(tValue[i], i, lookupY);
          mixedTint += alpha * getColorFromTexture(tValue[i], i, lookupY);
          totalOpacity += alpha;
        }
        return vec4(mixedTint / max(totalOpacity, 1.e-6), min(totalOpacity, 1.0));
      `,
    }] } })
    actor.setMapper(mapper)
    property.setIndependentComponents(true)
    property.setColorMixPreset(ColorMixPreset.CUSTOM)
    property.setInterpolationTypeToLinear()
    for (let i = 0; i < count; i++) {
      property.setRGBTransferFunction(i, colors[i])
      property.setScalarOpacity(i, opacities[i])
      property.setScalarOpacityUnitDistance(i, step)
    }
    renderer.addVolume(actor)
    window.setContainer(host)
    host.addEventListener('webglcontextlost', contextLost, true)
    const canvas = view.getCanvas()
    if (canvas) {
      canvas.style.width = '100%'
      canvas.style.height = '100%'
    }
    resetCamera()
    observer.observe(host)
  } catch (error) {
    dispose()
    throw error
  }

  return {
    update(channels: ChannelDisplay[]) {
      channels.forEach((channel, i) => {
        const [r, g, b] = rgb(channel.color).map(value => value / 255)
        const high = Math.max(channel.min + 1, channel.max)
        const color = colors[i], opacity = opacities[i]
        color.removeAllPoints()
        color.addRGBPoint(channel.min, r, g, b)
        color.addRGBPoint(high, r, g, b)
        opacity.removeAllPoints()
        opacity.addPoint(channel.min, 0)
        opacity.addPoint(high, channel.visible ? channel.opacity : 0)
      })
      resize()
    },
    reset() {
      resetCamera()
      renderWindow.render()
    },
    async capture() {
      let timer: ReturnType<typeof setTimeout> | undefined
      try {
        const cancelled = new Promise<never>((_, reject) => {
          rejectCapture = reject
          timer = setTimeout(() => reject(new Error('截图超时，请重试')), 5000)
        })
        const image = view.captureNextImage('image/png', { resetCamera: false })
        const result = Promise.race([image, cancelled])
        renderWindow.render()
        const captured = await result
        if (!captured) throw new Error('无法捕获当前三维视图')
        return captured
      } finally {
        clearTimeout(timer)
        rejectCapture = undefined
      }
    },
    benchmark(): Promise<{ fps: number; p95: number; width: number; height: number }> {
      return new Promise((resolve, reject) => {
        const originalSize = view.getSize()
        const camera = renderer.getActiveCamera()
        const gl = view.get3DContext()
        if (!gl) { reject(new Error('渲染器未就绪')); return }
        const frames: number[] = []
        const width = 960, height = 720
        view.setSize(width, height)
        mapper.setImageSampleDistance(2)
        let start = 0, previous = 0
        const restore = () => {
          benchmarkCancel = undefined
          if (disposed) return
          mapper.setImageSampleDistance(1)
          view.setSize(...originalSize)
          resize()
        }
        benchmarkCancel = () => reject(new Error('测试已关闭'))
        const frame = (now: number) => {
          if (!start) start = now
          try {
            camera.azimuth(1.5)
            renderWindow.render()
            gl.finish()
            const completed = performance.now()
            if (previous) frames.push(completed - previous)
            previous = completed
            if (now - start < 10000) {
              animation = requestAnimationFrame(frame)
            } else {
              const sorted = frames.sort((a, b) => a - b)
              restore()
              resolve({ fps: 1000 / sorted[Math.floor(sorted.length / 2)], p95: sorted[Math.floor(sorted.length * .95)], width, height })
            }
          } catch (error) {
            restore()
            reject(error)
          }
        }
        animation = requestAnimationFrame(frame)
      })
    },
    dispose,
  }
}
export type VolumeRenderer = ReturnType<typeof attachVolume>
