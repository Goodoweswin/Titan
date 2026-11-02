import {useEffect,useRef,useState} from 'react'
import {open,save,confirm} from '@tauri-apps/plugin-dialog'
import {getCurrentWindow} from '@tauri-apps/api/window'
import {Activity,ArrowDownToLine,Copy,FolderOpen,ImagePlus,Microscope,Plus,Save,ScanLine,ShieldCheck,Sparkles,Undo2,Redo2} from 'lucide-react'
import appIcon from '../assets/brand/titan-app-icon-128.png'
import gorillaHead from '../assets/brand/titan-head.svg'
import {callEngine} from './bridge'
import {createProject,editProject,commitResult,mergeSaved,restoreHistory,acceptReview,mergeImported,retainResult} from './state'
import type {Project,AnalysisResult,Rect,PlotSettings,DetectionPreview,ImageInspection,LibraryEntry,FrozenFigure,FigureSettings,FigureDocumentMetadata,PlotPreview} from './types'
import ImagePagePicker from './ImagePagePicker'
import Workspace from './Workspace'
import LaneSetup, {type CanvasHistory} from './LaneSetup'
import LaneResults from './LaneResults'
import ExportPreview from './ExportPreview'
import Results from './Results'
import SampleEditor from './SampleEditor'
import ProjectNavigator from './ProjectNavigator'
import ProjectLibrary from './ProjectLibrary'
import useProjectLibrary from './useProjectLibrary'
import FigureDocument from './FigureDocument'
import {mergeSavedFrom,sameProjectContext} from './project-library-state'
import type {ArchiveFigureRequest,LiveFigurePreview} from './PublicationFigure'
import type {Selection} from './ProjectNavigator'
import QualityPanel from './QualityPanel'
import {appendCandidates} from './workflow'
import WorkspaceHeader from './WorkspaceHeader'
import WbFigureEditor,{type WbHistory} from './WbFigureEditor'

