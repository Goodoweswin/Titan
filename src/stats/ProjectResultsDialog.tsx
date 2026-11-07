import {useEffect,useRef,useState} from 'react'
import {open} from '@tauri-apps/plugin-dialog'
import {callEngine} from '../bridge'
import type {LibraryCollection,LibraryEntry} from '../types'
import type {SourceCatalog} from './types'

export default function ProjectResultsDialog({entries,projects,initialPath,initialCollectionId,currentName,appendByDefault,busy,onClose,onImport}:{
 entries:LibraryEntry[];projects:LibraryCollection[];initialPath?:string;initialCollectionId?:string|null;currentName?:string;appendByDefault:boolean;busy:boolean;onClose:()=>void;
 onImport:(catalog:SourceCatalog,keys:string[],append:boolean,collectionId:string|null)=>Promise<void>;
}){
 const [path,setPath]=useState(initialPath??''),[catalog,setCatalog]=useState<SourceCatalog|null>(null)
 const dialog=useRef<HTMLDialogElement>(null)
 useEffect(()=>{dialog.current?.showModal()},[])
 const [keys,setKeys]=useState<string[]>([]),[confirmed,setConfirmed]=useState(false),[append,setAppend]=useState(!!currentName&&appendByDefault)
 const [collectionId,setCollectionId]=useState(initialCollectionId??'')
 const [loading,setLoading]=useState(false),[error,setError]=useState(''),generation=useRef(0)
 async function inspect(next=path){
  const token=++generation.current;setPath(next);setLoading(true);setError('');setCatalog(null);setKeys([]);setConfirmed(false)
  try{const data=await callEngine<SourceCatalog>('stats_source_catalog',{path:next});if(token!==generation.current)return;setCatalog(data)}
  catch(e){if(token===generation.current)setError(String(e))}
  finally{if(token===generation.current)setLoading(false)}
 }
 useEffect(()=>{if(initialPath)void inspect(initialPath);return()=>{generation.current++}},[initialPath])
 async function choose(){try{const selected=await open({directory:true,title:'选择 WB / IF 项目'});if(typeof selected==='string')await inspect(selected)}catch(e){setError(String(e))}}
 const disabled=busy||loading
 return <dialog className="modal stats-source-dialog stats-source-modal" ref={dialog} aria-label="从项目读取结果" onCancel={e=>{e.preventDefault();if(!busy)onClose()}}>
  <header><h2>从项目读取结果</h2><button className="icon-btn" aria-label="关闭项目结果选择" disabled={busy} onClick={onClose}>×</button></header>
  <p className="hint">读取已保存的分析结果。选择指标后生成关联数据表，保留原项目与来源版本。</p>
  <label>项目库<select aria-label="结果来源项目" value={entries.some(e=>e.path===path)?path:''} disabled={disabled} onChange={e=>void inspect(e.target.value)}>
   <option value="" disabled>选择 WB 或免疫荧光项目</option>
   {entries.filter(e=>e.module!=='stats').map(e=><option value={e.path} key={e.entry_id} disabled={!e.available}>{e.module==='if'?'IF':'WB'} · {e.name}{!e.available?'（路径不可用）':''}</option>)}
  </select></label>
  <div className="stats-source-path"><label>或选择项目目录<input aria-label="结果来源路径" value={path} disabled={disabled} onChange={e=>{generation.current++;setPath(e.target.value);setCatalog(null);setKeys([]);setConfirmed(false)}}/></label>
   <button className="btn secondary" disabled={disabled||!path.trim()} onClick={()=>inspect()}>读取项目结果</button>
   {!!(window as any).__TAURI_INTERNALS__&&<button className="btn secondary" disabled={disabled} onClick={choose}>浏览项目</button>}</div>
  {loading&&<p role="status">正在读取已保存的结果…</p>}
  {error&&<p role="alert" className="library-error">{error}</p>}
  {catalog&&<><p className="stats-source-meta">{catalog.name} · {catalog.kind==='if'?'免疫荧光':'Western blot'} · 来源版本 {catalog.revision}</p>
   {!catalog.choices.length&&<p role="status">还没有可读取的定量指标，请先回原模块完成测量并保存。</p>}
   <div className="stats-source-choices">{catalog.choices.map(c=><article key={c.key} className={c.unavailable?'unavailable':''}>
    <label className="stats-source-select"><input type="checkbox" aria-label={`选择指标 ${c.label}`} checked={keys.includes(c.key)} disabled={disabled||c.unavailable} onChange={e=>{setKeys(v=>e.target.checked?[...v,c.key]:v.filter(k=>k!==c.key));setConfirmed(false)}}/><strong>{c.label}</strong></label>
    <p>{c.groups.map(g=>`${g.name}: n=${g.n}`).join(' · ')} · 缺失 {c.missing} 个样本值 · 单位 {c.unit}</p>
    {c.reason&&<p className="library-error">{c.reason}</p>}
    {keys.includes(c.key)&&<><details><summary>查看样本预览与汇总规则</summary><table className="stats-results"><thead><tr><th>生物学样本</th><th>分组</th><th>数值</th><th>缺失原因</th></tr></thead><tbody>{c.preview.map((r,i)=><tr key={i}><td>{r.bio_id}</td><td>{r.group}</td><td>{r.value==null?'缺失':Number(r.value).toLocaleString(undefined,{maximumSignificantDigits:6})}</td><td>{r.missing_reason||'—'}</td></tr>)}</tbody></table>{c.notes.map((n,i)=><p className="hint" key={i}>{n}</p>)}</details>
     {c.missing>0&&<p className="library-error">存在缺失样本值；不会补零或将未完成视野当作完整样本。</p>}</>}
   </article>)}</div>
   {currentName&&<label>保存到<select aria-label="结果读取目标" value={append?'current':'new'} disabled={disabled} onChange={e=>setAppend(e.target.value==='current')}><option value="current">添加到：{currentName}</option><option value="new">新建统计分析</option></select></label>}
   {!append&&<label>归属项目<select value={collectionId} disabled={disabled} onChange={e=>setCollectionId(e.target.value)}><option value="">独立分析</option>{projects.map(project=><option key={project.id} value={project.id}>{project.name}</option>)}</select></label>}
   <label className="stats-confirm"><input type="checkbox" aria-label="确认来源统计单位" checked={confirmed} disabled={disabled||!keys.length} onChange={e=>setConfirmed(e.target.checked)}/>我已核对指标、分组、有效样本数与缺失情况；每个数值代表一个生物学样本。</label>
  </>}
  <footer><button className="btn secondary" disabled={busy} onClick={onClose}>取消</button><button className="btn primary" disabled={disabled||!catalog||!keys.length||!confirmed} onClick={async()=>{try{await onImport(catalog!,keys,append,collectionId||null)}catch(e){setError(String(e));setConfirmed(false)}}}>读取所选结果</button></footer>
 </dialog>
}
