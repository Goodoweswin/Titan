import {useEffect,useRef,useState} from 'react'
import type {ImageAsset,Rect,LaneColumn,BandCandidate} from './types'
import {displayStyle} from './image-display'
import useImageViewport from './useImageViewport'
import ImageViewControls from './ImageViewControls'

export const laneTools = [
 ['region','选择区域'],
 ['lanes','调整泳道'],
 ['align','移动整组'],
 ['peaks','调整峰区'],
 ['background','画背景'],
] as const

interface Props{asset:ImageAsset;region:Rect|null;columns:LaneColumn[];laneBounds?:Rect;bands:Record<string,BandCandidate>;selected:string;readOnly:boolean;onSelect:(id:string)=>void;onRegion:(r:Rect)=>void;onColumn:(id:string,r:Rect)=>void;onBand:(id:string,r:Rect)=>void;onBackground:(id:string,r:Rect)=>void;onAlign:(dx:number)=>void;onInvert:()=>void;onRotate?:()=>void}
type Gesture={start:[number,number];kind:string;id?:string;rect?:Rect}
export default function LaneLayoutEditor(p:Props){
 const svg=useRef<SVGSVGElement>(null),gesture=useRef<Gesture|null>(null),draftRef=useRef<Rect|null>(null)
 const viewport=useImageViewport(svg,[0,0,p.asset.width,p.asset.height],p.asset.id),{view,setView}=viewport
 const [tool,setTool]=useState('region'),[draft,setDraft]=useState<Rect|null>(null)
 useEffect(()=>{setView([0,0,p.asset.width,p.asset.height]);setTool(p.columns.length?'lanes':'region')},[p.asset.id])
 useEffect(()=>{if(!p.region)return;const [x0,y0,x1,y1]=p.region,padX=(x1-x0)*.06,padY=Math.max((y1-y0)*.5,(x1-x0)*.12);setView([Math.max(0,x0-padX),Math.max(0,y0-padY),Math.min(p.asset.width,x1+padX),Math.min(p.asset.height,y1+padY)])},[p.region?.join(',')])
 useEffect(()=>{setTool(p.columns.length?'lanes':'region')},[p.columns.length])
 useEffect(()=>{if(p.readOnly)cancel()},[p.readOnly])
 useEffect(()=>{if(p.selected)svg.current?.focus()},[p.selected])
 function cancel(){gesture.current=null;draftRef.current=null;setDraft(null)}
 function point(e:React.PointerEvent):[number,number]{const q=new DOMPoint(e.clientX,e.clientY).matrixTransform(svg.current!.getScreenCTM()!.inverse());return [Math.round(Math.max(0,Math.min(p.asset.width,q.x))),Math.round(Math.max(0,Math.min(p.asset.height,q.y)))]}
 function begin(e:React.PointerEvent,kind:string,id?:string,rect?:Rect){
  e.stopPropagation();if(p.readOnly)return
  svg.current?.focus();svg.current?.setPointerCapture(e.pointerId)
  gesture.current={start:point(e),kind,id,rect};draftRef.current=null;setDraft(null)
 }
 function limits(id:string){const others=p.columns.filter(c=>c.lane_id!==id),r=p.columns.find(c=>c.lane_id===id)!.rect;return [Math.max(p.laneBounds?.[0]??0,...others.filter(c=>c.rect[2]<=r[0]).map(c=>c.rect[2])),Math.min(p.laneBounds?.[2]??p.asset.width,...others.filter(c=>c.rect[0]>=r[2]).map(c=>c.rect[0]))]}
 function move(e:React.PointerEvent){
  const g=gesture.current;if(!g)return;const [x,y]=point(e),[a,b]=g.start
  let r:Rect
  if(g.rect){let [x0,y0,x1,y1]=g.rect
   if(g.kind.startsWith('lane')){
    const [left,right]=limits(g.id!)
    if(g.kind==='lane'){const dx=Math.max(left-x0,Math.min(right-x1,x-a));x0+=dx;x1+=dx}
    else if(g.kind==='lane-left')x0=Math.max(left,Math.min(x1-1,x))
    else x1=Math.max(x0+1,Math.min(right,x))
   }else if(g.kind==='peak'){const dy=Math.max(-y0,Math.min(p.asset.height-y1,y-b));y0+=dy;y1+=dy}
   else if(g.kind==='peak-size')y1=Math.max(y0+1,Math.min(p.asset.height,y))
   r=[x0,y0,x1,y1]
  }else r=[Math.min(a,x),Math.min(b,y),Math.max(a,x),Math.max(b,y)]
  draftRef.current=r;setDraft(r)
 }
 function finish(e:React.PointerEvent){const g=gesture.current,r=draftRef.current;cancel();if(!g)return
  if(g.kind==='align'){const left=p.laneBounds?.[0]??0,right=p.laneBounds?.[2]??p.asset.width,dx=Math.max(left-Math.min(...p.columns.map(c=>c.rect[0])),Math.min(right-Math.max(...p.columns.map(c=>c.rect[2])),point(e)[0]-g.start[0]));if(dx)p.onAlign(dx);return}
  if(!r||r[2]-r[0]<1||r[3]-r[1]<1||g.rect?.every((v,i)=>v===r[i]))return
  if(g.kind==='region')p.onRegion(r)
  else if(g.kind==='background'&&p.selected)p.onBackground(p.selected,r)
  else if(g.kind.startsWith('lane')&&g.id)p.onColumn(g.id,r)
  else if(g.id){const column=p.columns.find(c=>c.lane_id===g.id);p.onBand(g.id,g.kind==='new-peak'&&column?[column.rect[0],r[1],column.rect[2],r[3]]:r)}
 }
 function down(e:React.PointerEvent,id?:string){
  e.stopPropagation();if(p.readOnly)return
  if(id)p.onSelect(id)
  if(tool==='region')begin(e,'region')
  else if(tool==='align')begin(e,'align')
  else if(tool==='background'&&(id||p.selected))begin(e,'background')
  else if(tool==='peaks'&&(id||p.selected)){const key=id||p.selected,band=p.bands[key];begin(e,id&&band?'peak':'new-peak',key,id?band?.rect:undefined)}
  else if(tool==='lanes'&&id)begin(e,'lane',id,p.columns.find(c=>c.lane_id===id)!.rect)
 }
 function nudge(e:React.KeyboardEvent){
  if(viewport.onKeyDown(e))return
  if(e.key==='Escape'){cancel();return}
  if(p.readOnly||tool!=='lanes'||!p.selected||e.metaKey||e.ctrlKey||e.altKey||!['ArrowLeft','ArrowRight'].includes(e.key))return
  const c=p.columns.find(c=>c.lane_id===p.selected);if(!c)return
  e.preventDefault();const [left,right]=limits(c.lane_id),[x0,y0,x1,y1]=c.rect,delta=(e.key==='ArrowLeft'?-1:1)*(e.shiftKey?10:1),dx=Math.max(left-x0,Math.min(right-x1,delta))
  if(dx)p.onColumn(c.lane_id,[x0+dx,y0,x1+dx,y1])
 }
 const w=view[2]-view[0],h=view[3]-view[1],stroke=w/750,handle=Math.max(3,w/95)
 const selected=p.columns.find(c=>c.lane_id===p.selected),selectedBox=selected&&(draft&&gesture.current?.id===selected.lane_id&&gesture.current.kind.startsWith('lane')?draft:selected.rect)
 const handleY=selectedBox?(Math.max(selectedBox[1],view[1],p.region?.[1]??view[1])+Math.min(selectedBox[3],view[3],p.region?.[3]??view[3]))/2:0
 const hints:Record<string,string>={region:'拖选蛋白所在区域',lanes:'拖动泳道左右移动 · 两侧手柄调宽度 · ← → 微调，Shift 加速',align:'拖动以左右移动全部泳道',peaks:'拖动绿框上下移动 · 下方手柄调整高度',background:'为选中泳道拖画局部背景'}
 return <div className="lane-canvas-card"><div className="lane-toolbar"><div>{laneTools.map(([id,label])=><button key={id} className={tool===id&&!viewport.panMode?'tool selected':'tool'} aria-pressed={tool===id&&!viewport.panMode} disabled={p.readOnly||(id!=='region'&&!p.columns.length)} onClick={()=>{cancel();viewport.setPanMode(false);setTool(id)}}>{label}</button>)}</div><div>{p.onRotate&&<button className="text-btn" disabled={p.readOnly} onClick={p.onRotate}>旋转校正</button>}<button className="text-btn" disabled={p.readOnly} onClick={p.onInvert} aria-pressed={!!p.asset.display_inverted}>显示反色</button></div></div>
 <div className="image-view-bar"><ImageViewControls zoomPercent={viewport.zoomPercent} panMode={viewport.panMode} onPan={()=>{cancel();viewport.setPanMode(!viewport.panMode)}} onZoom={viewport.zoom} onFit={viewport.reset} fitLabel="查看全图"/><span className="hint">滚轮缩放 · 空格或中键拖动视图</span></div>
 <div className="lane-tool-hint" role="status">{viewport.panMode?'拖动移动视图，不修改区域或条带':hints[tool]}</div>
 <div className="lane-canvas-scroll"><svg ref={svg} tabIndex={0} aria-label="泳道分析画布" viewBox={`${view[0]} ${view[1]} ${w} ${h}`} style={{aspectRatio:`${w}/${h}`,touchAction:'none',cursor:viewport.cursor??(tool==='lanes'?'ew-resize':tool==='align'?'grab':'crosshair')}} onKeyDown={nudge} onKeyUp={viewport.onKeyUp} onBlur={viewport.cancelPan} onPointerDownCapture={e=>{viewport.beginPan(e)}} onPointerDown={e=>{if(e.button===0){svg.current?.focus();down(e)}}} onPointerMove={e=>{if(!viewport.movePan(e))move(e)}} onPointerUp={e=>{if(!viewport.endPan(e))finish(e)}} onPointerCancel={()=>{viewport.cancelPan();cancel()}} onLostPointerCapture={()=>{viewport.stopPan();cancel()}}>
 <image href={p.asset.preview} style={displayStyle(p.asset)} width={p.asset.width} height={p.asset.height}/>
 {p.region&&<rect aria-label="识别区域" x={p.region[0]} y={p.region[1]} width={p.region[2]-p.region[0]} height={p.region[3]-p.region[1]} fill="none" stroke="#93a5c4" strokeDasharray={`${stroke*4} ${stroke*3}`} strokeWidth={stroke} pointerEvents="none"/>}
 {p.columns.map(c=>{const box=draft&&gesture.current?.id===c.lane_id&&gesture.current.kind.startsWith('lane')?draft:c.rect;return <g key={c.lane_id}>
  <rect aria-label={`泳道 ${c.lane_id}`} x={box[0]} y={box[1]} width={box[2]-box[0]} height={box[3]-box[1]} fill={c.lane_id===p.selected?'#4474df15':'transparent'} stroke={c.lane_id===p.selected?'#81a9ff':'#7ca0d5'} strokeWidth={stroke} onPointerDown={e=>down(e,c.lane_id)}/>
  <text x={box[0]} y={box[1]-stroke*5} fill="#a6c6ff" fontSize={stroke*13} pointerEvents="none">{c.lane_id}</text>
 </g>})}
 {Object.entries(p.bands).map(([id,band])=>{const r=draft&&gesture.current?.id===id&&gesture.current.kind.startsWith('peak')?draft:band.rect;return <g key={id}>
  {band.backgrounds.map((b,i)=><rect key={i} x={b[0]} y={b[1]} width={b[2]-b[0]} height={b[3]-b[1]} fill="#e2ab3220" stroke="#d7ab57" strokeWidth={stroke} strokeDasharray={`${stroke*3} ${stroke*2}`} pointerEvents="none"/>)}
  <rect aria-label={`峰区 ${id}`} x={r[0]} y={r[1]} width={r[2]-r[0]} height={r[3]-r[1]} fill="#38cb9b20" stroke="#59d6ad" strokeWidth={stroke*1.2} onPointerDown={e=>down(e,id)}/>
  {id===p.selected&&tool==='peaks'&&<rect aria-label="调整峰区高度" x={r[2]-handle} y={r[3]-handle/2} width={handle} height={handle} fill="#59d6ad" onPointerDown={e=>begin(e,'peak-size',id,band.rect)}/>}
 </g>})}
 {selected&&selectedBox&&tool==='lanes'&&[0,2].map(edge=><rect key={edge} aria-label={edge===0?'调整泳道左边界':'调整泳道右边界'} x={selectedBox[edge]-handle/2} y={handleY-handle/2} width={handle} height={handle} fill="#81a9ff" stroke="#17243c" strokeWidth={stroke} onPointerDown={e=>begin(e,edge===0?'lane-left':'lane-right',selected.lane_id,selected.rect)}/>)}
 {draft&&!gesture.current?.rect&&gesture.current?.kind!=='align'&&<rect x={draft[0]} y={draft[1]} width={draft[2]-draft[0]} height={draft[3]-draft[1]} fill="#668bea20" stroke="#9abaff" strokeWidth={stroke} pointerEvents="none"/>}
 </svg></div><div className="lane-canvas-caption"><span>{p.asset.width} × {p.asset.height} px · {p.asset.dtype}</span><span>蓝框：泳道　绿框：峰区　虚线：背景</span></div></div>
}
