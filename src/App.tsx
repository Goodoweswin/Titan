import {invoke} from '@tauri-apps/api/core'
import {useCallback,useEffect,useRef,useState} from 'react'
import StatsWorkspace,{type StatsLibraryActions} from './stats/StatsWorkspace'
import IFWorkspace,{type IFLibraryActions} from './if/IFWorkspace'
import LibraryCreateDialog,{type AnalysisCreation,type LibraryDialog} from './LibraryCreateDialog'
import {open,save,confirm} from '@tauri-apps/plugin-dialog'
import {getCurrentWindow} from '@tauri-apps/api/window'
import {Activity,ArrowDownToLine,CircleHelp,Copy,Folder,FolderOpen,Home,ImagePlus,Plus,Save,ShieldCheck,Sparkles,Undo2,Redo2} from 'lucide-react'
import appIcon from '../assets/brand/titan-app-icon-128.png'
import gorillaHead from '../assets/brand/titan-head.svg'
import {callEngine} from './bridge'
import {createProject,editProject,commitResult,mergeSaved,restoreHistory,acceptReview,mergeImported,retainResult} from './state'
import type {CloseActions,Project,AnalysisResult,Rect,PlotSettings,DetectionPreview,ImageInspection,LibraryEntry,FrozenFigure,FigureSettings,FigureDocumentMetadata,PlotPreview,LibraryCollection,LibraryMaterial,LibraryArtifact,LibraryExportReceipt,LibraryResume} from './types'
import ImagePagePicker from './ImagePagePicker'
import Workspace from './Workspace'
import LaneSetup, {type CanvasHistory} from './LaneSetup'
import LaneResults from './LaneResults'
import ExportPreview from './ExportPreview'
import Results from './Results'
import SampleEditor from './SampleEditor'
import ProjectNavigator from './ProjectNavigator'
import ProjectLibrary,{type LibraryView} from './ProjectLibrary'
import useProjectLibrary from './useProjectLibrary'
import FigureDocument from './FigureDocument'
import {mergeSavedFrom,sameProjectContext} from './project-library-state'
import type {ArchiveFigureRequest,LiveFigurePreview} from './PublicationFigure'
import type {Selection} from './ProjectNavigator'
import QualityPanel from './QualityPanel'
import {appendCandidates} from './workflow'
import WorkspaceHeader from './WorkspaceHeader'
import WbFigureEditor,{type WbHistory} from './WbFigureEditor'
import type {WbDocument} from './wb-figure'
import WbImageGuide from './WbImageGuide'
import ProjectHome from './ProjectHome'
import SidebarResize from './SidebarResize'
import ToolHome,{toolInfo,type Tool} from './ToolHome'
import ImportDialog from './if/ImportDialog'
import ToolImport from './stats/ToolImport'
import type {IFSelection} from './if/types'
import type {Dataset} from './stats/types'
import './project-workspace.css'

type Screen={kind:'home'}|{kind:'project';id:string}|{kind:'tool';tool:Tool}|{kind:'analysis'}
export type ModuleView={path?:string|null;view:LibraryView;artifactId?:string}
type LeaveApproval={discard?:()=>void}
type FirstImport={tool:'if'|'stats';paths?:string[];collectionId:string|null;hashes?:Map<string,string>}
const analysisName=(path:string,fallback:string)=>Array.from(filename(path).replace(/\.[^.]+$/,'').trim()).slice(0,120).join('')||fallback
const filename=(path:string)=>path.split(/[\\/]/).pop()||'未命名分析'

