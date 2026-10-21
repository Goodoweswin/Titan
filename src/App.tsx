import {useEffect,useRef,useState} from 'react'
import {open,save,confirm} from '@tauri-apps/plugin-dialog'
import {getCurrentWindow} from '@tauri-apps/api/window'
import {Activity,ArrowDownToLine,ChevronRight,FolderOpen,FlaskConical,ImagePlus,Layers3,Loader2,Plus,Save,ShieldCheck,Sparkles,Undo2,Redo2} from 'lucide-react'
import {callEngine} from './bridge'
import {createProject,editProject,commitResult,mergeSaved,restoreHistory,acceptReview,mergeImported} from './state'
import type {Project,AnalysisResult,Rect} from './types'
import Workspace from './Workspace'
import Results from './Results'
import SampleEditor from './SampleEditor'

const native=()=>Boolean((window as any).__TAURI_INTERNALS__)
async function ask(text:string){return native()?await confirm(text,{title:'Titan WB',kind:'warning'}):window.confirm(text)}
export default function App(){
 const [project,setProject]=useState<Project|null>(null),[result,setResult]=useState<AnalysisResult|null>(null)
 const [tab,setTab]=useState<'workspace'|'samples'|'results'>('workspace')
 const [busy,setBusy]=useState(''),[message,setMessage]=useState(''),[connected,setConnected]=useState(false)
 const [recoveryPath,setRecoveryPath]=useState('')
 const [past,setPast]=useState<Project[]>([]),[future,setFuture]=useState<Project[]>([])
 const current=useRef(project),job=useRef(0),persisting=useRef(false);current.current=project
 useEffect(()=>{callEngine('health').then(()=>setConnected(true)).catch(e=>setMessage(String(e)))},[])
 const dirty=!!project&&project.saved_revision!==project.revision
 async function execute<T,>(label:string,task:()=>Promise<T>):Promise<T|undefined>{
  setBusy(label);setMessage('');const token=++job.current
  try{const value=await task();return job.current===token?value:undefined}catch(e){if(job.current===token)setMessage(String(e));return undefined}
  finally{if(job.current===token)setBusy('')}
 }
 function edit(f:(draft:Project)=>void){if(!project)return;try{const p=editProject(project,f);setPast(v=>[...v.slice(-29),project]);setFuture([]);setProject(p);setResult(null)}catch(e){setMessage(String(e))}}
 async function switchProject(p:Project){
  if(current.current&&current.current.saved_revision!==current.current.revision&&!await ask('当前实验尚有未保存的修改，放弃修改并切换？')){if(p.project_path&&p.project_path!==current.current.project_path)await callEngine('release_project',{path:p.project_path}).catch(()=>{});return}
  const old=current.current
  if(old?.project_path)await callEngine('release_project',{path:old.project_path}).catch(()=>{})
  job.current++;setBusy('');setProject(p);setPast([]);setFuture([]);setResult(null);setTab('workspace');setMessage('')
 }
 async function loadDemo(){const p=await execute<Project>('准备合成示例',()=>callEngine('demo'));if(p)await switchProject(p)}
 async function importImages(){
  if(!project)return
  const paths=await open({multiple:true,filters:[{name:'原始 WB 图像',extensions:['tif','tiff','png']}]});if(!paths)return
  let p=project;const failures:string[]=[]
  await execute('导入原始图像',async()=>{
   for(const path of Array.isArray(paths)?paths:[paths])try{p=await callEngine<Project>('import_image',{project:p,path})}catch(e){failures.push(`${path}: ${e}`)}
   setProject(current=>mergeImported(current,project,p));setResult(null);setMessage(failures.length?failures.join('\n'):'原图已导入，请确认极性与编码上界。')
  })
 }
 async function saveProject(asCopy=false){
  if(!project)return
  if(persisting.current){setMessage('自动保存正在完成，请稍后再试。');return}
  let path:string|null|undefined=asCopy?null:project.project_path
  if(!path)path=await save({defaultPath:`${project.name.replace(/[\/\\:]/g,'_')}.titanwb`,title:'保存为项目文件夹',filters:[{name:'Titan WB 项目',extensions:['titanwb']}]})
  if(!path)return
  const dest=path
  const p=await execute<Project>('保存实验',async()=>{
   const saved=await callEngine<Project>('save_project',{project:{...project,read_only:false},path:dest,expected_revision:asCopy?null:project.saved_revision??null})
   if(current.current?.id!==saved.id)await callEngine('release_project',{path:saved.project_path}).catch(()=>{})
   return saved
  })
  if(p){setProject(current=>mergeSaved(current,p));setMessage('实验已保存；保存期间的新修改仍保留。')}
 }
 async function openProject(){
  const path=await open({directory:true,multiple:false,title:'选择 .titanwb 项目文件夹'});if(!path||Array.isArray(path))return
  setRecoveryPath(path)
  let p:Project
  try{p=await callEngine<Project>('open_project',{path})}
  catch(e){
   if(String(e).includes('写入')&&await ask('项目已锁定，是否只读打开？'))p=await callEngine<Project>('open_project',{path,read_only:true})
   else{setMessage(String(e));return}
  }
  await switchProject(p)
 }
 async function recover(){
  if(!recoveryPath||!await ask('仅在旧写入进程已退出时恢复锁。损坏的项目会从有效备份创建新副本，原损坏文件保留。继续？'))return
  const p=await execute<Project>('恢复项目',()=>callEngine('recover_project',{path:recoveryPath}))
  if(p){await switchProject(p);setRecoveryPath('');setMessage('项目已恢复；若使用了备份，已创建独立恢复副本。')}
 }
 async function review(){
  if(!project)return
  const p=structuredClone(project);p.revision++;p.rois.forEach(r=>r.reviewed_revision=r.backgrounds.length?p.revision:null)
  const checked=await execute<Project>('检查条带与引用',()=>callEngine('validate',{project:p}))
  if(checked){const accepted=acceptReview(current.current,project,checked);if(!accepted){setMessage('复核期间输入已变化，请重新复核。');return}setPast(v=>[...v,project]);setProject(accepted);setResult(null);setMessage('已记录复核；缺少背景的ROI仍保持待复核。')}
 }
 async function analyze(){
  if(!project)return
  const r=await execute<AnalysisResult>('计算原始信号',()=>callEngine('analyze',{project}))
  if(r&&current.current){const accepted=commitResult(current.current,r);if(accepted){setResult(accepted);setTab('results')}else setMessage('输入已变化，旧计算结果已丢弃。')}
 }
 async function detect(imageId:string,window:Rect,analyte:string,role:'target'|'reference'){
  if(!project)return;const p=project
  const boxes=await execute<Rect[]>('识别候选条带',()=>callEngine('detect',{project:p,image_id:imageId,window,settings:{}}));if(!boxes)return
  if(current.current?.revision!==p.revision||current.current?.id!==p.id){setMessage('输入已变化，旧识别结果已丢弃。');return}
  edit(d=>{boxes.forEach((rect,index)=>{
   let lane=d.lanes[index]
   if(!lane){const n=d.lanes.length+1,sid=`S${n}`;d.samples.push({id:sid,bio_id:`B${n}`,group:'control',pair_id:'',kind:'biological',pool_id:''});lane={id:`L${n}`,sample_id:sid,membrane_id:'M1',technical_id:'1'};d.lanes.push(lane)}
   if(d.rois.some(r=>r.lane_id===lane.id&&r.analyte===analyte&&r.role===role))return
   d.rois.push({id:crypto.randomUUID(),image_id:imageId,lane_id:lane.id,analyte,role,rect,backgrounds:[],reference_id:null,reviewed_revision:null})
  })});setMessage(`${boxes.length} 个候选。映射仅为草稿，请核对样本并补背景后复核。`)
 }
 function historyUndo(redo=false){
  if(!project)return;const list=redo?future:past;if(!list.length)return
  const p=restoreHistory(project,list[list.length-1])
  if(redo){setFuture(list.slice(0,-1));setPast(v=>[...v,project])}else{setPast(list.slice(0,-1));setFuture(v=>[...v,project])}
  setProject(p);setResult(null)
 }
 async function exportResult(){
  if(!project||!result)return
  const path=await save({defaultPath:`${project.name}-结果`,title:'选择新的结果目录'});if(!path)return
  const r=await execute('导出数据与图表',()=>callEngine('export',{project,result,destination:path}));if(r)setMessage(`已导出到 ${path}`)
 }
 useEffect(()=>{
  if(!native())return;let stop:(()=>void)|undefined
  getCurrentWindow().onCloseRequested(async e=>{
   e.preventDefault();const p=current.current
   if(p&&p.saved_revision!==p.revision&&!await ask('有未保存修改，确认放弃并退出？'))return
   if(p?.project_path)await callEngine('release_project',{path:p.project_path}).catch(()=>{})
   await getCurrentWindow().destroy()
  }).then(fn=>stop=fn);return()=>stop?.()
 },[])
 useEffect(()=>{
  if(!project?.project_path||project.read_only||project.saved_revision===project.revision||busy)return
  const input=project
  const timer=setTimeout(async()=>{
   if(persisting.current)return;persisting.current=true
   try{
    const saved=await callEngine<Project>('save_project',{project:input,path:input.project_path,expected_revision:input.saved_revision})
    if(current.current?.id===saved.id)setProject(cur=>mergeSaved(cur,saved))
    else await callEngine('release_project',{path:saved.project_path})
   }catch(e){setMessage(`自动保存未完成：${e}。当前修改仍在内存中，请手动保存。`)}
   finally{persisting.current=false}
  },1500)
  return()=>clearTimeout(timer)
 },[project,busy])
 const reviewed=project?.rois.filter(r=>r.reviewed_revision===project.revision).length??0
 return <div className="app-shell">
  <aside className="sidebar"><div className="brand"><div className="brand-mark"><Layers3 size={21}/></div><strong>Titan<span>WB</span></strong></div><div className="sidebar-label">分析工作台</div>
   {([['workspace',Layers3,'图像与条带'],['samples',FlaskConical,'样本与参考'],['results',Activity,'定量结果']] as const).map(([t,Icon,label])=><button key={t} className={tab===t?'nav active':'nav'} onClick={()=>setTab(t)}><Icon size={18}/>{label}</button>)}
   <div className="sidebar-divider"/><div className="sidebar-label">实验项目</div>
   <button className="nav" onClick={()=>switchProject(createProject('未命名实验'))}><Plus size={18}/>新建实验</button><button className="nav" onClick={()=>openProject().catch(e=>setMessage(String(e)))}><FolderOpen size={18}/>打开项目</button><button className="nav" onClick={loadDemo}><Sparkles size={18}/>探索合成示例</button>
   <div className="sidebar-bottom"><ShieldCheck size={19}/><div><strong>本地分析 · 原图保留</strong><small>数据保存在你的电脑</small></div></div>
  </aside>
  <div className="main-shell"><header className="app-header"><div className="breadcrumb">实验工作区<ChevronRight size={14}/><span>{project?.name??'开始一个新实验'}</span>{dirty&&<i title="未保存"/>}</div><div className="header-actions">{project?.read_only&&<span className="pill">只读</span>}<span className="connection"><i className={connected?'online':''}/>{connected?'本地引擎就绪':'连接中'}</span>{project&&<><button className="btn secondary" disabled={!!busy} onClick={()=>saveProject(project.read_only).catch(e=>setMessage(String(e)))}><Save size={15}/>保存实验</button><button className="btn secondary" disabled={!result||!!busy} onClick={()=>exportResult().catch(e=>setMessage(String(e)))}><ArrowDownToLine size={15}/>导出结果</button></>}</div></header>
  {message&&<div className="notice" role="status"><span>{message}</span>{recoveryPath&&<button className="btn secondary" onClick={recover}>尝试恢复项目</button>}<button onClick={()=>setMessage('')}>×</button></div>}{busy&&<div className="busy" role="status"><Loader2 className="spin" size={15}/>{busy}…{(busy.startsWith('计算')||busy.startsWith('识别'))&&<button onClick={()=>{job.current++;setBusy('');setMessage('已取消等待，本次结果不会写入当前项目。')}}>取消等待</button>}</div>}
  {!project?<section className="welcome"><div className="eyebrow">WESTERN BLOT · RESEARCH WORKSPACE</div><h1>让每一条带，<br/>都有可靠的答案。</h1><p>从原始图像到定量结果，在一个工作区里完成。<br/>保留原始像素，复核每个选择，让分析过程可追溯。</p><div className="welcome-actions"><button className="btn primary" onClick={()=>switchProject(createProject('未命名实验'))}><Plus size={17}/>新建实验</button><button className="btn secondary" onClick={loadDemo}><Sparkles size={17}/>体验合成示例</button></div><div className="welcome-card"><div className="mini-blot">{Array.from({length:12},(_,i)=><i key={i} style={{opacity:.25+i*.06,height:12+(i%3)*4}}/>)}</div><span>原始图像 → 条带复核 → 定量分析</span><small>支持灰度 TIFF / PNG · 保留 8 / 16 位数据</small></div><div className="welcome-foot">Titan WB 0.1 · 科研分析工具 · 真实 WB 数据验证待完成</div></section>:
   <><section className="project-heading"><div><div className="eyebrow">EXPERIMENT WORKSPACE</div><input aria-label="实验名称" className="project-name" value={project.name} onChange={e=>edit(p=>p.name=e.target.value)}/><p>{project.images.length} 张原始图像 <span>·</span> {project.rois.length} 个条带区域 <span>·</span> {reviewed} 已复核 {(project as any).demo&&<b className="synthetic-label">纯合成示例 · 非实验数据</b>}</p></div><div className="project-actions"><button className="icon-btn" title="撤销" disabled={!past.length} onClick={()=>historyUndo()}><Undo2 size={17}/></button><button className="icon-btn" title="重做" disabled={!future.length} onClick={()=>historyUndo(true)}><Redo2 size={17}/></button><button className="btn secondary" disabled={!!busy||project.read_only} onClick={()=>importImages().catch(e=>setMessage(String(e)))}><ImagePlus size={16}/>导入图像</button><button className="btn primary" disabled={!!busy||!project.rois.length} onClick={analyze}><Activity size={16}/>开始定量</button></div></section>
   <div className="steps">{([['workspace','图像与条带'],['samples','样本与参考'],['results','定量结果']] as const).map(([t,label],i)=><button key={t} onClick={()=>setTab(t)} className={tab===t?'selected':''}><span>0{i+1}</span>{label}</button>)}<div className="steps-note"><ShieldCheck size={14}/>原始像素参与计算</div></div>
   <section className="page-content">{tab==='workspace'?<Workspace project={project} onEdit={edit} onDetect={detect} onReview={review} busy={!!busy}/>:tab==='samples'?<SampleEditor project={project} onEdit={edit} onReview={review}/>:<Results project={project} result={result} onEdit={edit} onAnalyze={analyze}/>}</section></>}
  <footer className="statusbar"><span><ShieldCheck size={12}/>原图与预览分离 · 本地运行</span><span>{project?`项目版本 ${project.revision} · ${dirty?'有未保存修改':'已保存'}`:'macOS · Tauri + Python'}</span></footer></div></div>
}
