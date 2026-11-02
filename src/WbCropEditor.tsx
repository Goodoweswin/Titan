import {useRef,useState} from 'react'
import type {Rect} from './types'
import {cropRect,type WbRow} from './wb-figure'
import useImageViewport from './useImageViewport'
import ImageViewControls from './ImageViewControls'

export default function WbCropEditor({row,png,disabled,onCrop}:{row:WbRow;png:string;disabled:boolean;onCrop:(rect:Rect)=>void}){
 const start=useRef<[number,number]|null>(null),[draft,setDraft]=useState<Rect|null>(null)
 const {width,height}=row.source,rect=draft??row.crop
 const svg=useRef<SVGSVGElement>(null),viewport=useImageViewport(svg,[0,0,width,height],row.source.id+':'+(row.source.rotation_degrees??0)),v=viewport.view
 function position(e:React.PointerEvent<SVGSVGElement>):[number,number]{const p=viewport.point(e.clientX,e.clientY);return [p.x,p.y]}
 function cancel(){start.current=null;setDraft(null)}
 return <div className="wb-crop-view"><ImageViewControls zoomPercent={viewport.zoomPercent} panMode={viewport.panMode} onPan={()=>{cancel();viewport.setPanMode(!viewport.panMode)}} onZoom={viewport.zoom} onFit={viewport.reset}/><p className="hint">滚轮缩放 · 空格或中键拖动视图 · 拖选仍按原图像素保存</p><div className="wb-crop-frame"><svg ref={svg} tabIndex={0} viewBox={`${v[0]} ${v[1]} ${v[2]-v[0]} ${v[3]-v[1]}`} style={{aspectRatio:`${width}/${height}`,cursor:viewport.cursor}} aria-label="原图裁剪画布" role="img" onKeyDown={viewport.onKeyDown} onKeyUp={viewport.onKeyUp} onBlur={viewport.cancelPan}
  onPointerDownCapture={e=>{viewport.beginPan(e)}}
  onPointerDown={e=>{if(e.button!==0||disabled||!png)return;e.currentTarget.focus();e.currentTarget.setPointerCapture(e.pointerId);start.current=position(e);setDraft(null)}}
  onPointerMove={e=>{if(!viewport.movePan(e)&&start.current)setDraft(cropRect(start.current,position(e),width,height))}}
  onPointerUp={e=>{if(viewport.endPan(e)||!start.current)return;const next=cropRect(start.current,position(e),width,height);cancel();if(next)onCrop(next)}}
  onPointerCancel={()=>{viewport.cancelPan();cancel()}} onLostPointerCapture={()=>{viewport.stopPan();cancel()}}>
  {png&&<image href={png} width={width} height={height} preserveAspectRatio="none"/>}
  <path d={`M0 0H${width}V${height}H0Z M${rect[0]} ${rect[1]}V${rect[3]}H${rect[2]}V${rect[1]}Z`} fill="#14273b" fillOpacity=".38" fillRule="evenodd" pointerEvents="none"/>
  <rect x={rect[0]} y={rect[1]} width={Math.max(0,rect[2]-rect[0])} height={Math.max(0,rect[3]-rect[1])} fill="none" stroke="#4c79d8" strokeWidth={2} vectorEffect="non-scaling-stroke" pointerEvents="none"/>
 </svg></div></div>
}