const native=()=>Boolean((window as any).__TAURI_INTERNALS__)
async function ask(text:string){return native()?await confirm(text,{title:'Titan',kind:'warning'}):window.confirm(text)}
export default function App(){
 const [module,setModule]=useState<Tool>('wb'),moduleRef=useRef(module);moduleRef.current=module
 const [screen,setScreen]=useState<Screen>({kind:'home'})
 const [firstImport,setFirstImport]=useState<FirstImport|null>(null)
 const [sidebarSlot,setSidebarSlot]=useState<HTMLDivElement|null>(null)
 const [ifView,setIFView]=useState<ModuleView>({view:'workspace'})
 const [statsView,setStatsView]=useState<ModuleView>({view:'workspace'})
 const reportIFView=useCallback((view:ModuleView)=>setIFView(view),[])
 const reportStatsView=useCallback((view:ModuleView)=>setStatsView(view),[])
 const ifClose=useRef<CloseActions|null>(null)
 const ifLibrary=useRef<IFLibraryActions|null>(null)
 const statsLibrary=useRef<StatsLibraryActions|null>(null)
 const statsClose=useRef<CloseActions|null>(null)
 const [libraryDialog,setLibraryDialog]=useState<LibraryDialog|null>(null)
 const [libraryBusy,setLibraryBusy]=useState(false),libraryFlight=useRef(false)
 const [libraryNotice,setLibraryNotice]=useState('')
 const [exportRetries,setExportRetries]=useState<NonNullable<LibraryExportReceipt['library_export_retry']>[]>([])
 function activateModule(target:Tool){setModule(target);setScreen({kind:'analysis'})}
 async function prepareCurrent(keepWbDraft=false,approval?:LeaveApproval){
  if(screen.kind!=='analysis')return true
  const source=moduleRef.current
  if(source==='wb'){
   if(busy||wbBusy.current)return false
   const input=current.current
   if(keepWbDraft&&input&&(!input.project_path||input.read_only||input.upgrade_from))return true
   if(!keepWbDraft&&!await canLeaveFigure())return false
   if(!await flushCurrent())return false
   if(!keepWbDraft){
    if(input&&input.revision!==input.saved_revision&&(!input.project_path||input.read_only||input.upgrade_from)){
     if(input.project_path)await activateProject(await callEngine<Project>('open_project',{path:input.project_path,read_only:!!input.read_only}))
     else{assignProject(null);assignResult(null);setPast([]);setFuture([]);setFrozen(null)}
    }else{
     const discard=()=>{
      if(wbDirty.current)wbHistory.current?.discard()
      if(figurePreview.current?.dirty){figurePreview.current=null;setFigureEpoch(value=>value+1)}
     }
     if(approval)approval.discard=discard
     else discard()
    }
   }
   return true
  }
  if(source==='if')return !!await ifLibrary.current?.prepareLeave()
  return !!await statsLibrary.current?.prepareLeave()
 }
 async function prepareModule(target:Tool){
  return moduleRef.current===target||await prepareCurrent()
 }
 function visit(next:Screen){
  void guardLibrary(async()=>{
   const keepWbDraft=next.kind==='tool'&&next.tool==='wb'&&moduleRef.current==='wb'
   if(!await prepareCurrent(keepWbDraft))return false
   setShowExport(false);setScreen(next);return true
  }).catch(error=>setLibraryNotice(String(error)))
 }
 function enterModule(target:Tool){visit({kind:'tool',tool:target})}
 const [statsSource,setStatsSource]=useState<{path?:string;request:number;collectionId?:string|null;forceNew?:boolean}|null>(null)
 function presentStatsSource(path?:string,forceNew=false){
  const entry=path?library.entries.find(entry=>entry.path===path):undefined
  setStatsSource(previous=>({path,request:(previous?.request??0)+1,collectionId:entry?.collection_id??null,forceNew}))
 }
 function sendIFStats(path:string){
  void guardLibrary(async()=>{
   if(!await ifLibrary.current?.prepareLeave())return false
   presentStatsSource(path)
   return true
  }).catch(error=>setLibraryNotice(String(error)))
 }
 async function sendStats(){
  await guardLibrary(async()=>{
   const source=current.current
   if(!source)return false
   if(source.demo&&!source.project_path){
    if(!await canLeaveFigure()||!await statsLibrary.current?.fromWB(source))return false
    activateModule('stats')
    return true
   }
   if(source.read_only&&source.revision!==source.saved_revision){
    setMessage('请先将修改保存为可写项目后再读取统计结果。')
    return false
   }
   if(!source.project_path||source.upgrade_from)await saveProject()
   const saved=current.current
   if(!saved||saved.id!==source.id||!saved.project_path||saved.upgrade_from||!await flushCurrent())return false
   if(current.current?.saved_revision!==current.current?.revision)return false
   presentStatsSource(saved.project_path)
   return true
  }).catch(error=>setLibraryNotice(String(error)))
 }


 const [project,setProject]=useState<Project|null>(null),[result,setResult]=useState<AnalysisResult|null>(null)
 const library=useProjectLibrary()
 const [frozen,setFrozen]=useState<FrozenFigure|null>(null),frozenRef=useRef<FrozenFigure|null>(null);frozenRef.current=frozen
 const figurePreview=useRef<LiveFigurePreview|null>(null)
 const [figureEpoch,setFigureEpoch]=useState(0)
 const wbDirty=useRef(false),wbHistory=useRef<WbHistory|null>(null),wbBusy=useRef(false)
 const [wbWorking,setWbWorking]=useState(false)
 const [initialStrip,setInitialStrip]=useState<WbDocument|null>(null)
 const [activeStrip,setActiveStrip]=useState<{id:string;version:string}|null>(null)
 const [workspaceEpoch,setWorkspaceEpoch]=useState(0),[switching,setSwitching]=useState(false),projectNavigation=useRef(0)
 const [exportContext,setExportContext]=useState<{project:Project;result:AnalysisResult;settings?:PlotSettings;figure?:FigureSettings;frozenId?:string;frozenVersion?:string;preview?:PlotPreview}|null>(null)
 const [showExport,setShowExport]=useState(false)
 const [showWbGuide,setShowWbGuide]=useState(false)
 const [pageChoice,setPageChoice]=useState<{path:string;info:ImageInspection;resolve:(pages:number[]|null)=>void}|null>(null)
 function choosePages(pages:number[]|null){pageChoice?.resolve(pages);setPageChoice(null)}
 const [candidates,setCandidates]=useState<DetectionPreview|null>(null)
 const staged=candidates&&candidates.projectId===project?.id&&candidates.revision===project?.revision?candidates:null
 useEffect(()=>{setCandidates(null);if(!frozenRef.current)setShowExport(false)},[project?.id,project?.revision])
 const [tab,setTab]=useState<'workspace'|'samples'|'results'|'wb'>('workspace')
 const homeVisible=!project||screen.kind!=='analysis'||module!=='wb'
 const [manualMode,setManualMode]=useState(false),[activeSetId,setActiveSetId]=useState('')
 const guided=!!project&&!(project as any).demo&&!manualMode
 useEffect(()=>{setManualMode(false);setActiveSetId('')},[project?.id])
 const navigation=useRef(0)
 async function navigate(next:typeof tab,discardApproved=false){if(!discardApproved&&!await canLeaveFigure())return;navigation.current++;frozenRef.current=null;setFrozen(null);figurePreview.current=null;setInitialStrip(null);setActiveStrip(null);setTab(next)}
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
 useEffect(()=>{callEngine('health').then(()=>setConnected(true)).catch(e=>setLibraryNotice('本地引擎未就绪：'+String(e)))},[])
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
   const sourceEntry=library.entries.find(entry=>entry.path===input.project_path)
   if(saved.project_path)await library.remember(saved.project_path,{
    touch_opened:!input.project_path||saved.project_path!==input.project_path,
    source_entry_id:saved.project_path!==input.project_path?sourceEntry?.entry_id:undefined,
   })
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
  job.current++;setBusy('');setSelection({imageId:p.images[0]?.id??'',roiId:'',ids:[]});assignProject(p);setPast([]);setFuture([]);assignResult(null);setInitialStrip(null);setActiveStrip(null);setTab('workspace');setManualMode(false);setActiveSetId('');setWorkspaceEpoch(v=>v+1);setMessage('')
 }
 async function switchProject(p:Project){
  if(!await canLeaveFigure()||!await flushCurrent()){if(p.project_path&&p.project_path!==current.current?.project_path)await callEngine('release_project',{path:p.project_path}).catch(()=>{});return false}
  await activateProject(p);return true
 }
 async function newExperiment(input:AnalysisCreation){
  const token=++projectNavigation.current;setSwitching(true)
  try{
   if(!await canLeaveFigure()||!await flushCurrent())return
   const base=current.current
   const created=await callEngine<{project:Project;entry:LibraryEntry}>('library_create',input)
   if(token!==projectNavigation.current||current.current?.id!==base?.id||current.current?.project_path!==base?.project_path||current.current?.revision!==base?.revision){await callEngine('release_project',{path:created.project.project_path}).catch(()=>{});void library.refresh();return}
   await activateProject(created.project);await library.refresh();return true
  }finally{if(token===projectNavigation.current)setSwitching(false)}
 }
 async function wbFiles(){return pickPaths('选择原始 WB 图像',{multiple:true,filters:[{name:'原始 WB 图像',extensions:['tif','tiff','png']}]})}
 async function readWbImages(base:Project,paths:string[],valid=()=>true,hashes?:Map<string,string>){
  let loaded=base
  const failures:string[]=[]
  for(const path of paths)try{
   if(!valid())break
   const info=await callEngine<ImageInspection>('inspect_image',{path})
   if(hashes?.has(path)&&hashes.get(path)!==info.sha256)throw new Error('项目资料副本已变化，请重新添加。')
   if(!valid())break
   const pages=info.page_count>1?await new Promise<number[]|null>(resolve=>setPageChoice({path,info,resolve})):[0]
   if(!pages)continue
   for(const page_index of pages){
    if(!valid())break
    loaded=await callEngine<Project>('import_image',{project:loaded,path,page_index,expected_sha256:info.sha256})
   }
  }catch(error){failures.push(`${filename(path)}: ${error}`)}
  return {loaded,failures}
 }
 async function importImages(){
  if(!project||project.read_only)return
  const paths=await wbFiles()
  const valid=()=>sameProjectContext(current.current,project)
  if(!paths.length||!valid())return
  await execute('导入原始图像',async()=>{
   const {loaded,failures}=await readWbImages(project,paths,valid)
   if(!valid())return
   const added=loaded.images.length-project.images.length
   if(added){assignProject(mergeImported(current.current,project,loaded));assignResult(null)}
   setMessage(failures.length?failures.join('\n'):added?`已导入 ${added} 张图像，请确认极性与编码上界。`:'未导入图像。')
  })
 }
 async function pickPaths(title:string,options:Parameters<typeof open>[0]={}):Promise<string[]>{
  const picked=native()?await open({title,...options}):window.prompt(title)
  return Array.isArray(picked)?picked:typeof picked==='string'&&picked.trim()?[picked]:[]
 }
 async function startToolImport(tool:Tool){return guardLibrary(()=>beginToolImport(tool))}
 async function beginToolImport(tool:Tool,collectionId:string|null=null,paths?:string[],hashes?:Map<string,string>){
  if(tool==='if'||tool==='stats'){
   setFirstImport({tool,paths,collectionId,hashes});return true
  }
  const inputs=paths??await wbFiles()
  if(!inputs.length)return false
  const base=await callEngine<Project>('new_project',{name:analysisName(inputs[0],'未命名 WB 分析')})
  setLibraryNotice('正在导入原始图像…')
  const {loaded,failures}=await readWbImages(base,inputs,undefined,hashes)
  if(!loaded.images.length||!await canLeaveFigure()||!await flushCurrent()){
   setLibraryNotice(failures.join('\n'));return false
  }
  const created=await callEngine<{project:Project;entry:LibraryEntry}>('library_create_from_wb',{project:loaded,collection_id:collectionId})
  await activateProject(created.project)
  activateModule('wb')
  await library.refresh()
  setLibraryNotice(failures.join('\n'))
  return true
 }
 async function firstIF(selections:IFSelection[],metadata:Record<string,unknown>){
  const imported=await guardLibrary(async()=>{
   const name=analysisName(selections[0].path,'未命名 IF 分析')
   const hashes=firstImport?.hashes
   if(hashes&&selections.some(item=>!hashes.has(item.path)))throw new Error('请选择此项目中已勾选的资料。')
   const selected=hashes?selections.map(item=>({...item,expected_sha256:hashes.get(item.path)})):selections
   if(!await ifLibrary.current?.importFirst({name,collection_id:firstImport?.collectionId??null,selections:selected,metadata}))return false
   setFirstImport(null);activateModule('if');return true
  })
  if(!imported)throw new Error('请先完成当前 IF 分析的保存。')
 }
 async function firstStats(name:string,dataset:Dataset){
  const imported=await guardLibrary(async()=>{
   const path=firstImport?.paths?.[0]
   if(path&&firstImport?.hashes?.get(path)!==dataset.source?.sha256)throw new Error('项目资料副本已变化，请重新添加。')
   if(!await statsLibrary.current?.importFirst({name,collection_id:firstImport?.collectionId??null,dataset}))return false
   setFirstImport(null);activateModule('stats');return true
  })
  if(!imported)throw new Error('请先完成当前统计分析的保存。')
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
 async function openPath(path:string,view:LibraryView='workspace',figureId?:string,entryId?:string,artifact?:LibraryArtifact,expectedProjectId?:string){
  const token=++projectNavigation.current;setSwitching(true)
  try{
   if(!await canLeaveFigure()||!await flushCurrent())return
   if(entryId)path=await callEngine<string>('library_check_path',{path,entry_id:entryId})
   const before=current.current
   if(before?.project_path!==path){
    const candidate=await readProject(path)
    const candidatePath=candidate.project_path!
    const stillCurrent=()=>token===projectNavigation.current&&current.current===before
    const releaseCandidate=async()=>{
     if(candidatePath!==current.current?.project_path)await callEngine('release_project',{path:candidatePath}).catch(()=>{})
    }
    if(!stillCurrent()){await releaseCandidate();return false}
    if(expectedProjectId&&candidate.id!==expectedProjectId){
     await releaseCandidate();throw new Error('来源分析身份不匹配，请重新定位原分析')
    }
    try{
     await library.change('library_register',{path:candidatePath,entry_id:entryId})
    }catch(error){await releaseCandidate();throw error}
    if(!stillCurrent()){await releaseCandidate();return false}
    await activateProject(candidate)
   }else{
    if(expectedProjectId&&before.id!==expectedProjectId)throw new Error('来源分析身份不匹配，请重新定位原分析')
    await library.change('library_register',{path,entry_id:entryId})
   }
   if(token!==projectNavigation.current)return false
   const openProject=current.current
   const actual=openProject?.project_path
   if(!openProject||!actual)return false
   if(figureId||artifact?.kind==='wb_figure'){
    const nav=navigation.current
    try{
     if(artifact?.kind==='wb_figure'){
      const document=await callEngine<WbDocument>('wb_load',{project:openProject,document_id:artifact.document_id,version_id:artifact.version_id})
      if(token!==projectNavigation.current||nav!==navigation.current||current.current?.project_path!==actual)return false
      await navigate('wb',true)
      setInitialStrip(document)
      setActiveStrip({id:document.id,version:document.version!})
     }else{
      const loaded=await callEngine<FrozenFigure>('load_figure',{path:actual,figure_id:figureId,version_id:artifact?.version_id})
      if(token!==projectNavigation.current||nav!==navigation.current||current.current?.project_path!==actual)return false
      setShowExport(false);figurePreview.current=null;frozenRef.current=loaded;setFrozen(loaded)
      navigation.current++;setTab('results')
     }
    }catch(error){
     if(token!==projectNavigation.current||nav!==navigation.current)return false
     await navigate('workspace',true)
     setMessage('图表不可用，已打开分析工作台：'+String(error))
    }
   }else{
    if(view==='workspace')setActiveSetId(openProject.band_sets.find(g=>g.role==='reference')?.id??'')
    await navigate(view,true)
   }
   return true
  }catch(e){
   if(token===projectNavigation.current){
    if(screen.kind==='analysis'&&moduleRef.current==='wb')setMessage(String(e))
    else setLibraryNotice(String(e))
   }
   return false
  }
  finally{if(token===projectNavigation.current)setSwitching(false)}
 }
 async function guardLibrary(action:()=>Promise<boolean|undefined>){
  if(libraryFlight.current)return false
  libraryFlight.current=true
  setLibraryBusy(true)
  try{return !!await action()}
  finally{libraryFlight.current=false;setLibraryBusy(false)}
 }
 async function submitLibrary(input:AnalysisCreation){
  const mode=libraryDialog
  if(!mode||mode.kind==='choose')return false
  return await guardLibrary(async()=>{
   if(mode.kind==='collection'){
    if(!await prepareCurrent())return false
    const created=await library.change<LibraryCollection>('library_create_collection',{name:input.name})
    setScreen({kind:'project',id:created.id});return true
   }
   if(mode.kind==='rename'){await library.change('library_update_collection',{id:mode.project.id,patch:{name:input.name}});return true}
   if(mode.kind==='remove'){
    await library.change('library_remove_collection',{id:mode.project.id})
    if(screen.kind==='project'&&screen.id===mode.project.id)setScreen({kind:'home'})
    return true
   }
   if(mode.kind==='move'||mode.kind==='detach'){
    await library.change('library_assign',{entry_id:mode.entry.entry_id,collection_id:mode.kind==='detach'?null:input.collection_id})
    return true
   }
   if(!await prepareModule(mode.kind))return false
   const created=mode.kind==='wb'?await newExperiment(input):
    mode.kind==='if'?await ifLibrary.current?.create(input):await statsLibrary.current?.create(input)
   if(!created)return false
   activateModule(mode.kind)
   return true
  })
 }
 async function addMaterials(collectionId:string){
  await guardLibrary(async()=>{
   const paths=await pickPaths('选择要复制到项目的资料',{multiple:true})
   if(!paths.length)return false
   await library.change('library_material_add',{collection_id:collectionId,paths})
   return true
  })
 }
 async function removeMaterial(collectionId:string,file:LibraryMaterial){
  await guardLibrary(async()=>{
   if(!await ask(`从此项目移除「${file.name}」？原文件和已经使用它的分析会保留。`))return false
   await library.change('library_material_remove',{collection_id:collectionId,material_id:file.id});return true
  })
 }
 async function useMaterials(collectionId:string,materials:LibraryMaterial[],tool:Tool){
  await guardLibrary(async()=>{
   const paths=await callEngine<string[]>('library_material_paths',{collection_id:collectionId,material_ids:materials.map(file=>file.id)})
   return beginToolImport(tool,collectionId,paths,new Map(paths.map((path,index)=>[path,materials[index].sha256])))
  })
 }
 async function exportBundle(project:LibraryCollection){
  await guardLibrary(async()=>{
   const suggested=project.name.replace(/[\\/:*?"<>|]/g,'_')+'.titanproject'
   const path=native()?await save({title:'导出项目包',defaultPath:suggested}):window.prompt('导出项目包',suggested)
   if(!path)return false
   setLibraryNotice('正在复制项目资料和已保存的分析…')
   const destination=path.toLowerCase().endsWith('.titanproject')?path:path+'.titanproject'
   const published=await callEngine<string>('library_export_bundle',{collection_id:project.id,destination})
   setLibraryNotice('项目包已导出：'+published)
   return true
  })
 }
 async function openBundle(){
  await guardLibrary(async()=>{
   const [path]=await pickPaths('选择 .titanproject 项目包',{directory:true,multiple:false})
   if(!path||!await prepareCurrent())return false
   const project=await library.change<LibraryCollection>('library_import_bundle',{path})
   setLibraryNotice('已打开项目包；导入的项目已保存为独立副本。')
   setScreen({kind:'project',id:project.id})
   return true
  })
 }
 function showDemo(tool:Tool){
  void guardLibrary(async()=>{
   if(!await prepareModule(tool))return false
   if(tool==='wb'){
    setLibraryNotice('正在准备合成示例…')
    try{
     const demo=await callEngine<Project>('demo')
     if(!await switchProject(demo))return false
     activateModule('wb');return true
    }finally{setLibraryNotice('')}
   }
   const ok=tool==='if'?await ifLibrary.current?.demo():await statsLibrary.current?.demo()
   if(ok)activateModule(tool)
   return ok
  }).catch(error=>setLibraryNotice(String(error)))
 }
 async function openAnalysis(entry:Pick<LibraryEntry,'path'|'module'|'figures'|'resume'|'artifacts'> & {entry_id?:string;project_id?:string},view?:LibraryView,figureId?:string,path=entry.path,artifact?:LibraryArtifact){
  const saved=entry.resume
  const module=entry.module??'wb'
  const savedId=!view&&saved?.view==='figure'?saved.artifact_id:undefined
  const document=entry.artifacts?.find(item=>(item.kind==='wb_figure'||item.kind==='stats_plot')&&item.id===savedId)
  const targetArtifact=artifact??(document?{...document,version_id:saved?.version_id??document.version_id}:undefined)
  const figure=figureId??(entry.figures.some(item=>item.id===savedId)?savedId:undefined)
  const plotVersion=!view&&figure&&saved?.version_id
  const next=view??(saved?.view==='figure'?(figure?'results':!savedId||document?'wb':'workspace'):saved?.view)??'workspace'
  if(!await prepareModule(module))return false
  if(module==='if'){
   if(!await ifLibrary.current?.open(path,next,entry.entry_id))return false
   activateModule('if')
   return true
  }
  if(module==='stats'){
   const resume:LibraryResume={view:next==='wb'?'figure':next,
    dataset_id:saved?.dataset_id,artifact_id:targetArtifact?.id}
   if(!await statsLibrary.current?.open(path,resume,entry.entry_id))return false
   activateModule('stats')
   return true
  }
  const frozenArtifact=plotVersion?{
   id:figure!,entry_id:entry.entry_id??'',title:'',kind:'result_export' as const,
   source_revision:null,available:true,version_id:plotVersion,
  }:undefined
  if(!await openPath(path,next,figure,entry.entry_id,targetArtifact??frozenArtifact,entry.project_id))return false
  activateModule('wb')
  return true
 }
 function openLibraryEntry(entry:LibraryEntry,view?:LibraryView,figureId?:string){
  void guardLibrary(()=>openAnalysis(entry,view,figureId)).catch(error=>setLibraryNotice(String(error)))
 }
 async function openProject(entry?:LibraryEntry){
  await guardLibrary(async()=>{
   const [path]=await pickPaths(entry?'重新定位分析':'选择 .titanwb、.titanif 或 .titanstats 分析文件夹',{directory:true,multiple:false})
   if(typeof path!=='string')return false
   if(entry)return openAnalysis(entry,undefined,undefined,path)
   const known=library.entries.find(item=>item.path===path)
   const target:Parameters<typeof openAnalysis>[0]=known??{path,module:path.toLowerCase().endsWith('.titanstats')?'stats':path.toLowerCase().endsWith('.titanif')?'if':'wb',figures:[]}
   return openAnalysis(target,undefined,undefined,path)
  })
 }
 function pinCollection(collection:LibraryCollection){
  void library.change('library_update_collection',{id:collection.id,patch:{pinned:!collection.pinned}}).catch(error=>setLibraryNotice(String(error)))
 }
 async function openRegisteredFile(entry:LibraryEntry,artifact:LibraryArtifact|undefined,reveal:boolean){
  try{
   if(native())await invoke('library_open_file',{entryId:entry.entry_id,artifactId:artifact?.id,reveal})
   else setLibraryNotice(await callEngine<string>('library_target',{entry_id:entry.entry_id,artifact_id:artifact?.id}))
  }catch(error){setLibraryNotice(String(error))}
 }
 function openArtifact(entry:LibraryEntry,artifact:LibraryArtifact){
  if(artifact.kind==='stats_plot'||artifact.kind==='wb_figure'||(artifact.kind==='wb_plot'||artifact.kind==='result_export')&&artifact.document_id){
   const strip=artifact.kind==='wb_figure'||artifact.kind==='stats_plot'
   void guardLibrary(()=>openAnalysis(entry,strip?'wb':'results',strip?undefined:artifact.document_id,entry.path,artifact))
    .catch(error=>setLibraryNotice(String(error)))
  }else void openRegisteredFile(entry,artifact,false)
 }
 function reportLibraryExport(receipt:LibraryExportReceipt){
  const retry=receipt.library_export_retry
  if(retry){
   setExportRetries(items=>[...items,retry])
   setLibraryNotice('文件已导出，左栏登记失败：'+receipt.library_export_error)
  }
  void library.refresh()
 }
 async function retryLibraryExport(){
  const retry=exportRetries[0]
  if(!retry)return
  try{
   await library.change('library_record_export',retry)
   setExportRetries(items=>items.slice(1))
   setLibraryNotice('已将导出文件添加到左栏。')
  }catch(error){setLibraryNotice('登记未完成：'+String(error))}
 }
 async function recover(){
  await guardLibrary(async()=>{
   const path=recoveryPath
   if(!path||!await ask('仅在旧写入进程已退出时恢复锁。损坏的项目会从有效备份创建新副本，原损坏文件保留。继续？'))return false
   if(!await prepareModule('wb')||!await canLeaveFigure()||!await flushCurrent())return false
   const restored=await callEngine<Project>('recover_project',{path})
   const source=library.entries.find(entry=>entry.path===path&&entry.project_id===restored.id)
   if(restored.project_path)await library.remember(restored.project_path,{
    source_entry_id:restored.project_path!==path?source?.entry_id:undefined,
   })
   await activateProject(restored);activateModule('wb');setRecoveryPath('');setLibraryNotice('')
   setMessage('项目已恢复；若使用了备份，已创建独立恢复副本。')
   return true
  }).catch(error=>setLibraryNotice(String(error)))
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
   if(moduleRef.current!=='wb'||!project||project.read_only||busy||showWbGuide||homeVisible)return
   e.preventDefault();historyUndo(e.shiftKey)
  }
  window.addEventListener('keydown',listener);return()=>window.removeEventListener('keydown',listener)
 },[project,past,future,busy,canvasHistory,guided,tab,showWbGuide,homeVisible])
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
  const exported=await callEngine<{outputs:Record<string,string>}&LibraryExportReceipt>('export',{project:context.project,result:context.result,destination:path,settings,figure_settings:figure})
  if(exported){
   setShowExport(false);setMessage(`已导出到 ${path}`);reportLibraryExport(exported)
   if(!context.project.read_only)try{await archiveFigure({project:context.project,result:context.result,figure_settings:figure,settings,name:(figure.title||'导出图表')+' · '+new Date().toLocaleTimeString(),frozen:!!context.frozenId,export_origin:{path,png_sha256:exported.outputs['plot.png']}})}catch(e){setMessage(`已导出到 ${path}；左栏归档未完成：${e}`)}
  }
 }
 useEffect(()=>{
  if(!native())return;let stop:(()=>void)|undefined
  getCurrentWindow().onCloseRequested(async e=>{
   e.preventDefault()
   await guardLibrary(async()=>{
    if(!await canLeaveFigure()||!await flushCurrent())return false
    if(statsClose.current&&!await statsClose.current.prepare())return false
    if(ifClose.current&&!await ifClose.current.prepare())return false
    const p=current.current
    await Promise.allSettled([
     ifClose.current?.finish(),statsClose.current?.finish(),
     p?.project_path?callEngine('release_project',{path:p.project_path}):undefined,
    ])
    await getCurrentWindow().destroy()
    return true
   }).catch(error=>setLibraryNotice(String(error)))
  }).then(fn=>stop=fn);return()=>stop?.()
 },[])
 useEffect(()=>{
  if(!project?.project_path||project.read_only||project.upgrade_from||project.saved_revision===project.revision||busy||switching)return
  const input=project,timer=setTimeout(async()=>{if(saveFlight.current)return;try{await persistSnapshot(input,input.project_path!)}catch(e){setMessage(`自动保存未完成：${e}。当前修改仍在内存中，请手动保存。`)}},1500)
  return()=>clearTimeout(timer)
 },[project,busy,switching])
 const activeEntryId=library.entries.find(entry=>entry.path===project?.project_path)?.entry_id
 useEffect(()=>{
  if(!activeEntryId||module!=='wb'||homeVisible||switching)return
  const view=frozen||tab==='wb'?'figure':tab==='results'?'results':'workspace'
  const figure=frozen?{artifact_id:frozen.document.id,version_id:frozen.document.selected_version}:
   tab==='wb'&&activeStrip?{artifact_id:'strip:'+activeStrip.id,version_id:activeStrip.version}:{}
  void library.resume(activeEntryId,{view,...figure})
 },[activeEntryId,module,homeVisible,switching,tab,frozen?.document.id,frozen?.document.selected_version,activeStrip?.id,activeStrip?.version])
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
 const tool=screen.kind==='tool'?screen.tool:screen.kind==='analysis'?module:null
 const wbView:ModuleView={path:project?.project_path,view:tab==='wb'?'wb':tab==='results'?'results':'workspace',
  artifactId:frozen?.document.id??(tab==='wb'&&activeStrip?'strip:'+activeStrip.id:undefined)}
 const currentView=module==='wb'?wbView:module==='if'?ifView:statsView
 const analysisVisible=screen.kind==='analysis'
 const currentEntry=analysisVisible?entries.find(entry=>entry.path===currentView.path):undefined
 const membership=library.projects.find(item=>item.id===currentEntry?.collection_id)
 const selectedProject=screen.kind==='project'?library.projects.find(item=>item.id===screen.id):undefined
 const memberLine=currentEntry&&<div className="analysis-membership">
  {membership?<button className="text-btn" onClick={()=>visit({kind:'project',id:membership.id})}><Folder size={13}/>{membership.name}</button>:<span>独立分析</span>}
 </div>
 const openFromDisk=(entry?:LibraryEntry)=>void openProject(entry).catch(error=>setLibraryNotice(String(error)))
 const actions=(operation:Promise<unknown>)=>void operation.catch(error=>setLibraryNotice(String(error)))
 const showDemoWB=()=>showDemo('wb')
 return <><div className={`app-shell titan-workspace${tool==='if'?' if-shell':tool==='stats'?' stats-shell':''}`}>
  <aside id="titan-sidebar" className="sidebar" inert={libraryBusy||!!firstImport||!!pageChoice}>
   <div className="brand"><img className="brand-mark" src={appIcon} alt="" aria-hidden="true"/><div className="brand-name"><strong>Titan</strong></div></div>
   <div className="sidebar-quick">
    <button className={`nav${screen.kind==='home'?' active':''}`} aria-current={screen.kind==='home'?'page':undefined} onClick={()=>visit({kind:'home'})}><Home size={17}/>首页</button>
    <button className="nav" onClick={()=>setLibraryDialog({kind:'choose'})}><Plus size={17}/>新建分析</button>
   </div>
   <SidebarResize sidebarId="titan-sidebar"/>
   <nav className="analysis-modules" aria-label="分析模块">{(Object.keys(toolInfo) as Tool[]).map(key=>{
    const {icon:Icon,label}=toolInfo[key]
    return <button type="button" key={key} className={`nav module-nav${tool===key?' active':''}`}
     aria-current={screen.kind==='tool'&&tool===key?'page':undefined} onClick={()=>enterModule(key)}><Icon size={18}/><span>{label}</span></button>
   })}</nav>
   <ProjectLibrary entries={entries} projects={library.projects} project={analysisVisible?{project_path:currentView.path}:null}
    selectedProjectId={selectedProject?.id} onProject={id=>visit({kind:'project',id})} onOpenBundle={()=>actions(openBundle())}
    activeFigure={currentView.artifactId??''} currentView={currentView.view} error={library.error} busy={switching||libraryBusy}
    onRetry={library.refresh} onRelocate={openFromDisk} onOpen={openLibraryEntry} onDialog={setLibraryDialog} onPin={pinCollection}
    onArtifact={openArtifact} onReveal={(entry,artifact)=>void openRegisteredFile(entry,artifact,true)} onOpenFile={()=>openFromDisk()}/>
   {project&&!homeVisible&&!guided&&!frozen&&tab!=='wb'&&<ProjectNavigator project={project} selection={selection} onSelect={select}/>}
   <div className="sidebar-tools" ref={setSidebarSlot}/>
   {(tool==='wb'&&analysisVisible)&&<button className="nav library-demo" onClick={showDemoWB}><Sparkles size={18}/>探索合成示例</button>}
  </aside>
  {screen.kind==='home'&&<main className="main-shell project-workspace" inert={libraryBusy}>
   <header className="project-intro"><Home size={24}/><div><h1>Titan 工作区</h1><p>从一份独立分析开始，或创建项目来管理资料、分析和图表。</p></div></header>
   <div className="tool-entry-actions">
    <button className="btn primary" onClick={()=>setLibraryDialog({kind:'choose'})}><Plus size={16}/>新建分析</button>
    <button className="btn secondary" onClick={()=>setLibraryDialog({kind:'collection'})}><Folder size={16}/>新建项目</button>
    <button className="btn secondary" onClick={()=>actions(openBundle())}><FolderOpen size={16}/>打开项目包</button>
   </div>
   <div className="tool-entry-links"><button className="text-btn" onClick={showDemoWB}><Sparkles size={15}/>体验合成示例</button></div>
   <footer className="statusbar"><span className="connection"><i className={connected?'online':''}/>{connected?'本地引擎就绪':'连接中'}</span></footer>
  </main>}
  {screen.kind==='project'&&<div className="module-pane" inert={libraryBusy||!!firstImport||!!pageChoice}>
   {selectedProject?<ProjectHome key={selectedProject.id} project={selectedProject} entries={entries.filter(entry=>entry.collection_id===selectedProject.id)}
    onNew={()=>setLibraryDialog({kind:'choose',collectionId:selectedProject.id})} onAdd={()=>actions(addMaterials(selectedProject.id))}
    onRemove={file=>actions(removeMaterial(selectedProject.id,file))} onUse={(files,tool)=>actions(useMaterials(selectedProject.id,files,tool))}
    onOpen={openLibraryEntry} onLocate={openFromDisk} onArtifact={openArtifact} onExport={()=>actions(exportBundle(selectedProject))}/>:
    <main className="main-shell project-workspace"><p role="status">项目暂不可用。</p><button className="btn secondary" onClick={()=>visit({kind:'home'})}>返回首页</button></main>}
  </div>}
  {screen.kind==='tool'&&<div className="module-pane" inert={libraryBusy||!!firstImport||!!pageChoice}>
   <ToolHome tool={screen.tool} hasCurrent={screen.tool==='wb'?!!project:!!(screen.tool==='if'?ifView.path:statsView.path)}
    onImport={()=>actions(startToolImport(screen.tool))} onNew={()=>setLibraryDialog({kind:screen.tool})}
    onResume={()=>activateModule(screen.tool)} onDemo={()=>showDemo(screen.tool)} onGuide={()=>setShowWbGuide(true)}
    onSource={()=>presentStatsSource(undefined,true)} onVolume={()=>ifLibrary.current?.showVolume()}/>
  </div>}
  <div className="module-pane" hidden={homeVisible} inert={libraryBusy||!!pageChoice}>
  <div className="main-shell"><WorkspaceHeader project={homeVisible?null:project} dirty={dirty} switching={switching} textSize={textSize} onTextSize={setTextSize} onName={name=>edit(p=>p.name=name)}>
   {project&&!homeVisible&&<>
    <button className="icon-btn header-icon" aria-label="保存实验" title="保存实验" disabled={!!busy||wbWorking} onClick={()=>saveProject(project.read_only).catch(e=>setMessage(String(e)))}><Save size={17}/></button>
    <button className="icon-btn header-icon" aria-label="另存副本" title="另存副本" disabled={!!busy||wbWorking} onClick={()=>saveProject(true).catch(e=>setMessage(String(e)))}><Copy size={17}/></button>
    {tab==='wb'&&<button className={project.images.length?'icon-btn header-icon':'btn primary'} aria-label="导入图像" title="导入图像" disabled={!!busy||wbWorking||project.read_only||switching} onClick={()=>importImages().catch(e=>setMessage(String(e)))}><ImagePlus size={15}/>{!project.images.length&&'导入图像'}</button>}
    {tab!=='wb'&&<><span className="header-separator" aria-hidden="true"/>
     {guided&&!frozen&&tab!=='results'&&<button className="icon-btn header-icon" aria-label="图像操作指引" title="图像操作指引" onClick={()=>setShowWbGuide(true)}><CircleHelp size={17}/></button>}
     <button className="icon-btn header-icon" title="撤销" disabled={(!(guided&&tab!=='results'&&canvasHistory?.canUndo)&&(!past.length||(guided&&tab!=='results'&&!!canvasHistory?.dirty)))||project.read_only||!!busy||!!frozen} onClick={()=>historyUndo()}><Undo2 size={16}/></button>
     <button className="icon-btn header-icon" title="重做" disabled={(!(guided&&tab!=='results'&&canvasHistory?.canRedo)&&(!future.length||(guided&&tab!=='results'&&!!canvasHistory?.dirty)))||project.read_only||!!busy||!!frozen} onClick={()=>historyUndo(true)}><Redo2 size={16}/></button>
     {tab!=='results'&&!frozen&&<button className="btn secondary" disabled={!!busy||project.read_only||switching} onClick={()=>importImages().catch(e=>setMessage(String(e)))}><ImagePlus size={15}/>导入图像</button>}
     {!guided&&<button className={`btn ${tab==='results'?'secondary':'primary'}`} disabled={!!busy||!project.rois.length} onClick={analyze}><Activity size={15}/>开始定量</button>}
     {tab==='results'&&!frozen&&<button className="btn secondary" disabled={!result||!!busy} onClick={sendStats}>发送到统计与绘图</button>}
     {(tab==='results'||frozen)&&<button className="btn primary" disabled={!result||!!busy} onClick={openExport}><ArrowDownToLine size={15}/>导出结果</button>}
     {manualMode&&<button className="text-btn" onClick={()=>{setManualMode(false);navigate('workspace')}}>返回简洁流程</button>}
    </>}
   </>}
  </WorkspaceHeader>
  {message&&<div className="notice" role="status"><span>{message}</span>{recoveryPath&&<button className="btn secondary" onClick={recover}>尝试恢复项目</button>}<button onClick={()=>setMessage('')}>×</button></div>}{busy&&<div className="busy" role="status"><img className="titan-loader" src={gorillaHead} alt="" aria-hidden="true"/>{busy}…{(busy.startsWith('计算')||busy.startsWith('识别'))&&<button onClick={()=>{job.current++;setBusy('');setMessage('已取消等待，本次结果不会写入当前项目。')}}>取消等待</button>}</div>}
  {module==='wb'&&memberLine}
   {project&&<div hidden={homeVisible}><div className="workspace-navigation">
    <nav className="steps" aria-label="实验视图">{(guided?([['workspace','内参'],['samples','目标'],['results','结果']] as const):([['workspace','图像与条带'],['samples','样本与分析设置'],['results','定量结果']] as const)).map(([t,label])=><button aria-label={label} key={t} onClick={()=>{if(guided&&t==='workspace')setActiveSetId(project.band_sets.find(g=>g.role==='reference')?.id??'');if(guided&&t==='samples'&&!project.band_sets.some(g=>g.id===activeSetId&&g.role==='target'))setActiveSetId('');navigate(t)}} className={tab===t?'selected':''} aria-current={tab===t?'page':undefined}>{label}</button>)}<button aria-label="WB 组图" onClick={()=>navigate('wb')} className={tab==='wb'?'selected':''} aria-current={tab==='wb'?'page':undefined}>WB 组图</button></nav>
    {guided&&!frozen&&tab!=='results'&&tab!=='wb'&&project.band_sets.length>0&&<div className="workspace-proteins"><label>当前蛋白<select aria-label="当前蛋白" value={activeSetId||project.band_sets[0].id} onChange={e=>{const g=project.band_sets.find(g=>g.id===e.target.value)!;setActiveSetId(g.id);navigate(g.role==='reference'?'workspace':'samples')}}>{project.band_sets.map(g=><option key={g.id} value={g.id}>{g.analyte} · {g.role==='reference'?'内参':'目标'}</option>)}</select></label></div>}
   </div>
   <section inert={switching} className={`page-content ${tab==='workspace'?'workbench-page':''}`}>{tab==='wb'?<WbFigureEditor key={project.id+':'+workspaceEpoch+':'+(initialStrip?.version??'')} project={project}
    initialDocument={initialStrip} onDocument={setActiveStrip} onSaved={library.refresh} onExported={reportLibraryExport} externalBusy={!!busy||switching} onBusy={working=>{wbBusy.current=working;setWbWorking(working)}} onBeforeSave={prepareWbSave} onDraft={dirty=>{wbDirty.current=dirty}} onHistory={history=>{wbHistory.current=history}}/>:frozen?<FigureDocument key={figureEpoch} figure={frozen} onArchive={archiveFigure} onPreview={onFigurePreview} onUpdate={updateFigureSource} canUpdate={!!result&&result.input_revision===project.revision} onWorkspace={()=>{setActiveSetId(project.band_sets.find(g=>g.role==='reference')?.id??'');navigate('workspace')}} onVersion={openFigureVersion}/>:guided?(tab==='results'?<LaneResults key={figureEpoch} project={project} result={result} onEdit={edit} onReview={review} onLocate={locate} onAnalyze={analyze} onExport={openExport} onArchive={archiveFigure} onPreview={onFigurePreview} figureDocument={figureDocument}/>:<LaneSetup onHistory={setCanvasHistory} key={workspaceEpoch} project={project} stage={tab==='workspace'?'reference':'targets'} activeSetId={activeSetId} onSet={setActiveSetId} onEdit={edit} onImport={()=>importImages().catch(e=>setMessage(String(e)))} onTarget={()=>{setActiveSetId('');navigate('samples')}} onManual={()=>{setManualMode(true);navigate('workspace')}}/>):<><QualityPanel project={project} result={result} onLocate={locate}/>{tab==='workspace'?<Workspace project={project} onEdit={edit} onDetect={detect} candidates={staged} onCandidates={setCandidates} onAcceptCandidates={acceptCandidates} onReview={review} busy={!!busy} selection={selection} onSelect={setSelection}/>:tab==='samples'?<SampleEditor project={project} onEdit={edit} onReview={review}/>:<Results project={project} result={result} onLocate={locate} onAnalyze={analyze}/>}</>}</section></div>}
  {showExport&&exportContext&&<ExportPreview project={exportContext.project} result={exportContext.result} initialSettings={exportContext.settings} initialFigure={exportContext.figure} initialData={exportContext.preview?.figure_data} onClose={()=>setShowExport(false)} onExport={exportResult}/>}{!homeVisible&&<footer className="statusbar"><div className="status-summary">{project&&!homeVisible&&<><span>{project.images.length} 张原始图像</span><span>{project.rois.length} 个条带区域</span><span>{reviewed} 已复核</span>{((project as any).demo||(project as any).synthetic)&&<b className="synthetic-label">纯合成示例 · 非实验数据</b>}</>}</div><div className="status-system"><span className="connection"><i className={connected?'online':''}/>{connected?'本地引擎就绪':'连接中'}</span>{project&&!homeVisible&&<span className="pixel-note"><ShieldCheck size={12}/>原始像素参与计算</span>}</div></footer>}</div></div>
  <IFWorkspace active={analysisVisible&&module==='if'} volumeAvailable={tool==='if'} onStatsSource={sendIFStats} registerClose={fn=>{ifClose.current=fn}}
   registerLibrary={actions=>{ifLibrary.current=actions}} library={library} libraryBusy={libraryBusy}
   sidebarSlot={sidebarSlot} reportView={reportIFView} membership={module==='if'?memberLine:null} onExported={reportLibraryExport}/>
  <StatsWorkspace active={analysisVisible&&module==='stats'} sourceRequest={statsSource} library={library} libraryBusy={libraryBusy}
   sidebarSlot={sidebarSlot} reportView={reportStatsView} membership={module==='stats'?memberLine:null}
   beforeSourceImport={async()=>{
    const approval:LeaveApproval={}
    if(!await prepareCurrent(false,approval))return null
    return ()=>approval.discard?.()
   }}
   onSourceCreated={()=>activateModule('stats')}
   onSource={source=>void guardLibrary(async()=>{
    const resolved=await callEngine<{path:string;entry_id:string|null;project_id:string}>('stats_resolve_source',{source})
    const sourceModule=source.kind==='if'?'if':'wb'
    return openAnalysis({...resolved,entry_id:resolved.entry_id??undefined,module:sourceModule,figures:[]},'results')
   }).catch(error=>setLibraryNotice(String(error)))}
   registerLibrary={actions=>{statsLibrary.current=actions}} registerClose={close=>{statsClose.current=close}} onExported={reportLibraryExport}/>
  {showWbGuide&&<WbImageGuide onClose={()=>setShowWbGuide(false)}/>}
  {pageChoice&&<ImagePagePicker path={pageChoice.path} info={pageChoice.info} onChoose={choosePages}/>}
  {firstImport?.tool==='if'&&<div className="if-shell"><ImportDialog initialPaths={firstImport.paths} onClose={()=>setFirstImport(null)} onImport={firstIF}/></div>}
  {firstImport?.tool==='stats'&&<ToolImport initialPath={firstImport.paths?.[0]} onClose={()=>setFirstImport(null)} onImport={firstStats}/>}
 </div>
 {(libraryNotice||exportRetries.length>0)&&<div className="library-notice" role="status">
  <span>{libraryNotice||'有导出文件等待登记到左栏'}</span>
  {recoveryPath&&(screen.kind!=='analysis'||module!=='wb')&&<button className="btn secondary" onClick={recover}>尝试恢复项目</button>}
  {exportRetries.length>0&&<button className="btn secondary" onClick={()=>void retryLibraryExport()}>重试登记</button>}
  <button className="icon-btn" aria-label="关闭项目库提示" onClick={()=>setLibraryNotice('')}>×</button>
 </div>}
 {libraryDialog&&<LibraryCreateDialog key={libraryDialog.kind} mode={libraryDialog} projects={library.projects} onClose={()=>setLibraryDialog(null)} onSubmit={submitLibrary}
  onSelectKind={(kind,collectionId)=>setLibraryDialog({kind,collectionId})}/>}
 </>
}
