import {useEffect,useState} from 'react'
import {ChevronRight,Ellipsis,Folder,FileBarChart2,FlaskConical,Search,Table2,Images,Plus,Pin} from 'lucide-react'
import type {LibraryArtifact,LibraryCollection,LibraryEntry} from './types'
import type {LibraryDialog} from './LibraryCreateDialog'

export type LibraryView='workspace'|'results'|'wb'
interface Props {
 entries:LibraryEntry[]
 projects:LibraryCollection[]
 selectedProjectId?:string
 onProject:(id:string)=>void
 onOpenBundle:()=>void
 project:{project_path?:string|null}|null
 activeFigure:string
 currentView:LibraryView
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

export default function ProjectLibrary({entries,projects,selectedProjectId,onProject,onOpenBundle,project,activeFigure,currentView,error,busy,onOpen,onRelocate,onRetry,onDialog,onOpenFile,onPin,onArtifact,onReveal}:Props){
 const [query,setQuery]=useState('')
 const [expanded,setExpanded]=useState<string[]>(['unassigned'])
 const [expandedEntries,setExpandedEntries]=useState<string[]>([])
 const [menu,setMenu]=useState('')
 const active=entries.find(entry=>entry.path===project?.project_path)
 useEffect(()=>{
  if(!active)return
  const group=active.collection_id??'unassigned'
  setExpanded(previous=>previous.includes(group)?previous:[...previous,group])
  setExpandedEntries(previous=>previous.includes(active.entry_id)?previous:[...previous,active.entry_id])
 },[active?.entry_id,active?.collection_id])
 useEffect(()=>{
  if(selectedProjectId)setExpanded(previous=>previous.includes(selectedProjectId)?previous:[...previous,selectedProjectId])
 },[selectedProjectId])
 const q=query.trim().toLocaleLowerCase()
 const matches=(name:string)=>name.toLocaleLowerCase().includes(q)
 const groups=projects.map(collection=>({
  collection, id:collection.id, name:collection.name,
  entries:entries.filter(entry=>entry.collection_id===collection.id),
 }))
 const order=(group:typeof groups[number])=>group.entries[0]?.last_opened??group.collection.created_at
 groups.sort((a,b)=>Number(b.collection.pinned)-Number(a.collection.pinned)||order(b).localeCompare(order(a)))
 const toggle=(ids:string[],id:string)=>ids.includes(id)?ids.filter(value=>value!==id):[...ids,id]
 function action(callback:()=>void){setMenu('');callback()}
 function popup(id:string,label:string,children:React.ReactNode){
  return <div className="library-popup-anchor">
   <button type="button" className="icon-btn library-menu-button" aria-label={label}
    aria-expanded={menu===id} disabled={busy} onClick={()=>setMenu(menu===id?'':id)}><Ellipsis size={16}/></button>
   {menu===id&&<div className="library-popup">{children}</div>}
  </div>
 }
 function analysisRow(entry:LibraryEntry){
  const selected=active?.entry_id===entry.entry_id
  const open=expandedEntries.includes(entry.entry_id)||!!q
  return <div className="library-project" key={entry.entry_id}>
   <div className={selected?'library-root active':'library-root'}>
    <button className="library-chevron" aria-label={`${open?'收起':'展开'}分析 ${entry.name}`} aria-expanded={open}
     onClick={()=>setExpandedEntries(previous=>toggle(previous,entry.entry_id))}><ChevronRight size={13} className={open?'expanded':''}/></button>
    <button className="library-title" title={entry.path} aria-label={`打开分析 ${entry.name}`} aria-current={selected?'page':undefined}
     disabled={busy} onClick={()=>entry.available?onOpen(entry):onRelocate(entry)}>
     <FlaskConical size={14}/><span>{entry.name}</span><small>{entry.module==='stats'?'统计':entry.module==='if'?'IF':'WB'}</small>
     {!entry.available&&<small>需定位</small>}
    </button>
    {popup('entry-'+entry.entry_id,'分析菜单 '+entry.name,<>
     <button onClick={()=>action(()=>onDialog({kind:'move',entry}))}>移到项目</button>
     {entry.collection_id&&<button onClick={()=>action(()=>onDialog({kind:'detach',entry}))}>移出项目</button>}
     <button disabled={!entry.available} onClick={()=>action(()=>onReveal(entry))}>在文件管理器中显示</button>
    </>)}
   </div>
   {open&&<div className="library-children">
    <button className={selected&&!activeFigure&&currentView==='workspace'?'selected':''} onClick={()=>onOpen(entry,'workspace')} disabled={busy||!entry.available}><FlaskConical size={14}/>{entry.module==='stats'?'数据表':'分析工作台'}</button>
    <button className={selected&&!activeFigure&&currentView==='results'?'selected':''} onClick={()=>onOpen(entry,'results')} disabled={busy||!entry.available}><Table2 size={14}/>结果表</button>
    <button className={selected&&!activeFigure&&currentView==='wb'?'selected':''} onClick={()=>onOpen(entry,'wb')} disabled={busy||!entry.available}><Images size={14}/>{entry.module==='stats'?'当前统计图':entry.module==='if'?'IF 论文组图':'条带组图'}</button>
    {entry.figure_error&&<p className="library-error">{entry.figure_error}</p>}
    {!entry.available&&<button onClick={()=>onRelocate(entry)}>重新定位项目</button>}
   </div>}
  </div>
 }
 function collectionRows(id:string,name:string,rows:LibraryEntry[],collection?:LibraryCollection){
  const shown=rows.filter(entry=>matches(name)||matches(entry.name)||entry.figures.some(figure=>matches(figure.name))||entry.artifacts?.some(artifact=>matches(artifact.title)))
  if(q&&!matches(name)&&!shown.length)return null
  const open=!!q||expanded.includes(id)
  const outputs=shown.flatMap(entry=>(entry.artifacts??[])
   .filter(artifact=>matches(name)||matches(entry.name)||matches(artifact.title))
   .map(artifact=>({entry,artifact})))
  const figures=shown.flatMap(entry=>entry.figures.filter(figure=>
   (matches(name)||matches(entry.name)||matches(figure.name))&&
   !outputs.some(({entry:owner,artifact})=>owner.entry_id===entry.entry_id&&
      artifact.document_id===figure.id&&artifact.kind==='result_export')
  ).map(figure=>({entry,figure})))
  return <section key={id} className="library-collection" aria-label={name}>
   <div className={selectedProjectId===id?'library-root active':'library-root'}>
    <button className="library-chevron" aria-label={`${open?'收起':'展开'}${collection?'项目 ':''}${name}`} aria-expanded={open}
     onClick={()=>setExpanded(previous=>toggle(previous,id))}><ChevronRight size={13} className={open?'expanded':''}/></button>
    {collection?<button className="library-title" aria-label={`打开项目 ${name}`} aria-current={selectedProjectId===id?'page':undefined}
     disabled={busy} onClick={()=>onProject(id)}><Folder size={15}/><span>{name}</span>{collection.pinned&&<Pin size={12}/>}</button>:
     <button className="library-title" aria-expanded={open} onClick={()=>setExpanded(previous=>toggle(previous,id))}><span>{name}</span></button>}
    {collection&&popup(id,'项目菜单 '+name,<>
     <button onClick={()=>action(()=>onDialog({kind:'choose',collectionId:id}))}>新建分析</button>
     <button onClick={()=>action(()=>onDialog({kind:'rename',project:collection}))}>重命名</button>
     <button onClick={()=>action(()=>onPin(collection))}>{collection.pinned?'取消置顶':'置顶'}</button>
     <button onClick={()=>action(()=>onDialog({kind:'remove',project:collection}))}>移出项目列表</button>
    </>)}
   </div>
   {open&&<div className="library-collection-body">
    {shown.length>0?<><p className="library-section-label">分析</p>{shown.map(analysisRow)}</>:<p className="hint library-empty">暂无分析</p>}
    {(figures.length>0||outputs.length>0)&&<><p className="library-section-label">图表与导出</p>
     <div className="library-children library-artifacts">{figures.map(({entry,figure})=><button key={entry.entry_id+':'+figure.id}
      className={entry.entry_id===active?.entry_id&&activeFigure===figure.id?'selected':''}
      title={`${entry.name} · 源版本 ${figure.source_revision}`}
      aria-label={`打开图表 ${figure.name}`} disabled={busy} onClick={()=>onArtifact(entry,{
       id:figure.id,entry_id:entry.entry_id,kind:'wb_plot',title:figure.name,
       available:true,source_revision:figure.source_revision,document_id:figure.id,version_id:figure.selected_version,
      })}>
      <FileBarChart2 size={14}/><span>{figure.name}<small>{entry.name}</small></span>{figure.source_stale&&<small>旧版本</small>}
     </button>)}
     {outputs.map(({entry,artifact})=>{
      const isDocument=artifact.kind==='wb_figure'||artifact.kind==='stats_plot'
      const disabled=busy||(isDocument?!entry.available:!artifact.available&&!artifact.document_id)
      return <div className="library-artifact-row" key={entry.entry_id+':'+artifact.id}>
       <button className={active?.entry_id===entry.entry_id&&(activeFigure===artifact.id||activeFigure===artifact.document_id)?'selected':''}
        title={`${entry.name} · ${artifact.source_revision===null?'图形版本 '+artifact.version_id:'源版本 '+artifact.source_revision}`}
        aria-label={`${isDocument?'打开组图':'打开导出'} ${artifact.title}`} disabled={disabled}
        onClick={()=>onArtifact(entry,artifact)}>
        {isDocument?<Images size={14}/>:<FileBarChart2 size={14}/>}
        <span>{artifact.title}<small>{entry.name}{artifact.source_revision===null?' · 组图':` · 版本 ${artifact.source_revision}`}</small></span>
        {!isDocument&&!artifact.available&&<small>文件缺失</small>}
       </button>
       {popup(entry.entry_id+':'+artifact.id,'产物菜单 '+artifact.title,<>
        <button disabled={!entry.available} onClick={()=>action(()=>onOpen(entry,'workspace'))}>打开源分析</button>
        {!isDocument&&<button disabled={!artifact.available} onClick={()=>action(()=>onReveal(entry,artifact))}>在文件管理器中显示</button>}
       </>)}
      </div>
     })}</div>
    </>}
   </div>}
  </section>
 }
 return <nav className="project-library" aria-label="实验项目库" onKeyDown={event=>{if(event.key==='Escape')setMenu('')}}
  onBlur={event=>{if(!event.currentTarget.contains(event.relatedTarget))setMenu('')}}>
  <label className="library-search"><Search size={14}/><input aria-label="搜索项目或图表" placeholder="搜索项目或图表" value={query} onChange={event=>setQuery(event.target.value)}/></label>
  <div className="library-heading"><span>项目</span><div className="library-popup-anchor">
   <button type="button" className="icon-btn library-menu-button" aria-label="新建或打开" title="新建或打开" aria-expanded={menu==='create'} disabled={busy}
    onClick={()=>setMenu(menu==='create'?'':'create')}><Plus size={18}/></button>
   {menu==='create'&&<div className="library-popup">
    <button onClick={()=>action(()=>onDialog({kind:'collection'}))}>新建项目</button>
    <button onClick={()=>action(()=>onDialog({kind:'wb'}))}>新建 WB 分析</button>
    <button onClick={()=>action(()=>onDialog({kind:'if'}))}>新建 IF 分析</button>
    <button onClick={()=>action(()=>onDialog({kind:'stats'}))}>新建统计分析</button>
    <button onClick={()=>action(onOpenFile)}>打开已有分析</button>
    <button onClick={()=>action(onOpenBundle)}>打开项目包</button>
   </div>}
  </div></div>
  {error&&<div className="library-error" role="alert"><p>项目列表暂不可用：{error}</p><button onClick={onRetry}>重试</button></div>}
  {!entries.length&&!projects.length&&!error&&<p className="hint library-empty">使用「＋」创建项目或分析。</p>}
  {groups.map(({id,name,entries,collection})=>collectionRows(id,name,entries,collection))}
  {collectionRows('unassigned','独立分析',entries.filter(entry=>!projects.some(collection=>collection.id===entry.collection_id)))}
 </nav>
}
