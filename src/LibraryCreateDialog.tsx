import {useEffect,useRef,useState} from 'react'
import type {LibraryCollection,LibraryEntry} from './types'

export type CreationKind='collection'|'wb'|'if'
export interface AnalysisCreation {
 name:string
 collection_id?:string|null
 new_collection_name?:string
}

export type LibraryDialog =
 | {kind:CreationKind;collectionId?:string|null}
 | {kind:'rename';project:LibraryCollection}
 | {kind:'move';entry:LibraryEntry}
 | {kind:'remove';project:LibraryCollection}

export const creationLabels:Record<CreationKind,string>={
 collection:'新建项目',
 wb:'新建 WB 分析',
 if:'新建 IF 分析',
}

export default function LibraryCreateDialog({mode,projects,onClose,onSubmit}:{
 mode:LibraryDialog
 projects:LibraryCollection[]
 onClose:()=>void
 onSubmit:(data:AnalysisCreation)=>Promise<boolean>
}){
 const dialog=useRef<HTMLDialogElement>(null)
 const [name,setName]=useState(mode.kind==='rename'?mode.project.name:'')
 const [collectionId,setCollectionId]=useState(
  mode.kind==='move'?mode.entry.collection_id??'':
  mode.kind==='wb'||mode.kind==='if'?mode.collectionId??'':'')
 const [newCollection,setNewCollection]=useState('')
 const [busy,setBusy]=useState(false)
 const [error,setError]=useState('')
 const creating=mode.kind==='wb'||mode.kind==='if'
 const needsName=creating||mode.kind==='collection'||mode.kind==='rename'
 const needsProject=creating||mode.kind==='move'
 const title=mode.kind==='rename'?'重命名项目':mode.kind==='move'?'移到项目':mode.kind==='remove'?'移出项目':creationLabels[mode.kind]
 const action=mode.kind==='rename'?'保存':mode.kind==='move'?'移动':mode.kind==='remove'?'移出':'创建'
 const valid=(!needsName||!!name.trim())&&(collectionId!=='new'||!!newCollection.trim())

 useEffect(()=>{dialog.current?.showModal()},[])
 async function submit(){
  if(!valid||busy)return
  setBusy(true)
  setError('')
  try{
   const data={name:name.trim(),collection_id:collectionId&&collectionId!=='new'?collectionId:null,
    ...(collectionId==='new'?{new_collection_name:newCollection.trim()}:{})}
   if(await onSubmit(data))onClose()
  }catch(e){setError(String(e))}
  finally{setBusy(false)}
 }

 return <dialog ref={dialog} className="library-dialog" aria-labelledby="library-dialog-title"
  onCancel={event=>{event.preventDefault();if(!busy)onClose()}}>
  <form onSubmit={event=>{event.preventDefault();void submit()}}>
   <h2 id="library-dialog-title">{title}</h2>
   {needsName&&<label>名称<input autoFocus required maxLength={120} value={name} onChange={event=>setName(event.target.value)}/></label>}
   {needsProject&&<label>归属项目<select autoFocus={!needsName} value={collectionId} onChange={event=>setCollectionId(event.target.value)}>
    <option value="">未归类</option>
    {projects.map(project=><option value={project.id} key={project.id}>{project.name}</option>)}
    {creating&&<option value="new">＋ 新建项目</option>}
   </select></label>}
   {creating&&collectionId==='new'&&<label>新项目名称<input required maxLength={120} value={newCollection} onChange={event=>setNewCollection(event.target.value)}/></label>}
   {mode.kind==='remove'&&<p>「{mode.project.name}」中的分析会回到「未归类」，实验文件保留。</p>}
   {error&&<p className="library-error" role="alert">{error}</p>}
   <footer><button type="button" className="btn secondary" disabled={busy} onClick={onClose}>取消</button>
    <button type="submit" className="btn primary" disabled={busy||!valid}>{busy?'处理中…':action}</button></footer>
  </form>
 </dialog>
}
