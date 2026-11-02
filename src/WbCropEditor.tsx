import {useRef,useState} from 'react'
import type {Rect} from './types'
import {cropRect,type WbRow} from './wb-figure'

export default function WbCropEditor({row,png,disabled,onCrop}:{row:WbRow;png:string;disabled:boolean;onCrop:(rect:Rect)=>void}){
 const start=useRef<[number,number]|null>(null),[draft,setDraft]=useState<Rect|null>(null)
 const {width,height}=row.source,rect=draft??row.crop
 function position(e:React.PointerEvent<SVGSVGElement>):[number,number]{const box=e.currentTarget.getBoundingClientRect();return [(e.clientX-box.left)/box.width*width,(e.clientY-box.top)/box.height*height]}
 return <div className="wb-crop-frame"><svg viewBox={`0 0 ${width} ${height}`} style={{aspectRatio:`${width}/${height}`}} aria-label="原图裁剪画布" role="img"
  onPointerDown={e=>{if(disabled||!png)return;e.currentTarget.setPointerCapture(e.pointerId);start.current=position(e);setDraft(null)}}
  onPointerMove={e=>{if(start.current)setDraft(cropRect(start.current,position(e),width,height))}}
  onPointerUp={e=>{if(!start.current)return;const next=cropRect(start.current,position(e),width,height);start.current=null;setDraft(null);if(next)onCrop(next)}}
  onPointerCancel={()=>{start.current=null;setDraft(null)}}>
  {png&&<image href={png} width={width} height={height} preserveAspectRatio="none"/>}
  <path d={`M0 0H${width}V${height}H0Z M${rect[0]} ${rect[1]}V${rect[3]}H${rect[2]}V${rect[1]}Z`} fill="#14273b" fillOpacity=".38" fillRule="evenodd" pointerEvents="none"/>
  <rect x={rect[0]} y={rect[1]} width={Math.max(0,rect[2]-rect[0])} height={Math.max(0,rect[3]-rect[1])} fill="none" stroke="#4c79d8" strokeWidth={2} vectorEffect="non-scaling-stroke" pointerEvents="none"/>
 </svg></div>
}
