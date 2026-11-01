import {useEffect,useRef,useState} from 'react'
import type {ImageAsset} from './types'
import {displayStyle} from './image-display'

export default function ImageRotationDialog({asset,onApply,onClose}:{asset:ImageAsset;onApply:(angle:number)=>Promise<void>;onClose:()=>void}){
 const preview=useRef<HTMLDivElement>(null),dragging=useRef<'x'|'y'|null>(null),[guides,setGuides]=useState({x:50,y:50}),[showGuides,setShowGuides]=useState(true)
 const dialog=useRef<HTMLDialogElement>(null),[angle,setAngle]=useState(0),[busy,setBusy]=useState(false),[error,setError]=useState('')
 useEffect(()=>{dialog.current?.showModal()},[])
 const coarse=Math.round(angle/90)*90,fine=angle-coarse,valid=Number.isFinite(angle)&&Math.abs(angle)<=360&&angle!==0
 async function apply(){setBusy(true);setError('');try{await onApply(angle)}catch(e){setError(String(e));setBusy(false)}}
 function moveGuide(e:React.PointerEvent,axis:'x'|'y'){
  const bounds=preview.current!.getBoundingClientRect(),value=Math.round(10*Math.max(0,Math.min(100,axis==='x'?(e.clientX-bounds.x)/bounds.width*100:(e.clientY-bounds.y)/bounds.height*100)))/10
  setGuides(g=>({...g,[axis]:value}))
 }
 function guideKey(e:React.KeyboardEvent,axis:'x'|'y'){
  const keys=axis==='x'?['ArrowLeft','ArrowRight']:['ArrowUp','ArrowDown'],direction=keys.indexOf(e.key)
  if(direction<0)return;e.preventDefault();setGuides(g=>({...g,[axis]:Math.max(0,Math.min(100,g[axis]+(direction===0?-1:1)*(e.shiftKey?10:1)))}))
 }
 return <dialog ref={dialog} className="export-dialog rotation-dialog" aria-labelledby="rotation-title" onCancel={e=>{e.preventDefault();onClose()}}>
  <div className="card-heading"><h2 id="rotation-title">旋转校正</h2><button className="text-btn" onClick={onClose}>取消</button></div>
  <div ref={preview} className="rotation-preview"><img src={asset.preview} alt="旋转校正预览" style={{...displayStyle(asset),transform:`rotate(${Number.isFinite(angle)?angle:0}deg) scale(.8)`}}/><div className="rotation-grid"/>{showGuides&&(['y','x'] as const).map(axis=><div key={axis} role="slider" tabIndex={0} aria-label={axis==='y'?'水平参考线':'垂直参考线'} aria-orientation={axis==='y'?'vertical':'horizontal'} aria-valuemin={0} aria-valuemax={100} aria-valuenow={guides[axis]} className={`rotation-guide ${axis==='y'?'horizontal':'vertical'}`} style={axis==='y'?{top:`${guides.y}%`}:{left:`${guides.x}%`}} onKeyDown={e=>guideKey(e,axis)} onPointerDown={e=>{e.preventDefault();dragging.current=axis;e.currentTarget.focus();e.currentTarget.setPointerCapture(e.pointerId);moveGuide(e,axis)}} onPointerMove={e=>{if(dragging.current===axis)moveGuide(e,axis)}} onPointerUp={()=>{dragging.current=null}} onPointerCancel={()=>{dragging.current=null}}><span>{axis==='y'?'水平':'垂直'}</span></div>)}</div>
  <div className="rotation-guide-controls"><label className="checkbox-label"><input type="checkbox" checked={showGuides} onChange={e=>setShowGuides(e.target.checked)}/>显示参考线</label><span>拖动参考线对齐条带</span><button className="text-btn" onClick={()=>setGuides({x:50,y:50})}>参考线居中</button></div>
  <div className="rotation-controls"><button className="btn secondary" disabled={busy} onClick={()=>setAngle(a=>Math.max(-360,a-90))}>向左 90°</button><button className="btn secondary" disabled={busy} onClick={()=>setAngle(a=>Math.min(360,a+90))}>向右 90°</button><label>角度<input aria-label="旋转角度" type="number" min="-360" max="360" step="0.1" disabled={busy} value={Number.isFinite(angle)?angle:''} onChange={e=>setAngle(e.target.value===''?NaN:Number(e.target.value))}/></label><button className="text-btn" disabled={busy} onClick={()=>setAngle(0)}>重置</button></div>
  <input aria-label="微调旋转角度" type="range" min="-15" max="15" step="0.1" disabled={busy} value={Number.isFinite(fine)?Math.max(-15,Math.min(15,fine)):0} onChange={e=>setAngle(Number((coarse+Number(e.target.value)).toFixed(1)))}/>
  <p className="hint">保留原图，生成校正视图后重新框选。定量读取选框对应的原始像素。</p>
  {error&&<p role="alert">{error}</p>}
  <div className="export-actions"><button className="btn primary" disabled={busy||!valid} onClick={apply}>{busy?'正在校正…':'应用校正'}</button></div>
 </dialog>
}
