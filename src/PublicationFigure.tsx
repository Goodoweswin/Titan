import {useEffect,useRef,useState} from 'react'
import type {AnalysisResult,FigureDocumentMetadata,FigureSettings,PlotPreview,PlotSettings,Project} from './types'
import {defaultFigureSettings,defaultPlotSettings} from './figure-settings'
import FigureEditor from './FigureEditor'
import useFigurePreview from './useFigurePreview'
export interface ArchiveFigureRequest{project:Project;result:AnalysisResult;figure_settings:FigureSettings;settings:PlotSettings;name:string;figure_id?:string;expected_version?:string;update_source?:boolean;default_key?:string;silent?:boolean;frozen?:boolean}
export interface LiveFigurePreview{project:Project;result:AnalysisResult;ready:boolean;data?:PlotPreview;dirty:boolean;figure_settings:FigureSettings;settings:PlotSettings}
interface Props{project:Project;result:AnalysisResult;document?:FigureDocumentMetadata;onApply?:(f:FigureSettings,s:PlotSettings)=>void;onArchive?:(request:ArchiveFigureRequest)=>Promise<FigureDocumentMetadata|undefined>;onPreview?:(value:LiveFigurePreview|null)=>void;onShowDesign?:()=>void;frozen?:boolean}
export default function PublicationFigure({project,result,document,onApply,onArchive,onPreview,onShowDesign,frozen=false}:Props){
 const [figure,setFigure]=useState<FigureSettings>(()=>structuredClone(project.figure_settings??defaultFigureSettings())),[settings,setSettings]=useState<PlotSettings>(()=>({...defaultPlotSettings,...project.plot_settings})),[name,setName]=useState(document?.name??'结果图表'),[saving,setSaving]=useState(false),[message,setMessage]=useState('')
 const baseline=useRef({figure:structuredClone(figure),settings:{...settings},name})
 const dirty=JSON.stringify([figure,settings,name])!==JSON.stringify([baseline.current.figure,baseline.current.settings,baseline.current.name])
 const {current,error,valid}=useFigurePreview(project,result,settings,figure),lastGood=useRef<PlotPreview|null>(null),auto=useRef('')
 if(current?.data)lastGood.current=current.data
 const data=current?.data??lastGood.current
 const defaultKey=figure.panel_key||'all'
 const historicalVersion=!!document&&document.selected_version!==document.current_version
 const stale=!!document&&!!result.source_signature&&document.source_signature!==result.source_signature
 useEffect(()=>{onPreview?.({project,result,ready:!!current?.data&&valid,data:current?.data??lastGood.current??undefined,dirty,figure_settings:figure,settings});return()=>onPreview?.(null)},[project.id,project.project_path,project.revision,current?.data,valid,dirty,JSON.stringify(figure),JSON.stringify(settings)])
 useEffect(()=>{if(!frozen&&document&&name==='结果图表'){baseline.current.name=document.name;setName(document.name)}},[document?.id])
 useEffect(()=>{
  if(frozen||document||!onArchive||!current?.data||project.read_only||project.saved_revision!==project.revision||!project.project_path)return
  const key=JSON.stringify([project.project_path,defaultKey,result.source_signature])
  if(auto.current===key)return;auto.current=key
  const input=current.data,analyte=input.figure_data?.panels.length===1?input.figure_data.panels[0].analyte:'全部蛋白'
  onArchive({project,result,figure_settings:input.figure_settings??figure,settings:input.settings,name:analyte+' · 柱图',default_key:defaultKey,silent:true}).catch(()=>{auto.current=''})
 },[current?.data,project.saved_revision,document?.id])
 async function archive(asNew=false){
  if(!current?.data||!onArchive)return;setSaving(true);setMessage('')
  try{const saved=await onArchive({project,result,figure_settings:current.data.figure_settings??figure,settings:current.data.settings,name,figure_id:!asNew?document?.id:undefined,expected_version:!asNew?document?.current_version:undefined,update_source:!asNew&&stale,frozen,default_key:!asNew&&!document?defaultKey:undefined});if(saved){const canonical=current.data.figure_settings??figure;baseline.current={figure:structuredClone(canonical),settings:{...current.data.settings},name};setFigure(canonical);setMessage('图表已保存在左栏；源数据与样式可继续追溯。')}}catch(e){setMessage(String(e))}finally{setSaving(false)}
 }
 return <section className="result-visualization" aria-label="结果可视化"><div className="card-heading"><h3>{frozen?'图表文档':'结果图表'}</h3><span className="muted">{data?.figure_data?.unit==='lane'?'逐泳道比值 · ND 未检出 · NA 不可计算':'独立生物学单位 · 均值、原始点与所选误差线'}</span></div>
 {frozen&&<p className="figure-source-note">冻结源版本 {result.input_revision}。调整样式保留这份数据；更换数据源需明确更新。</p>}
 <div className="result-figure">{error?<p role="alert">{error}</p>:current?.data?<img src={current.data.png} alt="当前结果图表" style={{width:Math.max(520,(current.data.figure_data?.panels.length??1)*400)}}/>:<p role="status">正在生成当前图表…</p>}</div>
 {(data?.figure_data?.notes??[]).map((note,i)=><p className="hint" key={i}>{note}</p>)}{data?.figure_data?.panels.flatMap(p=>p.warnings).map((warning,i)=><p className="error-text" key={i}>{warning}</p>)}
 {dirty&&<p className="hint">当前样式为未保存草稿。<button className="text-btn" onClick={()=>{setFigure(structuredClone(baseline.current.figure));setSettings({...baseline.current.settings});setName(baseline.current.name)}}>还原未保存样式</button></p>}
 <details className="figure-details"><summary>图形设置</summary><FigureEditor project={project} result={result} figure={figure} settings={settings} data={data?.figure_data} onChange={setFigure} onDimensions={setSettings} disabled={saving}/><div className="figure-actions"><button className="btn secondary" onClick={()=>{setFigure(defaultFigureSettings());setSettings(defaultPlotSettings)}} disabled={saving}>恢复黄灰参考风格</button>{onApply&&<button className="btn secondary" disabled={!current?.data||saving||project.read_only} onClick={()=>{const f=current!.data!.figure_settings??figure,s=current!.data!.settings;baseline.current.figure=structuredClone(f);baseline.current.settings={...s};setFigure(f);onApply(f,s)}}>应用样式到项目</button>}{onShowDesign&&data?.figure_data?.unit==='lane'&&<button className="text-btn" onClick={onShowDesign}>核对分组与独立重复</button>}</div></details>
 {onArchive&&<div className="figure-save"><label>图表名称<input aria-label="图表名称" maxLength={120} value={name} onChange={e=>setName(e.target.value)} disabled={project.read_only||saving}/></label><button className="btn secondary" disabled={!current?.data||saving||project.read_only||historicalVersion} onClick={()=>archive()}>{saving?'正在保存…':stale?'用当前结果更新图表':document?'保存当前图表':'保存图表'}</button>{document&&<button className="text-btn" disabled={!current?.data||saving||project.read_only} onClick={()=>archive(true)}>另存新图</button>}</div>}
 {historicalVersion&&<p className="hint">正在查看历史版本；修改后可另存新图，保留当前图的数据源。</p>}
 {message&&<p role="status" className="hint">{message}</p>}
 </section>
}
