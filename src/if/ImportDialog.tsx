import {useEffect,useRef,useState} from 'react'
import {open} from '@tauri-apps/plugin-dialog'
import {callEngine} from '../bridge'
import type {IFInspection,IFSelection} from './types'
const planes=(axes:string,shape:number[],previous:Record<string,number>={})=>Object.fromEntries([...axes].filter(a=>'TZ'.includes(a)).map(a=>[a,Math.max(0,Math.min((shape[axes.indexOf(a)]??1)-1,previous[a]??0))]))
type Source={path:string;info:IFInspection;series:number;axes:string;channels:number[];indexers:Record<string,number>}
type Props={
 initialPaths?:string[]
 onClose:()=>void
 onImport:(selections:IFSelection[],metadata:Record<string,unknown>)=>void|Promise<void>
}
export default function ImportDialog({initialPaths,onClose,onImport}:Props){
 const [paths,setPaths]=useState(()=>initialPaths?.join('\n')??'')
 const pendingInitialInspection=useRef(paths)
 const [sources,setSources]=useState<Source[]>([]),[error,setError]=useState(''),[working,setWorking]=useState(false),[confirmed,setConfirmed]=useState(false)
 const [submitting,setSubmitting]=useState(false)
 const [meta,setMeta]=useState({name:'视野 '+new Date().toLocaleTimeString(),sample_id:'',bio_id:'',group:'',batch_id:''}),[px,setPx]=useState(''),[py,setPy]=useState('')
 useEffect(()=>{
  const text=pendingInitialInspection.current
  pendingInitialInspection.current=''
  if(text.trim())void inspect(text)
 },[])
 async function inspect(text:string){
  setWorking(true)
  setSources([])
  setConfirmed(false)
  setError('')
  try{
   const next:Source[]=[]
   for(const path of text.split('\n').map(s=>s.trim()).filter(Boolean)){
    const info=await callEngine<IFInspection>('if_inspect',{path})
    const series=info.series[0]
    if(!series)throw new Error('文件没有可读取的图像序列')
    const axes=series.requires_axes_mapping?'':series.axes
    next.push({path,info,series:series.index,axes,channels:Array.from({length:series.channel_count},(_,i)=>i),indexers:planes(axes,series.shape)})
   }
   setSources(next)
   const size=next[0]?.info.series[0]?.pixel_size_um
   setPx(size?String(size[0]):'')
   setPy(size?String(size[1]):'')
  }catch(e){
   setError(e instanceof Error?e.message:String(e))
  }finally{
   setWorking(false)
  }
 }
 function editPaths(text:string){
  setPaths(text)
  setSources([])
  setConfirmed(false)
  setError('')
 }
 async function submit(){
  setSubmitting(true)
  setError('')
  try{
   const selections=sources.map(s=>({
    path:s.path,series_index:s.series,indexers:s.indexers,
    axes_override:s.axes===s.info.series.find(v=>v.index===s.series)?.axes?null:s.axes,
    channel_indices:s.channels,
   }))
   await onImport(selections,{...meta,pixel_size_um:px?[Number(px),Number(py)]:null})
  }catch(e){
   setError(e instanceof Error?e.message:String(e))
  }finally{
   setSubmitting(false)
  }
 }
 function patch(i:number,change:Partial<Source>){setSources(v=>v.map((s,j)=>i===j?{...s,...change}:s));setConfirmed(false)}
 async function choose(){try{const paths=await open({multiple:true,filters:[{name:'二维显微图像',extensions:['tif','tiff','png']}]});if(paths){const text=(Array.isArray(paths)?paths:[paths]).join('\n');setPaths(text);await inspect(text)}}catch(e){setError(String(e))}}
 const valid=sources.length>0&&sources.every(s=>s.axes.includes('Y')&&s.axes.includes('X')&&s.channels.length>0)&&!!meta.sample_id.trim()&&!!meta.bio_id.trim()&&!!meta.group.trim()&&!!meta.batch_id.trim()&&confirmed&&((!px&&!py)||(Number(px)>0&&Number(py)>0))
 return <div className="modal-backdrop"><section className="modal if-import" role="dialog" aria-modal="true" aria-label="导入 IF 视野"><header><h2>导入 IF 视野</h2><button className="icon-btn" aria-label="关闭导入" disabled={submitting} onClick={onClose}>×</button></header><p className="hint">单个多通道文件，或同一视野的分通道文件。每次导入一个二维视野，明确选择序列及 Z / T 平面。</p><div className="if-paths"><label>原始文件路径（每行一个）<textarea aria-label="IF 原始文件路径" value={paths} disabled={working||submitting} readOnly={!!initialPaths} onChange={e=>editPaths(e.target.value)}/></label>{!initialPaths&&<button className="btn secondary" disabled={working||submitting} onClick={choose}>选择图像文件</button>}<button className="btn secondary" disabled={working||submitting||!paths.trim()} onClick={()=>inspect(paths)}>读取图像信息</button></div>
 {sources.map((source,i)=>{const s=source.info.series.find(s=>s.index===source.series)!;return <fieldset key={source.path} disabled={submitting}><legend>{source.info.name}</legend><div className="if-form-grid"><label>图像序列<select aria-label="图像序列" value={source.series} onChange={e=>{const s=source.info.series.find(s=>s.index===Number(e.target.value))!;patch(i,{series:s.index,axes:s.requires_axes_mapping?'':s.axes,channels:Array.from({length:s.channel_count},(_,i)=>i),indexers:planes(s.requires_axes_mapping?'':s.axes,s.shape)});if(i===0){setPx(s.pixel_size_um?String(s.pixel_size_um[0]):'');setPy(s.pixel_size_um?String(s.pixel_size_um[1]):'')}}}>{source.info.series.map(s=><option key={s.index} value={s.index}>{s.index} · {s.axes} [{s.shape.join(' × ')}] · {s.dtype}</option>)}</select></label><label>确认维度轴<input aria-label={`维度轴 ${i+1}`} value={source.axes} placeholder={s.requires_axes_mapping?'请填写，如 CYX':s.axes} onChange={e=>patch(i,{axes:e.target.value.toUpperCase(),indexers:planes(e.target.value.toUpperCase(),s.shape,source.indexers)})}/></label>{[...source.axes].filter(a=>'TZ'.includes(a)).map(a=><label key={a}>{a} 平面（从 0 开始）<input type="number" min="0" max={(s.shape[source.axes.indexOf(a)]??1)-1} value={source.indexers[a]??0} onChange={e=>patch(i,{indexers:{...source.indexers,[a]:Number(e.target.value)}})}/></label>)}</div><div className="if-check-row">{Array.from({length:source.axes.includes('C')?(s.shape[source.axes.indexOf('C')]??s.channel_count):s.channel_count},(_,c)=><label key={c}><input type="checkbox" checked={source.channels.includes(c)} onChange={e=>patch(i,{channels:e.target.checked?[...source.channels,c]:source.channels.filter(v=>v!==c)})}/>{s.channel_names[c]||`通道 ${c+1}`}</label>)}</div><p className="hint">{s.width} × {s.height} px · {s.quantitative?'原始强度可定量':'仅组图：彩色图像不参与强度定量'}{s.requires_axes_mapping?' · 维度不明确，必须手动确认轴映射':''}</p></fieldset>})}
 {!!sources.length&&<><fieldset disabled={submitting}><legend>本视野样本信息</legend><div className="if-form-grid">{Object.entries({name:'视野名称',sample_id:'样本编号',bio_id:'生物学样本编号',group:'实验分组',batch_id:'采集批次'}).map(([key,label])=><label key={key}>{label}<input aria-label={label} value={meta[key as keyof typeof meta]} onChange={e=>setMeta({...meta,[key]:e.target.value})}/></label>)}<label>X 像素尺寸（µm，可空）<input type="number" min="0" step="any" value={px} onChange={e=>setPx(e.target.value)}/></label><label>Y 像素尺寸（µm，可空）<input type="number" min="0" step="any" value={py} onChange={e=>setPy(e.target.value)}/></label></div></fieldset><label className="if-confirm"><input type="checkbox" disabled={submitting} checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>已确认所选文件属于同一视野，通道对应及 Z / T 平面正确</label></>}
 {error&&<p role="alert" className="library-error">{error}</p>}<footer><button className="btn secondary" disabled={submitting} onClick={onClose}>取消</button><button className="btn primary" disabled={!valid||working||submitting} onClick={submit}>确认并导入视野</button></footer></section></div>
}
