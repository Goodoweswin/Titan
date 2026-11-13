import {useEffect,useRef,useState} from 'react'
import {open,save} from '@tauri-apps/plugin-dialog'
import {Download,Undo2,Redo2} from 'lucide-react'
import {callEngine} from '../bridge'
import {useActionMenu,type ActionMenuItem} from '../ActionMenu'
import type {AnalysisLocation,ModuleView} from '../workspace-navigation'
import type {ProjectLibraryModel} from '../useProjectLibrary'
import type {AnalysisCreation} from '../LibraryCreateDialog'
import type {CloseActions,LibraryExportReceipt,LibraryResume,Project} from '../types'
import type {Dataset,DatasetSource,Figure,Group,Row,Run,SourceCatalog,StatsProject,Style} from './types'
import {currentRun,inputKey} from './types'
import ProjectResultsDialog from './ProjectResultsDialog'
import SourceStatus from './SourceStatus'
import packageInfo from '../../package.json'
import './stats.css'
const id=()=>crypto.randomUUID()
const native=()=>Boolean((window as any).__TAURI_INTERNALS__)
const fmt=(v:unknown)=>typeof v==='number'?v.toLocaleString(undefined,{maximumSignificantDigits:5}):v==null?'—':String(v)
function locationResources(target:StatsProject,location:AnalysisLocation){
 const table=target.datasets.find(table=>table.id===location.resourceId)
 const figure=location.artifactId?target.figures.find(figure=>'stats:'+figure.id===location.artifactId):undefined
 const run=location.runId?target.datasets.flatMap(table=>table.runs).find(run=>run.id===location.runId):undefined
 if(location.artifactId&&!figure||location.runId&&!run||!figure&&!run&&!table)throw new Error('原数据表或图形已移除，请从当前列表选择。')
 return {table,figure,run}
}
export interface StatsLibraryActions {
 prepareLeave:()=>Promise<boolean>
 restore:(location:AnalysisLocation)=>Promise<boolean>
 create:(input:AnalysisCreation)=>Promise<boolean>
 demo:()=>Promise<boolean>
 importFirst:(input:AnalysisCreation & {dataset:Dataset})=>Promise<boolean>
 open:(path:string,resume:LibraryResume,entryId?:string)=>Promise<boolean>
 fromWB:(project:Project)=>Promise<boolean>
}

interface Props {
 active:boolean
 sourceRequest?:{path?:string;request:number;collectionId?:string|null;forceNew?:boolean}|null
 library:ProjectLibraryModel
 libraryBusy:boolean
 onSource:(source:DatasetSource)=>void
 registerClose:(actions:CloseActions)=>void
 registerLibrary:(actions:StatsLibraryActions)=>void
 reportView:(view:ModuleView)=>void
 membership:React.ReactNode
 beforeSourceImport:()=>Promise<(()=>void)|null>
 onSourceCreated:()=>void
 onExported:(receipt:LibraryExportReceipt)=>void
}

