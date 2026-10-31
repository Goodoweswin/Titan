import {useEffect,useState} from 'react'
import {callEngine} from './bridge'
import type {AnalysisResult,PlotPreview,Project} from './types'

export default function ResultVisualization({project,result}:{project:Project;result:AnalysisResult}){
 const [response,setResponse]=useState<{key:string;data?:PlotPreview;error?:string}|null>(null)
 const [retry,setRetry]=useState(0)
 const key=JSON.stringify([project.id,project.revision,result.input_revision,retry])
 useEffect(()=>{
  let cancelled=false
  const timer=setTimeout(()=>callEngine<PlotPreview>('export_preview',{project,result}).then(data=>{if(!cancelled)setResponse({key,data})}).catch(error=>{if(!cancelled)setResponse({key,error:String(error)})}),150)
  return()=>{cancelled=true;clearTimeout(timer)}
 },[key])
 const current=response?.key===key?response:null
 const panels=new Set((result.biological.length?result.biological.map(r=>[r.analyte,r.analysis_block]):(result.lane_results??[]).map(r=>[r.analyte,r.membrane_id])).map(v=>JSON.stringify(v))).size
 return <section className="result-visualization" aria-label="结果可视化"><div className="card-heading"><h3>结果图表</h3><span className="muted">{result.biological.length?'生物学单位 · 均值与 SD':'逐泳道比值 · ND 未检出 · NA 不可计算'}</span></div>
 <div className="result-figure">{current?.data?<img src={current.data.png} alt="当前结果图表" style={{width:Math.max(520,panels*400)}}/>:current?.error?<div role="alert"><p>{current.error}</p><button className="btn secondary" onClick={()=>setRetry(v=>v+1)}>重新生成图表</button></div>:<p role="status">正在生成当前图表…</p>}</div><p className="hint">{result.biological.length?'每个点代表按确认设计汇总的生物学单位；同一蛋白与分析块分别展示。':'每个点对应一个泳道；没有有效数值的位置保留，不用 0 替代。'}导出时可调整尺寸和字号，获得 Excel、PNG 和 SVG。</p>
 </section>
}