const native=()=>Boolean((window as any).__TAURI_INTERNALS__)
async function ask(text:string){return native()?await confirm(text,{title:'Titan',kind:'warning'}):window.confirm(text)}
export default function App(){
 const [project,setProject]=useState<Project|null>(null),[result,setResult]=useState<AnalysisResult|null>(null)
 const library=useProjectLibrary()
 const [frozen,setFrozen]=useState<FrozenFigure|null>(null),frozenRef=useRef<FrozenFigure|null>(null);frozenRef.current=frozen
 const figurePreview=useRef<LiveFigurePreview|null>(null)
 const wbDirty=useRef(false),wbHistory=useRef<WbHistory|null>(null),wbBusy=useRef(false)
 const [wbWorking,setWbWorking]=useState(false)
 const [workspaceEpoch,setWorkspaceEpoch]=useState(0),[switching,setSwitching]=useState(false),projectNavigation=useRef(0)
 const [exportContext,setExportContext]=useState<{project:Project;result:AnalysisResult;settings?:PlotSettings;figure?:FigureSettings;frozenId?:string;frozenVersion?:string;preview?:PlotPreview}|null>(null)
 const [showExport,setShowExport]=useState(false)
 const [pageChoice,setPageChoice]=useState<{path:string;info:ImageInspection;resolve:(pages:number[]|null)=>void}|null>(null)
 function choosePages(pages:number[]|null){pageChoice?.resolve(pages);setPageChoice(null)}
 const [candidates,setCandidates]=useState<DetectionPreview|null>(null)
 const staged=candidates&&candidates.projectId===project?.id&&candidates.revision===project?.revision?candidates:null
 useEffect(()=>{setCandidates(null);if(!frozenRef.current)setShowExport(false)},[project?.id,project?.revision])
 const [tab,setTab]=useState<'workspace'|'samples'|'results'|'wb'>('workspace')
 const [manualMode,setManualMode]=useState(false),[activeSetId,setActiveSetId]=useState('')
 const guided=!!project&&!(project as any).demo&&!manualMode
 useEffect(()=>{setManualMode(false);setActiveSetId('')},[project?.id])
 const navigation=useRef(0)
 async function navigate(next:typeof tab,discardApproved=false){if(!discardApproved&&!await canLeaveFigure())return;navigation.current++;frozenRef.current=null;setFrozen(null);figurePreview.current=null;setTab(next)}
 const [busy,setBusy]=useState(''),[message,setMessage]=useState(''),[connected,setConnected]=useState(false)
 const [recoveryPath,setRecoveryPath]=useState('')
 const [selection,setSelection]=useState<Selection>({imageId:'',roiId:'',ids:[]})
 const [textSize,setTextSize]=useState(()=>{try{return localStorage.getItem('titan-text-size')==='large'?'large':'standard'}catch{return 'standard'}})
 useEffect(()=>{document.documentElement.dataset.textSize=textSize;try{localStorage.setItem('titan-text-size',textSize)}catch{}},[textSize])
 function select(s:Selection){setSelection(s);navigate('workspace')}
 function locate(id:string){const r=project?.rois.find(r=>r.id===id);if(r){if(guided&&r.band_set_id){setActiveSetId(r.band_set_id);navigate(r.role==='reference'?'workspace':'samples')}else select({imageId:r.image_id,roiId:r.id,ids:[]})}}
 const [canvasHistory,setCanvasHistory]=useState<CanvasHistory|null>(null)
 const [past,setPast]=useState<Project[]>([]),[future,setFuture]=useState<Project[]>([])
 const current=useRef(project),resultRef=useRef(result),job=useRef(0),persisting=useRef(false),saveFlight=useRef<Promise<Project>|null>(null);current.current=project;resultRef.current=result
 function assignProject(p:Project|null){current.current=p;setProject(p)}
 function assignResult(r:AnalysisResult|null){resultRef.current=r;setResult(r)}
 useEffect(()=>{callEngine('health').then(()=>setConnected(true)).catch(e=>setMessage(String(e)))},[])
 const dirty=!!project&&project.saved_revision!==project.revision
 async function execute<T,>(label:string,task:()=>Promise<T>):Promise<T|undefined>{
  setBusy(label);setMessage('');const token=++job.current
  try{const value=await task();return job.current===token?value:undefined}catch(e){if(job.current===token)setMessage(String(e));return undefined}
  finally{if(job.current===token)setBusy('')}
 }
 function edit(f:(draft:Project)=>void){const base=current.current;if(!base)return;try{const p=editProject(base,f);setPast(v=>[...v.slice(-29),base]);setFuture([]);assignProject(p);assignResult(retainResult(base,p,resultRef.current));setMessage('')}catch(e){setMessage(String(e))}}
 async function persistSnapshot(input:Project,path:string,asCopy=false){
  const flight=callEngine<Project>('save_project',{project:{...input,read_only:false},path,expected_revision:asCopy?null:input.saved_revision??null})
  saveFlight.current=flight;persisting.current=true
  try{
   const saved=await flight,accepted=sameProjectContext(current.current,input)
   if(accepted){const merged=mergeSavedFrom(current.current,input,saved);if(merged){delete merged.upgrade_from;assignProject(merged)}}
   else if(saved.project_path!==current.current?.project_path)await callEngine('release_project',{path:saved.project_path}).catch(()=>{})
   if(accepted&&input.project_path&&input.project_path!==saved.project_path)await callEngine('release_project',{path:input.project_path}).catch(()=>{})
   if(saved.project_path)void library.remember(saved.project_path)
   return saved
  }finally{if(saveFlight.current===flight){saveFlight.current=null;persisting.current=false}}
 }
 async function flushCurrent(){
  if(saveFlight.current)try{await saveFlight.current}catch(e){setMessage('保存未完成：'+String(e));return false}
  const p=current.current;if(!p||p.saved_revision===p.revision)return true
  if(!p.project_path||p.upgrade_from||p.read_only)return await ask('当前实验尚有未保存的修改，放弃修改并切换？')
  try{await persistSnapshot(p,p.project_path);const latest=current.current;if(!sameProjectContext(latest,p)||latest?.saved_revision!==latest?.revision){setMessage('保存期间仍有新修改，请完成保存后再切换。');return false}return true}catch(e){setMessage('自动保存未完成，当前工作仍保留：'+String(e));return false}
 }
 async function canLeaveFigure(){
  if(wbDirty.current&&!await ask('当前组图有未保存修改，放弃并切换？已保存组图保持不变。'))return false
  return !figurePreview.current?.dirty||await ask('当前图表有未保存的样式草稿。放弃这些草稿并切换？已保存图表保持不变。')
 }
 async function prepareWbSave(){
  const input=current.current,token=projectNavigation.current
  if(!input||input.read_only)throw new Error('请在可写实验中保存组图')
  if(!input.project_path){await saveProject(false,true);if(current.current?.id!==input.id||token!==projectNavigation.current||!current.current?.project_path)throw new Error('请先保存实验')}
  if(!await flushCurrent()||!current.current||current.current.id!==input.id)throw new Error('实验已切换或保存未完成')
  return current.current
 }
 async function activateProject(p:Project){
  const old=current.current;choosePages(null);figurePreview.current=null;frozenRef.current=null;setFrozen(null);setShowExport(false);setCandidates(null)
  if(old?.project_path&&old.project_path!==p.project_path)await callEngine('release_project',{path:old.project_path}).catch(()=>{})
  job.current++;setBusy('');setSelection({imageId:p.images[0]?.id??'',roiId:'',ids:[]});assignProject(p);setPast([]);setFuture([]);assignResult(null);setTab('workspace');setManualMode(false);setActiveSetId('');setWorkspaceEpoch(v=>v+1);setMessage('')
 }
 async function switchProject(p:Project){
  if(!await canLeaveFigure()||!await flushCurrent()){if(p.project_path&&p.project_path!==current.current?.project_path)await callEngine('release_project',{path:p.project_path}).catch(()=>{});return false}
  await activateProject(p);return true
 }
 async function newExperiment(){
  const token=++projectNavigation.current;setSwitching(true)
  try{
   if(!await canLeaveFigure()||!await flushCurrent())return
   const base=current.current
   const created=await execute<{project:Project;entry:LibraryEntry}>('创建并保存实验',()=>callEngine('library_create',{name:'未命名实验'}))
   if(!created)return
   if(token!==projectNavigation.current||current.current?.id!==base?.id||current.current?.project_path!==base?.project_path||current.current?.revision!==base?.revision){await callEngine('release_project',{path:created.project.project_path}).catch(()=>{});void library.refresh();return}
   await activateProject(created.project);void library.refresh()
  }finally{if(token===projectNavigation.current)setSwitching(false)}
 }
 async function loadDemo(){const p=await execute<Project>('准备合成示例',()=>callEngine('demo'));if(p)await switchProject(p)}
 async function importImages(){
  if(!project||project.read_only)return
  const paths=await open({multiple:true,filters:[{name:'原始 WB 图像',extensions:['tif','tiff','png']}]});if(!paths)return
  if(!sameProjectContext(current.current,project))return
  let p=project;const failures:string[]=[]
  await execute('导入原始图像',async()=>{
   for(const path of Array.isArray(paths)?paths:[paths])try{
    if(!sameProjectContext(current.current,project))return
    const info=await callEngine<ImageInspection>('inspect_image',{path})
    if(!sameProjectContext(current.current,project))return
    const pages=info.page_count>1?await new Promise<number[]|null>(resolve=>setPageChoice({path,info,resolve})):[0]
    if(!pages)continue
    for(const page_index of pages){
     if(!sameProjectContext(current.current,project))return
     p=await callEngine<Project>('import_image',{project:p,path,page_index,expected_sha256:info.sha256})
    }
   }catch(e){failures.push(`${path}: ${e}`)}
   if(!sameProjectContext(current.current,project))return
   const added=p.images.length-project.images.length
   if(added){assignProject(mergeImported(current.current,project,p));assignResult(null)}
   setMessage(failures.length?failures.join('\n'):added?`已导入 ${added} 张图像，请确认极性与编码上界。`:'未导入图像。')
  })
 }
 async function saveProject(asCopy=false,fromWb=false){
  if(wbBusy.current&&!fromWb){setMessage('请等待组图操作完成后再保存实验副本。');return}
  if(saveFlight.current)try{await saveFlight.current}catch(e){setMessage(String(e));return}
  const input=current.current;if(!input)return
  let path:string|null|undefined=asCopy||input.upgrade_from?null:input.project_path
  if(!path)path=await save({defaultPath:`${input.name.replace(/[\/\\:]/g,'_')}.titanwb`,title:'保存为项目文件夹',filters:[{name:'Titan 项目',extensions:['titanwb']}]})
  if(!path||!sameProjectContext(current.current,input))return
  const saved=await execute<Project>('保存实验',()=>persistSnapshot(input,path!,asCopy))
  if(saved)setMessage('实验已保存；保存期间的新修改仍保留。')
 }
 async function readProject(path:string){
  try{const p=await callEngine<Project>('open_project',{path});setRecoveryPath('');return p}
  catch(e){
   if(String(e).includes('写入')){
    // Backend recovery only releases locks whose owner is demonstrably gone.
    try{const p=await callEngine<Project>('recover_project',{path});setRecoveryPath('');return p}catch{}
    if(await ask('项目已锁定，是否只读打开？')){const p=await callEngine<Project>('open_project',{path,read_only:true});setRecoveryPath('');return p}
   }
   setRecoveryPath(path);throw e
  }
 }
 async function openPath(path:string,view:'workspace'|'results'|'wb'='workspace',figureId?:string){
  const token=++projectNavigation.current;setSwitching(true)
  try{
   if(!await canLeaveFigure()||!await flushCurrent())return
   if(current.current?.project_path!==path){
    const before=current.current,p=await readProject(path)
    if(token!==projectNavigation.current||!((!before&&!current.current)||sameProjectContext(current.current,before)&&current.current?.revision===before?.revision)){if(p.project_path!==current.current?.project_path)await callEngine('release_project',{path:p.project_path}).catch(()=>{});return}
    await activateProject(p)
   }
   if(token!==projectNavigation.current)return
   void library.remember(path)
   if(figureId){const view=navigation.current,loaded=await callEngine<FrozenFigure>('load_figure',{path,figure_id:figureId});if(token!==projectNavigation.current||view!==navigation.current||current.current?.project_path!==path)return;setShowExport(false);figurePreview.current=null;frozenRef.current=loaded;setFrozen(loaded);navigation.current++;setTab('results')}
   else{if(view==='workspace')setActiveSetId(current.current?.band_sets.find(g=>g.role==='reference')?.id??'');navigate(view,true)}
  }catch(e){if(token===projectNavigation.current)setMessage(String(e))}
  finally{if(token===projectNavigation.current)setSwitching(false)}
 }
 async function openProject(){const path=await open({directory:true,multiple:false,title:'选择 .titanwb 项目文件夹'});if(path&&!Array.isArray(path))await openPath(path)}
 async function relocateProject(entry:LibraryEntry){const path=await open({directory:true,multiple:false,title:'重新定位 .titanwb 项目'});if(!path||Array.isArray(path))return;const located=await library.remember(path,entry.entry_id);if(located)await openPath(located.path)}
 async function recover(){
  if(!recoveryPath||!await ask('仅在旧写入进程已退出时恢复锁。损坏的项目会从有效备份创建新副本，原损坏文件保留。继续？'))return
  const p=await execute<Project>('恢复项目',()=>callEngine('recover_project',{path:recoveryPath}))
  if(p){await switchProject(p);setRecoveryPath('');setMessage('项目已恢复；若使用了备份，已创建独立恢复副本。')}
 }
 async function review(){
  if(!project)return
  const p=structuredClone(project);p.revision++;p.rois.forEach(r=>r.reviewed_revision=r.backgrounds.length?p.revision:null)
  const checked=await execute<Project>('检查条带与引用',()=>callEngine('validate',{project:p}))
  if(checked){const accepted=acceptReview(current.current,project,checked);if(!accepted){setMessage('复核期间输入已变化，请重新复核。');return}setPast(v=>[...v,project]);assignProject(accepted);assignResult(null);setMessage('已记录复核；缺少背景的ROI仍保持待复核。')}
 }
 async function analyze(){
  if(!project)return
  const navigationAtStart=navigation.current
  const r=await execute<AnalysisResult>('计算原始信号',()=>callEngine('analyze',{project}))
  if(r&&current.current&&sameProjectContext(current.current,project)){const accepted=commitResult(current.current,r);if(accepted){assignResult(accepted);if(navigation.current===navigationAtStart)setTab('results')}else setMessage('输入已变化，旧计算结果已丢弃。')}
 }
 async function detect(imageId:string,window:Rect,analyte:string,role:'target'|'reference'){
  if(!project||project.read_only)return;const p=project
  setCandidates(null)
  const boxes=await execute<Rect[]>('识别候选条带',()=>callEngine('detect',{project:p,image_id:imageId,window,settings:{}}));if(!boxes)return
  if(!sameProjectContext(current.current,p)||current.current?.revision!==p.revision){setMessage('输入已变化，旧识别结果已丢弃。');return}
  if(!boxes.length){setMessage('此区域没有识别到候选条带，请调整范围或手动画框。');return}
  setCandidates({projectId:p.id,revision:p.revision,imageId,analyte,role,boxes,included:boxes.map((_,i)=>i)})
  setMessage('候选尚未加入项目。请排除不需要的框，再确认加入。')
 }
 function acceptCandidates(){
  if(!staged||!staged.included.length||project?.read_only)return
  edit(d=>{const added=appendCandidates(d,staged.imageId,staged.boxes,staged.analyte,staged.role,staged.included);setMessage(`已加入 ${added} 个候选，跳过 ${staged.included.length-added} 个已有同泳道、同名称、同角色的条带。请核对泳道、补充背景并复核。`)})
  setCandidates(null)
 }
 function historyUndo(redo=false){
  if(tab==='wb'){if(redo)wbHistory.current?.redo();else wbHistory.current?.undo();return}
  if(!project||frozenRef.current||figurePreview.current?.dirty)return
  if(guided&&tab!=='results'&&canvasHistory){if(redo?canvasHistory.canRedo:canvasHistory.canUndo){(redo?canvasHistory.redo:canvasHistory.undo)();return}if(canvasHistory.dirty)return}
  const list=redo?future:past;if(!list.length)return
  const p=restoreHistory(project,list[list.length-1])
  if(redo){setFuture(list.slice(0,-1));setPast(v=>[...v,project])}else{setPast(list.slice(0,-1));setFuture(v=>[...v,project])}
  assignProject(p);assignResult(retainResult(project,p,resultRef.current))
 }
 useEffect(()=>{
  const listener=(e:KeyboardEvent)=>{
   if(!(e.metaKey||e.ctrlKey)||e.key.toLowerCase()!=='z'||(e.target instanceof HTMLElement&&(e.target.closest('input,textarea,select,[contenteditable="true"]'))))return
   if(!project||project.read_only||busy)return
   e.preventDefault();historyUndo(e.shiftKey)
  }
  window.addEventListener('keydown',listener);return()=>window.removeEventListener('keydown',listener)
 },[project,past,future,busy,canvasHistory,guided,tab])
 function onFigurePreview(value:LiveFigurePreview|null){figurePreview.current=value}
 function stillViewingFigure(history:FrozenFigure,token:number,view:number){return projectNavigation.current===token&&navigation.current===view&&frozenRef.current===history&&current.current?.project_path===history.project.project_path}
 function openExport(){
  const history=frozenRef.current,p=history?.project??current.current,r=history?.result??resultRef.current;if(!p||!r)return
  const preview=figurePreview.current
  const matching=preview&&sameProjectContext(preview.project,p)&&preview.project.revision===p.revision?preview:null
  const data=matching?.data
  setExportContext({project:p,result:r,settings:matching?.ready?data?.settings:matching?.settings,figure:matching?.ready?data?.figure_settings:matching?.figure_settings,frozenId:history?.document.id,frozenVersion:history?.document.selected_version,preview:data});setShowExport(true)
 }
 async function archiveFigure(request:ArchiveFigureRequest){
  const activeAtStart=frozenRef.current,token=projectNavigation.current,view=navigation.current
  let p=request.project,r=request.result
  if(!request.frozen){
   if(!sameProjectContext(current.current,p))throw new Error('当前实验已切换，本次图表未写入新项目')
   if(!await flushCurrent())throw new Error('请先完成项目保存')
   const latest=current.current,latestResult=resultRef.current
   if(!latest||!latestResult||!sameProjectContext(latest,p)||(r.source_signature?latestResult.source_signature!==r.source_signature:latest.revision!==p.revision))throw new Error('分析输入已改变，请等待新结果后保存图表')
   p=latest;r=latestResult
  }
  const doc=await callEngine<FigureDocumentMetadata>('save_figure',{...request,project:p,result:r})
  if(current.current?.project_path!==p.project_path)await callEngine('release_project',{path:p.project_path}).catch(()=>{})
  await library.refresh()
  if(request.frozen&&activeAtStart&&stillViewingFigure(activeAtStart,token,view)){const loaded=await callEngine<FrozenFigure>('load_figure',{path:p.project_path,figure_id:doc.id});if(stillViewingFigure(activeAtStart,token,view)){frozenRef.current=loaded;setFrozen(loaded)}}
  return doc
 }
 async function updateFigureSource(){
  const history=frozenRef.current,p=current.current,r=resultRef.current;if(!history||!p||!r)return
  const token=++projectNavigation.current,view=navigation.current
  try{if(!await flushCurrent()||!stillViewingFigure(history,token,view))return;const preview=figurePreview.current?.data;const doc=await archiveFigure({project:current.current!,result:r,figure_settings:preview?.figure_settings??history.figure_settings,settings:preview?.settings??history.settings,name:history.document.name,figure_id:history.document.id,expected_version:history.document.current_version,update_source:true});if(doc&&stillViewingFigure(history,token,view)){const loaded=await callEngine<FrozenFigure>('load_figure',{path:p.project_path,figure_id:doc.id});if(!stillViewingFigure(history,token,view))return;frozenRef.current=loaded;setFrozen(loaded);setMessage('已用当前分析更新源数据，旧版本仍保留。')}}catch(e){if(stillViewingFigure(history,token,view))setMessage(String(e))}
 }
 async function openFigureVersion(version:string){const history=frozenRef.current,token=++projectNavigation.current,view=navigation.current;if(!history||!await canLeaveFigure()||!stillViewingFigure(history,token,view))return;try{const loaded=await callEngine<FrozenFigure>('load_figure',{path:history.project.project_path,figure_id:history.document.id,version_id:version});if(!stillViewingFigure(history,token,view))return;figurePreview.current=null;frozenRef.current=loaded;setFrozen(loaded);setShowExport(false)}catch(e){if(stillViewingFigure(history,token,view))setMessage(String(e))}}
 async function exportResult(settings:PlotSettings,figure:FigureSettings){
  const context=exportContext;if(!context)return
  const path=await save({defaultPath:`${context.project.name}-结果`,title:'选择新的结果目录'});if(!path)return
  const stillSelected=context.frozenId?frozenRef.current?.document.id===context.frozenId&&frozenRef.current?.document.selected_version===context.frozenVersion:sameProjectContext(current.current,context.project)&&current.current?.revision===context.project.revision
  if(!stillSelected)throw new Error('项目或图表已变化，请重新预览后导出')
  const exported=await callEngine<{outputs:Record<string,string>}>('export',{project:context.project,result:context.result,destination:path,settings,figure_settings:figure})
  if(exported){
   setShowExport(false);setMessage(`已导出到 ${path}`)
   if(!context.project.read_only)try{await archiveFigure({project:context.project,result:context.result,figure_settings:figure,settings,name:(figure.title||'导出图表')+' · '+new Date().toLocaleTimeString(),frozen:!!context.frozenId,export_origin:{path,png_sha256:exported.outputs['plot.png']}})}catch(e){setMessage(`已导出到 ${path}；左栏归档未完成：${e}`)}
  }
 }
 useEffect(()=>{
  if(!native())return;let stop:(()=>void)|undefined
  getCurrentWindow().onCloseRequested(async e=>{
   e.preventDefault();if(!await canLeaveFigure()||!await flushCurrent())return;const p=current.current
   if(p?.project_path)await callEngine('release_project',{path:p.project_path}).catch(()=>{})
   await getCurrentWindow().destroy()
  }).then(fn=>stop=fn);return()=>stop?.()
 },[])
 useEffect(()=>{
  if(!project?.project_path||project.read_only||project.upgrade_from||project.saved_revision===project.revision||busy||switching)return
  const input=project,timer=setTimeout(async()=>{if(saveFlight.current)return;try{await persistSnapshot(input,input.project_path!)}catch(e){setMessage(`自动保存未完成：${e}。当前修改仍在内存中，请手动保存。`)}},1500)
  return()=>clearTimeout(timer)
 },[project,busy,switching])
 useEffect(()=>{if(project?.project_path&&project.saved_revision===project.revision)void library.remember(project.project_path)},[project?.project_path,project?.saved_revision])
 useEffect(()=>{
  if(!guided||!project?.band_sets.length||result?.input_revision===project.revision)return
  const input=project;let cancelled=false
  const timer=setTimeout(()=>callEngine<AnalysisResult>('analyze',{project:input}).then(data=>{
   if(!cancelled&&sameProjectContext(current.current,input)&&current.current?.revision===input.revision)assignResult(commitResult(input,data))
  }).catch(e=>{if(!cancelled)setMessage(String(e))}),300)
  return()=>{cancelled=true;clearTimeout(timer)}
 },[project,guided])
 const entries=library.entries.map(entry=>entry.path===project?.project_path?{...entry,name:project.name,figures:entry.figures.map(doc=>({...doc,source_stale:result?.source_signature?doc.source_signature!==result.source_signature:dirty||doc.source_stale}))}:entry)
 const activeEntry=entries.find(e=>e.path===project?.project_path)
 const figureDocument=activeEntry?.figures.find(f=>f.default_key===(project?.figure_settings?.panel_key||'all'))
 const reviewed=project?.rois.filter(r=>r.reviewed_revision===project.revision).length??0
 return <div className="app-shell">
  <aside className="sidebar"><div className="brand"><img className="brand-mark" src={appIcon} alt="" aria-hidden="true"/><div className="brand-name"><strong>Titan</strong></div></div>
   <nav className="analysis-modules" aria-label="分析模块"><button type="button" className="nav active module-nav" aria-current="page" title="Western blot" onClick={()=>navigate('workspace')}><ScanLine size={18}/><span>Western blot</span></button><button type="button" className="nav module-nav" disabled title="免疫荧光分析待开发"><Microscope size={18}/><span>免疫荧光</span><span className="module-state">待开发</span></button></nav>
   <button className="nav" disabled={switching} onClick={newExperiment}><Plus size={18}/>新建实验</button><button className="nav" disabled={switching} onClick={()=>openProject().catch(e=>setMessage(String(e)))}><FolderOpen size={18}/>打开项目</button>
   <ProjectLibrary entries={entries} project={project} activeFigure={frozen?.document.id??''} currentView={tab==='wb'?'wb':tab==='results'?'results':'workspace'} error={library.error} onRetry={library.refresh} onRelocate={relocateProject} onOpen={(entry,view,figureId)=>openPath(entry.path,view,figureId)}/>
   {project&&!guided&&!frozen&&tab!=='wb'&&<ProjectNavigator project={project} selection={selection} onSelect={select}/>}
   <button className="nav library-demo" onClick={loadDemo}><Sparkles size={18}/>探索合成示例</button>
  </aside>
  <div className={`main-shell${project?'':' welcome-shell'}`}><WorkspaceHeader project={project} dirty={dirty} switching={switching} textSize={textSize} onTextSize={setTextSize} onName={name=>edit(p=>p.name=name)}>
   {project&&<>
    <button className="icon-btn header-icon" aria-label="保存实验" title="保存实验" disabled={!!busy||wbWorking} onClick={()=>saveProject(project.read_only).catch(e=>setMessage(String(e)))}><Save size={17}/></button>
    <button className="icon-btn header-icon" aria-label="另存副本" title="另存副本" disabled={!!busy||wbWorking} onClick={()=>saveProject(true).catch(e=>setMessage(String(e)))}><Copy size={17}/></button>
    {tab==='wb'&&<button className={project.images.length?'icon-btn header-icon':'btn primary'} aria-label="导入图像" title="导入图像" disabled={!!busy||wbWorking||project.read_only||switching} onClick={()=>importImages().catch(e=>setMessage(String(e)))}><ImagePlus size={15}/>{!project.images.length&&'导入图像'}</button>}
    {tab!=='wb'&&<><span className="header-separator" aria-hidden="true"/>
     <button className="icon-btn header-icon" title="撤销" disabled={(!(guided&&tab!=='results'&&canvasHistory?.canUndo)&&(!past.length||(guided&&tab!=='results'&&!!canvasHistory?.dirty)))||project.read_only||!!busy||!!frozen} onClick={()=>historyUndo()}><Undo2 size={16}/></button>
     <button className="icon-btn header-icon" title="重做" disabled={(!(guided&&tab!=='results'&&canvasHistory?.canRedo)&&(!future.length||(guided&&tab!=='results'&&!!canvasHistory?.dirty)))||project.read_only||!!busy||!!frozen} onClick={()=>historyUndo(true)}><Redo2 size={16}/></button>
     {tab!=='results'&&!frozen&&<button className="btn secondary" disabled={!!busy||project.read_only||switching} onClick={()=>importImages().catch(e=>setMessage(String(e)))}><ImagePlus size={15}/>导入图像</button>}
     {!guided&&<button className={`btn ${tab==='results'?'secondary':'primary'}`} disabled={!!busy||!project.rois.length} onClick={analyze}><Activity size={15}/>开始定量</button>}
     {(tab==='results'||frozen)&&<button className="btn primary" disabled={!result||!!busy} onClick={openExport}><ArrowDownToLine size={15}/>导出结果</button>}
     {manualMode&&<button className="text-btn" onClick={()=>{setManualMode(false);navigate('workspace')}}>返回简洁流程</button>}
    </>}
   </>}
  </WorkspaceHeader>
  {message&&<div className="notice" role="status"><span>{message}</span>{recoveryPath&&<button className="btn secondary" onClick={recover}>尝试恢复项目</button>}<button onClick={()=>setMessage('')}>×</button></div>}{busy&&<div className="busy" role="status"><img className="titan-loader" src={gorillaHead} alt="" aria-hidden="true"/>{busy}…{(busy.startsWith('计算')||busy.startsWith('识别'))&&<button onClick={()=>{job.current++;setBusy('');setMessage('已取消等待，本次结果不会写入当前项目。')}}>取消等待</button>}</div>}
  {!project?<section className="welcome">
   <div className="welcome-hero"><div className="welcome-copy"><h1>Western blot</h1><div className="welcome-actions"><button className="btn primary" onClick={newExperiment}><Plus size={17}/>新建实验</button><button className="btn secondary" onClick={loadDemo}><Sparkles size={17}/>体验合成示例</button></div></div>
   <div className="welcome-card"><div className="preview-heading"><span><ScanLine size={15}/>条带预览</span></div><div className="signal-preview"><div className="preview-lanes" aria-hidden="true">{Array.from({length:6},(_,i)=><span key={i}>L{i+1}</span>)}</div><svg viewBox="0 0 420 174" role="img" aria-label="条带分析流程示意，非实验图像"><defs><linearGradient id="membrane" x2="1" y2="1"><stop stopColor="#e2e6ec"/><stop offset="1" stopColor="#f4f5f8"/></linearGradient><filter id="band-soften"><feGaussianBlur stdDeviation="1.7"/></filter></defs><rect width="420" height="174" rx="5" fill="url(#membrane)"/>{[.42,.6,.48,.83,.67,.9].map((opacity,i)=><g key={i}><rect x={28+i*64} y={53+(i%2)*2} width={36} height={9+(i%3)*2} rx="3" fill="#253140" opacity={opacity} filter="url(#band-soften)"/><rect x={28+i*64} y="122" width={36} height="8" rx="3" fill="#253140" opacity={.58+(i%3)*.05} filter="url(#band-soften)"/><rect x={21+i*64} y="43" width="50" height="32" rx="3" fill="#406de406" stroke="#668bea" strokeWidth=".85"/><rect x={21+i*64} y="111" width="50" height="29" rx="3" fill="none" stroke="#90a1bc" strokeWidth=".8" strokeDasharray="3 3"/></g>)}</svg><div className="preview-legend"><span><i/>目标信号</span><span><i/>上样参考</span><small>示意图</small></div></div></div></div>
   </section>:
   <><div className="workspace-navigation">
    <nav className="steps" aria-label="实验视图">{(guided?([['workspace','内参'],['samples','目标'],['results','结果']] as const):([['workspace','图像与条带'],['samples','样本与分析设置'],['results','定量结果']] as const)).map(([t,label])=><button aria-label={label} key={t} onClick={()=>{if(guided&&t==='workspace')setActiveSetId(project.band_sets.find(g=>g.role==='reference')?.id??'');if(guided&&t==='samples'&&!project.band_sets.some(g=>g.id===activeSetId&&g.role==='target'))setActiveSetId('');navigate(t)}} className={tab===t?'selected':''} aria-current={tab===t?'page':undefined}>{label}</button>)}<button aria-label="WB 组图" onClick={()=>navigate('wb')} className={tab==='wb'?'selected':''} aria-current={tab==='wb'?'page':undefined}>WB 组图</button></nav>
    {guided&&!frozen&&tab!=='results'&&tab!=='wb'&&project.band_sets.length>0&&<div className="workspace-proteins"><label>当前蛋白<select aria-label="当前蛋白" value={activeSetId||project.band_sets[0].id} onChange={e=>{const g=project.band_sets.find(g=>g.id===e.target.value)!;setActiveSetId(g.id);navigate(g.role==='reference'?'workspace':'samples')}}>{project.band_sets.map(g=><option key={g.id} value={g.id}>{g.analyte} · {g.role==='reference'?'内参':'目标'}</option>)}</select></label></div>}
   </div>
   <section inert={switching} className={`page-content ${tab==='workspace'?'workbench-page':''}`}>{tab==='wb'?<WbFigureEditor key={project.id+':'+workspaceEpoch} project={project} externalBusy={!!busy||switching} onBusy={working=>{wbBusy.current=working;setWbWorking(working)}} onBeforeSave={prepareWbSave} onDraft={dirty=>{wbDirty.current=dirty}} onHistory={history=>{wbHistory.current=history}}/>:frozen?<FigureDocument figure={frozen} onArchive={archiveFigure} onPreview={onFigurePreview} onUpdate={updateFigureSource} canUpdate={!!result&&result.input_revision===project.revision} onWorkspace={()=>{setActiveSetId(project.band_sets.find(g=>g.role==='reference')?.id??'');navigate('workspace')}} onVersion={openFigureVersion}/>:guided?(tab==='results'?<LaneResults project={project} result={result} onEdit={edit} onReview={review} onLocate={locate} onAnalyze={analyze} onExport={openExport} onArchive={archiveFigure} onPreview={onFigurePreview} figureDocument={figureDocument}/>:<LaneSetup onHistory={setCanvasHistory} key={workspaceEpoch} project={project} stage={tab==='workspace'?'reference':'targets'} activeSetId={activeSetId} onSet={setActiveSetId} onEdit={edit} onImport={()=>importImages().catch(e=>setMessage(String(e)))} onTarget={()=>{setActiveSetId('');navigate('samples')}} onManual={()=>{setManualMode(true);navigate('workspace')}}/>):<><QualityPanel project={project} result={result} onLocate={locate}/>{tab==='workspace'?<Workspace project={project} onEdit={edit} onDetect={detect} candidates={staged} onCandidates={setCandidates} onAcceptCandidates={acceptCandidates} onReview={review} busy={!!busy} selection={selection} onSelect={setSelection}/>:tab==='samples'?<SampleEditor project={project} onEdit={edit} onReview={review}/>:<Results project={project} result={result} onLocate={locate} onAnalyze={analyze}/>}</>}</section></>}
  {pageChoice&&<ImagePagePicker path={pageChoice.path} info={pageChoice.info} onChoose={choosePages}/>} {showExport&&exportContext&&<ExportPreview project={exportContext.project} result={exportContext.result} initialSettings={exportContext.settings} initialFigure={exportContext.figure} initialData={exportContext.preview?.figure_data} onClose={()=>setShowExport(false)} onExport={exportResult}/>}<footer className="statusbar"><div className="status-summary">{project&&<><span>{project.images.length} 张原始图像</span><span>{project.rois.length} 个条带区域</span><span>{reviewed} 已复核</span>{((project as any).demo||(project as any).synthetic)&&<b className="synthetic-label">纯合成示例 · 非实验数据</b>}</>}</div><div className="status-system"><span className="connection"><i className={connected?'online':''}/>{connected?'本地引擎就绪':'连接中'}</span>{project&&<span className="pixel-note"><ShieldCheck size={12}/>原始像素参与计算</span>}</div></footer></div></div>
}
