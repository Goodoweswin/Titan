import {useEffect,useRef,useState} from 'react'
import {open,save} from '@tauri-apps/plugin-dialog'
import {BarChart3,ScanLine,Microscope,Plus,FolderOpen,Table2,FlaskConical,Image,Download,Undo2,Redo2} from 'lucide-react'
import {callEngine} from '../bridge'
import ProjectLibrary,{type LibraryView} from '../ProjectLibrary'
import type {ProjectLibraryModel} from '../useProjectLibrary'
import type {AnalysisCreation,LibraryDialog} from '../LibraryCreateDialog'
import type {LibraryArtifact,LibraryCollection,LibraryEntry,LibraryExportReceipt,LibraryResume,Project} from '../types'
import appIcon from '../../assets/brand/titan-app-icon-128.png'
import type {Dataset,Figure,Run,StatsProject,Style} from './types'
import {currentRun,inputKey} from './types'
import './stats.css'
const id=()=>crypto.randomUUID()
const native=()=>Boolean((window as any).__TAURI_INTERNALS__)
const fmt=(v:unknown)=>typeof v==='number'?v.toLocaleString(undefined,{maximumSignificantDigits:5}):v==null?'—':String(v)
export interface StatsLibraryActions {
 prepareLeave:()=>Promise<boolean>
 create:(input:AnalysisCreation)=>Promise<boolean>
 open:(path:string,resume:LibraryResume,entryId?:string)=>Promise<boolean>
 fromWB:(project:Project)=>Promise<boolean>
}

interface Props {
 active:boolean
 library:ProjectLibraryModel
 libraryBusy:boolean
 onWB:()=>void
 onIF:()=>void
 onSource:(path:string)=>void
 registerClose:(callback:()=>Promise<boolean>)=>void
 registerLibrary:(actions:StatsLibraryActions)=>void
 onOpen:(entry:LibraryEntry,view?:LibraryView,figureId?:string)=>void
 onDialog:(dialog:LibraryDialog)=>void
 onPin:(collection:LibraryCollection)=>void
 onArtifact:(entry:LibraryEntry,artifact:LibraryArtifact)=>void
 onReveal:(entry:LibraryEntry,artifact?:LibraryArtifact)=>void
 onExported:(receipt:LibraryExportReceipt)=>void
 onOpenFile:()=>void
 onRelocate:(entry:LibraryEntry)=>void
}

