import {useEffect,useRef,useState} from 'react'
import type {AnalysisResult,Project} from './types'
import {activityStorageKey,newActivity,parseActivity,recordAnalysis,type ResearchActivity} from './research-activity'

export default function useResearchActivity(project:Project|null,result:AnalysisResult|null){
 const [initial]=useState(()=>{
  try{const raw=localStorage.getItem(activityStorageKey);return {activity:raw?parseActivity(raw):newActivity(),error:''}}
  catch{return {activity:null,error:'本机研究足迹暂不可用，已有记录不会被覆盖。'}}
 })
 const [activity,setActivity]=useState<ResearchActivity|null>(initial.activity)
 const [error,setError]=useState(initial.error)
 const current=useRef(activity)
 useEffect(()=>{
  if(!current.current)return
  const next=project&&result?recordAnalysis(current.current,project,result):current.current
  current.current=next;setActivity(next)
  try{localStorage.setItem(activityStorageKey,JSON.stringify(next));setError('')}
  catch{setError('研究足迹无法保存；当前新增记录仅在本次运行中保留。')}
 },[project,result])
 return {activity,error}
}
