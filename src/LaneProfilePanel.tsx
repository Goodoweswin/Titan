import {useEffect,useState} from 'react'
import {callEngine} from './bridge'
import type {Project,Rect,LaneProfileData} from './types'
export default function LaneProfilePanel({project,layoutId,laneId,window,peak}:{project:Project;layoutId:string;laneId:string;window:Rect;peak?:Rect}){
 const [response,setResponse]=useState<{key:string;data?:LaneProfileData;error?:string}|null>(null)
 const key=JSON.stringify([project.id,project.revision,project.lane_layouts.find(l=>l.id===layoutId),laneId,window])
 useEffect(()=>{let cancelled=false;const timer=setTimeout(()=>callEngine<LaneProfileData>('lane_profile',{project,layout_id:layoutId,lane_id:laneId,window}).then(data=>{if(!cancelled)setResponse({key,data})}).catch(e=>{if(!cancelled)setResponse({key,error:String(e)})}),150);return()=>{cancelled=true;clearTimeout(timer)}},[key])
 const data=response?.key===key?response.data:undefined,error=response?.key===key?response.error:undefined
 const max=Math.max(1,...(data?.samples.map(s=>s.max)??[])),x=(y:number)=>45+(y-window[1])/Math.max(1,window[3]-window[1])*600,y=(v:number)=>155-v/max*130
 return <section className="lane-profile"><h3>{laneId} · 灰度曲线</h3>{error?<p role="alert">{error}</p>:!data?<p role="status">正在读取曲线…</p>:<svg viewBox="0 0 680 190" aria-label="逐泳道积分曲线" role="img"><line x1="45" y1="155" x2="645" y2="155" stroke="#a8b4c8"/>{peak&&<rect x={x(peak[1])} y="15" width={Math.max(1,x(peak[3])-x(peak[1]))} height="140" fill="#3ab98e20"/>}<polyline points={data.samples.map(s=>`${x(s.y)},${y(s.sum)}`).join(' ')} fill="none" stroke="#527de0" strokeWidth="2"/><text x="45" y="180">{window[1]} px</text><text x="590" y="180">{window[3]} px</text></svg>}<p className="hint">{project.images.find(a=>a.id===project.lane_layouts.find(l=>l.id===layoutId)?.image_id)?.rotation_degrees?'横轴为校正视图纵向位置；曲线供识别参考，定量积分使用对应的原始像素。':'横轴为原图纵向位置，纵轴为该泳道每行的像素总和。积分使用完整原始像素。'}</p></section>
}
