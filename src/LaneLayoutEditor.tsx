import {useEffect,useRef,useState} from 'react'
import type {ImageAsset,Rect,LaneColumn,BandCandidate} from './types'
import WbPreviewImage from './WbPreviewImage'
import useImageViewport from './useImageViewport'
import ImageViewControls from './ImageViewControls'
import {rectanglesOverlap} from './lane-workflow'

export const laneTools = [
 ['region','选择区域'],
 ['lanes','调整泳道'],
 ['align','移动整组'],
] as const

export type LaneTool=typeof laneTools[number][0]

interface Props{asset:ImageAsset;displaySrc:string|undefined;tool:LaneTool;onToolChange:(tool:LaneTool)=>void;region:Rect|null;columns:LaneColumn[];laneBounds?:Rect;bands:Record<string,BandCandidate>;selected:string;readOnly:boolean;onSelect:(id:string)=>void;onRegion:(r:Rect)=>void;onColumn:(id:string,r:Rect)=>void;onBand:(id:string,r:Rect)=>void;onBackground:(id:string,r:Rect,index?:number)=>void;onAlign:(dx:number)=>void;onInvert:()=>void;onRotate?:()=>void;onAcquisition:()=>void}
const edges=['左','上','右','下'] as const
const edgeIndices=[0,1,2,3] as const
type Edge=typeof edgeIndices[number]
type DrawBox={kind:'new-band'|'new-background';id:string}
type Action=
 | {kind:'region'|'align'}
 | {kind:'lane'|'lane-left'|'lane-right';id:string;rect:Rect}
 | DrawBox
 | {kind:'band-edge';id:string;rect:Rect;edge:Edge}
 | {kind:'background-edge';id:string;index:number;rect:Rect;edge:Edge}
type Gesture=Action&{start:[number,number]}
const clamp=(value:number,min:number,max:number)=>Math.max(min,Math.min(max,value))