export default function StatsWorkspace({
 active,sourceRequest,library,libraryBusy,onSource,registerClose,registerLibrary,
 reportView,membership,beforeSourceImport,onSourceCreated,onExported,
}:Props){
 const [sourceDialog,setSourceDialog]=useState<{path?:string;collectionId?:string|null;forceNew?:boolean;requested?:boolean}|null>(null)
 useEffect(()=>{
  if(sourceRequest)setSourceDialog({...sourceRequest,requested:true})
 },[sourceRequest])
 const [p,setP]=useState<StatsProject|null>(null),ref=useRef(p);ref.current=p
 const [datasetId,setDatasetId]=useState(''),[view,setView]=useState<'data'|'analysis'|'graph'>('data'),[busy,setBusy]=useState(''),[message,setMessage]=useState('')
 const [frozen,setFrozen]=useState<Figure|null>(null),[preview,setPreview]=useState<{png:string;caption:string;notes:string[]}|null>(null),[previewError,setPreviewError]=useState('')
 const [importFormat,setImportFormat]=useState<'wide'|'long'>('wide')
 const [modal,setModal]=useState<''|'import'|'export'|'open'|'copy'>(''),[text,setText]=useState(''),[location,setLocation]=useState(''),[sheet,setSheet]=useState(''),[imported,setImported]=useState<{dataset:Dataset;sheets:string[]}|null>(null)
 const [past,setPast]=useState<StatsProject[]>([]),[future,setFuture]=useState<StatsProject[]>([])
 const flight=useRef<Promise<unknown>|null>(null),epoch=useRef(0),opening=useRef(false)
 const d=p?.datasets.find(d=>d.id===datasetId)??p?.datasets[0],display=frozen?.dataset??d,run=display?(frozen?.run??currentRun(display)):null,style=frozen?.style??d?.style,locked=!!d?.source?.locked
 function assign(next:StatsProject){ref.current=next;setP(next)}
 async function persist(){
  if(flight.current)await flight.current
  const before=ref.current;if(!before||before.revision===before.saved_revision)return
  const promise=callEngine<StatsProject>('stats_save',{project:before});flight.current=promise
  try{const saved=await promise;const live=ref.current;if(live?.id===before.id&&live.project_path===before.project_path)assign({...live,saved_revision:saved.saved_revision,project_path:saved.project_path});void library.refresh()}finally{if(flight.current===promise)flight.current=null}
 }
 async function flush(){try{await persist();await persist();if(ref.current&&ref.current.revision!==ref.current.saved_revision)throw new Error('保存期间数据仍在修改');return true}catch(e){setMessage('保存未完成：'+e);return false}}
 useEffect(()=>{
  registerClose({prepare:prepareLeave,finish:async()=>{
   if(ref.current?.project_path)await callEngine('stats_release',{path:ref.current.project_path})
  }})
  registerLibrary({
   prepareLeave,
   restore:restoreLocation,
   create:input=>change('stats_new',input,undefined,true),
   demo:()=>change('stats_demo',{},undefined,true),
   importFirst:input=>change('stats_new_from_import',input,undefined,true),
   open:(path,resume,entryId)=>change('stats_open',{path,entry_id:entryId},resume,true),
   fromWB:project=>change('stats_from_wb',{project},undefined,true),
  })
 })
 useEffect(()=>{if(!p||p.revision===p.saved_revision||busy)return;const timer=setTimeout(()=>persist().catch(e=>setMessage('自动保存失败：'+e)),900);return()=>clearTimeout(timer)},[p,busy])
 const activeEntryId=library.entries.find(entry=>entry.path===p?.project_path)?.entry_id
 const frozenDocument=frozen&&p?.figures.some(figure=>figure.id===frozen.id)?frozen:null
 useEffect(()=>{
  if(!active||!activeEntryId||libraryBusy||busy)return
  void library.resume(activeEntryId,{
   view:view==='data'?'workspace':view==='analysis'?'results':'figure',
   ...(datasetId?{dataset_id:datasetId}:{}),
   ...(view==='graph'&&frozenDocument?{artifact_id:'stats:'+frozenDocument.id,version_id:frozenDocument.id}:{}),
  })
 },[active,activeEntryId,libraryBusy,busy,view,datasetId,frozenDocument?.id])
 async function task(label:string,fn:()=>Promise<void>){setBusy(label);setMessage('');try{await fn()}catch(e){setMessage(String(e))}finally{setBusy('')}}
 async function prepareLeave(){
  return !busy&&!opening.current&&await flush()
 }
 async function change(command:string,payload:object,resume?:LibraryResume,raiseError=false,expected?:AnalysisLocation){
  if(opening.current||busy)return false
  opening.current=true
  setBusy('打开统计项目')
  setMessage('')
  try{
   if(!await flush())return false
   const old=ref.current
   const next=await callEngine<StatsProject>(command,payload)
   if(expected){
    try{
     if(next.id!==expected.projectId)throw new Error('原统计分析身份已变化，请从左栏重新打开。')
     locationResources(next,expected)
    }catch(error){
     if(next.project_path!==old?.project_path)await callEngine('stats_release',{path:next.project_path}).catch(()=>{})
     throw error
    }
   }
   if(old?.project_path&&old.project_path!==next.project_path){
    await callEngine('stats_release',{path:old.project_path}).catch(()=>{})
   }
   const figure=resume?.artifact_id?next.figures.find(item=>'stats:'+item.id===resume.artifact_id):undefined
   const dataset=next.datasets.find(item=>item.id===(figure?.dataset.id??resume?.dataset_id))
   epoch.current++
   assign(next)
   setDatasetId(dataset?.id??next.datasets[0].id)
   setFrozen(figure??null)
   setPast([]);setFuture([])
   setView(figure?'graph':resume?.artifact_id?'data':resume?.view==='figure'?'graph':resume?.view==='results'?'analysis':'data')
   setModal('')
   void library.refresh()
   return true
  }catch(e){if(!expected)setMessage(String(e));if(raiseError)throw e;return false}
  finally{opening.current=false;setBusy('')}
 }
 function edit(fn:(p:StatsProject)=>void){const before=ref.current;if(!before||busy)return;const next=structuredClone(before);fn(next);next.revision++;setPast(v=>[...v.slice(-29),before]);setFuture([]);assign(next)}
 function editD(fn:(d:Dataset)=>void){edit(next=>fn(next.datasets.find(t=>t.id===d?.id)!))}
 function undo(redo=false){const stack=redo?future:past;if(!p||!stack.length)return;const next={...structuredClone(stack[stack.length-1]),revision:p.revision+1,saved_revision:p.saved_revision,project_path:p.project_path};if(redo){setFuture(stack.slice(0,-1));setPast(v=>[...v,p])}else{setPast(stack.slice(0,-1));setFuture(v=>[...v,p])}assign(next)}
 const previewKey=display&&style?JSON.stringify([display,style,run?.id]):''
 useEffect(()=>{if(!active||!display||!style)return;let cancelled=false;setPreview(null);setPreviewError('');const timer=setTimeout(()=>{callEngine<{png:string;caption:string;notes:string[]}>('stats_preview',{dataset:display,style,run}).then(v=>{if(!cancelled)setPreview(v)}).catch(e=>{if(!cancelled)setPreviewError(String(e))})},350);return()=>{cancelled=true;clearTimeout(timer)}},[active,previewKey])
 async function analyze(){if(!d)return;const before=d,token=epoch.current,revision=ref.current?.revision;await task('运行统计分析',async()=>{const r=await callEngine<Run>('stats_analyze',{dataset:before});const live=ref.current;if(!live||token!==epoch.current)return;const target=live.datasets.find(t=>t.id===before.id);if(!target||inputKey(target)!==inputKey(before))throw new Error('数据已改变，请重新分析');const next=structuredClone(live);next.datasets.find(t=>t.id===before.id)!.runs.push({...r,source_revision:revision});next.revision++;assign(next);setView('analysis');await persist()})}
 async function readProjectResults(catalog:SourceCatalog,keys:string[],append:boolean,collectionId:string|null){
  setBusy('读取项目结果')
  setMessage('')
  try{
   const afterImport=sourceDialog?.requested?await beforeSourceImport():()=>{}
   if(!afterImport)return
   if(!await flush())throw new Error('请先完成当前统计项目的保存')
   const previous=ref.current
   const next=await callEngine<StatsProject>('stats_from_source',{
    path:catalog.path,entry_id:catalog.entry_id,keys,expected_signature:catalog.signature,
    confirmed:true,project:append?previous:undefined,collection_id:collectionId,
   })
   if(previous?.project_path&&previous.project_path!==next.project_path){
    await callEngine('stats_release',{path:previous.project_path}).catch(()=>{})
   }
   const selected=JSON.parse(keys[0]) as Record<string,string>
   const dataset=next.datasets.find(({source})=>{
    if(!source||source.kind!==catalog.kind||source.project_id!==catalog.project_id)return false
    const sameAnalysis=source.entry_id&&catalog.entry_id?source.entry_id===catalog.entry_id:source.path===catalog.path
    const selector=source.selector??{endpoint:source.endpoint,block:source.block}
    return sameAnalysis&&Object.entries(selected).every(([key,value])=>selector[key as keyof typeof selector]===value)
   })
   epoch.current++
   assign(next)
   setDatasetId(dataset?.id??next.datasets[0].id)
   setFrozen(null);setPast([]);setFuture([]);setView('data');setSourceDialog(null);afterImport();onSourceCreated()
   setMessage('已读取所选结果。已有同一指标保留原快照，可在来源栏显式更新。')
   void library.refresh()
  }finally{setBusy('')}
 }
 async function refreshSource(){
  if(!d)return
  await task('更新来源',async()=>{
   if(!await flush())return
   const next=await callEngine<StatsProject>('stats_update_source',{project:ref.current,dataset_id:d.id})
   epoch.current++
   assign(next);setPast([]);setFuture([])
   setMessage('来源已更新，请重新运行分析；历史分析和图形快照保留原数据。')
  })
 }
 async function addTable(dataset?:Dataset){if(!p)return;const next=dataset??await callEngine<Dataset>('stats_dataset',{name:'数据表 '+(p.datasets.length+1)});edit(v=>v.datasets.push(next));setDatasetId(next.id);setFrozen(null);setView('data');setModal('')}
 function selectResource(value:string){
  const figure=p?.figures.find(item=>value==='figure:'+item.id)
  if(figure){setFrozen(figure);setView('graph');return}
  const table=p?.datasets.find(item=>value==='table:'+item.id)
  if(table){setDatasetId(table.id);setFrozen(null);setView('data')}
 }
 async function restoreLocation(location:AnalysisLocation){
  if(!['data','analysis','graph'].includes(location.view))return false
  if(ref.current?.id!==location.projectId||ref.current?.project_path!==location.path){
   if(!location.path||!await prepareLeave()||!await change('stats_open',{path:location.path,entry_id:location.entryId},undefined,true,location))return false
  }
  const target=ref.current
  if(!target)return false
  const {table,figure,run}=locationResources(target,location)
  if(table)setDatasetId(table.id)
  setFrozen(figure??(run?{id:run.id,name:'历史分析 '+run.created_at,dataset:run.dataset,run,style:run.dataset.style}:null))
  setView(location.view as 'data'|'analysis'|'graph')
  return true
 }
 async function inspectImport(file?:string,worksheet?:string){await task('解析数据',async()=>{const result=await callEngine<{dataset:Dataset;sheets:string[]}>('stats_import',file?{path:file,sheet:worksheet||undefined,format:importFormat}:{text,format:importFormat});setImported(result);if(file)setLocation(file)})}
 async function chooseImport(){if(!native())return;try{const chosen=await open({filters:[{name:'表格',extensions:['xlsx','csv','tsv','txt']}]});if(typeof chosen==='string')await inspectImport(chosen)}catch(e){setMessage(String(e))}}
 async function chooseFolder(kind:'open'|'export'|'copy'){setLocation('');setModal(kind);if(native()){try{const chosen=kind==='open'?await open({directory:true,title:'打开 .titanstats 项目'}):await save({title:kind==='copy'?'另存统计项目':'导出到新文件夹',defaultPath:kind==='copy'?p?.name+'.titanstats':p?.name+'-统计结果'});if(typeof chosen==='string'){setLocation(chosen);await finishPath(kind,chosen)}else setModal('')}catch(e){setMessage(String(e))}}}
 async function finishPath(kind:string,dest:string){
  if(kind==='open'){await change('stats_open',{path:dest});return}
  if(!p||!display||!style)return
  await task('保存文件',async()=>{
   if(!await flush())return
   const source=ref.current
   if(!source)return
   if(kind==='copy'){
    const next=await callEngine<StatsProject>('stats_save',{project:source,path:dest.endsWith('.titanstats')?dest:dest+'.titanstats'})
    if(next.project_path!==source.project_path)await callEngine('stats_release',{path:source.project_path})
    assign(next)
   }else{
    const receipt=await callEngine<LibraryExportReceipt>('stats_export',{
     project:source,dataset:display,style,run,destination:dest,figure_id:frozenDocument?.id,
     run_id:frozen&&!frozenDocument?frozen.run?.id:undefined,
    })
    onExported(receipt)
   }
   setModal('')
   setMessage('已保存至 '+dest)
   void library.refresh()
  })
 }
 function freeze(){if(!d||!style||!preview)return;const f:Figure={id:id(),source_revision:p?.revision,name:(style.title||d.name)+' · 图 '+((p?.figures.length??0)+1),dataset:structuredClone({...d,runs:[]}),run:run?structuredClone(run):null,style:structuredClone(style)};edit(p=>p.figures.push(f));setMessage('已保存图形快照；后续数据修改不会覆盖这张图。')}
 function copyTable(){if(!display)return;const clone=structuredClone(display);clone.id=id();clone.name+=' · 副本';clone.source=null;clone.confirmed=false;clone.runs=[];void addTable(clone)}
 function paste(event:React.ClipboardEvent<HTMLInputElement>,ri:number,gi:number){const raw=event.clipboardData.getData('text');if(!raw.includes('\t')&&!raw.includes('\n'))return;event.preventDefault();const cells=raw.trimEnd().split(/\r?\n/).map(r=>r.split('\t'));if(cells.some(r=>r.length+gi>(d?.groups.length??0))){setMessage('粘贴列数超过现有分组，请先添加组。');return}editD(t=>{while(t.rows.length<ri+cells.length)t.rows.push({id:id(),label:String(t.rows.length+1),values:{},excluded:{}});cells.forEach((row,i)=>row.forEach((v,j)=>{t.rows[ri+i].values[t.groups[gi+j].id]=v}))})}
 const disabled=!!busy||!!frozen
 const {openMenu,closeMenu}=useActionMenu()
 const cellScope=JSON.stringify([active,p?.id,p?.project_path,display?.id,p?.revision,view,frozen?.id,locked,busy,modal,!!sourceDialog,libraryBusy])
 const currentCellScope=useRef(cellScope);currentCellScope.current=cellScope
 useEffect(()=>closeMenu(),[cellScope,closeMenu])
 function cellMenu(event:React.MouseEvent<HTMLTableCellElement>|React.KeyboardEvent<HTMLTableCellElement>,row:Row,group:Group){
  event.preventDefault();event.stopPropagation()
  if(!active||!p||!display||busy||libraryBusy||view!=='data')return
  const scope=cellScope,projectId=p.id,path=p.project_path,datasetId=display.id
  const excluded=!!row.excluded[group.id]
  const reason=frozen?'历史快照只读':locked?'来源数据已锁定':null
  const items:ActionMenuItem[]=[...(reason?[{id:'readonly',label:reason,disabled:true,onSelect:()=>{}}]:[]),
   {id:'exclusion',label:excluded?'恢复此值':'排除此值',disabled:!!reason,onSelect:()=>{
    const live=ref.current,table=live?.datasets.find(table=>table.id===datasetId)
    if(currentCellScope.current!==scope||live?.id!==projectId||live.project_path!==path||!table||table.source?.locked||
     !table.rows.some(item=>item.id===row.id)||!table.groups.some(item=>item.id===group.id))return
    editD(target=>{target.rows.find(item=>item.id===row.id)!.excluded[group.id]=!excluded})
   }}]
  const origin=(event.target as HTMLElement).closest<HTMLElement>('input:not(:disabled)')??event.currentTarget
  const box=origin.getBoundingClientRect()
  openMenu({id:`cell:${projectId}:${datasetId}:${row.id}:${group.id}`,label:`数值菜单 · ${display.name} · ${row.label} / ${group.label}`,
   origin,items,position:'clientX' in event?{x:event.clientX,y:event.clientY}:{x:box.left,y:box.bottom}})
 }
 function valueCell(row:Row,ri:number,group:Group,gi:number){
  return <td key={group.id} className={row.excluded[group.id]?'excluded':''} tabIndex={disabled||locked?0:-1}
   onContextMenu={event=>cellMenu(event,row,group)} onKeyDown={event=>{
    if(event.key==='ContextMenu'||event.shiftKey&&event.key==='F10')cellMenu(event,row,group)
   }}>
   <input aria-label={`数值 ${ri+1} ${gi+1}`} value={row.values[group.id]??''} disabled={disabled||locked}
    onChange={event=>editD(table=>{table.rows[ri].values[group.id]=event.target.value})} onPaste={event=>paste(event,ri,gi)}/>
  </td>
 }
 useEffect(()=>{reportView({path:p?.project_path,projectId:p?.id,name:p?.name,view,resourceId:display?.id,
  artifactId:frozenDocument?'stats:'+frozenDocument.id:undefined,runId:!frozenDocument?frozen?.run?.id:undefined,
  busy:!!busy||!!modal||!!sourceDialog})},
  [reportView,p?.project_path,p?.id,p?.name,view,display?.id,frozenDocument?.id,frozen?.run?.id,busy,modal,sourceDialog])
 return <><div className="module-pane stats-pane" hidden={!active} inert={!active||libraryBusy}>
 <div className="main-shell"><header className="app-header stats-header">{p?<><input aria-label="统计项目名称" value={p.name} disabled={!!busy} onChange={e=>edit(p=>{p.name=e.target.value})}/><span>{p.revision===p.saved_revision?'已保存':'待保存'}</span><div className="stats-toolbar"><button className="icon-btn" aria-label="撤销统计修改" disabled={!past.length||!!busy} onClick={()=>undo()}><Undo2 size={16}/></button><button className="icon-btn" aria-label="重做统计修改" disabled={!future.length||!!busy} onClick={()=>undo(true)}><Redo2 size={16}/></button><button className="btn secondary" disabled={!!busy} onClick={()=>flush()}>保存</button><button className="btn secondary" disabled={!!busy} onClick={()=>chooseFolder('copy')}>另存副本</button><button className="btn primary" disabled={!!busy} onClick={()=>chooseFolder('export')}><Download size={15}/>导出</button></div></>:<strong>统计与绘图</strong>}</header>
 {membership}{message&&<div className="notice" role="status">{message}<button onClick={()=>setMessage('')}>×</button></div>}{busy&&<div className="busy" role="status">{busy}…</div>}
 {p&&display&&style&&<>
 <div className="workbench-pickers stats-resource-picker">
  <label>数据与图形<select aria-label="选择数据表或图形" disabled={!!busy}
   value={frozenDocument?'figure:'+frozenDocument.id:frozen?'history':'table:'+d!.id}
   onChange={event=>selectResource(event.target.value)}>
   {frozen&&!frozenDocument&&<option value="history" disabled>{frozen.name}</option>}
   <optgroup label="数据表">{p.datasets.map(table=><option key={table.id} value={'table:'+table.id}>{table.name}</option>)}</optgroup>
   {p.figures.length>0&&<optgroup label="图形快照">{p.figures.map(figure=><option key={figure.id} value={'figure:'+figure.id}>{figure.name}</option>)}</optgroup>}
  </select></label>
 </div>
 <nav className="stats-tabs" aria-label="统计工作区"><button className={view==='data'?'selected':''} onClick={()=>setView('data')}>数据表</button><button className={view==='analysis'?'selected':''} onClick={()=>setView('analysis')}>统计分析</button><button className={view==='graph'?'selected':''} onClick={()=>setView('graph')}>图形</button><span/><button disabled={!!busy} onClick={()=>setSourceDialog({})}>从项目读取结果</button><button disabled={!!busy} onClick={()=>addTable()}>＋ 数据表</button><button disabled={!!busy} onClick={()=>{setImported(null);setText('');setLocation('');setModal('import')}}>导入 / 粘贴</button></nav>
 <main className="stats-content">{frozen&&<div className="stats-source">正在查看冻结图形 {frozen.name}。<button className="text-btn" onClick={copyTable}>复制数据为新表</button></div>}
 {(display.source?.kind==='wb'||display.source?.kind==='if')&&<SourceStatus source={display.source} active={active} frozen={!!frozen}
  busy={!!busy||libraryBusy} onReturn={()=>onSource(display.source!)} onUpdate={refreshSource} onCopy={copyTable}/>}
 {view==='data'&&<section><div className="stats-section-title"><input aria-label="数据表名称" value={display.name} disabled={disabled} onChange={e=>editD(t=>{t.name=e.target.value})}/><span>{display.rows.length} 行 · {display.groups.length} 组</span></div><p className="hint">每格填入一个独立单位的数值。配对设计使用左列相同 ID；空格为缺失。右键选择排除或恢复，原值保留。</p><div className="stats-grid-scroll"><table className="stats-grid"><thead><tr><th>独立单位 / 配对 ID</th>{display.groups.map((g,i)=><th key={g.id}><input aria-label={`组名 ${i+1}`} value={g.label} disabled={disabled||locked} onChange={e=>editD(t=>{t.groups[i].label=e.target.value})}/>{!locked&&!frozen&&<button aria-label={`删除组 ${g.label}`} disabled={disabled||display.groups.length<=1} onClick={()=>editD(t=>{t.groups.splice(i,1);t.rows.forEach(r=>{delete r.values[g.id];delete r.excluded[g.id]});if(t.analysis.control_group===g.id)t.analysis.control_group=t.groups[0].id})}>×</button>}</th>)}<th/></tr></thead><tbody>{display.rows.map((row,ri)=><tr key={row.id}><th><input aria-label={`样本 ID ${ri+1}`} value={row.label} disabled={disabled||locked} onChange={e=>editD(t=>{t.rows[ri].label=e.target.value})}/></th>{display.groups.map((g,gi)=>valueCell(row,ri,g,gi))}<td><button aria-label={`删除行 ${ri+1}`} disabled={disabled||locked} onClick={()=>editD(t=>{t.rows.splice(ri,1)})}>×</button></td></tr>)}</tbody></table></div><div className="stats-actions"><button className="btn secondary" disabled={disabled||locked} onClick={()=>editD(t=>t.rows.push({id:id(),label:String(t.rows.length+1),values:{},excluded:{}}))}>添加行</button><button className="btn secondary" disabled={disabled||locked||display.groups.length>=30} onClick={()=>editD(t=>t.groups.push({id:id(),label:'Group '+(t.groups.length+1)}))}>添加组</button><button className="btn primary" onClick={()=>setView('analysis')}>设置统计分析</button></div></section>}
 {view==='analysis'&&<section><h2>{display.name}</h2><fieldset disabled={disabled} className="stats-analysis-controls"><label>统计方法<select aria-label="统计方法" value={display.analysis.method} onChange={e=>editD(t=>{t.analysis.method=e.target.value})}><option value="descriptive">仅描述统计</option><option value="welch">Welch 独立样本 t 检验</option><option value="paired">配对 t 检验</option><option value="anova">普通单因素 ANOVA</option><option value="welch_anova">Welch 单因素 ANOVA</option></select></label><label>分析尺度<select value={display.analysis.scale} onChange={e=>editD(t=>{t.analysis.scale=e.target.value})}><option value="raw">原始数值</option><option value="log2">log2（仅正值）</option></select></label>{['anova','welch_anova'].includes(display.analysis.method)&&<><label>比较范围<select aria-label="统计比较范围" value={display.analysis.scope} onChange={e=>editD(t=>{t.analysis.scope=e.target.value})}><option value="control">各组与对照</option><option value="all">全部两两比较</option></select></label><label>对照组<select value={display.analysis.control_group} onChange={e=>editD(t=>{t.analysis.control_group=e.target.value})}>{display.groups.map(g=><option value={g.id} key={g.id}>{g.label}</option>)}</select></label></>}</fieldset><label className="stats-confirm"><input type="checkbox" aria-label="确认独立单位" checked={display.confirmed} disabled={disabled||locked} onChange={e=>editD(t=>{t.confirmed=e.target.checked})}/>已确认每格代表独立生物学单位；技术重复已汇总；配对关系由 ID 明确。</label><p className="hint">普通 ANOVA 假定独立、残差近似正态及等方差；Welch 允许不等方差。多组对照采用 Dunnett，全部比较采用 Tukey；Welch 后使用 Games–Howell。方法应由实验设计决定。</p>{!frozen&&<button className="btn primary" disabled={!!busy} onClick={analyze}>运行分析</button>}
 {!run?<p className="stats-empty">{display.runs?.length?'数据或设置已改变，请重新运行分析。':'尚未运行当前分析。'}</p>:<><p className="stats-method">{run.method_text}</p>{run.omnibus&&<p>总体检验：F = {fmt(run.omnibus.statistic)}，P = {fmt(run.omnibus.p_raw)}</p>}<table className="stats-results"><thead><tr><th>组别</th><th>独立 n</th><th>均值</th><th>SD</th><th>SEM</th></tr></thead><tbody>{run.summaries.map(s=><tr key={s.group}><td>{display.groups.find(g=>g.id===s.group)?.label??s.label}</td><td>{s.n}</td><td>{fmt(s.mean)}</td><td>{fmt(s.sd)}</td><td>{fmt(s.sem)}</td></tr>)}</tbody></table>{run.comparisons.length>0&&<table className="stats-results"><thead><tr><th>对比（B−A）</th><th>效应</th><th>95% CI</th><th>P 值</th><th>校正</th></tr></thead><tbody>{run.comparisons.map((r,i)=><tr key={i}><td>{display.groups.find(g=>g.id===r.group_b)?.label} − {display.groups.find(g=>g.id===r.group_a)?.label}</td><td>{fmt(r.effect)}</td><td>{r.ci95?.map(fmt).join(' 至 ')}</td><td>{fmt(r.p_adjusted)}</td><td>{r.adjustment_method}</td></tr>)}</tbody></table>}<p className="hint">图上每组均值区间、组对差值的普通区间与多重比较同时区间分别解释。SciPy {run.scipy_version}。</p><button className="btn secondary" onClick={()=>setView('graph')}>查看图形</button></>}
 {!!display.runs?.length&&<details><summary>分析历史（{display.runs.length}）</summary>{display.runs.map(r=><button className="text-btn" key={r.id} onClick={()=>{setFrozen({id:r.id,name:'历史分析 '+r.created_at,dataset:r.dataset,run:r,style:r.dataset.style});setView('analysis')}}>{new Date(r.created_at).toLocaleString()} · {r.dataset.analysis.method}</button>)}</details>}</section>}
 {view==='graph'&&<div className="stats-graph-layout"><section className="stats-paper"><div className="stats-section-title"><h2>{frozen?.name??display.name}</h2><span>{style.width_mm} × {style.height_mm} mm</span></div>{previewError?<p role="alert">{previewError}</p>:preview?<><img src={preview.png} alt="统计图预览"/><p className="stats-caption">{preview.caption}</p>{preview.notes.map(n=><p role="alert" key={n}>{n}</p>)}</>:<p role="status">正在绘图…</p>}{!frozen&&<button className="btn secondary" disabled={!preview||!!busy||(!run&&display.analysis.method!=='descriptive')} onClick={freeze}>保存图形快照</button>}</section><fieldset className="stats-inspector" disabled={disabled}><legend>图形设置</legend>{([['kind','图形类型',[['bar_points','柱形 + 原始点'],['scatter','散点 + 均值'],['bar','柱形'],['paired','配对连线']]],['error','误差线',[['sd','SD'],['sem','SEM'],['ci95','95% CI'],['none','无']]],['annotations','统计标注',[['none','无'],['p','精确 P 值'],['stars','星号']]],['text_mode','矢量文字',[['editable','可编辑文字'],['outline','SVG 文字轮廓']]]] as const).map(([key,label,options])=><label key={key}>{label}<select aria-label={label} value={style[key]} onChange={e=>editD(t=>{t.style[key]=e.target.value})}>{options.map(([value,text])=><option value={value} key={value}>{text}</option>)}</select></label>)}{(['title','y_label'] as const).map((key,i)=><label key={key}>{i?'Y轴标题':'图形标题'}<input value={style[key]} onChange={e=>editD(t=>{t.style[key]=e.target.value})}/></label>)}{([['width_mm','宽度 mm'],['height_mm','高度 mm'],['font_size','字号 pt'],['dpi','DPI']] as const).map(([key,label])=><label key={key}>{label}<input aria-label={label} type="number" value={style[key]} onChange={e=>editD(t=>{t.style[key]=Number(e.target.value)})}/></label>)}{(['y_min','y_max'] as const).map((key,i)=><label key={key}>Y轴{i?'上限':'下限'}<input type="number" placeholder="自动" value={style[key]??''} onChange={e=>editD(t=>{t.style[key]=e.target.value===''?null:Number(e.target.value)})}/></label>)}{run&&run.comparisons.length>0&&<details><summary>选择比较标注</summary>{run.comparisons.map(r=>{const key=r.group_a+':'+r.group_b;return <label key={key}><input type="checkbox" checked={style.comparison_keys?.includes(key)??true} onChange={e=>editD(t=>{const keys=t.style.comparison_keys??run.comparisons.map(c=>c.group_a+':'+c.group_b);t.style.comparison_keys=e.target.checked?[...keys,key]:keys.filter(k=>k!==key)})}/>{display.groups.find(g=>g.id===r.group_a)?.label} ↔ {display.groups.find(g=>g.id===r.group_b)?.label}</label>})}</details>}<details><summary>散点、线条与显示顺序</summary><label>点形<select value={style.point_marker??'circle'} onChange={e=>editD(t=>{t.style.point_marker=e.target.value})}><option value="circle">圆形</option><option value="square">方形</option><option value="triangle">三角形</option></select></label><label><input type="checkbox" checked={style.hollow??false} onChange={e=>editD(t=>{t.style.hollow=e.target.checked})}/>空心散点</label>{([['point_size','点大小',4],['axis_width','坐标轴线宽',.8],['error_width','误差线宽',.8],['error_cap','误差端帽',3],['bar_width','柱宽',.6],['label_angle','组名角度',30]] as const).map(([key,label,fallback])=><label key={key}>{label}<input type="number" step="any" value={style[key]??fallback} onChange={e=>editD(t=>{t.style[key]=Number(e.target.value)})}/></label>)}{[...display.groups].sort((a,b)=>{const order=style.group_order??display.groups.map(g=>g.id);return order.indexOf(a.id)-order.indexOf(b.id)}).map((g,i)=><label key={g.id}>显示名称<input value={style.labels?.[g.id]??g.label} onChange={e=>editD(t=>{t.style.labels={...t.style.labels,[g.id]:e.target.value}})}/><button type="button" disabled={!i} onClick={()=>editD(t=>{const order=t.style.group_order?.length?[...t.style.group_order]:t.groups.map(g=>g.id);const index=order.indexOf(g.id);if(index>0){[order[index-1],order[index]]=[order[index],order[index-1]];t.style.group_order=order}})}>上移 {g.label}</button></label>)}</details>{display.groups.map((g,i)=><label className="stats-color" key={g.id}>{g.label}<input type="color" value={style.colors[g.id]??['#88B8D0','#E29EB6','#D4B483','#879CA6','#BD998B','#A9B9BF'][i%6]} onChange={e=>editD(t=>{t.style.colors[g.id]=e.target.value})}/></label>)}</fieldset></div>}
 </main></>}
 <footer className="statusbar"><span>统计与绘图 · Column / 配对 · 本地数据</span><span>Titan {packageInfo.version}</span></footer></div>
 {modal&&<div className="modal-backdrop"><section className="modal stats-modal" role="dialog" aria-modal="true" aria-label={modal==='import'?'导入统计数据':'统计文件位置'}><h2>{modal==='import'?'导入与粘贴数据':'选择文件位置'}</h2>{modal==='import'?<><label>数据排列<select aria-label="导入数据排列" value={importFormat} onChange={e=>{setImportFormat(e.target.value as 'wide'|'long');setImported(null)}}><option value="wide">宽表：每列一组</option><option value="long">长表：group / value / unit_id</option></select></label><p>{importFormat==='wide'?'首行填写组名；可用第一列 ID 标识配对。支持从 Excel 粘贴。':'首行需要 group、value、unit_id；可添加 pair_id。技术重复须先明确汇总。'}</p><textarea aria-label="粘贴统计数据" rows={7} value={text} onChange={e=>{setText(e.target.value);setImported(null)}} placeholder={'Control\tTreatment\n1\t2\n2\t3'}/><div className="stats-actions"><button className="btn secondary" disabled={!!busy} onClick={()=>inspectImport()}>预览粘贴数据</button>{native()&&<button className="btn secondary" onClick={chooseImport}>选择 Excel / CSV</button>}</div><label>文件完整路径<input aria-label="统计导入路径" value={location} onChange={e=>{setLocation(e.target.value);setImported(null)}}/></label><button className="text-btn" disabled={!!busy||!location} onClick={()=>inspectImport(location)}>读取文件</button>{imported?.sheets.length?<label>工作表<select value={sheet||imported.sheets[0]} onChange={e=>{setSheet(e.target.value);void inspectImport(location,e.target.value)}}>{imported.sheets.map(s=><option key={s}>{s}</option>)}</select></label>:null}{imported&&<div className="stats-import-preview"><strong>{imported.dataset.rows.length} 行 / {imported.dataset.groups.map(g=>g.label).join('、')}</strong><table><tbody>{imported.dataset.rows.slice(0,5).map(r=><tr key={r.id}><th>{r.label}</th>{imported.dataset.groups.map(g=><td key={g.id}>{r.values[g.id]}</td>)}</tr>)}</tbody></table></div>}</>:<label>完整路径<input aria-label="统计文件路径" value={location} onChange={e=>setLocation(e.target.value)}/></label>}<footer><button className="btn secondary" onClick={()=>setModal('')}>取消</button><button className="btn primary" disabled={!!busy||(modal==='import'?!imported:!location)} onClick={()=>modal==='import'?addTable(imported!.dataset):finishPath(modal,location)}>{modal==='import'?'添加数据表':'确认'}</button></footer></section></div>}
 </div>
 {(active||sourceDialog?.requested)&&sourceDialog&&<ProjectResultsDialog entries={library.entries} initialPath={sourceDialog.path}
  projects={library.projects} initialCollectionId={sourceDialog.collectionId}
  currentName={!sourceDialog.forceNew?p?.name:undefined} appendByDefault={!sourceDialog.requested} busy={!!busy} onClose={()=>setSourceDialog(null)} onImport={readProjectResults}/>}
 </>
}
