import {useEffect,useState} from 'react'
import {callEngine} from './bridge'
import type {AnalysisResult,FigureSettings,PlotPreview,PlotSettings,Project} from './types'
export default function useFigurePreview(project:Project,result:AnalysisResult,settings:PlotSettings,figure:FigureSettings){
 const [response,setResponse]=useState<{key:string;data?:PlotPreview;error?:string}|null>(null)
 const key=JSON.stringify([project.id,project.project_path,project.revision,result.input_revision,settings,figure])
 const finite=Object.values(settings).every(v=>typeof v==='number'&&Number.isFinite(v))&&Object.values(figure).every(v=>typeof v!=='number'||Number.isFinite(v))
 const valid=finite&&Object.entries(settings).every(([k,v])=>{const [lo,hi]=k==='dpi'?[72,300]:k==='font_size'?[8,24]:[3,8];return v>=lo&&v<=hi})
 useEffect(()=>{
  if(!valid)return
  let cancelled=false
  const timer=setTimeout(()=>callEngine<PlotPreview>('export_preview',{project,result,settings,figure_settings:figure}).then(data=>{if(!cancelled)setResponse({key,data})}).catch(e=>{if(!cancelled)setResponse({key,error:String(e)})}),220)
  return()=>{cancelled=true;clearTimeout(timer)}
 },[key,valid])
 return {key,valid,current:valid&&response?.key===key?response:null,error:!valid?'请填写有效图形尺寸、字号和数值参数。':response?.key===key?response.error:undefined}
}