export default function StatsWorkspace({
 active,library,libraryBusy,onWB,onIF,onSource,registerClose,registerLibrary,
 onOpen,onDialog,onPin,onArtifact,onReveal,onExported,onOpenFile,onRelocate,
}:Props){
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
  registerClose(async()=>{
   if(!await prepareLeave())return false
   if(ref.current?.project_path)await callEngine('stats_release',{path:ref.current.project_path})
   return true
  })
  registerLibrary({
   prepareLeave,
   create:input=>change('stats_new',input,undefined,true),
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
 async function change(command:string,payload:object,resume?:LibraryResume,raiseError=false){
  if(opening.current||busy)return false
  opening.current=true
  setBusy('打开统计项目')
  setMessage('')
  try{
   if(!await flush())return false
   const old=ref.current
   const next=await callEngine<StatsProject>(command,payload)
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
  }catch(e){setMessage(String(e));if(raiseError)throw e;return false}
  finally{opening.current=false;setBusy('')}
 }
 function edit(fn:(p:StatsProject)=>void){const before=ref.current;if(!before||busy)return;const next=structuredClone(before);fn(next);next.revision++;setPast(v=>[...v.slice(-29),before]);setFuture([]);assign(next)}
 function editD(fn:(d:Dataset)=>void){edit(next=>fn(next.datasets.find(t=>t.id===d?.id)!))}
 function undo(redo=false){const stack=redo?future:past;if(!p||!stack.length)return;const next={...structuredClone(stack[stack.length-1]),revision:p.revision+1,saved_revision:p.saved_revision,project_path:p.project_path};if(redo){setFuture(stack.slice(0,-1));setPast(v=>[...v,p])}else{setPast(stack.slice(0,-1));setFuture(v=>[...v,p])}assign(next)}
 async function leave(fn:()=>void){if(!libraryBusy&&await prepareLeave())fn()}
 const previewKey=display&&style?JSON.stringify([display,style,run?.id]):''
 useEffect(()=>{if(!active||!display||!style)return;let cancelled=false;setPreview(null);setPreviewError('');const timer=setTimeout(()=>{callEngine<{png:string;caption:string;notes:string[]}>('stats_preview',{dataset:display,style,run}).then(v=>{if(!cancelled)setPreview(v)}).catch(e=>{if(!cancelled)setPreviewError(String(e))})},350);return()=>{cancelled=true;clearTimeout(timer)}},[active,previewKey])
 async function analyze(){if(!d)return;const before=d,token=epoch.current;await task('运行统计分析',async()=>{const r=await callEngine<Run>('stats_analyze',{dataset:before});const live=ref.current;if(!live||token!==epoch.current)return;const target=live.datasets.find(t=>t.id===before.id);if(!target||inputKey(target)!==inputKey(before))throw new Error('数据已改变，请重新分析');const next=structuredClone(live);next.datasets.find(t=>t.id===before.id)!.runs.push(r);next.revision++;assign(next);setView('analysis');await persist()})}
 async function addTable(dataset?:Dataset){if(!p)return;const next=dataset??await callEngine<Dataset>('stats_dataset',{name:'数据表 '+(p.datasets.length+1)});edit(v=>v.datasets.push(next));setDatasetId(next.id);setFrozen(null);setView('data');setModal('')}
 function selectTable(key:string,next:typeof view){setDatasetId(key);setFrozen(null);setView(next)}
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
 return <div className="app-shell stats-shell" style={{display:active?undefined:'none'}} inert={libraryBusy}>
 <aside className="sidebar"><div className="brand"><img className="brand-mark" src={appIcon} alt=""/><strong>Titan</strong></div><nav className="analysis-modules" aria-label="分析模块"><button className="nav module-nav" onClick={onWB}><ScanLine size={18}/>Western blot</button><button className="nav module-nav" onClick={onIF}><Microscope size={18}/>免疫荧光</button><button className="nav active module-nav" aria-current="page"><BarChart3 size={18}/>统计与绘图</button></nav>
 <ProjectLibrary entries={library.entries} projects={library.projects} project={p}
  activeFigure={view==='graph'&&frozenDocument?'stats:'+frozenDocument.id:''}
  currentView={view==='data'?'workspace':view==='analysis'?'results':'wb'} error={library.error}
  busy={!!busy||libraryBusy} onRetry={library.refresh} onRelocate={onRelocate}
  onOpen={onOpen} onDialog={onDialog} onPin={onPin} onOpenFile={onOpenFile}
  onArtifact={onArtifact} onReveal={onReveal}/>
 {p&&<div className="stats-tree"><div className="sidebar-label">数据与图形</div>{p?.datasets.map(t=><div key={t.id}><button className={d?.id===t.id&&!frozen?'selected':''} onClick={()=>selectTable(t.id,'data')}><Table2 size={15}/>{t.name}</button><div className="stats-tree-child"><button onClick={()=>selectTable(t.id,'analysis')}><FlaskConical size={14}/>分析结果 · {t.runs.length}</button><button onClick={()=>selectTable(t.id,'graph')}><BarChart3 size={14}/>当前图形</button></div></div>)}{p?.figures.map(f=><button key={f.id} className={frozen?.id===f.id?'selected':''} onClick={()=>{setFrozen(f);setView('graph')}}><Image size={15}/>{f.name}</button>)}</div>}<button className="nav library-demo" disabled={!!busy} onClick={()=>change('stats_demo',{})}>体验统计合成示例</button></aside>
 <div className="main-shell"><header className="app-header stats-header">{p?<><input aria-label="统计项目名称" value={p.name} disabled={!!busy} onChange={e=>edit(p=>{p.name=e.target.value})}/><span>{p.revision===p.saved_revision?'已保存':'待保存'}</span><div className="stats-toolbar"><button className="icon-btn" aria-label="撤销统计修改" disabled={!past.length||!!busy} onClick={()=>undo()}><Undo2 size={16}/></button><button className="icon-btn" aria-label="重做统计修改" disabled={!future.length||!!busy} onClick={()=>undo(true)}><Redo2 size={16}/></button><button className="btn secondary" disabled={!!busy} onClick={()=>flush()}>保存</button><button className="btn secondary" disabled={!!busy} onClick={()=>chooseFolder('copy')}>另存副本</button><button className="btn primary" disabled={!!busy} onClick={()=>chooseFolder('export')}><Download size={15}/>导出</button></div></>:<strong>统计与绘图</strong>}</header>
 {message&&<div className="notice" role="status">{message}<button onClick={()=>setMessage('')}>×</button></div>}{busy&&<div className="busy" role="status">{busy}…</div>}
 {!p?<section className="welcome stats-welcome"><BarChart3 size={48} strokeWidth={1}/><h1>从数据到论文图</h1><p>整理实验数据、运行统计分析，制作可编辑的图形。</p><div className="welcome-actions"><button className="btn primary" onClick={()=>onDialog({kind:'stats'})}>新建统计项目</button><button className="btn secondary" onClick={()=>change('stats_demo',{})}>体验合成示例</button></div><p className="hint">Excel / CSV / 粘贴 · 独立与配对设计 · 本地保存</p></section>:display&&style&&<>
 <nav className="stats-tabs" aria-label="统计工作区"><button className={view==='data'?'selected':''} onClick={()=>setView('data')}>数据表</button><button className={view==='analysis'?'selected':''} onClick={()=>setView('analysis')}>统计分析</button><button className={view==='graph'?'selected':''} onClick={()=>setView('graph')}>图形</button><span/><button disabled={!!busy} onClick={()=>addTable()}>＋ 数据表</button><button disabled={!!busy} onClick={()=>{setImported(null);setText('');setLocation('');setModal('import')}}>导入 / 粘贴</button></nav>
 <main className="stats-content">{frozen&&<div className="stats-source">正在查看冻结图形 {frozen.name}。<button className="text-btn" onClick={copyTable}>复制数据为新表</button></div>}
 {display.source?.kind==='wb'&&<div className="stats-source">WB 来源：{display.source.endpoint} · {display.source.block} · 版本 {display.source.revision}<button className="text-btn" onClick={()=>display.source?.path&&leave(()=>onSource(display.source!.path!))}>返回 WB</button>{!frozen&&<button className="text-btn" disabled={!!busy} onClick={()=>task('更新来源',async()=>{if(!await flush())return;const next=await callEngine<StatsProject>('stats_update_source',{project:ref.current,dataset_id:d!.id});assign(next);setPast([]);setFuture([]);setMessage('来源已更新；历史图保留原数据，请重新选择分析。')})}>用当前 WB 更新</button>}<button className="text-btn" disabled={!!busy} onClick={copyTable}>复制为可编辑表</button></div>}
 {view==='data'&&<section><div className="stats-section-title"><input aria-label="数据表名称" value={display.name} disabled={disabled} onChange={e=>editD(t=>{t.name=e.target.value})}/><span>{display.rows.length} 行 · {display.groups.length} 组</span></div><p className="hint">每格填入一个独立单位的数值。配对设计使用左列相同 ID；空格为缺失。右键单元格可排除/恢复，原值始终保留。</p><div className="stats-grid-scroll"><table className="stats-grid"><thead><tr><th>独立单位 / 配对 ID</th>{display.groups.map((g,i)=><th key={g.id}><input aria-label={`组名 ${i+1}`} value={g.label} disabled={disabled||locked} onChange={e=>editD(t=>{t.groups[i].label=e.target.value})}/>{!locked&&!frozen&&<button aria-label={`删除组 ${g.label}`} disabled={disabled||display.groups.length<=1} onClick={()=>editD(t=>{t.groups.splice(i,1);t.rows.forEach(r=>{delete r.values[g.id];delete r.excluded[g.id]});if(t.analysis.control_group===g.id)t.analysis.control_group=t.groups[0].id})}>×</button>}</th>)}<th/></tr></thead><tbody>{display.rows.map((row,ri)=><tr key={row.id}><th><input aria-label={`样本 ID ${ri+1}`} value={row.label} disabled={disabled||locked} onChange={e=>editD(t=>{t.rows[ri].label=e.target.value})}/></th>{display.groups.map((g,gi)=><td key={g.id} className={row.excluded[g.id]?'excluded':''}><input aria-label={`数值 ${ri+1} ${gi+1}`} value={row.values[g.id]??''} disabled={disabled||locked} onChange={e=>editD(t=>{t.rows[ri].values[g.id]=e.target.value})} onPaste={e=>paste(e,ri,gi)} onContextMenu={e=>{e.preventDefault();if(!disabled&&!locked)editD(t=>{t.rows[ri].excluded[g.id]=!row.excluded[g.id]})}}/></td>)}<td><button aria-label={`删除行 ${ri+1}`} disabled={disabled||locked} onClick={()=>editD(t=>{t.rows.splice(ri,1)})}>×</button></td></tr>)}</tbody></table></div><div className="stats-actions"><button className="btn secondary" disabled={disabled||locked} onClick={()=>editD(t=>t.rows.push({id:id(),label:String(t.rows.length+1),values:{},excluded:{}}))}>添加行</button><button className="btn secondary" disabled={disabled||locked||display.groups.length>=30} onClick={()=>editD(t=>t.groups.push({id:id(),label:'Group '+(t.groups.length+1)}))}>添加组</button><button className="btn primary" onClick={()=>setView('analysis')}>设置统计分析</button></div></section>}
 {view==='analysis'&&<section><h2>{display.name}</h2><fieldset disabled={disabled} className="stats-analysis-controls"><label>统计方法<select aria-label="统计方法" value={display.analysis.method} onChange={e=>editD(t=>{t.analysis.method=e.target.value})}><option value="descriptive">仅描述统计</option><option value="welch">Welch 独立样本 t 检验</option><option value="paired">配对 t 检验</option><option value="anova">普通单因素 ANOVA</option><option value="welch_anova">Welch 单因素 ANOVA</option></select></label><label>分析尺度<select value={display.analysis.scale} onChange={e=>editD(t=>{t.analysis.scale=e.target.value})}><option value="raw">原始数值</option><option value="log2">log2（仅正值）</option></select></label>{['anova','welch_anova'].includes(display.analysis.method)&&<><label>比较范围<select aria-label="统计比较范围" value={display.analysis.scope} onChange={e=>editD(t=>{t.analysis.scope=e.target.value})}><option value="control">各组与对照</option><option value="all">全部两两比较</option></select></label><label>对照组<select value={display.analysis.control_group} onChange={e=>editD(t=>{t.analysis.control_group=e.target.value})}>{display.groups.map(g=><option value={g.id} key={g.id}>{g.label}</option>)}</select></label></>}</fieldset><label className="stats-confirm"><input type="checkbox" aria-label="确认独立单位" checked={display.confirmed} disabled={disabled||locked} onChange={e=>editD(t=>{t.confirmed=e.target.checked})}/>已确认每格代表独立生物学单位；技术重复已汇总；配对关系由 ID 明确。</label><p className="hint">普通 ANOVA 假定独立、残差近似正态及等方差；Welch 允许不等方差。多组对照采用 Dunnett，全部比较采用 Tukey；Welch 后使用 Games–Howell。方法应由实验设计决定。</p>{!frozen&&<button className="btn primary" disabled={!!busy} onClick={analyze}>运行分析</button>}
 {!run?<p className="stats-empty">{display.runs?.length?'数据或设置已改变，请重新运行分析。':'尚未运行当前分析。'}</p>:<><p className="stats-method">{run.method_text}</p>{run.omnibus&&<p>总体检验：F = {fmt(run.omnibus.statistic)}，P = {fmt(run.omnibus.p_raw)}</p>}<table className="stats-results"><thead><tr><th>组别</th><th>独立 n</th><th>均值</th><th>SD</th><th>SEM</th></tr></thead><tbody>{run.summaries.map(s=><tr key={s.group}><td>{display.groups.find(g=>g.id===s.group)?.label??s.label}</td><td>{s.n}</td><td>{fmt(s.mean)}</td><td>{fmt(s.sd)}</td><td>{fmt(s.sem)}</td></tr>)}</tbody></table>{run.comparisons.length>0&&<table className="stats-results"><thead><tr><th>对比（B−A）</th><th>效应</th><th>95% CI</th><th>P 值</th><th>校正</th></tr></thead><tbody>{run.comparisons.map((r,i)=><tr key={i}><td>{display.groups.find(g=>g.id===r.group_b)?.label} − {display.groups.find(g=>g.id===r.group_a)?.label}</td><td>{fmt(r.effect)}</td><td>{r.ci95?.map(fmt).join(' 至 ')}</td><td>{fmt(r.p_adjusted)}</td><td>{r.adjustment_method}</td></tr>)}</tbody></table>}<p className="hint">图上每组均值区间、组对差值的普通区间与多重比较同时区间分别解释。SciPy {run.scipy_version}。</p><button className="btn secondary" onClick={()=>setView('graph')}>查看图形</button></>}
 {!!display.runs?.length&&<details><summary>分析历史（{display.runs.length}）</summary>{display.runs.map(r=><button className="text-btn" key={r.id} onClick={()=>{setFrozen({id:r.id,name:'历史分析 '+r.created_at,dataset:r.dataset,run:r,style:r.dataset.style});setView('analysis')}}>{new Date(r.created_at).toLocaleString()} · {r.dataset.analysis.method}</button>)}</details>}</section>}
 {view==='graph'&&<div className="stats-graph-layout"><section className="stats-paper"><div className="stats-section-title"><h2>{frozen?.name??display.name}</h2><span>{style.width_mm} × {style.height_mm} mm</span></div>{previewError?<p role="alert">{previewError}</p>:preview?<><img src={preview.png} alt="统计图预览"/><p className="stats-caption">{preview.caption}</p>{preview.notes.map(n=><p role="alert" key={n}>{n}</p>)}</>:<p role="status">正在绘图…</p>}{!frozen&&<button className="btn secondary" disabled={!preview||!!busy||(!run&&display.analysis.method!=='descriptive')} onClick={freeze}>保存图形快照</button>}</section><fieldset className="stats-inspector" disabled={disabled}><legend>图形设置</legend>{([['kind','图形类型',[['bar_points','柱形 + 原始点'],['scatter','散点 + 均值'],['bar','柱形'],['paired','配对连线']]],['error','误差线',[['sd','SD'],['sem','SEM'],['ci95','95% CI'],['none','无']]],['annotations','统计标注',[['none','无'],['p','精确 P 值'],['stars','星号']]],['text_mode','矢量文字',[['editable','可编辑文字'],['outline','SVG 文字轮廓']]]] as const).map(([key,label,options])=><label key={key}>{label}<select aria-label={label} value={style[key]} onChange={e=>editD(t=>{t.style[key]=e.target.value})}>{options.map(([value,text])=><option value={value} key={value}>{text}</option>)}</select></label>)}{(['title','y_label'] as const).map((key,i)=><label key={key}>{i?'Y轴标题':'图形标题'}<input value={style[key]} onChange={e=>editD(t=>{t.style[key]=e.target.value})}/></label>)}{([['width_mm','宽度 mm'],['height_mm','高度 mm'],['font_size','字号 pt'],['dpi','DPI']] as const).map(([key,label])=><label key={key}>{label}<input aria-label={label} type="number" value={style[key]} onChange={e=>editD(t=>{t.style[key]=Number(e.target.value)})}/></label>)}{(['y_min','y_max'] as const).map((key,i)=><label key={key}>Y轴{i?'上限':'下限'}<input type="number" placeholder="自动" value={style[key]??''} onChange={e=>editD(t=>{t.style[key]=e.target.value===''?null:Number(e.target.value)})}/></label>)}{run&&run.comparisons.length>0&&<details><summary>选择比较标注</summary>{run.comparisons.map(r=>{const key=r.group_a+':'+r.group_b;return <label key={key}><input type="checkbox" checked={style.comparison_keys?.includes(key)??true} onChange={e=>editD(t=>{const keys=t.style.comparison_keys??run.comparisons.map(c=>c.group_a+':'+c.group_b);t.style.comparison_keys=e.target.checked?[...keys,key]:keys.filter(k=>k!==key)})}/>{display.groups.find(g=>g.id===r.group_a)?.label} ↔ {display.groups.find(g=>g.id===r.group_b)?.label}</label>})}</details>}<details><summary>散点、线条与显示顺序</summary><label>点形<select value={style.point_marker??'circle'} onChange={e=>editD(t=>{t.style.point_marker=e.target.value})}><option value="circle">圆形</option><option value="square">方形</option><option value="triangle">三角形</option></select></label><label><input type="checkbox" checked={style.hollow??false} onChange={e=>editD(t=>{t.style.hollow=e.target.checked})}/>空心散点</label>{([['point_size','点大小',4],['axis_width','坐标轴线宽',.8],['error_width','误差线宽',.8],['error_cap','误差端帽',3],['bar_width','柱宽',.6],['label_angle','组名角度',30]] as const).map(([key,label,fallback])=><label key={key}>{label}<input type="number" step="any" value={style[key]??fallback} onChange={e=>editD(t=>{t.style[key]=Number(e.target.value)})}/></label>)}{[...display.groups].sort((a,b)=>{const order=style.group_order??display.groups.map(g=>g.id);return order.indexOf(a.id)-order.indexOf(b.id)}).map((g,i)=><label key={g.id}>显示名称<input value={style.labels?.[g.id]??g.label} onChange={e=>editD(t=>{t.style.labels={...t.style.labels,[g.id]:e.target.value}})}/><button type="button" disabled={!i} onClick={()=>editD(t=>{const order=t.style.group_order?.length?[...t.style.group_order]:t.groups.map(g=>g.id);const index=order.indexOf(g.id);if(index>0){[order[index-1],order[index]]=[order[index],order[index-1]];t.style.group_order=order}})}>上移 {g.label}</button></label>)}</details>{display.groups.map((g,i)=><label className="stats-color" key={g.id}>{g.label}<input type="color" value={style.colors[g.id]??['#88B8D0','#E29EB6','#D4B483','#879CA6','#BD998B','#A9B9BF'][i%6]} onChange={e=>editD(t=>{t.style.colors[g.id]=e.target.value})}/></label>)}</fieldset></div>}
 </main></>}
 <footer className="statusbar"><span>统计与绘图 · Column / 配对 · 本地数据</span><span>基于 Titan 0.4 beta3</span></footer></div>
 {modal&&<div className="modal-backdrop"><section className="modal stats-modal" role="dialog" aria-modal="true" aria-label={modal==='import'?'导入统计数据':'统计文件位置'}><h2>{modal==='import'?'导入与粘贴数据':'选择文件位置'}</h2>{modal==='import'?<><label>数据排列<select aria-label="导入数据排列" value={importFormat} onChange={e=>{setImportFormat(e.target.value as 'wide'|'long');setImported(null)}}><option value="wide">宽表：每列一组</option><option value="long">长表：group / value / unit_id</option></select></label><p>{importFormat==='wide'?'首行填写组名；可用第一列 ID 标识配对。支持从 Excel 粘贴。':'首行需要 group、value、unit_id；可添加 pair_id。技术重复须先明确汇总。'}</p><textarea aria-label="粘贴统计数据" rows={7} value={text} onChange={e=>{setText(e.target.value);setImported(null)}} placeholder={'Control\tTreatment\n1\t2\n2\t3'}/><div className="stats-actions"><button className="btn secondary" disabled={!!busy} onClick={()=>inspectImport()}>预览粘贴数据</button>{native()&&<button className="btn secondary" onClick={chooseImport}>选择 Excel / CSV</button>}</div><label>文件完整路径<input aria-label="统计导入路径" value={location} onChange={e=>{setLocation(e.target.value);setImported(null)}}/></label><button className="text-btn" disabled={!!busy||!location} onClick={()=>inspectImport(location)}>读取文件</button>{imported?.sheets.length?<label>工作表<select value={sheet||imported.sheets[0]} onChange={e=>{setSheet(e.target.value);void inspectImport(location,e.target.value)}}>{imported.sheets.map(s=><option key={s}>{s}</option>)}</select></label>:null}{imported&&<div className="stats-import-preview"><strong>{imported.dataset.rows.length} 行 / {imported.dataset.groups.map(g=>g.label).join('、')}</strong><table><tbody>{imported.dataset.rows.slice(0,5).map(r=><tr key={r.id}><th>{r.label}</th>{imported.dataset.groups.map(g=><td key={g.id}>{r.values[g.id]}</td>)}</tr>)}</tbody></table></div>}</>:<label>完整路径<input aria-label="统计文件路径" value={location} onChange={e=>setLocation(e.target.value)}/></label>}<footer><button className="btn secondary" onClick={()=>setModal('')}>取消</button><button className="btn primary" disabled={!!busy||(modal==='import'?!imported:!location)} onClick={()=>modal==='import'?addTable(imported!.dataset):finishPath(modal,location)}>{modal==='import'?'添加数据表':'确认'}</button></footer></section></div>}
 </div>
}
