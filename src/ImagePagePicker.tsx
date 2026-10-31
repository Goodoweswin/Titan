import {useEffect,useRef,useState} from 'react'
import {callEngine} from './bridge'
import type {ImageInspection} from './types'

export default function ImagePagePicker({path,info,onChoose}:{path:string;info:ImageInspection;onChoose:(pages:number[]|null)=>void}){
 const dialog=useRef<HTMLDialogElement>(null)
 const [selected,setSelected]=useState<number[]>([])
 const [active,setActive]=useState(info.pages.find(p=>!p.error)?.page_index??0)
 const [response,setResponse]=useState<{page:number;src?:string;error?:string}|null>(null)
 const page=info.pages[active],shown=response?.page===active?response:null
 useEffect(()=>{dialog.current?.showModal()},[])
 useEffect(()=>{
  if(page.error)return
  let cancelled=false
  callEngine<string>('preview_image_page',{path,page_index:active,expected_sha256:info.sha256})
   .then(src=>{if(!cancelled)setResponse({page:active,src})})
   .catch(error=>{if(!cancelled)setResponse({page:active,error:String(error)})})
  return()=>{cancelled=true}
 },[path,info.sha256,active,page.error])
 return <dialog ref={dialog} className="export-dialog image-pages-dialog" aria-labelledby="image-pages-title" onCancel={e=>{e.preventDefault();onChoose(null)}}>
  <div className="card-heading"><div><h2 id="image-pages-title">选择 TIFF 页面</h2><p className="hint">{info.name} · 共 {info.page_count} 页</p></div><button className="btn secondary" onClick={()=>onChoose(null)}>跳过此文件</button></div>
  <p>预览并勾选需要的灰度页。每页将作为独立图像导入，保留原始位深和页码。</p>
  <div className="image-pages-layout"><div><button className="text-btn" onClick={()=>setSelected(info.pages.filter(p=>!p.error).map(p=>p.page_index))}>全选可用页</button><div className="image-pages-list">{info.pages.map(p=><div key={p.page_index} className={`image-page-row ${p.page_index===active?'selected':''}`}>
   <input type="checkbox" aria-label={`导入第 ${p.page_index+1} 页`} disabled={!!p.error} checked={selected.includes(p.page_index)} onChange={e=>{setSelected(s=>e.target.checked?[...s,p.page_index]:s.filter(i=>i!==p.page_index));setActive(p.page_index)}}/>
   <button className="text-btn" aria-label={`预览第 ${p.page_index+1} 页`} aria-pressed={p.page_index===active} onClick={()=>setActive(p.page_index)}><strong>第 {p.page_index+1} 页</strong><span>{p.width} × {p.height} · {p.dtype}</span>{p.error&&<small>无法用于定量：{p.error}</small>}</button>
  </div>)}</div></div><div className="export-canvas image-page-preview">{page.error?<p role="status">此页无法用于定量：{page.error}</p>:shown?.error?<p role="alert">{shown.error}</p>:shown?.src?<img src={shown.src} style={{filter:page.display_inverted?'invert(1)':'none'}} alt={`第 ${active+1} 页预览`}/>:<p role="status">正在读取第 {active+1} 页…</p>}</div></div>
  <p className="hint">预览单独拉伸亮度，定量读取所选页的原始像素。不同页可能来自不同曝光或通道，请核对采集记录。</p>
  <div className="export-actions"><button className="btn primary" disabled={!selected.length} onClick={()=>onChoose([...selected].sort((a,b)=>a-b))}>导入所选页面</button></div>
 </dialog>
}
