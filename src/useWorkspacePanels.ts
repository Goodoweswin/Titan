import {useEffect,useRef,useState} from 'react'

export const inspectorSelector=[
 '.workspace-grid>.inspector','.lane-workspace>.lane-task','.wb-columns>.wb-inspector',
 '.if-analysis-layout>.if-settings','.if-figure-layout>.if-settings',
 '.stats-graph-layout>.stats-inspector','.figure-workbench.with-inspector>.figure-inspector',
].join(',')

function read(key:string){try{return localStorage.getItem(key)==='true'}catch{return false}}
export default function useWorkspacePanels(){
 const root=useRef<HTMLDivElement>(null)
 const [leftCollapsed,setLeftCollapsed]=useState(()=>read('titan-left-collapsed'))
 const [rightCollapsed,setRightCollapsed]=useState(()=>read('titan-right-collapsed'))
 const [hasInspector,setHasInspector]=useState(false)
 useEffect(()=>{try{localStorage.setItem('titan-left-collapsed',String(leftCollapsed))}catch{}},[leftCollapsed])
 useEffect(()=>{try{localStorage.setItem('titan-right-collapsed',String(rightCollapsed))}catch{}},[rightCollapsed])
 useEffect(()=>{
  const element=root.current
  if(!element)return
  const update=()=>setHasInspector(Array.from(element.querySelectorAll(inspectorSelector)).some(panel=>!panel.closest('[hidden]')))
  update()
  const observer=new MutationObserver(update)
  observer.observe(element,{childList:true,subtree:true,attributes:true,attributeFilter:['hidden','class']})
  return()=>observer.disconnect()
 },[])
 return {root,leftCollapsed,rightCollapsed,hasInspector,
  toggleLeft:()=>setLeftCollapsed(value=>!value),toggleRight:()=>setRightCollapsed(value=>!value)}
}
