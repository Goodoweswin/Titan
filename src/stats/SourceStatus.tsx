import {useEffect,useState} from 'react'
import {callEngine} from '../bridge'
import type {Dataset} from './types'

export default function SourceStatus({source,active,frozen,busy,onReturn,onUpdate,onCopy}:{
 source:NonNullable<Dataset['source']>;active:boolean;frozen:boolean;busy:boolean;
 onReturn:()=>void;onUpdate:()=>void;onCopy:()=>void;
}){
 const [status,setStatus]=useState<{state:string;message:string}|null>(null),[checking,setChecking]=useState(false),[tick,setTick]=useState(0)
 useEffect(()=>{
  if(!active||frozen)return
  let cancelled=false,request=0
  const check=()=>{const token=++request;setChecking(true);callEngine<{state:string;message:string}>('stats_source_status',{source}).then(s=>{if(!cancelled&&token===request)setStatus(s)}).catch(e=>{if(!cancelled&&token===request)setStatus({state:'unavailable',message:String(e)})}).finally(()=>{if(!cancelled&&token===request)setChecking(false)})}
  setStatus(null);check();window.addEventListener('focus',check)
  return()=>{cancelled=true;window.removeEventListener('focus',check)}
 },[active,frozen,source.path,source.signature,tick])
 return <div className="stats-source">
  <strong>{source.kind==='if'?'IF':'WB'} 来源：{source.project_name??''} · {source.endpoint} · {source.block} · 版本 {source.revision}</strong>
  {!frozen&&status&&<p role="status" className={status.state==='current'?'hint':'library-error'}>{status.message}</p>}
  {source.blocked&&<p className="library-error">{source.blocked}</p>}
  <div className="stats-source-actions"><button className="text-btn" disabled={busy||!source.path} onClick={onReturn}>返回 {source.kind==='if'?'IF':'WB'}</button>
   {!frozen&&<><button className="text-btn" disabled={busy||checking} onClick={()=>setTick(v=>v+1)}>{checking?'正在检查来源…':'检查来源更新'}</button><button className="text-btn" disabled={busy||checking||status?.state==='unavailable'} onClick={onUpdate}>用当前 {source.kind==='if'?'IF':'WB'} 更新</button></>}
   <button className="text-btn" disabled={busy} onClick={onCopy}>复制为可编辑表</button></div>
  {source.notes?.map((note,i)=><p className="hint" key={i}>{note}</p>)}
 </div>
}
