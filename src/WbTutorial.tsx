import {useEffect,useRef,useState} from 'react'
import {ChevronLeft,ChevronRight,LocateFixed,RotateCcw,X} from 'lucide-react'
import {advanceTutorial,createTutorial,loadTutorial,saveTutorial,tutorialStepState,tutorialSteps,type TutorialContext,type TutorialRun,type TutorialView} from './wb-tutorial'

function useHighlight(target:string,active:boolean){
 const [box,setBox]=useState<{left:number;top:number;width:number;height:number}|null>(null)
 useEffect(()=>{
  if(!active){setBox(null);return}
  let frame=0,observed:Element|null=null
  const resize=new ResizeObserver(schedule)
  function update(){
   frame=0
   const found=Array.from(document.querySelectorAll(`[data-wb-guide="${target}"]`)).find(e=>e.getClientRects().length&&!(e as HTMLElement).closest('[hidden]'))??null
   if(found!==observed){resize.disconnect();if(found)resize.observe(found);observed=found}
   const r=found?.getBoundingClientRect()
   const left=r?Math.max(2,r.left-3):0,top=r?Math.max(2,r.top-3):0
   setBox(r&&r.bottom>0&&r.top<innerHeight&&r.right>0&&r.left<innerWidth?{left,top,width:Math.max(0,Math.min(innerWidth-2,r.right+3)-left),height:Math.max(0,Math.min(innerHeight-2,r.bottom+3)-top)}:null)
  }
  function schedule(){if(!frame)frame=requestAnimationFrame(update)}
  const changes=new MutationObserver(schedule)
  changes.observe(document.querySelector('.titan-workspace')??document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['hidden','class','disabled','aria-selected']})
  addEventListener('resize',schedule);addEventListener('scroll',schedule,true);schedule()
  return()=>{cancelAnimationFrame(frame);resize.disconnect();changes.disconnect();removeEventListener('resize',schedule);removeEventListener('scroll',schedule,true)}
 },[target,active])
 return box
}

export default function WbTutorial({context,onLocate,onReveal}:{context:TutorialContext;onLocate:(view:TutorialView)=>void;onReveal:()=>void}){
 const [run,setRun]=useState<TutorialRun>(()=>{try{return loadTutorial(localStorage,context.project.id)}catch{return createTutorial(context.project.id)}})
 const current=useRef(context);current.current=context
 const status=tutorialStepState(run,context)
 const box=useHighlight(status.target,context.active&&run.status==='active')
 useEffect(()=>{try{saveTutorial(localStorage,run)}catch{/* Browser storage may be disabled. */}},[run])
 function locate(){
  onReveal()
  if(context.view!==status.required){onLocate(status.required);return}
  requestAnimationFrame(()=>{
   const element=Array.from(document.querySelectorAll(`[data-wb-guide="${status.target}"]`)).find(e=>e.getClientRects().length)
   element?.scrollIntoView({block:'nearest',inline:'nearest',behavior:'auto'})
  })
 }
 function next(){setRun(r=>advanceTutorial(r,current.current))}
 if(run.status!=='active')return <aside className="wb-tutorial-summary" aria-label="WB 教程状态">
  <span>{run.status==='completed'?'教程已完成':'教程已暂停'} · 当前分析和编辑内容继续保留</span>
  <button className="text-btn" onClick={()=>setRun(r=>run.status==='completed'?createTutorial(r.projectId):{...r,status:'active'})}>{run.status==='completed'?'从头查看引导':'继续教程'}</button>
 </aside>
 return <>
  <section className="wb-tutorial" role="region" aria-label="WB 分步教程">
   <div className="wb-tutorial-heading"><div aria-live="polite"><span>第 {run.step+1} / {tutorialSteps.length} 步</span><strong>{tutorialSteps[run.step].title}</strong></div><button className="icon-btn" aria-label="退出引导" title="退出引导，保留当前分析" onClick={()=>setRun(r=>({...r,status:'dismissed'}))}><X size={17}/></button></div>
   <progress aria-label="教程进度" max={tutorialSteps.length} value={run.step}/>
   <p>{run.step===3&&context.editor?.hasPreview?'当前调整已生成峰区建议。查看绿框；出现“选择峰”的泳道，需要根据原图和曲线选择正确的主峰。':tutorialSteps[run.step].text}</p>
   <div className="wb-tutorial-bottom"><p role="status" className={status.ready?'wb-tutorial-ready':''}>{status.ready?(run.step===0?'查看原图后可以继续。':run.step===7?'文件已成功导出，可以完成教程。':'这一步已完成，可以继续。'):status.message}</p>
    <div className="wb-tutorial-actions">
     {status.recovery&&<button className="text-btn" onClick={()=>setRun(r=>({...r,step:3,baseline:{regionEdits:0,laneSelections:0,identifications:0,peakTools:0,backgroundTools:0}}))}><RotateCcw size={14}/>返回识别步骤</button>}
     <button className="text-btn" onClick={locate}><LocateFixed size={14}/>定位此步</button>
     <button className="btn secondary" aria-label="教程上一步" disabled={run.step===0} onClick={()=>setRun(r=>({...r,step:r.step-1,baseline:{regionEdits:0,laneSelections:0,identifications:0,peakTools:0,backgroundTools:0}}))}><ChevronLeft size={14}/>上一步</button>
     <button className="btn primary" disabled={!status.ready} onClick={next}>{run.step===7?'完成教程':'下一步'}<ChevronRight size={14}/></button>
    </div>
   </div>
  </section>
  {box&&<div aria-hidden="true" className="wb-tutorial-highlight" data-highlight-target={status.target} style={box}/>}
 </>
}