export default function LaneLayoutEditor(p:Props){
 const {tool,onToolChange}=p
 const svg=useRef<SVGSVGElement>(null),gesture=useRef<Gesture|null>(null),draftRef=useRef<Rect|null>(null)
 const viewport=useImageViewport(svg,[0,0,p.asset.width,p.asset.height],p.asset.id),{view,setView}=viewport
 const [draft,setDraft]=useState<Rect|null>(null)
 const [drawing,setDrawing]=useState<DrawBox|null>(null)
 const [background,setBackground]=useState<{id:string;index:number}|null>(null)
 const armed=drawing?.id===p.selected?drawing:null
 const selectedBand=p.bands[p.selected]
 const selectedBackground=background?.id===p.selected?selectedBand?.backgrounds[background.index]:undefined
 useEffect(()=>{setView([0,0,p.asset.width,p.asset.height]);setBackground(null);setDrawing(null);cancel()},[p.asset.id])
 useEffect(()=>{if(!p.region)return;const [x0,y0,x1,y1]=p.region,padX=(x1-x0)*.06,padY=Math.max((y1-y0)*.5,(x1-x0)*.12);setView([Math.max(0,x0-padX),Math.max(0,y0-padY),Math.min(p.asset.width,x1+padX),Math.min(p.asset.height,y1+padY)])},[p.region?.join(',')])
 useEffect(()=>{onToolChange(p.columns.length?'lanes':'region')},[p.asset.id,p.columns.length,onToolChange])
 useEffect(()=>{cancel();setDrawing(null);viewport.setPanMode(false)},[tool])
 useEffect(()=>{if(p.readOnly){cancel();setDrawing(null)}},[p.readOnly])
 useEffect(()=>{if(p.selected)svg.current?.focus({preventScroll:true})},[p.selected])
 function cancel(){gesture.current=null;draftRef.current=null;setDraft(null)}
 function point(e:React.PointerEvent):[number,number]{const q=new DOMPoint(e.clientX,e.clientY).matrixTransform(svg.current!.getScreenCTM()!.inverse());return [Math.round(Math.max(0,Math.min(p.asset.width,q.x))),Math.round(Math.max(0,Math.min(p.asset.height,q.y)))]}
 function begin(e:React.PointerEvent,action:Action){
  e.stopPropagation();if(p.readOnly||e.button!==0)return
  e.preventDefault()
  svg.current?.focus({preventScroll:true});svg.current?.setPointerCapture(e.pointerId)
  gesture.current={...action,start:point(e)};draftRef.current=null;setDraft(null)
 }
 function limits(id:string){const others=p.columns.filter(c=>c.lane_id!==id),r=p.columns.find(c=>c.lane_id===id)!.rect;return [Math.max(p.laneBounds?.[0]??0,...others.filter(c=>c.rect[2]<=r[0]).map(c=>c.rect[2])),Math.min(p.laneBounds?.[2]??p.asset.width,...others.filter(c=>c.rect[0]>=r[2]).map(c=>c.rect[0]))]}
 function move(e:React.PointerEvent){
  const g=gesture.current;if(!g)return;const [x,y]=point(e),[a,b]=g.start
  let r:Rect
  if(g.kind==='band-edge'||g.kind==='background-edge'){
   r=[...g.rect]
   const column=g.kind==='band-edge'?p.columns.find(c=>c.lane_id===g.id)?.rect:undefined
   const minimum=[column?.[0]??0,0,r[0]+1,r[1]+1][g.edge]
   const maximum=[r[2]-1,r[3]-1,column?.[2]??p.asset.width,p.asset.height][g.edge]
   r[g.edge]=clamp(g.rect[g.edge]+(g.edge%2?y-b:x-a),minimum,maximum)
   const peak=p.bands[g.id]?.rect
   if(g.kind==='background-edge'&&peak&&rectanglesOverlap(r,peak)){
    // Keep the edited edge on its original side of the peak.
    r[g.edge]=clamp(peak[(g.edge+2)%4],minimum,maximum)
    if(rectanglesOverlap(r,peak))r=g.rect
   }
  }else if(g.kind==='lane'||g.kind==='lane-left'||g.kind==='lane-right'){
   let [x0,y0,x1,y1]=g.rect
   const [left,right]=limits(g.id)
   if(g.kind==='lane'){const dx=clamp(x-a,left-x0,right-x1);x0+=dx;x1+=dx}
   else if(g.kind==='lane-left')x0=clamp(x,left,x1-1)
   else x1=clamp(x,x0+1,right)
   r=[x0,y0,x1,y1]
  }else{
   r=[Math.min(a,x),Math.min(b,y),Math.max(a,x),Math.max(b,y)]
   if(g.kind==='new-band'){
    const lane=p.columns.find(c=>c.lane_id===g.id)
    if(!lane)return
    r[0]=clamp(r[0],lane.rect[0],lane.rect[2])
    r[2]=clamp(r[2],lane.rect[0],lane.rect[2])
   }
  }
  draftRef.current=r;setDraft(r)
 }
 function finish(e:React.PointerEvent){const g=gesture.current,r=draftRef.current;cancel();if(!g)return
  if(g.kind==='align'){const left=p.laneBounds?.[0]??0,right=p.laneBounds?.[2]??p.asset.width,dx=Math.max(left-Math.min(...p.columns.map(c=>c.rect[0])),Math.min(right-Math.max(...p.columns.map(c=>c.rect[2])),point(e)[0]-g.start[0]));if(dx)p.onAlign(dx);return}
  if(!r||r[2]-r[0]<1||r[3]-r[1]<1||('rect' in g&&g.rect.every((v,i)=>v===r[i])))return
  if(g.kind==='region')p.onRegion(r)
  else if(g.kind==='band-edge'||g.kind==='new-band')p.onBand(g.id,r)
  else if(g.kind==='background-edge')p.onBackground(g.id,r,g.index)
  else if(g.kind==='new-background')p.onBackground(g.id,r)
  else if('id' in g)p.onColumn(g.id,r)
  if(g.kind==='new-background'||g.kind==='new-band')setDrawing(null)
 }
 function down(e:React.PointerEvent,id?:string){
  e.stopPropagation();if(p.readOnly||e.button!==0)return
  if(armed){begin(e,armed);return}
  if(tool==='region'){begin(e,{kind:'region'});return}
  if(id){setBackground(null);p.onSelect(id)}
  if(tool==='align')begin(e,{kind:'align'})
  else if(id)begin(e,{kind:'lane',id,rect:p.columns.find(c=>c.lane_id===id)!.rect})
 }
 function selectBackground(e:React.PointerEvent,id:string,index:number){
  if(tool!=='lanes'||armed){down(e,id);return}
  e.stopPropagation();if(p.readOnly||e.button!==0)return
  p.onSelect(id);setBackground({id,index})
 }
 function nudge(e:React.KeyboardEvent){
  if(viewport.onKeyDown(e))return
  if(e.key==='Escape'){cancel();setDrawing(null);return}
  if(p.readOnly||tool!=='lanes'||!p.selected||e.metaKey||e.ctrlKey||e.altKey||!['ArrowLeft','ArrowRight'].includes(e.key))return
  const c=p.columns.find(c=>c.lane_id===p.selected);if(!c)return
  e.preventDefault();const [left,right]=limits(c.lane_id),[x0,y0,x1,y1]=c.rect,delta=(e.key==='ArrowLeft'?-1:1)*(e.shiftKey?10:1),dx=Math.max(left-x0,Math.min(right-x1,delta))
  if(dx)p.onColumn(c.lane_id,[x0+dx,y0,x1+dx,y1])
 }
 const w=view[2]-view[0],h=view[3]-view[1],stroke=w/750,handle=Math.max(3,w/95)
 const selected=p.columns.find(c=>c.lane_id===p.selected),activeGesture=gesture.current
 const laneDraft=draft&&activeGesture&&'id' in activeGesture&&activeGesture.kind.startsWith('lane')?activeGesture.id:null
 const selectedBox=selected&&(laneDraft===selected.lane_id?draft!:selected.rect)
 const canResize=tool==='lanes'&&!p.readOnly&&!armed&&!viewport.cursor
 const handleY=selectedBox?selectedBand?Math.max(selectedBox[1],view[1])+handle/2:(selectedBox[1]+selectedBox[3])/2:0
 const hints:Record<LaneTool,string>={region:'拖选蛋白所在区域',lanes:'拖蓝框调整泳道 · 选中绿框或虚线背景框，拖边缘调整',align:'拖动以左右移动全部泳道'}
 function edgeHandles(r:Rect,id:string,index?:number){
  const isBackground=index!==undefined
  const size=Math.min(handle,(r[2]-r[0])/3,(r[3]-r[1])/3)
  const centersX=[r[0],(r[0]+r[2])/2,r[2],(r[0]+r[2])/2]
  const centersY=[(r[1]+r[3])/2,r[1],(r[1]+r[3])/2,r[3]]
  return edgeIndices.map(edge=><rect key={edge} aria-label={`调整${isBackground?'背景':'条带'}${edges[edge]}边缘`}
   x={centersX[edge]-size/2} y={centersY[edge]-size/2} width={size} height={size}
   fill={isBackground?'#e2b96c':'#59d6ad'} stroke="#17243c" strokeWidth={stroke}
   style={{cursor:edge%2?'ns-resize':'ew-resize'}}
   onPointerDown={e=>begin(e,index===undefined?{kind:'band-edge',id,rect:r,edge}:{kind:'background-edge',id,rect:r,edge,index})}/>)
 }
 const drawHint=armed?.kind==='new-band'?'在选中泳道内拖出条带框':armed?'拖出与条带分开的局部背景框':hints[tool]
 return <div className="lane-canvas-card"><div className="lane-toolbar"><div>{laneTools.map(([id,label])=><button key={id} className={tool===id&&!viewport.panMode?'tool selected':'tool'} aria-pressed={tool===id&&!viewport.panMode} disabled={p.readOnly||(id!=='region'&&!p.columns.length)} data-wb-guide={'tool-'+id} onClick={()=>{cancel();setDrawing(null);viewport.setPanMode(false);onToolChange(id)}}>{label}</button>)}</div><div><button className="text-btn" onClick={p.onAcquisition}>采集信息</button>{p.onRotate&&<button className="text-btn" disabled={p.readOnly} onClick={p.onRotate}>旋转校正</button>}<button className="text-btn" disabled={p.readOnly} onClick={p.onInvert} aria-pressed={!!p.asset.display_inverted}>显示反色</button></div></div>
 <div className="image-view-bar"><ImageViewControls zoomPercent={viewport.zoomPercent} panMode={viewport.panMode} onPan={()=>{cancel();viewport.setPanMode(!viewport.panMode)}} onZoom={viewport.zoom} onFit={viewport.reset} fitLabel="查看全图"/><span className="hint">滚轮缩放 · 空格或中键拖动视图</span></div>
 <div className="lane-tool-hint" role="status"><span aria-hidden={viewport.panMode}>{drawHint}</span><span aria-hidden={!viewport.panMode}>拖动移动视图，不修改区域或条带</span></div>
 <div className="lane-canvas-scroll"><svg ref={svg} tabIndex={0} data-wb-guide="canvas" aria-label="泳道分析画布" viewBox={`${view[0]} ${view[1]} ${w} ${h}`} style={{aspectRatio:`${w}/${h}`,touchAction:'none',cursor:viewport.cursor??(tool==='lanes'?'ew-resize':tool==='align'?'grab':'crosshair')}} onKeyDown={nudge} onKeyUp={viewport.onKeyUp} onBlur={viewport.cancelPan} onPointerDownCapture={e=>{viewport.beginPan(e)}} onPointerDown={e=>{if(e.button===0){svg.current?.focus({preventScroll:true});down(e)}}} onPointerMove={e=>{if(!viewport.movePan(e))move(e)}} onPointerUp={e=>{if(!viewport.endPan(e))finish(e)}} onPointerCancel={()=>{viewport.cancelPan();cancel()}} onLostPointerCapture={()=>{viewport.stopPan();cancel()}}>
 <WbPreviewImage href={p.displaySrc} inverted={p.asset.display_inverted} width={p.asset.width} height={p.asset.height}/>
 {p.region&&<rect aria-label="识别区域" x={p.region[0]} y={p.region[1]} width={p.region[2]-p.region[0]} height={p.region[3]-p.region[1]} fill="none" stroke="#93a5c4" strokeDasharray={`${stroke*4} ${stroke*3}`} strokeWidth={stroke} pointerEvents="none"/>}
 {p.columns.map(c=>{const box=draft&&laneDraft===c.lane_id?draft:c.rect;return <g key={c.lane_id}>
  <rect aria-label={`泳道 ${c.lane_id}`} x={box[0]} y={box[1]} width={box[2]-box[0]} height={box[3]-box[1]} fill={c.lane_id===p.selected?'#4474df15':'transparent'} stroke={c.lane_id===p.selected?'#81a9ff':'#7ca0d5'} strokeWidth={stroke} onPointerDown={e=>down(e,c.lane_id)}/>
  <text x={box[0]} y={box[1]-stroke*5} fill="#a6c6ff" fontSize={stroke*13} pointerEvents="none">{c.lane_id}</text>
 </g>})}
 {Object.entries(p.bands).map(([id,band])=>{const r=draft&&activeGesture?.kind==='band-edge'&&activeGesture.id===id?draft:band.rect;return <g key={id}>
  {band.backgrounds.map((source,i)=>{
   const b=draft&&activeGesture?.kind==='background-edge'&&activeGesture.id===id&&activeGesture.index===i?draft:source
   return <rect key={i} aria-label={`背景 ${id} · ${i+1}`} x={b[0]} y={b[1]} width={b[2]-b[0]} height={b[3]-b[1]} fill="#e2ab3220" stroke="#d7ab57" strokeWidth={stroke} strokeDasharray={`${stroke*3} ${stroke*2}`} onPointerDown={e=>selectBackground(e,id,i)}/>
  })}
  <rect aria-label={`峰区 ${id}`} x={r[0]} y={r[1]} width={r[2]-r[0]} height={r[3]-r[1]} fill="#38cb9b20" stroke="#59d6ad" strokeWidth={stroke*1.2} onPointerDown={e=>down(e,id)}/>
 </g>})}
 {selected&&selectedBox&&canResize&&[0,2].map(edge=><rect key={edge} aria-label={edge===0?'调整泳道左边界':'调整泳道右边界'} x={selectedBox[edge]-handle/2} y={handleY-handle/2} width={handle} height={handle} fill="#81a9ff" stroke="#17243c" strokeWidth={stroke} onPointerDown={e=>begin(e,{kind:edge===0?'lane-left':'lane-right',id:selected.lane_id,rect:selected.rect})}/>)}
 {canResize&&selectedBand&&(selectedBackground&&background
  ?edgeHandles(draft&&activeGesture?.kind==='background-edge'?draft:selectedBackground,p.selected,background.index)
  :edgeHandles(draft&&activeGesture?.kind==='band-edge'?draft:selectedBand.rect,p.selected))}
 {draft&&activeGesture&&(!('rect' in activeGesture)&&activeGesture.kind!=='align')&&<rect x={draft[0]} y={draft[1]} width={draft[2]-draft[0]} height={draft[3]-draft[1]} fill="#668bea20" stroke={armed?.kind==='new-background'?'#d7ab57':'#9abaff'} strokeWidth={stroke} pointerEvents="none"/>}
 </svg></div><div className="lane-canvas-caption"><span>{p.asset.width} × {p.asset.height} px · {p.asset.dtype}</span><span>蓝框：泳道　绿框：峰区　虚线：背景</span>
 {selected&&tool==='lanes'&&!p.readOnly&&<button type="button" className="text-btn" aria-pressed={!!armed} onClick={()=>{
  cancel();viewport.setPanMode(false)
  setDrawing(armed?null:{id:selected.lane_id,kind:selectedBand?'new-background':'new-band'})
 }}>{selectedBand?'添加背景框':'补画条带'}</button>}
 </div></div>
}
