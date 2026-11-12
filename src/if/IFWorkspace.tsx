import {lazy,Suspense,useEffect,useRef,useState} from 'react'
import {save} from '@tauri-apps/plugin-dialog'
import {Box,ImagePlus,Microscope,Save} from 'lucide-react'
import type {AnalysisLocation,ModuleView} from '../workspace-navigation'
import {callEngine} from '../bridge'
import type {LibraryView} from '../ProjectLibrary'
import type {AnalysisCreation} from '../LibraryCreateDialog'
import type {ProjectLibraryModel} from '../useProjectLibrary'
import type {CloseActions,LibraryExportReceipt} from '../types'
import {canAcceptJob,editField,mergeSaved,copyRecipe,undoMask} from './state'
import type {ActiveJob,IFField,IFFigure,IFJob,IFProject,IFSelection} from './types'
import ImportDialog from './ImportDialog'
import FieldCanvas from './FieldCanvas'
import FieldSettings from './FieldSettings'
import IFResults from './Results'
import IFFigureEditor from './Figure'
import './if.css'
const VolumeViewer=lazy(()=>import('./VolumeViewer'))
const fingerprint=(p:IFProject)=>JSON.stringify(p.fields.map(f=>({id:f.id,channels:f.channels.map(c=>({id:c.id,name:c.name,source:c.source})),rois:f.rois,recipe:f.recipe,mask:f.mask,pixel_size_um:f.pixel_size_um,quantitative:f.quantitative,sample_id:f.sample_id,bio_id:f.bio_id,group:f.group,batch_id:f.batch_id})))
export interface IFLibraryActions {
 prepareLeave:()=>Promise<boolean>
 restore:(location:AnalysisLocation)=>Promise<boolean>
 open:(path:string,view:LibraryView,entryId?:string)=>Promise<boolean>
 create:(input:AnalysisCreation)=>Promise<boolean>
 demo:()=>Promise<boolean>
 showVolume:()=>void
 importFirst:(input:AnalysisCreation & {selections:IFSelection[];metadata:Record<string,unknown>})=>Promise<boolean>
}

interface Props {
 active:boolean
 volumeAvailable:boolean
 onStatsSource:(path:string)=>void
 registerClose:(actions:CloseActions)=>void
 registerLibrary:(actions:IFLibraryActions)=>void
 library:ProjectLibraryModel
 libraryBusy:boolean
 reportView:(view:ModuleView)=>void
 membership:React.ReactNode
 onExported:(receipt:LibraryExportReceipt)=>void
}

