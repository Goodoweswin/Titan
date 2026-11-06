import {useEffect, useRef, useState} from 'react'
import {Hand, X} from 'lucide-react'
import {laneTools} from './LaneLayoutEditor'

const tools = [...laneTools, ['rotate','旋转校正'], ['pan','移动视图']] as const
type Mode = typeof tools[number][0]

const descriptions: Record<Mode, string> = {
 region: '在图像上横向拖出一个框，圈住同一种蛋白的所有条带，避开分子量标记（Marker）。框好后再识别泳道。',
 lanes: '点选一条泳道。拖蓝框左右移动，拖两侧手柄改宽度。画布聚焦时可用左右方向键微调。',
 align: '在画布上左右拖动，让所有泳道一起对齐。适合目标图像上的泳道整体偏移时使用。',
 peaks: '拖动绿框上下对齐条带，拖下方手柄改高度。绿框标记用于定量的峰区。',
 background: '先选中泳道，再拖出背景框。选条带附近干净的区域，避开其他条带，用来扣除局部背景。',
 rotate: '图像倾斜时，参照水平线和垂直线微调角度。应用后保留原图，并在校正视图上重新框选。',
 pan: '拖动画布查看边缘。要继续框选，点「选择区域」或再点一次「移动视图」退出。',
}

function ToolDiagram({mode}: {mode: Mode}) {
 const showLanes = mode === 'lanes' || mode === 'align' || mode === 'peaks' || mode === 'background'
 return <svg className="wb-guide-diagram" viewBox="0 0 400 162" aria-hidden="true">
  <rect width="400" height="162" fill="#171b23"/>
  <rect x="24" y="22" width="352" height="118" rx="4" fill="#303742" stroke="#515b69"/>
  <g transform={mode === 'rotate' ? 'rotate(-7 200 81)' : mode === 'pan' ? 'translate(19 0)' : undefined}>
   <path d="M50 55h11m-11 12h11m-11 16h11m-11 15h11m-11 10h11" stroke="#aeb8c4" strokeWidth="3" strokeLinecap="round"/>
   {[102, 171, 240, 309].map((x, index) => {
    const y = [79, 75, 78, 81][index]
    return <g key={x}>
     <rect x={x} y={y} width="37" height="9" rx="4" fill="#c8d1dc"/>
     {showLanes && <rect x={x-9} y="54" width="55" height="56" rx="2" fill="#81a9ff12" stroke="#81a9ff" opacity={mode === 'align' || index === 1 ? 1 : .4}/>}
    </g>
   })}
  </g>
  {mode === 'region' && <rect x="87" y="53" width="271" height="55" rx="2" fill="#81a9ff18" stroke="#9abaff" strokeDasharray="5 4" strokeWidth="2"/>}
  {mode === 'lanes' && <path d="M159 78h6v7h-6zm55 0h6v7h-6z" fill="#81a9ff"/>}
  {(mode === 'peaks' || mode === 'background') && <rect x="162" y="70" width="55" height="20" fill="#59d6ad23" stroke="#59d6ad"/>}
  {mode === 'peaks' && <rect x="210" y="87" width="7" height="7" fill="#59d6ad"/>}
  {mode === 'background' && <rect x="162" y="95" width="55" height="12" fill="#d7ab5733" stroke="#d7ab57" strokeDasharray="4 3"/>}
  {mode === 'rotate' && <path d="M35 82h330M200 29v104" stroke="#81a9ff" strokeDasharray="5 4"/>}
  {(mode === 'align' || mode === 'pan') && <path d="M174 124h52m-46-5-6 5 6 5m40-10 6 5-6 5" fill="none" stroke="#b3caff" strokeWidth="2" strokeLinecap="round"/>}
 </svg>
}

export default function WbImageGuide({onClose}: {onClose: () => void}) {
 const dialog = useRef<HTMLDialogElement>(null)
 const [step, setStep] = useState(0)
 const [mode, label] = tools[step]
 const lastStep = step === tools.length - 1
 useEffect(() => {
  const element = dialog.current
  if (element && !element.open) element.showModal()
 }, [])

 return <dialog ref={dialog} className="export-dialog wb-guide" aria-labelledby="wb-guide-title" onClose={onClose}>
  <header className="wb-guide-header">
   <div>
    <h2 id="wb-guide-title">WB 图像操作指引</h2>
    <p>点选工具，查看它在画布上的用法。</p>
   </div>
   <button type="button" className="icon-btn" aria-label="关闭指引" onClick={() => dialog.current?.close()}><X size={18}/></button>
  </header>
  <div className="wb-guide-preview">
   <div className="wb-guide-tools" role="group" aria-label="图像工具示意">
    {tools.map(([id, name], index) =>
     <button key={id} type="button" className={mode === id ? 'tool selected' : 'tool'} aria-pressed={mode === id} onClick={() => setStep(index)}>
      {id === 'pan' && <Hand size={15} aria-hidden="true"/>}{name}
     </button>
    )}
   </div>
   <div className="wb-guide-body">
    <div className="wb-guide-illustration"><ToolDiagram mode={mode}/><small>操作示意图</small></div>
    <div className="wb-guide-copy" aria-live="polite" aria-atomic="true">
     <span className="wb-guide-progress">第 {step+1} / {tools.length} 步</span>
     <h3>{label}</h3>
     <p>{descriptions[mode]}</p>
    </div>
   </div>
  </div>
  <footer className="wb-guide-actions">
   <button type="button" className="btn secondary" disabled={step === 0} onClick={() => setStep(step-1)}>上一步</button>
   <button type="button" className="btn primary" onClick={() => lastStep ? dialog.current?.close() : setStep(step+1)}>{lastStep ? '完成' : '下一步'}</button>
  </footer>
 </dialog>
}
