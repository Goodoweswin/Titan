import {useRef,type PointerEvent} from 'react'
import {boundWbOffset,snapWbOffset,wbPointsPerMm,type WbOffset,type WbPreview,type WbPreviewRow,type WbPreviewText,type WbRow} from './wb-figure'

export type WbRowMove={rowId:string;offset:WbOffset}
type Gesture={pointerId:number;row:WbPreviewRow;start:DOMPoint;offset:WbOffset}
interface Props {
 preview:WbPreview
 rows:WbRow[]
 selected:string
 move:WbRowMove|null
 disabled:boolean
 currentOffset:(row:WbPreviewRow)=>WbOffset
 onSelect:(id:string)=>void
 onMove:(move:WbRowMove|null)=>void
 onCommit:(id:string,offset:WbOffset)=>void
}

export default function WbFigureSheet({preview,rows,selected,move,disabled,currentOffset,onSelect,onMove,onCommit}:Props){
 const svg=useRef<SVGSVGElement>(null)
 const gesture=useRef<Gesture|null>(null)
 const {layout}=preview
 const width=preview.width_mm*wbPointsPerMm,height=preview.height_mm*wbPointsPerMm
 const text=(t:WbPreviewText,index:number)=><text key={index} x={t.x} y={t.y} textAnchor={t.anchor}
  fontFamily="Noto Sans SC, Arial, sans-serif" fontSize={t.font_pt??layout.font_pt} fill="#000">{t.text}</text>
 function point(event:PointerEvent){
  const matrix=svg.current?.getScreenCTM()
  return matrix?new DOMPoint(event.clientX,event.clientY).matrixTransform(matrix.inverse()):null
 }
 function start(event:PointerEvent<SVGGElement>,row:WbPreviewRow){
  if(event.button!==0||gesture.current)return
  onSelect(row.id)
  const origin=point(event)
  if(disabled||!origin||!svg.current)return
  event.preventDefault()
  event.currentTarget.focus({preventScroll:true})
  svg.current.setPointerCapture(event.pointerId)
  gesture.current={pointerId:event.pointerId,row,start:origin,offset:currentOffset(row)}
 }
 function draggedOffset(event:PointerEvent){
  const active=gesture.current,at=point(event)
  if(!active||active.pointerId!==event.pointerId||!at||disabled)return null
  return snapWbOffset(active.row,[
   active.offset[0]+(at.x-active.start.x)/wbPointsPerMm,
   active.offset[1]+(at.y-active.start.y)/wbPointsPerMm,
  ])
 }
 function cancel(){
  gesture.current=null
  onMove(null)
 }
 function cancelPointer(event:PointerEvent<SVGSVGElement>){
  if(gesture.current?.pointerId===event.pointerId)cancel()
 }
 function finish(event:PointerEvent<SVGSVGElement>){
  const active=gesture.current
  if(!active||event.pointerId!==active.pointerId)return
  const offset=draggedOffset(event)
  cancel()
  if(offset&&(offset[0]!==active.offset[0]||offset[1]!==active.offset[1]))onCommit(active.row.id,offset)
 }
 return <svg ref={svg} viewBox={`0 0 ${width} ${height}`} role="group" aria-label="WB 组图预览"
  onPointerMove={event=>{
   const offset=draggedOffset(event)
   if(offset&&gesture.current)onMove({rowId:gesture.current.row.id,offset})
  }} onPointerUp={finish} onPointerCancel={cancelPointer} onLostPointerCapture={cancelPointer}>
  <rect width={width} height={height} fill="white"/>
  {layout.rows.map((item,index)=>{
   const row=rows.find(row=>row.id===item.id)
   if(!row)return null
   const offset=move?.rowId===item.id?move.offset:boundWbOffset(item,row.offset_mm??[0,0])
   const dx=(offset[0]-item.offset_mm[0])*wbPointsPerMm,dy=(offset[1]-item.offset_mm[1])*wbPointsPerMm
   return <g key={item.id} transform={`translate(${dx} ${dy})`}
    className={`wb-sheet-row${disabled?' static':''}`} tabIndex={0} role="button"
    aria-label={`选择组图第 ${index+1} 行${row.protein?` ${row.protein}`:''}`}
    aria-pressed={item.id===selected} onPointerDown={event=>start(event,item)} onClick={()=>onSelect(item.id)}
    onKeyDown={event=>{
     if(event.key==='Escape'&&gesture.current)cancel()
     if(event.key==='Enter'||event.key===' '){event.preventDefault();onSelect(item.id)}
    }}>
    <image href={item.png} x={item.x_pt} y={item.y_pt} width={item.width_pt} height={item.height_pt} preserveAspectRatio="none"/>
    {layout.texts.filter(t=>t.row_id===item.id).map(text)}
    {item.id===selected&&<rect className="wb-sheet-selection" x={item.x_pt} y={item.y_pt}
     width={item.width_pt} height={item.height_pt} fill="none" vectorEffect="non-scaling-stroke" pointerEvents="none"/>}
   </g>
  })}
  {layout.texts.filter(t=>!t.row_id).map(text)}
 </svg>
}
