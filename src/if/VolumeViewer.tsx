import { useEffect, useRef, useState } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { open, save } from '@tauri-apps/plugin-dialog'
import { Camera, FolderOpen, RotateCcw, X } from 'lucide-react'
import { callEngine } from '../bridge'
import { createSlice, sliceGeometry, type ChannelDisplay, type SliceMode, type Triple } from './volumeSlices'
import type { VolumeRenderer } from './volumeRenderer'
import './volumeViewer.css'

type Series = { index: number; dimensions: Triple; spacing: [number | null, number | null, number | null];
  timepoints: number; channels: string[]; error?: string }
type Inspection = { name: string; series: Series[] }
type Volume = { name: string; dimensions: Triple; original_dimensions: Triple; spacing: Triple;
  channels: string[]; ranges: [number, number][]; bytes: number }
type Data = { info: Volume; values: Uint16Array }
type Job = { job_id: string; status: string; completed?: number; total?: number; error?: string; volume?: Volume }
type Mode = '3D' | SliceMode
const MODES: Mode[] = ['3D', 'XY', 'XZ', 'YZ']
const COLORS = ['#4f8dff', '#43ff91', '#ff5867']
const BENCHMARK = import.meta.env.VITE_TITAN_IF_BENCHMARK === '1'
const CHUNK = 4 * 1024 * 1024