export default function IFWorkspace({active,volumeAvailable,onStatsSource,registerClose,registerLibrary,library,libraryBusy,reportView,membership,onExported}:Props){
 const [project,setProject]=useState<IFProject|null>(null),current=useRef(project);current.current=project
 const [fieldId,setFieldId]=useState(''),[tab,setTab]=useState<'analysis'|'results'|'figure'>('analysis'),[message,setMessage]=useState(''),[busy,setBusy]=useState(''),[job,setJob]=useState<IFJob|null>(null),[showImport,setShowImport]=useState(false),[template,setTemplate]=useState(false),[batch,setBatch]=useState(false),[selectedFields,setSelectedFields]=useState<string[]>([]),[destination,setDestination]=useState(''),[exportKind,setExportKind]=useState<'figure'|'results'|null>(null)
 const [showVolume,setShowVolume]=useState(false)
 const epoch=useRef(0),activeJob=useRef<ActiveJob|null>(null),flight=useRef<Promise<unknown>|null>(null),poll=useRef<ReturnType<typeof setTimeout>|undefined>(undefined),mounted=useRef(true)
 const field=project?.fields.find(f=>f.id===fieldId)??project?.fields[0],disabled=!!project?.read_only||!!busy
 function assign(p:IFProject|null){current.current=p;setProject(p)}
 async function persist(){if(flight.current)await flight.current;const input=current.current;if(!input||input.read_only||input.saved_revision===input.revision)return;const promise=callEngine<IFProject>('if_save',{project:input,expected_revision:input.saved_revision});flight.current=promise;try{const saved=await promise;if(current.current?.id===input.id)assign(mergeSaved(current.current,input,saved));void library.refresh()}finally{if(flight.current===promise)flight.current=null}}
 async function flush(){try{await persist();if(current.current&&current.current.saved_revision!==current.current.revision){await persist();if(current.current.saved_revision!==current.current.revision)throw new Error('保存期间仍有新修改')}return true}catch(e){setMessage('保存未完成，当前修改仍保留：'+e);return false}}
 async function cancel(){const pending=activeJob.current;activeJob.current=null;epoch.current++;clearTimeout(poll.current);setJob(null);if(pending)try{await callEngine('if_cancel_job',{job_id:pending.job_id})}catch(e){setMessage(String(e))}setMessage('任务已取消，本次结果不会应用。')}
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;epoch.current++;clearTimeout(poll.current)}},[])
 useEffect(()=>{registerClose({prepare:prepareLeave,finish:async()=>{
  const p=current.current;if(p?.project_path)await callEngine('if_release',{path:p.project_path})
 }})})
 useEffect(()=>{if(!project||project.read_only||project.saved_revision===project.revision||busy)return;const timer=setTimeout(()=>persist().catch(e=>setMessage('自动保存未完成：'+e)),1200);return()=>clearTimeout(timer)},[project,busy])
 async function changeProject(command:'if_new'|'if_demo'|'if_open'|'if_new_from_import',payload:object={},view:LibraryView='workspace',raiseError=false,expected?:AnalysisLocation){
  if(busy)return false
  let generation=epoch.current
  setBusy(command==='if_open'?'打开实验':'准备实验')
  setMessage('')
  try{
   if(!await flush()||generation!==epoch.current)return false
   const cancelling=cancel()
   generation=epoch.current
   await cancelling
   if(generation!==epoch.current)return false
   setMessage('')
   const p=await callEngine<IFProject>(command,payload)
   const invalid=expected&&(p.id!==expected.projectId?'原 IF 分析身份已变化，请从左栏重新打开。':
    expected.resourceId&&!p.fields.some(field=>field.id===expected.resourceId)?'原视野已移除，请从当前视野列表选择。':'')
   if(invalid){
    if(p.project_path!==current.current?.project_path)await callEngine('if_release',{path:p.project_path}).catch(()=>{})
    throw new Error(invalid)
   }
   if(generation!==epoch.current){
    if(p.project_path&&p.project_path!==current.current?.project_path)await callEngine('if_release',{path:p.project_path}).catch(()=>{})
    return false
   }
   const old=current.current
   if(old?.project_path&&old.project_path!==p.project_path)await callEngine('if_release',{path:old.project_path})
   if(generation!==epoch.current)return false
   assign(p);setFieldId(p.fields[0]?.id??'');setTab(view==='results'?'results':view==='wb'?'figure':'analysis')
   void library.refresh()
   return true
  }catch(e){if(!expected)setMessage(String(e));if(raiseError)throw e;return false}
  finally{setBusy('')}
 }
 const activeEntryId=library.entries.find(entry=>entry.path===project?.project_path)?.entry_id
 useEffect(()=>{
  if(!active||!activeEntryId||busy||libraryBusy)return
  void library.resume(activeEntryId,{view:tab==='analysis'?'workspace':tab})
 },[active,activeEntryId,tab,busy,libraryBusy])
 useEffect(()=>{
  registerLibrary({
   prepareLeave,
   restore:restoreLocation,
   open:(path,view,entryId)=>changeProject('if_open',{path,entry_id:entryId},view,true),
   create:input=>changeProject('if_new',input,'workspace',true),
   demo:()=>changeProject('if_demo',{},'workspace',true),
   showVolume:()=>setShowVolume(true),
   importFirst:input=>changeProject('if_new_from_import',input,'workspace',true),
  })
 })
 function edit(change:(p:IFProject)=>void){const p=current.current;if(!p||p.read_only)return;const next=structuredClone(p);change(next);next.revision++;assign(next);setMessage('')}
 function updateField(change:(f:IFField)=>void,kind:'display'|'analysis'|'segmentation'='analysis'){const p=current.current;if(!p||!field)return;assign(editField(p,field.id,change,kind));setMessage('')}
 async function restoreLocation(location:AnalysisLocation){
  if(!['analysis','results','figure'].includes(location.view))return false
  if(current.current?.id!==location.projectId||current.current?.project_path!==location.path){
   if(!location.path||!await prepareLeave()||!await changeProject('if_open',{path:location.path,entry_id:location.entryId},'workspace',true,location))return false
  }
  const target=current.current
  if(!target)return false
  if(location.resourceId&&!target.fields.some(field=>field.id===location.resourceId))throw new Error('原视野已移除，请从当前视野列表选择。')
  if(location.resourceId)setFieldId(location.resourceId)
  setTab(location.view as 'analysis'|'results'|'figure')
  return true
 }
 async function run(operation:string,options:Record<string,unknown>){const input=current.current;if(!input||input.read_only||activeJob.current||busy)return;const generation=epoch.current;setBusy('提交任务');setMessage('');try{const started=await callEngine<IFJob>('if_start_job',{project:input,operation,options});if(generation!==epoch.current||current.current?.id!==input.id){await callEngine('if_cancel_job',{job_id:started.job_id});return}const key={job_id:started.job_id,epoch:generation,project_id:input.id};activeJob.current=key;setJob({...started,completed:0,total:1});setBusy('');const tick=async()=>{if(!canAcceptJob(key.job_id,epoch.current,activeJob.current,current.current))return;try{const status=await callEngine<IFJob>('if_job_status',{job_id:key.job_id});if(!canAcceptJob(key.job_id,epoch.current,activeJob.current,current.current))return;setJob(status);if(status.status==='completed'){const before=current.current!;const accepted=await callEngine<IFProject>('if_accept_job',{project:before,job_id:key.job_id});if(!canAcceptJob(key.job_id,epoch.current,activeJob.current,current.current))return;const latest=current.current!;if(latest.revision!==before.revision){if(fingerprint(latest)!==fingerprint(before))throw new Error('任务完成时分析输入已改变，请重新运行');accepted.fields=accepted.fields.map(f=>{const live=latest.fields.find(v=>v.id===f.id);return live?{...f,channels:live.channels}:f});accepted.figure=latest.figure;accepted.name=latest.name;accepted.revision=Math.max(accepted.revision,latest.revision+1)}assign(accepted);setFieldId(id=>accepted.fields.some(f=>f.id===id)?id:accepted.fields[0]?.id??'');activeJob.current=null;setJob(null);setMessage(status.failures?.length?'部分视野处理失败：'+status.failures.map(f=>`${accepted.fields.find(v=>v.id===f.field_id)?.name??f.field_id}：${f.error}`).join('；'):(operation==='segment'||operation==='edit_mask'?'任务已完成。请复核核标签，然后确认分割。':'任务已完成，结果已应用。'));void library.refresh();return}if(status.status==='failed'||status.status==='cancelled'){activeJob.current=null;setJob(null);setMessage(status.error||status.message||'任务未完成');return}poll.current=setTimeout(tick,350)}catch(e){if(canAcceptJob(key.job_id,epoch.current,activeJob.current,current.current)){activeJob.current=null;setJob(null);setMessage('任务结果未应用：'+e)}}};void tick()}catch(e){setMessage(String(e))}finally{setBusy('')}}
 async function prepareLeave(){
  if(busy||!await flush())return false
  await cancel()
  setMessage('')
  return true
 }
 async function exportTo(kind:'figure'|'results'){setExportKind(kind);if((window as any).__TAURI_INTERNALS__){try{const path=await save({defaultPath:project?.name+(kind==='figure'?'-IF组图':'-IF结果'),title:'选择新的导出文件夹'});if(path)await finishExport(kind,path);else setExportKind(null)}catch(e){setMessage(String(e))}}}
 async function finishExport(kind:'figure'|'results',destination:string){if(!current.current||!destination.trim())return;setBusy('导出文件');try{const r=await callEngine<{files:string[]}&LibraryExportReceipt>(kind==='figure'?'if_export_figure':'if_export_results',{project:current.current,destination});setMessage('已导出：'+r.files.join('；'));setExportKind(null);onExported(r)}catch(e){setMessage(String(e))}finally{setBusy('')}}
 function applyTemplate(){if(!field||!current.current)return;assign(copyRecipe(current.current,field.id,selectedFields));setTemplate(false);setMessage('已应用设置；请复核各视野核标签与区域后测量。')}
 useEffect(()=>{reportView({path:project?.project_path,projectId:project?.id,name:project?.name,view:tab,resourceId:field?.id,
  busy:!!busy||!!job||showImport||template||batch||!!exportKind||showVolume})},
  [reportView,project?.project_path,project?.id,project?.name,tab,field?.id,busy,job,showImport,template,batch,exportKind,showVolume])
 return <><div className="module-pane if-pane" hidden={!active} inert={!active||libraryBusy}>
 <div className="main-shell"><header className="app-header"><div className="if-heading">{project?<><input aria-label="IF 实验名称" value={project.name} disabled={project.read_only} onChange={e=>edit(p=>{p.name=e.target.value})}/><span>{project.read_only?'只读':project.saved_revision===project.revision?'已保存':'待保存'}</span></>:<strong>免疫荧光</strong>}</div>{project&&<div className="if-header-actions">
 <button className="btn secondary" onClick={()=>setShowVolume(true)} disabled={!!busy||!!job}><Box size={15}/>3D 查看（原型）</button>
 <button className="icon-btn header-icon" aria-label="保存 IF 实验" disabled={disabled} onClick={()=>flush().then(ok=>ok&&setMessage('实验已保存。'))}><Save size={17}/></button><button className="btn secondary" disabled={disabled||!!job} onClick={()=>setShowImport(true)}><ImagePlus size={15}/>导入 IF 视野</button></div>}</header>{membership}{message&&<div className="notice" role="status"><span>{message}</span><button aria-label="关闭提示" onClick={()=>setMessage('')}>×</button></div>}{busy&&<div className="busy" role="status">{busy}…</div>}{job&&<div className="if-job" role="status"><progress max={job.total||1} value={job.completed||0}/><span>{job.message||'正在处理'} · {job.completed||0}/{job.total||1}</span><button className="btn secondary" onClick={cancel}>取消 IF 任务</button></div>}
 {project&&<><div className="workspace-navigation"><nav className="steps" aria-label="IF 实验视图">{([['analysis','图像与分析'],['results','IF 定量结果'],['figure','IF 论文组图']] as const).map(([key,label])=><button key={key} className={tab===key?'selected':''} aria-current={tab===key?'page':undefined} onClick={()=>setTab(key)}>{label}</button>)}</nav>{field&&tab==='analysis'&&<div className="if-batch-actions workbench-pickers">
 <label>视野<select aria-label="选择 IF 视野" value={field.id} onChange={event=>setFieldId(event.target.value)}>
 {project.fields.map(item=><option key={item.id} value={item.id}>{item.name} · {item.mask&&!item.mask.confirmed?'待复核':item.result?'已测量':'待测量'}</option>)}
 </select></label><button className="btn secondary" disabled={disabled||!!job} onClick={()=>{setSelectedFields(project.fields.map(f=>f.id));setBatch(true)}}>批量测量</button></div>}</div><main className="if-content">{tab==='analysis'?field?<div className="if-analysis-layout"><FieldCanvas key={field.id} field={field} disabled={disabled} onROI={roi=>updateField(f=>{f.rois.push(roi)})} onEditMask={action=>run('edit_mask',{field_id:field.id,action})} onUndoMask={()=>current.current&&assign(undoMask(current.current,field.id))}/><FieldSettings field={field} disabled={disabled} onEdit={updateField} onRun={operation=>run(operation,{field_id:field.id})} onTemplate={()=>{setSelectedFields(project.fields.filter(f=>f.id!==field.id&&f.batch_id===field.batch_id).map(f=>f.id));setTemplate(true)}}/></div>:<div className="if-empty"><Microscope size={36} strokeWidth={1}/><h2>导入第一个视野</h2><p>确认通道、样本与空间标定后开始分析。</p><button className="btn primary" disabled={disabled} onClick={()=>setShowImport(true)}>导入 IF 视野</button></div>:tab==='results'?<IFResults project={project} disabled={!!busy||!!job} onStats={()=>onStatsSource(project.project_path)} onExport={()=>exportTo('results')}/>:<IFFigureEditor project={project} disabled={disabled} onEdit={change=>edit(p=>change(p.figure))} onExport={()=>exportTo('figure')}/>}</main></>}
 <footer className="statusbar"><div className="status-summary">{project&&<><span>{project.fields.length} 个视野</span><span>{project.fields.filter(f=>f.result).length} 已测量</span>{(project.synthetic||project.demo)&&<b className="synthetic-label">纯合成示例 · 非实验数据</b>}</>}</div><div className="status-system"><span className="pixel-note">原始通道参与定量</span></div></footer></div>{showImport&&<ImportDialog onClose={()=>setShowImport(false)} onImport={(selections:IFSelection[],metadata)=>{setShowImport(false);void run('import',{selections,metadata})}}/>}{(template||batch)&&project&&<div className="modal-backdrop"><section className="modal if-batch-dialog" role="dialog" aria-modal="true" aria-label={template?'应用分析模板':'批量测量视野'}><h2>{template?'复制分析设置':'批量测量'}</h2><p className="hint">{template?'按通道名称匹配，复制分析与冻结阈值。区域保持各视野原图坐标。':'保留各视野设置；核分析需先逐一确认 mask。失败视野保持缺失，不记为零。'}</p>{project.fields.filter(f=>!template||(f.id!==field?.id&&f.batch_id===field?.batch_id)).map(f=><label className="if-check" key={f.id}><input type="checkbox" checked={selectedFields.includes(f.id)} onChange={e=>setSelectedFields(v=>e.target.checked?[...v,f.id]:v.filter(id=>id!==f.id))}/>{f.name} · {f.bio_id} · {f.batch_id}</label>)}<footer><button className="btn secondary" onClick={()=>{setTemplate(false);setBatch(false)}}>取消</button><button className="btn primary" disabled={!selectedFields.length} onClick={()=>{try{if(template)applyTemplate();else{setBatch(false);void run('batch',{field_ids:selectedFields})}}catch(e){setMessage(String(e))}}}>{template?'确认应用到所选视野':'开始批量测量'}</button></footer></section></div>}{exportKind&&!(window as any).__TAURI_INTERNALS__&&<div className="modal-backdrop"><section className="modal" role="dialog" aria-label="IF 导出位置"><h2>导出到新文件夹</h2><label>完整文件夹路径<input aria-label="IF 导出路径" value={destination} onChange={e=>setDestination(e.target.value)}/></label><footer><button className="btn secondary" onClick={()=>setExportKind(null)}>取消</button><button className="btn primary" disabled={!destination.trim()||!!busy} onClick={()=>finishExport(exportKind,destination)}>确认导出</button></footer></section></div>}</div>{volumeAvailable&&showVolume&&<Suspense fallback={<div className="modal-backdrop"><section className="modal">正在打开 3D 查看…</section></div>}><VolumeViewer onClose={()=>setShowVolume(false)}/></Suspense>}</>
}
