import {useEffect,useRef,useState} from 'react'
import {callEngine} from './bridge'
import type {Project,ROI,SignalProfileData} from './types'

export default function SignalProfile({project,roi}:{project:Project;roi?:ROI}){
 const container=useRef<HTMLElement>(null)
 const [chartWidth,setChartWidth]=useState(800)
 useEffect(()=>{const node=container.current;if(!node)return;const observer=new ResizeObserver(()=>setChartWidth(Math.max(220,node.clientWidth-32)));observer.observe(node);return()=>observer.disconnect()},[])
 const [expanded,setExpanded]=useState(true),[corrected,setCorrected]=useState(false)
 const [response,setResponse]=useState<{key:string;data?:SignalProfileData;error?:string}|null>(null)
 const key=JSON.stringify([project.id,project.revision,roi?.id])
 useEffect(()=>{
  if(!expanded||!roi)return
  let cancelled=false
  const timer=setTimeout(()=>{callEngine<SignalProfileData>('profile',{project,roi_id:roi.id}).then(data=>{
   if(!cancelled)setResponse({key,data})
  }).catch(error=>{if(!cancelled)setResponse({key,error:String(error)})})},180)
  return()=>{cancelled=true;clearTimeout(timer)}
 },[key,expanded])
 const current=response?.key===key?response:null,data=current?.data
 const offset=corrected&&data?.background_mean!=null?data.background_mean:0
 const samples=data?.samples??[],baseline=(data?.background_mean??0)-offset,low=Math.min(0,baseline,...samples.map(s=>s.min-offset)),high=Math.max(1,baseline,...samples.map(s=>s.max-offset))
 const x=(y:number)=>68+y/Math.max(1,(data?.height??1)-1)*(chartWidth-100)
 const y=(value:number)=>170-(value-offset-low)/(high-low)*142
 const line=samples.map(s=>`${x(s.y)},${y(s.mean)}`).join(' ')
 const format=(n:number)=>n.toLocaleString(undefined,{maximumFractionDigits:2})
 return <section ref={container} className="card signal-profile"><button className="profile-toggle" aria-expanded={expanded} onClick={()=>setExpanded(v=>!v)}><strong>强度与背景</strong><span>{roi?`${roi.lane_id} · ${roi.analyte}`:'原始像素检查'} · {expanded?'收起':'展开'}</span></button>{expanded&&<>
 {!roi?<p className="hint">选择一个条带，查看原始像素强度。</p>:current?.error?<p role="alert">{current.error}</p>:!data?<p role="status">正在读取原始像素…</p>:<>
 <div className="profile-controls"><span>横轴：原图 y 坐标 · 纵轴：泳道宽度内平均信号</span><label className="checkbox-label"><input type="checkbox" checked={corrected&&data.background_mean!=null} disabled={data.background_mean==null} onChange={e=>setCorrected(e.target.checked)}/>显示扣背景曲线</label></div>
 <svg className="profile-chart" viewBox={`0 0 ${chartWidth} 210}`} role="img" aria-label="泳道强度曲线">
 <rect x={x(data.rect[1])} y="20" width={Math.max(1,x(Math.min(data.height-1,data.rect[3]))-x(data.rect[1]))} height="150" fill="#e6edff"/>
 {[low,(low+high)/2,high].map((v,i)=><g key={i}><line x1="68" x2={chartWidth-32} y1={y(v+offset)} y2={y(v+offset)} stroke="#dce3ee"/><text x="62" y={y(v+offset)+4} textAnchor="end">{v.toPrecision(3)}</text></g>)}
 {samples.some(s=>s.min!==s.max)&&<path d={`M ${samples.map(s=>`${x(s.y)},${y(s.max)}`).join(' L ')} L ${[...samples].reverse().map(s=>`${x(s.y)},${y(s.min)}`).join(' L ')} Z`} fill="#406de433"/>}
 <polyline points={line} fill="none" stroke="#406de4" strokeWidth="2"/>
 {data.background_mean!=null&&<line x1="68" x2={chartWidth-32} y1={y(data.background_mean)} y2={y(data.background_mean)} stroke="#aa6b25" strokeWidth="1.5" strokeDasharray="6 4"/>}
 {[0,Math.floor((data.height-1)/2),data.height-1].map(v=><text key={v} x={x(v)} y="196" textAnchor="middle">{v} px</text>)}
 </svg>
 <div className="profile-legend"><span>蓝色：{offset?'扣背景后信号':'按极性转换的信号'}</span><span>阴影：条带范围 [{data.rect[1]}, {data.rect[3]})</span><span>虚线：{offset?'零基线':'局部背景均值'}</span></div>
 {data.measurement?<div className="profile-values" data-testid="profile-measurement"><span>原始像素总和<strong>{format(data.measurement.raw_sum)}</strong></span><span>背景均值<strong>{format(data.background_mean!)}</strong></span><span>扣背景积分<strong>{format(data.measurement.corrected_sum)}</strong></span></div>:<p role="status">{data.warning}</p>}
 <p className="hint">使用原始位深；积分保留负值。曲线按条带宽度取平均，背景来自所画背景框的并集。此处仅供检查，正式结果请运行定量。</p>
 </>}
 </>}</section>
}
