import {useState} from 'react'
import type {KeyboardEvent} from 'react'
import {ArrowDownToLine,ArrowRight,CheckCircle2,Table2} from 'lucide-react'
import type {Project,AnalysisResult,FigureDocumentMetadata} from './types'
import SampleEditor from './SampleEditor'
import ComparisonEditor from './ComparisonEditor'
import MultiGroupEditor from './MultiGroupEditor'
import PublicationFigure from './PublicationFigure'
import type {ArchiveFigureRequest,LiveFigurePreview} from './PublicationFigure'
import {flagLabel,flagSource} from './workflow'

const views=[['quantitative','定量结果'],['samples','样本设置'],['figures','统计与图表']] as const
type View=typeof views[number][0]
const format=(n:number|null)=>n==null?'—':n.toLocaleString(undefined,{maximumFractionDigits:4})
const labels:Record<string,string>={valid:'已计算',not_detected:'未检出',excluded:'已排除',pending:'待确认',blocked:'需处理'}

export default function LaneResults({project,result,onEdit,onReview,onLocate,onAnalyze,onExport,onArchive,onPreview,figureDocument}:{project:Project;result:AnalysisResult|null;onEdit:(f:(p:Project)=>void)=>void;onReview:()=>void;onLocate:(id:string)=>void;onAnalyze:()=>void;onExport:()=>void;onArchive?:(r:ArchiveFigureRequest)=>Promise<FigureDocumentMetadata|undefined>;onPreview?:(v:LiveFigurePreview|null)=>void;figureDocument?:FigureDocumentMetadata}){
 const [view,setView]=useState<View>('quantitative')
 const current=result?.input_revision===project.revision?result:null
 const hasTargets=project.band_sets.some(g=>g.role==='target')
 function activateView(next:View){setView(next);document.getElementById(`result-tab-${next}`)?.focus()}
 function showDesign(){activateView('samples')}
 function switchWithKeyboard(event:KeyboardEvent<HTMLButtonElement>,index:number){
  let next:number
  if(event.key==='ArrowRight')next=(index+1)%views.length
  else if(event.key==='ArrowLeft')next=(index+views.length-1)%views.length
  else if(event.key==='Home')next=0
  else if(event.key==='End')next=views.length-1
  else return
  event.preventDefault();setView(views[next][0]);document.getElementById(`result-tab-${views[next][0]}`)?.focus()
 }
 return <div className="lane-results results-workspace">
  <div className="results-heading"><h2>结果分析</h2><button className="btn primary" disabled={!current||!hasTargets} onClick={onExport}><ArrowDownToLine size={16}/>导出 Excel 与图表</button></div>
  <div className="results-tabs" role="tablist" aria-label="结果分析视图">{views.map(([id,label],i)=><button type="button" role="tab" id={`result-tab-${id}`} aria-controls={`result-panel-${id}`} aria-selected={view===id} tabIndex={view===id?0:-1} key={id} onClick={()=>setView(id)} onKeyDown={e=>switchWithKeyboard(e,i)}>{label}</button>)}</div>
  <section className="result-panel" id="result-panel-quantitative" role="tabpanel" aria-labelledby="result-tab-quantitative" hidden={view!=='quantitative'}>
   <div className="results-section-heading"><div><h3>泳道定量结果</h3><p>目标净积分 ÷ 同一泳道的内参净积分</p></div>{current&&<span className="results-record-count">{current.lane_results?.length??0} 条记录</span>}</div>
   {!current?<div className="results-empty"><Table2 size={30} strokeWidth={1.3}/><h3>{hasTargets?'正在更新当前结果…':'还没有定量结果'}</h3><p>{hasTargets?'图像与样本更新后，将重新计算当前版本。':'确认内参并添加目标后，在这里查看归一化结果。'}</p>{hasTargets&&<button className="text-btn" onClick={onAnalyze}>重新计算</button>}</div>:<>
    <div className="results-table-scroll table-wrap"><table aria-label="泳道定量结果"><thead><tr><th scope="col">泳道 / 样本</th><th scope="col">目标</th><th scope="col" className="numeric">目标净积分</th><th scope="col" className="numeric">内参净积分</th><th scope="col" className="numeric">目标 / 内参</th><th scope="col">状态</th></tr></thead><tbody>{current.lane_results?.map((r,i)=><tr key={`${r.band_set_id}-${r.lane_id}-${i}`}><td><span className="lane-identity">{r.lane_id} / {project.samples.find(s=>s.id===r.sample_id)?.name||r.sample_id}</span><small>{r.membrane_id}</small></td><td>{r.analyte}</td><td className="numeric">{format(r.corrected_sum)}</td><td className="numeric">{format(r.reference_net)}</td><td className="numeric result-value">{format(r.normalized)}</td><td><span className={`result-status ${r.status}`} title={r.flags.map(flagLabel).join('；')}>{r.status==='valid'&&<CheckCircle2 size={13}/>} {labels[r.status]??r.status}</span>{r.status==='blocked'&&r.target_roi_id&&<><button className="text-btn" onClick={()=>onLocate(flagSource(project,r.target_roi_id!,r.flags.find(f=>f.startsWith('reference:'))??r.flags[0]??'').roiId)}>查看原图</button><small>{r.flags.map(flagLabel).join('；')}</small></>}</td></tr>)}</tbody></table></div>
    <div className="results-table-footer"><span>未检出与不可计算的记录保留为空值</span><button className="text-btn" onClick={()=>activateView('figures')}>查看统计与图表<ArrowRight size={14}/></button></div>
    {current.lane_results?.some(r=>r.flags.length>0)&&<details className="results-disclosure"><summary>采集与测量提示</summary><p className="hint">{Array.from(new Set(current.lane_results.flatMap(r=>r.flags.map(flagLabel)))).join('；')}。采集信息未完整确认时，比值用于探索性分析。</p></details>}
   </>}
  </section>
  <section className="result-panel" id="result-panel-samples" role="tabpanel" aria-labelledby="result-tab-samples" hidden={view!=='samples'}><SampleEditor project={project} onEdit={onEdit} onReview={onReview} showComparisons={false}/></section>
  <section className="result-panel" id="result-panel-figures" role="tabpanel" aria-labelledby="result-tab-figures" hidden={view!=='figures'}>
   {current&&hasTargets?<PublicationFigure inspector project={project} result={current} document={figureDocument} onApply={(f,s)=>onEdit(p=>{p.figure_settings=f;p.plot_settings=s})} onArchive={onArchive} onPreview={onPreview} onShowDesign={showDesign}/>:<p className="hint" role="status">{hasTargets?'正在更新当前图表…':'添加目标并完成定量后显示图表。'}</p>}
   <details className="results-disclosure statistics-disclosure" open><summary>统计分析与方法说明</summary><MultiGroupEditor project={project} result={current} onEdit={onEdit} onShowDesign={showDesign}/><ComparisonEditor project={project} onEdit={onEdit}/></details>
  </section>
 </div>
}
