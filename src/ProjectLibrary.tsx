import {useEffect,useRef,useState} from 'react'
import type {KeyboardEvent,MouseEvent} from 'react'
import {useActionMenu,type ActionMenuItem} from './ActionMenu'
import {ChevronRight,Ellipsis,Folder,FileBarChart2,FlaskConical,Search,Images,Plus,Pin} from 'lucide-react'
import type {LibraryArtifact,LibraryCollection,LibraryEntry} from './types'
import type {LibraryDialog} from './LibraryCreateDialog'

export type LibraryView='workspace'|'results'|'wb'
interface Props {
 entries:LibraryEntry[]
 projects:LibraryCollection[]
 selectedProjectId?:string
 onProject:(id:string)=>void
 onOpenBundle:()=>void
 activeEntry?:LibraryEntry
 activeFigure:string
 error:string
 busy?:boolean
 onOpen:(entry:LibraryEntry,view?:LibraryView,figureId?:string)=>void
 onRelocate:(entry:LibraryEntry)=>void
 onRetry:()=>void
 onDialog:(dialog:LibraryDialog)=>void
 onOpenFile:()=>void
 onPin:(project:LibraryCollection)=>void
 onArtifact:(entry:LibraryEntry,artifact:LibraryArtifact)=>void
 onReveal:(entry:LibraryEntry,artifact?:LibraryArtifact)=>void
}

