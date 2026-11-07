import {useRef,useEffect,useState} from 'react'
import {open} from '@tauri-apps/plugin-dialog'
import {callEngine} from '../bridge'
import type {Dataset} from './types'

export default function ToolImport({initialPath,onClose,onImport}:{
 initialPath?:string;onClose:()=>void;onImport:(name:string,dataset:Dataset)=>Promise<void>
}){
 const dialog=useRef<HTMLDialogElement>(null)
 const [path,setPath]=useState(initialPath??''),[content,setContent]=useState('')
 const [format,setFormat]=useState<'wide'|'long'>('wide'),[sheet,setSheet]=useState('')
 const [parsed,setParsed]=useState<{dataset:Dataset;sheets:string[]}|null>(null)
 const [error,setError]=useState(''),[busy,setBusy]=useState(false)
 useEffect(()=>{dialog.current?.showModal()},[])
 async function inspect(file=path,worksheet=sheet){
  setBusy(true);setError('');setParsed(null)
  try{setParsed(await callEngine('stats_import',file?{path:file,sheet:worksheet||undefined,format}:{text:content,format}))}
  catch(e){setError(String(e))}
  finally{setBusy(false)}
 }
 async function pick(){
  try{
   const selected=await open({filters:[{name:'表格',extensions:['xlsx','csv','tsv','txt']}]})
   if(typeof selected==='string'){setPath(selected);setSheet('');await inspect(selected,'')}
  }catch(e){setError(String(e))}
 }
 async function submit(){
  if(!parsed)return
  setBusy(true);setError('')
  try{await onImport(Array.from(path.split(/[\\/]/).pop()?.replace(/\.[^.]+$/,'').trim()??'').slice(0,120).join('')||'导入数据',parsed.dataset)}
  catch(e){setError(String(e))}
  finally{setBusy(false)}
 }
 return <dialog className="library-dialog tool-import-dialog" ref={dialog} aria-label="导入统计数据"
  onCancel={e=>{e.preventDefault();if(!busy)onClose()}}>
  <form onSubmit={e=>{e.preventDefault();void (parsed?submit():inspect())}}>
   <h2>导入统计数据</h2>
   <label>数据排列<select value={format} disabled={busy} onChange={e=>{setFormat(e.target.value as 'wide'|'long');setParsed(null)}}>
    <option value="wide">宽表：每列一组</option><option value="long">长表：group / value / unit_id</option>
   </select></label>
   {!initialPath&&<label>表格路径<input value={path} disabled={busy} onChange={e=>{setPath(e.target.value);setSheet('');setParsed(null)}}/></label>}
   {initialPath&&<p>项目资料：{initialPath.split(/[\\/]/).pop()}</p>}
   {!initialPath&&Boolean((window as any).__TAURI_INTERNALS__)&&<button type="button" className="btn secondary" disabled={busy} onClick={pick}>选择表格</button>}
   {!path&&<label>或粘贴表格<textarea rows={5} value={content} disabled={busy} onChange={e=>{setContent(e.target.value);setParsed(null)}}/></label>}
   {parsed&&parsed.sheets.length>1&&<label>工作表<select value={sheet||parsed.sheets[0]} disabled={busy}
    onChange={e=>{setSheet(e.target.value);void inspect(path,e.target.value)}}>
    {parsed.sheets.map(name=><option key={name}>{name}</option>)}
   </select></label>}
   {parsed&&<p role="status">读到 {parsed.dataset.groups.length} 组，{parsed.dataset.rows.length} 行。确认后创建分析。</p>}
   {error&&<p className="library-error" role="alert">{error}</p>}
   <footer><button type="button" className="btn secondary" disabled={busy} onClick={onClose}>取消</button>
    <button type="submit" className="btn primary" disabled={busy||(!path.trim()&&!content.trim())}>
     {busy?'处理中…':parsed?'确认并创建分析':'预览数据'}
    </button></footer>
  </form>
 </dialog>
}
