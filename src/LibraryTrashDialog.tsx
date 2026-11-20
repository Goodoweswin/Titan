import {useEffect,useRef,useState} from 'react'
import {callEngine} from './bridge'

interface DeletedItem {
 id:string
 kind:'project'|'analysis'
 name:string
 deleted_at:string
}

export default function LibraryTrashDialog({onClose,onRestore}:{
 onClose:()=>void
 onRestore:(id:string)=>Promise<boolean>
}){
 const dialog=useRef<HTMLDialogElement>(null)
 const [items,setItems]=useState<DeletedItem[]|null>(null)
 const [busy,setBusy]=useState('')
 const [error,setError]=useState('')
 useEffect(()=>{
  dialog.current?.showModal()
  let active=true
  callEngine<DeletedItem[]>('library_trash').then(items=>{if(active)setItems(items)})
   .catch(error=>{if(active)setError(String(error))})
  return()=>{active=false}
 },[])
 async function restore(id:string){
  if(busy)return
  setBusy(id);setError('')
  try{if(await onRestore(id))setItems(items=>items?.filter(item=>item.id!==id)??null)}
  catch(error){setError(String(error))}
  finally{setBusy('')}
 }
 return <dialog ref={dialog} className="library-dialog library-trash-dialog" aria-labelledby="library-trash-title"
  onCancel={event=>{event.preventDefault();if(!busy)onClose()}}>
  <h2 id="library-trash-title">最近删除</h2>
  {error&&<p className="library-error" role="alert">{error}</p>}
  {!items&&!error&&<p role="status">正在读取…</p>}
  {items?.length===0&&<p>暂无删除记录。</p>}
  {!!items?.length&&<ul>{items.map(item=><li key={item.id}>
   <div><strong>{item.name}</strong><small>{item.kind==='project'?'项目':'分析'} · {new Date(item.deleted_at).toLocaleDateString()}</small></div>
   <button type="button" className="btn secondary" aria-label={`恢复 ${item.name}`} disabled={!!busy}
    onClick={()=>void restore(item.id)}>{busy===item.id?'恢复中…':'恢复'}</button>
  </li>)}</ul>}
  <footer><button autoFocus type="button" className="btn secondary" disabled={!!busy} onClick={onClose}>关闭</button></footer>
 </dialog>
}
