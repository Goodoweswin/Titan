import {useEffect,useRef,useState} from 'react'
import type {ImageAsset,Rect,LaneColumn,BandCandidate} from './types'
import {displayStyle} from './image-display'

interface Props{asset:ImageAsset;region:Rect|null;columns:LaneColumn[];bands:Record<string,BandCandidate>;selected:string;readOnly:boolean;onSelect:(id:string)=>void;onRegion:(r:Rect)=>void;onColumn:(id:string,r:Rect)=>void;onBand:(id:string,r:Rect)=>void;onBackground:(id:string,r:Rect)=>void;onAlign:(dx:number)=>void;onInvert:()=>void}
export default function LaneLayoutEditor(p:Props){
 const svg=useRef<SVGSVGElement>(null),gesture=useRef<{start:[number,number];kind:string;id?:string;rect?:Rect}|null>(null)
 const [tool,setTool]=useState('region'),[draft,setDraft]=useState<Rect|null>(null),[view,setView]=useState<Rect>([0,0,p.asset.width,p.asset.height])
 useEffect(()=>{setView([0,0,p.asset.width,p.asset.height]);setTool('region')},[p.asset.id])
 useEffect(()=>{if(!p.region)return;const [x0,y0,x1,y1]=p.region,padX=(x1-x0)*.06,padY=Math.max((y1-y0)*.5,(x1-x0)*.12);setView([Math.max(0,x0-padX),Math.max(0,y0-padY),Math.min(p.asset.width,x1+padX),Math.min(p.asset.height,y1+padY)])},[p.region?.join(',')])
 useEffect(()=>{if(p.columns.length)setTool('lanes')},[p.columns.length])
 function point(e:React.PointerEvent):[number,number]{const matrix=svg.current!.getScreenCTM()!;const q=new DOMPoint(e.clientX,e.clientY).matrixTransform(matrix.inverse());return [Math.round(Math.max(0,Math.min(p.asset.width,q.x))),Math.round(Math.max(0,Math.min(p.asset.height,q.y)))]}
 function begin(e:React.PointerEvent,kind:string,id?:string,rect?:Rect){if(p.readOnly)return;e.stopPropagation();svg.current?.setPointerCapture(e.pointerId);gesture.current={start:point(e),kind,id,rect};setDraft(null)}
 function move(e:React.PointerEvent){const g=gesture.current;if(!g)return;const [x,y]=point(e),[a,b]=g.start
  if(g.rect){let [x0,y0,x1,y1]=g.rect;if(g.kind==='lane'){const dx=Math.max(-x0,Math.min(p.asset.width-x1,x-a));x0+=dx;x1+=dx}else if(g.kind==='lane-size'){x1=Math.max(x0+1,Math.min(p.asset.width,x))}else if(g.kind==='peak'){const dy=Math.max(-y0,Math.min(p.asset.height-y1,y-b));y0+=dy;y1+=dy}else if(g.kind==='peak-size'){y1=Math.max(y0+1,Math.min(p.asset.height,y))}setDraft([x0,y0,x1,y1])}
  else setDraft([Math.min(a,x),Math.min(b,y),Math.max(a,x),Math.max(b,y)])
 }
 function finish(e:React.PointerEvent){const g=gesture.current;gesture.current=null;const r=draft;setDraft(null);if(!g)return
  if(g.kind==='align'){p.onAlign(point(e)[0]-g.start[0]);return}
  if(!r||r[2]-r[0]<1||r[3]-r[1]<1)return
  if(g.kind==='region')p.onRegion(r)
  else if(g.kind==='background'&&p.selected)p.onBackground(p.selected,r)
  else if(g.kind.startsWith('lane')&&g.id)p.onColumn(g.id,r)
  else if(g.id){const column=p.columns.find(c=>c.lane_id===g.id);p.onBand(g.id,g.kind==='new-peak'&&column?[column.rect[0],r[1],column.rect[2],r[3]]:r)}
 }
 const w=view[2]-view[0],h=view[3]-view[1],stroke=w/750,handle=Math.max(3,w/110)
 return <div className="lane-canvas-card"><div className="lane-toolbar"><div>{[['region','选择区域'],['lanes','调整泳道'],['align','移动整组'],['peaks','调整峰区'],['background','画背景']].map(([id,label])=><button key={id} className={tool===id?'tool selected':'tool'} disabled={p.readOnly||(id!=='region'&&!p.columns.length)} onClick={()=>setTool(id)}>{label}</button>)}</div><div><button className="text-btn" onClick={p.onInvert} aria-pressed={!!p.asset.display_inverted}>显示反色</button><button className="text-btn" onClick={()=>setView([0,0,p.asset.width,p.asset.height])}>查看全图</button></div></div>
 <div className="lane-canvas-scroll"><svg ref={svg} aria-label="泳道分析画布" viewBox={`${view[0]} ${view[1]} ${w} ${h}`} style={{aspectRatio:`${w}/${h}`,touchAction:'none'}} onPointerDown={e=>begin(e,tool==='align'?'align':tool==='background'?'background':tool==='peaks'&&p.selected?'new-peak':'region',tool==='peaks'?p.selected:undefined)} onPointerMove={move} onPointerUp={finish} onPointerCancel={()=>{gesture.current=null;setDraft(null)}}>
 <image href={p.asset.preview} style={displayStyle(p.asset)} width={p.asset.width} height={p.asset.height}/>
 {p.region&&<rect x={p.region[0]} y={p.region[1]} width={p.region[2]-p.region[0]} height={p.region[3]-p.region[1]} fill="none" stroke="#93a5c4" strokeDasharray={`${stroke*4} ${stroke*3}`} strokeWidth={stroke} pointerEvents="none"/>}
 {p.columns.map(c=>{const box=draft&&gesture.current?.id===c.lane_id&&gesture.current.kind.startsWith('lane')?draft:c.rect,selected=c.lane_id===p.selected;return <g key={c.lane_id}>
  <rect aria-label={`泳道 ${c.lane_id}`} x={box[0]} y={box[1]} width={box[2]-box[0]} height={box[3]-box[1]} fill={selected?'#4474df15':'transparent'} stroke={selected?'#81a9ff':'#7ca0d5'} strokeWidth={stroke} onPointerDown={e=>{p.onSelect(c.lane_id);if(tool==='lanes')begin(e,'lane',c.lane_id,c.rect);else if(tool==='align')begin(e,'align');else if(tool==='region')begin(e,'region');else if(tool==='background')begin(e,'background');else if(tool==='peaks')begin(e,'new-peak',c.lane_id);else e.stopPropagation()}}/>
  <text x={box[0]} y={box[1]-stroke*5} fill="#a6c6ff" fontSize={stroke*13} pointerEvents="none">{c.lane_id}</text>
  {selected&&tool==='lanes'&&<rect aria-label="调整泳道宽度" x={box[2]-handle/2} y={box[1]+(box[3]-box[1])/2-handle/2} width={handle} height={handle} fill="#81a9ff" onPointerDown={e=>begin(e,'lane-size',c.lane_id,c.rect)}/>}
 </g>})}
 {Object.entries(p.bands).map(([id,band])=>{const r=draft&&gesture.current?.id===id&&gesture.current.kind.startsWith('peak')?draft:band.rect;return <g key={id}>
  {band.backgrounds.map((b,i)=><rect key={i} x={b[0]} y={b[1]} width={b[2]-b[0]} height={b[3]-b[1]} fill="#e2ab3220" stroke="#d7ab57" strokeWidth={stroke} strokeDasharray={`${stroke*3} ${stroke*2}`} pointerEvents="none"/>)}
  <rect aria-label={`峰区 ${id}`} x={r[0]} y={r[1]} width={r[2]-r[0]} height={r[3]-r[1]} fill="#38cb9b20" stroke="#59d6ad" strokeWidth={stroke*1.2} onPointerDown={e=>{p.onSelect(id);if(tool==='peaks')begin(e,'peak',id,band.rect);else if(tool==='region')begin(e,'region');else if(tool==='align')begin(e,'align');else if(tool==='background')begin(e,'background');else e.stopPropagation()}}/>
  {id===p.selected&&tool==='peaks'&&<rect x={r[2]-handle} y={r[3]-handle/2} width={handle} height={handle} fill="#59d6ad" onPointerDown={e=>begin(e,'peak-size',id,band.rect)}/>}
 </g>})}
 {draft&&!gesture.current?.rect&&gesture.current?.kind!=='align'&&<rect x={draft[0]} y={draft[1]} width={draft[2]-draft[0]} height={draft[3]-draft[1]} fill="#668bea20" stroke="#9abaff" strokeWidth={stroke}/>}
 </svg></div><div className="lane-canvas-caption"><span>{p.asset.width} × {p.asset.height} px · {p.asset.dtype}</span><span>蓝框：泳道　绿框：峰区　虚线：背景</span></div></div>
}
