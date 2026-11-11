import {useEffect,useRef,useState} from 'react'
import {createHistory,recordLocation,historyTarget,moveHistory,sameLocation,type WorkspaceLocation} from './workspace-navigation'

export default function useWorkspaceHistory(location:WorkspaceLocation|null,blocked:boolean,restore:(location:WorkspaceLocation)=>Promise<boolean>){
 const [history,setHistory]=useState(()=>createHistory({kind:'home'}))
 const current=useRef(history),flight=useRef(false),restoreRef=useRef(restore)
 const destination=useRef<WorkspaceLocation|null>(null)
 const [restoring,setRestoring]=useState(false)
 restoreRef.current=restore
 const serialized=JSON.stringify(location)
 useEffect(()=>{
  if(!location||blocked||flight.current)return
  if(destination.current){
   const requested=destination.current
   const resolved=requested.kind==='analysis'&&location.kind==='analysis'&&!requested.resourceId?{...requested,resourceId:location.resourceId}:requested
   if(!sameLocation(location,resolved))return
   destination.current=null;setRestoring(false)
   // An initially empty analysis may now have its first image/field. Resolve
   // that default against current data without creating a new history branch.
   const entries=[...current.current.entries];entries[current.current.index]=location
   const next={...current.current,entries};current.current=next;setHistory(next)
   return
  }else if(restoring)return
  // Module view reports can arrive one render after a guarded project switch.
  // Record the settled destination, not the previous module's temporary report.
  const timer=setTimeout(()=>{
   if(flight.current)return
   const next=recordLocation(current.current,location)
   current.current=next;setHistory(next)
  },0)
  return()=>clearTimeout(timer)
 },[serialized,blocked,restoring,history.index])
 async function go(direction:-1|1){
  if(blocked||flight.current||destination.current||restoring)return
  const target=historyTarget(current.current,direction)
  if(!target)return
  flight.current=true;destination.current=target.location;setRestoring(true)
  let completed=false
  try{
   if(await restoreRef.current(target.location)){
    completed=true
    const next=moveHistory(current.current,target.index)
    current.current=next;setHistory(next)
   }
  }finally{flight.current=false;if(!completed){destination.current=null;setRestoring(false)}}
 }
 const goRef=useRef(go);goRef.current=go
 useEffect(()=>{
  function keyboard(event:KeyboardEvent){
   if(event.defaultPrevented||event.shiftKey||event.ctrlKey||event.target instanceof Element&&event.target.closest('input,textarea,select,[contenteditable=true]'))return
   if(document.querySelector('dialog[open],[aria-modal=true],.modal-backdrop'))return
   const back=event.altKey&&event.key==='ArrowLeft'||event.metaKey&&event.key==='['
   const forward=event.altKey&&event.key==='ArrowRight'||event.metaKey&&event.key===']'
   if(back||forward){event.preventDefault();void goRef.current(back?-1:1)}
  }
  window.addEventListener('keydown',keyboard)
  return()=>window.removeEventListener('keydown',keyboard)
 },[])
 return {canBack:history.index>0,canForward:history.index<history.entries.length-1,restoring,go}
}
