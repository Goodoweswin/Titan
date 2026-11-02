import {useEffect,useRef,useState} from 'react'
import type {KeyboardEvent,PointerEvent,RefObject} from 'react'
import type {Rect} from './types'

export function rotationView(width:number,height:number,angle:number):Rect {
 const radians=(Number.isFinite(angle)?angle:0)*Math.PI/180
 const w=(Math.abs(width*Math.cos(radians))+Math.abs(height*Math.sin(radians)))*1.1
 const h=(Math.abs(width*Math.sin(radians))+Math.abs(height*Math.cos(radians)))*1.1
 return [(width-w)/2,(height-h)/2,(width+w)/2,(height+h)/2]
}

export default function useImageViewport(svg:RefObject<SVGSVGElement|null>,initial:Rect,key:string,wheelTarget?:RefObject<HTMLElement|null>){
 const [view,setState]=useState<Rect>(initial),current=useRef(view),initialRef=useRef(initial)
 initialRef.current=initial
 const [panMode,setPanMode]=useState(false),[spaceHeld,setSpaceHeld]=useState(false),[panning,setPanning]=useState(false)
 const space=useRef(false),pan=useRef<{view:Rect;start:DOMPoint;matrix:DOMMatrix}|null>(null)
 function setView(next:Rect){current.current=next;setState(next)}
 function point(x:number,y:number){return new DOMPoint(x,y).matrixTransform(svg.current!.getScreenCTM()!.inverse())}
 function zoom(factor:number,anchor?:DOMPoint){
  const v=current.current,w=v[2]-v[0],fitWidth=initialRef.current[2]-initialRef.current[0]
  // Rotation can change the fitted extent; a new limit must never reverse a zoom step.
  const nextWidth=Math.max(Math.min(w,fitWidth/16),Math.min(Math.max(w,fitWidth*4),w/factor)),ratio=nextWidth/w
  const at=anchor??new DOMPoint((v[0]+v[2])/2,(v[1]+v[3])/2)
  setView([at.x+(v[0]-at.x)*ratio,at.y+(v[1]-at.y)*ratio,at.x+(v[2]-at.x)*ratio,at.y+(v[3]-at.y)*ratio])
 }
 function reset(){setView(initialRef.current)}
 function stopPan(){pan.current=null;setPanning(false)}
 function cancelPan(){stopPan();space.current=false;setSpaceHeld(false)}
 useEffect(()=>{reset();cancelPan();setPanMode(false)},[key])
 useEffect(()=>{
  const node=wheelTarget?.current??svg.current;if(!node)return
  function wheel(event:Event){
   const e=event as WheelEvent
   if(!e.deltaY||pan.current)return
   e.preventDefault()
   const delta=e.deltaY*(e.deltaMode===1?16:e.deltaMode===2?200:1)
   zoom(Math.exp(-Math.max(-600,Math.min(600,delta))*.002),point(e.clientX,e.clientY))
  }
  node.addEventListener('wheel',wheel,{passive:false})
  window.addEventListener('blur',cancelPan)
  return ()=>{node.removeEventListener('wheel',wheel);window.removeEventListener('blur',cancelPan)}
 },[key,wheelTarget])
 function beginPan(e:PointerEvent){
  if(e.button!==1&&!(e.button===0&&(space.current||panMode)))return false
  e.preventDefault();e.stopPropagation();svg.current?.focus();svg.current?.setPointerCapture(e.pointerId)
  const matrix=svg.current!.getScreenCTM()!.inverse()
  pan.current={view:[...current.current],start:new DOMPoint(e.clientX,e.clientY).matrixTransform(matrix),matrix}
  setPanning(true);return true
 }
 function movePan(e:PointerEvent){
  const g=pan.current;if(!g)return false
  const p=new DOMPoint(e.clientX,e.clientY).matrixTransform(g.matrix),dx=g.start.x-p.x,dy=g.start.y-p.y
  setView([g.view[0]+dx,g.view[1]+dy,g.view[2]+dx,g.view[3]+dy]);return true
 }
 function endPan(e:PointerEvent){if(!pan.current)return false;movePan(e);pan.current=null;setPanning(false);return true}
 function onKeyDown(e:KeyboardEvent){
  if(e.code==='Space'){e.preventDefault();space.current=true;setSpaceHeld(true);return true}
  if(e.ctrlKey||e.metaKey||e.altKey)return false
  if(['+','=','-','0'].includes(e.key)){e.preventDefault();if(e.key==='0')reset();else zoom(e.key==='-'?1/1.25:1.25);return true}
  return false
 }
 function onKeyUp(e:KeyboardEvent){if(e.code==='Space'){e.preventDefault();space.current=false;setSpaceHeld(false)}}
 return {view,setView,zoom,reset,point,panMode,setPanMode,beginPan,movePan,endPan,cancelPan,stopPan,onKeyDown,onKeyUp,
  zoomPercent:Math.round((initialRef.current[2]-initialRef.current[0])/(view[2]-view[0])*100),cursor:panning?'grabbing':panMode||spaceHeld?'grab':undefined}
}
