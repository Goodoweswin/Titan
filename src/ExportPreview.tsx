import {useEffect,useRef,useState} from 'react'
import {callEngine} from './bridge'
import type {AnalysisResult,PlotPreview,PlotSettings,Project} from './types'

export default function ExportPreview({project,result,onClose,onExport}:{project:Project;result:AnalysisResult;onClose:()=>void;onExport:(settings:PlotSettings)=>Promise<void>}){
 const dialog=useRef<HTMLDialogElement>(null)
 const [settings,setSettings]=useState<PlotSettings>({panel_width:5,height:4,font_size:11,dpi:220})
 const [response,setResponse]=useState<{key:string;data?:PlotPreview;error?:string}|null>(null)
 const [exporting,setExporting]=useState(false),[exportError,setExportError]=useState('')
 const key=JSON.stringify([project.id,project.revision,result.input_revision,settings])
 const valid=Object.entries(settings).every(([k,v])=>{const [lo,hi]=k==='dpi'?[72,300]:k==='font_size'?[8,24]:[3,8];return Number.isFinite(v)&&v>=lo&&v<=hi})
 useEffect(()=>{dialog.current?.showModal()},[])
 useEffect(()=>{
  if(!valid)return
  let cancelled=false
  const timer=setTimeout(()=>{callEngine<PlotPreview>('export_preview',{project,result,settings}).then(data=>{
   if(!cancelled)setResponse({key,data})
  }).catch(error=>{if(!cancelled)setResponse({key,error:String(error)})})},250)
  return()=>{cancelled=true;clearTimeout(timer)}
 },[key,valid])
 const current=response?.key===key?response:null
 async function confirmExport(){
  if(!current?.data||!valid||exporting)return
  setExporting(true);setExportError('')
  try{await onExport(current.data.settings)}catch(e){setExportError(String(e))}finally{setExporting(false)}
 }
 return <dialog ref={dialog} className="export-dialog" aria-labelledby="export-title" onCancel={e=>{if(exporting)e.preventDefault();else onClose()}}>
 <div className="card-heading"><div><h2 id="export-title">导出预览</h2><p className="hint">查看实际生成的图表，确认字号与尺寸。</p></div><button className="btn secondary" disabled={exporting} onClick={onClose}>关闭预览</button></div>
 <fieldset className="export-settings" disabled={exporting}>{([['panel_width','每面板宽度 in',3,8],['height','图表高度 in',3,8],['font_size','图表字号 pt',8,24],['dpi','图表 DPI',72,300]] as const).map(([k,label,min,max])=><label key={k}>{label}<input type="number" min={min} max={max} step={k==='panel_width'||k==='height'?.5:1} value={settings[k]} onChange={e=>{setExportError('');setSettings(s=>({...s,[k]:Number(e.target.value)}))}}/></label>)}</fieldset>
 <div className="export-canvas">{!valid?<p role="alert">尺寸须为 3–8 in，字号 8–24 pt，DPI 72–300。</p>:current?.error?<p role="alert">{current.error}</p>:current?.data?<img src={current.data.png} alt="实际导出图表"/>:<p role="status">正在生成图表预览…</p>}</div>
 {current?.data&&valid&&<p data-testid="export-dimensions">PNG：{current.data.width} × {current.data.height} px · 同时导出 SVG 矢量图</p>}
 <p className="hint">整图宽度随分析面板数量增加。导出还包含 CSV、原始图像、标注与审计记录；预览缩放仅影响屏幕显示。</p>
 {exportError&&<p role="alert">{exportError}</p>}
 <div className="export-actions"><button className="btn primary" disabled={!valid||!current?.data||exporting} onClick={confirmExport}>{exporting?'正在导出…':'选择目录并导出'}</button></div>
 </dialog>
}
