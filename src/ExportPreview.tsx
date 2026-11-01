import {useEffect,useRef,useState} from 'react'
import {callEngine} from './bridge'
import FigureEditor from './FigureEditor'
import {defaultFigureSettings,defaultPlotSettings} from './figure-settings'
import type {AnalysisResult,FigureData,FigureSettings,PlotPreview,PlotSettings,Project} from './types'

export default function ExportPreview({project,result,onClose,onExport,initialSettings,initialFigure,initialData}:{project:Project;result:AnalysisResult;onClose:()=>void;onExport:(settings:PlotSettings,figure:FigureSettings)=>Promise<void>;initialSettings?:PlotSettings;initialFigure?:FigureSettings;initialData?:FigureData}){
 const dialog=useRef<HTMLDialogElement>(null)
 const [settings,setSettings]=useState<PlotSettings>({...defaultPlotSettings,...project.plot_settings,...initialSettings})
 const [figure,setFigure]=useState<FigureSettings>(structuredClone(initialFigure??project.figure_settings??defaultFigureSettings()))
 const [response,setResponse]=useState<{key:string;data?:PlotPreview;error?:string}|null>(null)
 const [exporting,setExporting]=useState(false),[exportError,setExportError]=useState('')
 const key=JSON.stringify([project.id,project.revision,result.input_revision,settings,figure])
 const valid=Object.entries(settings).every(([k,v])=>{const [lo,hi]=k==='dpi'?[72,300]:k==='font_size'?[8,24]:[3,8];return Number.isFinite(v)&&v>=lo&&v<=hi})
 useEffect(()=>{dialog.current?.showModal()},[])
 useEffect(()=>{
  if(!valid)return
  let cancelled=false
  const timer=setTimeout(()=>{callEngine<PlotPreview>('export_preview',{project,result,settings,figure_settings:figure}).then(data=>{
   if(!cancelled)setResponse({key,data})
  }).catch(error=>{if(!cancelled)setResponse({key,error:String(error)})})},250)
  return()=>{cancelled=true;clearTimeout(timer)}
 },[key,valid])
 const lastGood=useRef<PlotPreview|null>(null)
 const current=response?.key===key?response:null
 if(current?.data)lastGood.current=current.data
 async function confirmExport(){
  if(!current?.data||!valid||exporting)return
  setExporting(true);setExportError('')
  try{await onExport(current.data.settings,current.data.figure_settings??figure)}catch(e){setExportError(String(e))}finally{setExporting(false)}
 }
 return <dialog ref={dialog} className="export-dialog" aria-labelledby="export-title" onCancel={e=>{if(exporting)e.preventDefault();else onClose()}}>
 <div className="card-heading"><div><h2 id="export-title">导出预览</h2><p className="hint">查看实际生成的图表，确认字号与尺寸。</p></div><button className="btn secondary" disabled={exporting} onClick={onClose}>关闭预览</button></div>
 <fieldset className="export-settings" disabled={exporting}>{([['panel_width','每面板宽度 in',3,8],['height','图表高度 in',3,8],['font_size','图表字号 pt',8,24],['dpi','图表 DPI',72,300]] as const).map(([k,label,min,max])=><label key={k}>{label}<input type="number" min={min} max={max} step={k==='panel_width'||k==='height'?.5:1} value={settings[k]} onChange={e=>{setExportError('');setSettings(s=>({...s,[k]:Number(e.target.value)}))}}/></label>)}</fieldset>
 <details className="figure-details"><summary>图形样式、配色与标记</summary><FigureEditor project={project} result={result} figure={figure} settings={settings} data={current?.data?.figure_data??lastGood.current?.figure_data??initialData} onChange={setFigure} onDimensions={setSettings} disabled={exporting} dimensionsControls={false}/></details>
 <div className="export-canvas">{!valid?<p role="alert">尺寸须为 3–8 in，字号 8–24 pt，DPI 72–300。</p>:current?.error?<p role="alert">{current.error}</p>:current?.data?<img src={current.data.png} alt="实际导出图表"/>:<p role="status">正在生成图表预览…</p>}</div>
 {current?.data&&valid&&<p data-testid="export-dimensions">PNG：{current.data.width} × {current.data.height} px · 同时导出 SVG 矢量图</p>}
 <p className="hint">整图宽度随分析面板数量增加。预览缩放仅影响屏幕显示。</p>
 <div className="export-contents"><p><strong>results.xlsx</strong> · 泳道结果、原始测量、内参归一化、样本与来源、汇总/统计、图表。</p><p><strong>plot.png / plot.svg</strong> · 当前图表；另附 CSV、原图、标注与审计记录。</p><p className="hint">Excel 数值可继续计算；未检出为空值，状态列保留原因。</p></div>
 {exportError&&<p role="alert">{exportError}</p>}
 <div className="export-actions"><button className="btn primary" disabled={!valid||!current?.data||exporting} onClick={confirmExport}>{exporting?'正在导出…':'选择目录并导出'}</button></div>
 </dialog>
}
