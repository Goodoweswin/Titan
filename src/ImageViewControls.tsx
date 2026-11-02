import {Hand,ZoomIn,ZoomOut} from 'lucide-react'

export default function ImageViewControls({zoomPercent,panMode,onPan,onZoom,onFit,fitLabel='适合窗口'}:{zoomPercent:number;panMode:boolean;onPan:()=>void;onZoom:(factor:number)=>void;onFit:()=>void;fitLabel?:string}){
 return <div className="image-view-controls" role="group" aria-label="图像视图操作">
  <button type="button" className={panMode?'tool selected':'tool'} aria-label="移动视图" aria-pressed={panMode} title="移动视图（也可按住空格或使用中键拖动）" onClick={onPan}><Hand size={16}/><span>移动视图</span></button>
  <button type="button" className="icon-btn" aria-label="缩小图像" onClick={()=>onZoom(1/1.25)}><ZoomOut size={16}/></button>
  <output aria-label="图像缩放比例">{zoomPercent}%</output>
  <button type="button" className="icon-btn" aria-label="放大图像" onClick={()=>onZoom(1.25)}><ZoomIn size={16}/></button>
  <button type="button" className="text-btn" onClick={onFit}>{fitLabel}</button>
 </div>
}