export default function ProjectLibrary({entries,projects,selectedProjectId,onProject,onOpenBundle,activeEntry,activeFigure,error,busy,onOpen,onRelocate,onRetry,onDialog,onOpenFile,onPin,onArtifact,onReveal}:Props){
 const [query,setQuery]=useState('')
 const [expanded,setExpanded]=useState<string[]>(['unassigned'])
 const {openMenu,closeMenu,activeId}=useActionMenu()
 const stateKey=JSON.stringify([entries,projects,selectedProjectId,activeEntry?.entry_id,activeFigure,busy])
 const live=useRef({key:stateKey,busy});live.current={key:stateKey,busy}
 useEffect(()=>{if(busy||activeId!=='create')closeMenu()},[stateKey,closeMenu])
 const active=activeEntry
 useEffect(()=>{
  if(selectedProjectId)setExpanded(previous=>previous.includes(selectedProjectId)?previous:[...previous,selectedProjectId])
 },[selectedProjectId])
 const q=query.trim().toLocaleLowerCase()
 const matches=(name:string)=>name.toLocaleLowerCase().includes(q)
 const groups=projects.map(collection=>({
  collection, id:collection.id, name:collection.name,
  entries:entries.filter(entry=>entry.collection_id===collection.id),
 }))
 // Opening an analysis updates last_opened for resume without moving the sidebar rows.
 groups.sort((a,b)=>Number(b.collection.pinned)-Number(a.collection.pinned)||
  b.collection.created_at.localeCompare(a.collection.created_at)||a.id.localeCompare(b.id))
 const toggle=(ids:string[],id:string)=>ids.includes(id)?ids.filter(value=>value!==id):[...ids,id]
 function item(id:string,label:string,callback:()=>void,disabled=false,contextual=true):ActionMenuItem{
  const key=stateKey
  return {id,label,disabled,onSelect:()=>{if((!contextual||live.current.key===key)&&!live.current.busy)callback()}}
 }
 function showMenu(id:string,label:string,items:ActionMenuItem[],origin:HTMLElement,position:{x:number;y:number}){
  if(!busy)openMenu({id,label,items,origin,position})
 }
 function keyboardMenu(event:KeyboardEvent<HTMLElement>,id:string,label:string,items:ActionMenuItem[]){
  if(event.key!=='ContextMenu'&&!(event.shiftKey&&event.key==='F10'))return
  event.preventDefault();event.stopPropagation()
  const origin=(event.target as HTMLElement).closest<HTMLElement>('button:not(:disabled)')??event.currentTarget
  const box=origin.getBoundingClientRect();showMenu(id,label,items,origin,{x:box.left,y:box.bottom})
 }
 function rowMenu(id:string,label:string,items:ActionMenuItem[]){
  return {tabIndex:-1,onContextMenu:(event:MouseEvent<HTMLElement>)=>{
   event.preventDefault();event.stopPropagation()
   const origin=(event.target as HTMLElement).closest<HTMLElement>('button:not(:disabled)')??event.currentTarget
   showMenu(id,label,items,origin,{x:event.clientX,y:event.clientY})
  },onKeyDown:(event:KeyboardEvent<HTMLElement>)=>keyboardMenu(event,id,label,items)}
 }
 function popup(id:string,label:string,items:ActionMenuItem[]){
  return <div className="library-popup-anchor">
   <button type="button" className="icon-btn library-menu-button" aria-label={label} data-action-menu-trigger={id}
    aria-haspopup="menu" aria-expanded={activeId===id} disabled={busy}
    onKeyDown={event=>keyboardMenu(event,id,label,items)}
    onClick={event=>{if(activeId===id)closeMenu();else{const box=event.currentTarget.getBoundingClientRect();showMenu(id,label,items,event.currentTarget,{x:box.left,y:box.bottom+4})}}}><Ellipsis size={16}/></button>
  </div>
 }
 function analysisRow(entry:LibraryEntry){
  const selected=active?.entry_id===entry.entry_id
  const items=[item('open','打开分析',()=>entry.available?onOpen(entry):onRelocate(entry)),
   item('move','移到项目',()=>onDialog({kind:'move',entry})),
   ...(entry.collection_id?[item('detach','移出项目',()=>onDialog({kind:'detach',entry}))]:[]),
   item('reveal','在文件管理器中显示',()=>onReveal(entry),!entry.available),
   ...(entry.figure_error?[item('error',entry.figure_error,()=>{},true)]:[])]
  const id='entry-'+entry.entry_id,label='分析菜单 '+entry.name
  return <div key={entry.entry_id} className={selected?'library-root library-analysis active':'library-root library-analysis'} {...rowMenu(id,label,items)}>
   <button className="library-title" title={entry.error??entry.name} aria-label={`打开分析 ${entry.name}`}
    aria-current={selected?'page':undefined} disabled={busy} onClick={()=>entry.available?onOpen(entry):onRelocate(entry)}>
    <span>{entry.name}</span><small>{entry.module==='stats'?'统计':entry.module==='if'?'IF':'WB'}</small>
    {!entry.available&&<small>需定位</small>}
   </button>
   {popup(id,label,items)}
  </div>
 }
 function artifactRow(entry:LibraryEntry,artifact:LibraryArtifact,legacy=false){
  const document=artifact.kind==='wb_figure'||artifact.kind==='stats_plot'
  const disabled=busy||(document?!entry.available:!artifact.available&&!artifact.document_id)
  const id=entry.entry_id+':'+artifact.id,label=(legacy?'图表菜单 ':'产物菜单 ')+artifact.title
  const items=[item('open',document||legacy?'打开图表':'打开导出',()=>onArtifact(entry,artifact),!!disabled),
   item('source','打开源分析',()=>onOpen(entry,'workspace'),!entry.available),
   ...(artifact.destination?[item('reveal','在文件管理器中显示',()=>onReveal(entry,artifact),!artifact.available)]:[])]
  return <div className="library-artifact-row" key={id} {...rowMenu(id,label,items)}>
   <button className={active?.entry_id===entry.entry_id&&(activeFigure===artifact.id||activeFigure===artifact.document_id)?'selected':''}
    title={`${entry.name} · ${artifact.source_revision===null?'图形版本 '+artifact.version_id:'源版本 '+artifact.source_revision}`}
    aria-label={`${legacy?'打开图表':document?'打开组图':'打开导出'} ${artifact.title}`} disabled={disabled}
    onClick={()=>onArtifact(entry,artifact)}>
    {document?<Images size={14}/>:<FileBarChart2 size={14}/>}
    <span>{artifact.title}<small>{entry.name}{!legacy&&(artifact.source_revision===null?' · 组图':` · 版本 ${artifact.source_revision}`)}</small></span>
    {legacy&&entry.figures.find(figure=>figure.id===artifact.id)?.source_stale&&<small>旧版本</small>}
    {!document&&!legacy&&!artifact.available&&<small>文件缺失</small>}
   </button>{popup(id,label,items)}
  </div>
 }
 function collectionRows(id:string,name:string,rows:LibraryEntry[],collection?:LibraryCollection){
  const shown=rows.filter(entry=>matches(name)||matches(entry.name)||entry.figures.some(figure=>matches(figure.name))||entry.artifacts?.some(artifact=>matches(artifact.title)))
   .sort((a,b)=>(b.created_at??'').localeCompare(a.created_at??'')||a.entry_id.localeCompare(b.entry_id))
  if(q&&!matches(name)&&!shown.length)return null
  const open=!!q||expanded.includes(id)
  const selected=selectedProjectId===id||(!open&&rows.some(entry=>entry.entry_id===active?.entry_id))
  const projectItems=collection?[item('open','打开项目',()=>onProject(id)),
   item('new','新建分析',()=>onDialog({kind:'choose',collectionId:id})),
   item('rename','重命名',()=>onDialog({kind:'rename',project:collection})),
   item('pin',collection.pinned?'取消置顶':'置顶',()=>onPin(collection)),
   item('remove','移出项目列表',()=>onDialog({kind:'remove',project:collection}))]:[]
  const outputs=shown.flatMap(entry=>(entry.artifacts??[])
   .filter(artifact=>matches(name)||matches(entry.name)||matches(artifact.title))
   .map(artifact=>({entry,artifact})))
  const figures=shown.flatMap(entry=>entry.figures.filter(figure=>
   (matches(name)||matches(entry.name)||matches(figure.name))&&
   !outputs.some(({entry:owner,artifact})=>owner.entry_id===entry.entry_id&&
      artifact.document_id===figure.id&&artifact.kind==='result_export')
  ).map(figure=>({entry,figure})))
  return <section key={id} className="library-collection" aria-label={name}>
   <div className={selected?'library-root active':'library-root'} {...(collection?rowMenu(id,'项目菜单 '+name,projectItems):{})}>
    {collection?<><button className="library-chevron" aria-label={`${open?'收起':'展开'}项目 ${name}`} aria-expanded={open}
     onClick={()=>setExpanded(previous=>toggle(previous,id))}><ChevronRight size={13} className={open?'expanded':''}/></button>
     <button className="library-title" title={name} aria-label={`打开项目 ${name}`} aria-current={selectedProjectId===id?'page':undefined}
      disabled={busy} onClick={()=>onProject(id)}><Folder size={15}/><span>{name}</span>{collection.pinned&&<Pin size={12}/>}</button></>:
     <button className="library-title library-section-toggle" aria-expanded={open} onClick={()=>setExpanded(previous=>toggle(previous,id))}>
      <ChevronRight size={13} className={open?'expanded':''}/><span>{name}</span>
     </button>}
    {collection&&popup(id,'项目菜单 '+name,projectItems)}
   </div>
   {open&&<div className="library-collection-body">
    {shown.length>0?shown.map(analysisRow):<p className="hint library-empty">暂无分析</p>}
    {(figures.length>0||outputs.length>0)&&<><p className="library-section-label">图表与导出</p>
     <div className="library-children library-artifacts">{figures.map(({entry,figure})=>artifactRow(entry,{
      id:figure.id,entry_id:entry.entry_id,kind:'wb_plot',title:figure.name,available:entry.available,
      source_revision:figure.source_revision,document_id:figure.id,version_id:figure.selected_version,
     },true))}{outputs.map(({entry,artifact})=>artifactRow(entry,artifact))}</div>
    </>}
   </div>}
  </section>
 }
 const createItems=[item('project','新建项目',()=>onDialog({kind:'collection'}),false,false),
  ...(['wb','if','stats'] as const).map(kind=>item(kind,kind==='wb'?'新建 WB 分析':kind==='if'?'新建 IF 分析':'新建统计分析',()=>onDialog({kind}),false,false)),
  item('open','打开已有分析',onOpenFile,false,false),item('bundle','打开项目包',onOpenBundle,false,false)]
 return <nav className="project-library" aria-label="实验项目库">
  <label className="library-search"><Search size={14}/><input aria-label="搜索项目或图表" placeholder="搜索项目或图表" value={query} onChange={event=>setQuery(event.target.value)}/></label>
  <div className="library-heading"><span>项目</span><div className="library-popup-anchor">
   <button type="button" className="icon-btn library-menu-button" aria-label="新建或打开" title="新建或打开" data-action-menu-trigger="create" aria-haspopup="menu" aria-expanded={activeId==='create'} disabled={busy}
    onKeyDown={event=>keyboardMenu(event,'create','新建或打开',createItems)}
    onClick={event=>{if(activeId==='create')closeMenu();else{const box=event.currentTarget.getBoundingClientRect();showMenu('create','新建或打开',createItems,event.currentTarget,{x:box.left,y:box.bottom+4})}}}><Plus size={18}/></button>
  </div></div>
  <div className="library-scroll">
  {error&&<div className="library-error" role="alert"><p>项目列表暂不可用：{error}</p><button onClick={onRetry}>重试</button></div>}
  {!entries.length&&!projects.length&&!error&&<p className="hint library-empty">使用「＋」创建项目或分析。</p>}
  {groups.map(({id,name,entries,collection})=>collectionRows(id,name,entries,collection))}
  {collectionRows('unassigned','独立分析',entries.filter(entry=>!projects.some(collection=>collection.id===entry.collection_id)))}
  </div>
 </nav>
}
