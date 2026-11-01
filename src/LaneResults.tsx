import type {Project,AnalysisResult} from './types'
import SampleEditor from './SampleEditor'
import {useRef} from 'react'
import MultiGroupEditor from './MultiGroupEditor'
import PublicationFigure from './PublicationFigure'
import type {ArchiveFigureRequest,LiveFigurePreview} from './PublicationFigure'
import type {FigureDocumentMetadata} from './types'
import {flagLabel,flagSource} from './workflow'
export default function LaneResults({project,result,onEdit,onReview,onLocate,onAnalyze,onExport,onArchive,onPreview,figureDocument}:{project:Project;result:AnalysisResult|null;onEdit:(f:(p:Project)=>void)=>void;onReview:()=>void;onLocate:(id:string)=>void;onAnalyze:()=>void;onExport:()=>void;onArchive?:(r:ArchiveFigureRequest)=>Promise<FigureDocumentMetadata|undefined>;onPreview?:(v:LiveFigurePreview|null)=>void;figureDocument?:FigureDocumentMetadata}){
 const design=useRef<HTMLDetailsElement>(null)
 function showDesign(){if(design.current){design.current.open=true;design.current.scrollIntoView({behavior:'smooth',block:'start'})}}
 const current=result?.input_revision===project.revision?result:null
 const format=(n:number|null)=>n==null?'—':n.toLocaleString(undefined,{maximumFractionDigits:4})
 const labels:Record<string,string>={valid:'已计算',not_detected:'未检出',excluded:'已排除',pending:'待确认',blocked:'需处理'}
 return <div className="lane-results"><div className="section-title"><div><h2>泳道定量结果</h2><p>每个目标使用同一泳道的内参净积分归一化；空值保留原因。</p></div><button className="btn primary" disabled={!current||!project.band_sets.some(g=>g.role==='target')} onClick={onExport}>导出 Excel 与图表</button></div>{!current?<p role="status">{project.band_sets.some(g=>g.role==='target')?'正在更新当前结果…':'确认内参并添加目标后，这里显示归一化结果。'}</p>:<><div className="table-wrap"><table aria-label="泳道定量结果"><thead><tr><th>泳道 / 样本</th><th>目标</th><th>目标净积分</th><th>内参净积分</th><th>目标 / 内参</th><th>状态</th></tr></thead><tbody>{current.lane_results?.map((r,i)=><tr key={`${r.band_set_id}-${r.lane_id}-${i}`}><td>{r.lane_id} / {project.samples.find(s=>s.id===r.sample_id)?.name||r.sample_id}<small>{r.membrane_id}</small></td><td>{r.analyte}</td><td>{format(r.corrected_sum)}</td><td>{format(r.reference_net)}</td><td><strong>{format(r.normalized)}</strong></td><td><span title={r.flags.map(flagLabel).join('；')}>{labels[r.status]??r.status}</span>{r.status==='blocked'&&r.target_roi_id&&<><button className="text-btn" onClick={()=>onLocate(flagSource(project,r.target_roi_id!,r.flags.find(f=>f.startsWith('reference:'))??r.flags[0]??'').roiId)}>查看原图</button><small>{r.flags.map(flagLabel).join('；')}</small></>}</td></tr>)}</tbody></table></div>{project.band_sets.some(g=>g.role==='target')&&<PublicationFigure project={project} result={current} document={figureDocument} onApply={(f,s)=>onEdit(p=>{p.figure_settings=f;p.plot_settings=s})} onArchive={onArchive} onPreview={onPreview} onShowDesign={showDesign}/>} {current.lane_results?.some(r=>r.flags.length>0)&&<details className="lane-advanced"><summary>采集与测量提示</summary><p className="hint">{Array.from(new Set(current.lane_results.flatMap(r=>r.flags.map(flagLabel)))).join('；')}。采集信息未完整确认时，比值用于探索性分析。</p></details>}</>}
 <details className="lane-advanced"><summary>统计分析与方法说明</summary><MultiGroupEditor project={project} result={current} onEdit={onEdit} onShowDesign={showDesign}/></details>
 <details className="lane-advanced" ref={design}><summary>样本信息、分组与统计</summary><p className="hint">核对独立生物学单位、技术重复和组别后再确认。泳道数不会自动作为生物学重复数。</p><SampleEditor project={project} onEdit={onEdit} onReview={onReview}/></details>
 </div>
}