export default function VolumeViewer({ onClose }: { onClose: () => void }) {
  const [inspection, setInspection] = useState<Inspection>()
  const [path, setPath] = useState('')
  const [seriesIndex, setSeriesIndex] = useState(0)
  const [time, setTime] = useState(0)
  const [selected, setSelected] = useState<number[]>([])
  const [spacing, setSpacing] = useState(['', '', ''])
  const [data, setData] = useState<Data>()
  const [mode, setMode] = useState<Mode>('3D')
  const [layers, setLayers] = useState({ XY: 0, XZ: 0, YZ: 0 })
  const [channels, setChannels] = useState<ChannelDisplay[]>([])
  const [busy, setBusy] = useState('')
  const [progress, setProgress] = useState<Job>()
  const [notice, setNotice] = useState('')
  const [gpuError, setGpuError] = useState('')
  const [gpuReady, setGpuReady] = useState(false)
  const [firstFrame, setFirstFrame] = useState<number>()
  const [benchmark, setBenchmark] = useState('')
  const [benchmarking, setBenchmarking] = useState(false)
  const [saving, setSaving] = useState(false)
  const request = useRef(0)
  const currentJob = useRef('')
  const host = useRef<HTMLDivElement>(null)
  const canvas = useRef<HTMLCanvasElement>(null)
  const renderer = useRef<VolumeRenderer | undefined>(undefined)
  const currentChannels = useRef(channels)
  const startedAt = useRef(0)
  currentChannels.current = channels

  const series = inspection?.series.find(item => item.index === seriesIndex)
  const slice = data && mode !== '3D' ? sliceGeometry(data.info, mode) : undefined

  function release(id: string) {
    return callEngine('if_cancel_job', { job_id: id }).catch(() => undefined)
  }

  function invalidate() {
    request.current++
    const id = currentJob.current
    currentJob.current = ''
    if (id) void release(id)
    setBusy('')
    setProgress(undefined)
  }

  useEffect(() => () => {
    request.current++
    if (currentJob.current) void release(currentJob.current)
    currentJob.current = ''
  }, [])

  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !saving) onClose()
    }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [onClose, saving])

  function selectSeries(next: Series) {
    setSeriesIndex(next.index)
    setTime(0)
    setSelected(next.error ? [] : next.channels.slice(0, 3).map((_, index) => index))
    setSpacing(next.error ? ['', '', ''] : next.spacing.map(value => value?.toString() ?? ''))
  }

  async function chooseFile() {
    try {
      const chosen = await open({ multiple: false, title: '打开 OME-TIFF Z-stack',
        filters: [{ name: 'OME-TIFF', extensions: ['tif', 'tiff'] }] })
      if (typeof chosen !== 'string') return
      invalidate()
      setNotice('')
      setBenchmark('')
      setData(undefined)
      setInspection(undefined)
      setPath(chosen)
      const generation = request.current
      setBusy('检查 OME-TIFF')
      try {
        const meta = await callEngine<Inspection>('if_volume_inspect', { path: chosen })
        if (request.current !== generation) return
        setInspection(meta)
        const initial = meta.series.find(item => !item.error) ?? meta.series[0]
        if (initial) selectSeries(initial)
        else setNotice('此文件中没有可读取的图像序列。')
      } catch (error) {
        if (request.current === generation) setNotice(String(error))
      } finally {
        if (request.current === generation) setBusy('')
      }
    } catch (error) { setNotice(String(error)) }
  }

  async function load() {
    if (!series || series.error || !selected.length) return
    invalidate()
    const generation = request.current
    setNotice('')
    setData(undefined)
    setBenchmark('')
    setFirstFrame(undefined)
    setGpuReady(false)
    setGpuError('')
    setMode('3D')
    setBusy('准备体数据')
    startedAt.current = performance.now()
    let id = ''
    try {
      const job = await callEngine<Job>('if_volume_start', {
        path, series: series.index, time, channels: selected, spacing: spacing.map(Number),
      })
      id = job.job_id
      if (request.current !== generation) return
      currentJob.current = id
      while (request.current === generation) {
        const status = await callEngine<Job>('if_job_status', { job_id: id })
        if (request.current !== generation) return
        setProgress(status)
        if (status.status === 'failed' || status.status === 'cancelled') throw new Error(status.error || '读取已取消')
        if (status.status === 'completed' && status.volume) {
          setBusy('加载体数据')
          const info = status.volume
          const bytes = new Uint8Array(info.bytes)
          for (let offset = 0; offset < bytes.length; offset += CHUNK) {
            if (request.current !== generation) return
            const length = Math.min(CHUNK, bytes.length - offset)
            const chunk = await invoke<ArrayBuffer>('if_volume_read', { jobId: id, offset, length })
            if (!(chunk instanceof ArrayBuffer) || chunk.byteLength !== length) throw new Error('体数据传输不完整')
            bytes.set(new Uint8Array(chunk), offset)
          }
          if (request.current !== generation) return
          setLayers({ XY: Math.floor(info.dimensions[2] / 2), XZ: Math.floor(info.dimensions[1] / 2),
            YZ: Math.floor(info.dimensions[0] / 2) })
          setChannels(info.ranges.map(([min, max], index) => ({
            visible: true, color: COLORS[index], min, max, opacity: .18,
          })))
          setData({ info, values: new Uint16Array(bytes.buffer) })
          return
        }
        await new Promise(resolve => setTimeout(resolve, 100))
      }
    } catch (error) {
      if (request.current === generation) setNotice(String(error))
    } finally {
      if (id) void release(id)
      if (currentJob.current === id) currentJob.current = ''
      if (request.current === generation) {
        setProgress(undefined)
        setBusy('')
      }
    }
  }

  useEffect(() => {
    if (!data || !host.current) return
    const element = host.current
    let live = true
    let frame = 0
    let attached: VolumeRenderer | undefined
    function fallback(error: unknown) {
      if (!live) return
      setGpuError(String(error))
      setGpuReady(false)
      setMode('XY')
    }
    import('./volumeRenderer').then(({ attachVolume }) => {
      if (!live) return
      attached = attachVolume(element, data.info, data.values, data.info.channels.length,
        () => fallback('GPU 渲染已中断'))
      renderer.current = attached
      attached.update(currentChannels.current)
      setGpuReady(true)
      if (BENCHMARK) frame = requestAnimationFrame(() => {
        frame = requestAnimationFrame(() => { if (live) setFirstFrame(performance.now() - startedAt.current) })
      })
    }).catch(fallback)
    return () => {
      live = false
      cancelAnimationFrame(frame)
      attached?.dispose()
      renderer.current = undefined
    }
  }, [data])

  useEffect(() => {
    if (mode === '3D') renderer.current?.update(channels)
    if (!data || mode === '3D' || !canvas.current) return
    const { width, height } = sliceGeometry(data.info, mode)
    const context = canvas.current.getContext('2d')
    const pixels = context?.createImageData(width, height)
    if (pixels) {
      pixels.data.set(createSlice(data.values, data.info, mode, layers[mode], channels))
      context?.putImageData(pixels, 0, 0)
    }
  }, [data, mode, layers, channels])

  function editChannel(index: number, changes: Partial<ChannelDisplay>) {
    setChannels(previous => previous.map((channel, i) => i === index ? { ...channel, ...changes } : channel))
  }

  async function screenshot() {
    if (!data) return
    setSaving(true)
    setNotice('')
    try {
      let image: string | undefined
      if (mode === '3D') image = await renderer.current?.capture()
      else if (canvas.current && slice) {
        const exportCanvas = document.createElement('canvas')
        const width = Math.max(1, Math.round(768 * Math.min(1, slice.aspect)))
        const height = Math.max(1, Math.round(768 * Math.min(1, 1 / slice.aspect)))
        exportCanvas.width = width
        exportCanvas.height = height
        const context = exportCanvas.getContext('2d')
        if (context) {
          context.imageSmoothingEnabled = false
          context.drawImage(canvas.current, 0, 0, width, height)
          image = exportCanvas.toDataURL('image/png')
        }
      }
      if (!image) throw new Error('当前视图尚未准备好')
      const destination = await save({ title: '保存当前视图截图',
        defaultPath: data.info.name.replace(/\.ome\.tiff?$/i, '') + '-' + mode + '.png',
        filters: [{ name: 'PNG 图片', extensions: ['png'] }] })
      if (!destination) return
      await callEngine('if_volume_save_png', { destination, png: image.split(',')[1] })
      setNotice('已保存截图 · ' + destination)
    } catch (error) { setNotice(String(error)) }
    finally { setSaving(false) }
  }

  async function runBenchmark() {
    if (!renderer.current) return
    setBenchmarking(true)
    setBenchmark('正在测量 10 秒旋转…')
    try {
      const result = await renderer.current.benchmark()
      setBenchmark(`${result.width}×${result.height} · 中位 ${result.fps.toFixed(1)} FPS · P95 帧间隔 ${result.p95.toFixed(1)} ms`)
    } catch (error) { setBenchmark(String(error)) }
    finally { setBenchmarking(false) }
  }

  return <div className="modal-backdrop if-volume-backdrop">
    <section className="if-volume-dialog" role="dialog" aria-modal="true" aria-label="免疫荧光 3D 查看">
      <header className="if-volume-header">
        <div><h2>3D 查看 <small>原型</small></h2>
          <p>{inspection?.name ?? '打开一个 OME-TIFF Z-stack，在本地查看荧光的空间分布。'}</p></div>
        <div className="if-volume-buttons">
          <button className="btn secondary" onClick={chooseFile} disabled={saving || benchmarking}>
            <FolderOpen size={16}/>打开 Z-stack
          </button>
          <button className="icon-btn" aria-label="关闭 3D 查看" onClick={onClose} disabled={saving}><X size={20}/></button>
        </div>
      </header>
      {notice && <p className="if-volume-status" role="status">{notice}</p>}
      {busy && <div className="if-volume-status" role="status">
        <span>{busy}{progress?.total && progress.total > 1 ? ` · ${progress.completed ?? 0}/${progress.total} 层` : '…'}</span>
        {progress?.total && progress.total > 1 ? <progress max={progress.total} value={progress.completed ?? 0}/> : null}
        <button className="btn secondary" onClick={invalidate}>取消读取</button>
      </div>}
      {inspection && !data && <div className="if-volume-setup">
        <h3>选择要查看的序列和通道</h3>
        <label>图像序列 <select value={seriesIndex} disabled={!!busy} onChange={event => {
          const next = inspection.series.find(item => item.index === Number(event.target.value))
          if (next) selectSeries(next)
        }}>{inspection.series.map(item => <option value={item.index} key={item.index}>
          序列 {item.index + 1}{item.error ? ' · 不支持' : ' · ' + item.dimensions.join(' × ')}
        </option>)}</select></label>
        {series?.error && <p role="alert">{series.error}</p>}
        {series && !series.error && <>
          {series.timepoints > 1 && <label>时间点 <select value={time} disabled={!!busy} onChange={e => setTime(Number(e.target.value))}>
            {Array.from({ length: series.timepoints }, (_, i) => <option key={i} value={i}>{i + 1}</option>)}
          </select></label>}
          <fieldset disabled={!!busy}><legend>显示通道 · 最多三个</legend>
            {series.channels.map((name, i) => <label key={i}>
              <input type="checkbox" checked={selected.includes(i)} disabled={!selected.includes(i) && selected.length >= 3}
                onChange={e => setSelected(e.target.checked ? [...selected, i].sort((a, b) => a - b) : selected.filter(n => n !== i))}/>
              {name}
            </label>)}
          </fieldset>
          <fieldset disabled={!!busy}><legend>体素标定 · µm</legend>
            {['X', 'Y', 'Z'].map((axis, i) => <label key={axis}>{axis}
              <input type="number" step="any" min={0} aria-label={axis + ' 标定'} value={spacing[i]}
                disabled={series.spacing[i] !== null} placeholder="请输入"
                onChange={e => setSpacing(values => values.map((value, j) => j === i ? e.target.value : value))}/>
            </label>)}
          </fieldset>
          <button className="btn primary" onClick={load} disabled={!!busy || !selected.length ||
            spacing.some(value => !Number.isFinite(Number(value)) || Number(value) <= 0)}>加载 3D 视图</button>
        </>}
      </div>}
      {!inspection && !busy && <div className="if-volume-empty">选择带有多个 Z 层的 OME-TIFF 文件开始。</div>}
      {data && <>
        <div className="if-volume-toolbar">
          <div className="if-volume-modes" role="group" aria-label="观察方向">
            {MODES.map(view => <button className="btn secondary" key={view} aria-pressed={mode === view}
              disabled={benchmarking || saving || (view === '3D' && !!gpuError)} onClick={() => setMode(view)}>{view}</button>)}
          </div>
          <div className="if-volume-buttons">
            {mode === '3D' && <button className="btn secondary" disabled={!gpuReady || benchmarking || saving}
              onClick={() => renderer.current?.reset()}><RotateCcw size={15}/>重置视角</button>}
            <button className="btn secondary" disabled={saving || benchmarking || (mode === '3D' && !gpuReady)}
              onClick={screenshot}><Camera size={16}/>保存截图</button>
          </div>
        </div>
        {gpuError && <p className="if-volume-status" role="status">{gpuError}。可以继续浏览正交切片。</p>}
        <div className="if-volume-content">
          <div className="if-volume-viewport">
            <div className="if-volume-webgl" ref={host} hidden={mode !== '3D'} aria-label="三维荧光图像"/>
            {mode !== '3D' && slice && <div className="if-volume-slice">
              <canvas ref={canvas} width={slice.width} height={slice.height} style={{ width: `min(100cqw, ${slice.aspect * 100}cqh)`,
                height: `min(100cqh, ${100 / slice.aspect}cqw)` }}
                aria-label={mode + ' 荧光切片'}/>
            </div>}
            {mode === '3D' && !gpuReady && <div className="if-volume-loading">启动三维渲染…</div>}
          </div>
          <aside className="if-volume-controls" aria-label="通道显示">
            <h3>通道显示</h3>
            {channels.map((channel, i) => <fieldset key={i} disabled={benchmarking || saving}>
              <legend>{data.info.channels[i]}</legend>
              <div className="if-volume-channel-top">
                <label><input type="checkbox" checked={channel.visible}
                  onChange={e => editChannel(i, { visible: e.target.checked })}/>显示</label>
                <input type="color" aria-label={data.info.channels[i] + ' 颜色'} value={channel.color}
                  onChange={e => editChannel(i, { color: e.target.value })}/>
              </div>
              <label>透明度 <input type="range" min="0" max="1" step=".01" value={channel.opacity}
                aria-label={data.info.channels[i] + ' 透明度'}
                onChange={e => editChannel(i, { opacity: Number(e.target.value) })}/></label>
              <div className="if-volume-range">
                <label>下限 <input type="number" min={0} max={65534} value={channel.min}
                  onChange={e => editChannel(i, { min: Math.max(0, Math.min(channel.max - 1, Number(e.target.value))) })}/></label>
                <label>上限 <input type="number" min={1} max={65535} value={channel.max}
                  onChange={e => editChannel(i, { max: Math.min(65535, Math.max(channel.min + 1, Number(e.target.value))) })}/></label>
              </div>
            </fieldset>)}
          </aside>
        </div>
        <div className="if-volume-footer">
          {mode !== '3D' && slice && <label className="if-volume-layer">
            {mode} 切片 {layers[mode] + 1} / {slice.count}
            <input type="range" min={1} max={slice.count} value={layers[mode] + 1} aria-label={mode + ' 切片位置'}
              onChange={e => setLayers({ ...layers, [mode]: Number(e.target.value) - 1 })}/>
          </label>}
          <span>显示 {data.info.dimensions.join(' × ')}
            {data.info.original_dimensions.some((n, i) => n !== data.info.dimensions[i]) && ' · 原始 ' + data.info.original_dimensions.join(' × ')}
            {' · ' + data.info.spacing.map(n => Number(n.toPrecision(4))).join(' × ') + ' µm/体素'}
          </span>
          {BENCHMARK && <div className="if-volume-benchmark">
            {firstFrame !== undefined && <span>首次出图 {(firstFrame / 1000).toFixed(2)} 秒</span>}
            <button className="btn secondary" disabled={mode !== '3D' || !gpuReady || benchmarking || saving} onClick={runBenchmark}>
              测试旋转流畅度
            </button>
            {benchmark && <span role="status">{benchmark}</span>}
          </div>}
        </div>
      </>}
    </section>
  </div>
}
