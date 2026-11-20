import {Channel,invoke} from '@tauri-apps/api/core'
import {relaunch} from '@tauri-apps/plugin-process'
import {check,type DownloadEvent,type Update} from '@tauri-apps/plugin-updater'
import {Download,X} from 'lucide-react'
import {useCallback,useEffect,useLayoutEffect,useRef,useState} from 'react'
import './app-update.css'

type Phase='idle'|'checking'|'current'|'unsupported'|'unconfigured'|'available'|'downloading'|'ready'|'installing'|'installed'
type UpdatePackage=Pick<Update,'version'|'body'|'download'|'install'|'close'>
type State={phase:Phase;current?:string;update?:UpdatePackage;progress?:number;message?:string;installerRestarts?:boolean}
type InstallGuard=(install:()=>Promise<void>)=>Promise<boolean>

async function checkWindowsUpdate():Promise<UpdatePackage|null>{
 const update=await invoke<Pick<Update,'version'|'body'>|null>('check_windows_update')
 if(!update)return null
 const {version}=update
 return {...update,
  download(onEvent){
   const channel=new Channel<DownloadEvent>()
   if(onEvent)channel.onmessage=onEvent
   return invoke('download_windows_update',{version,onEvent:channel})
  },
  install:()=>invoke('install_windows_update',{version}),
  close:()=>invoke('clear_windows_update',{version}),
 }
}

export function useAppUpdate(native:boolean,withSavedWork:InstallGuard){
 const [state,setState]=useState<State>({phase:'idle'})
 const flight=useRef<'check'|'download'|'install'|null>(null)
 const deferred=useRef(false)
 const installGuard=useRef(withSavedWork)
 useLayoutEffect(()=>{installGuard.current=withSavedWork},[withSavedWork])
 const checkForUpdate=useCallback(async (previous?:UpdatePackage)=>{
  if(!native||flight.current)return
  flight.current='check'
  setState({phase:'checking'})
  try{
   await previous?.close().catch(()=>{})
   const config=await invoke<{enabled:boolean;supported:boolean;version:string;installerRestarts?:boolean}>('update_configuration')
   if(!config.supported){setState({phase:'unsupported',current:config.version});return}
   if(!config.enabled){setState({phase:'unconfigured',current:config.version});return}
   const update=config.installerRestarts?await checkWindowsUpdate():await check({timeout:15000})
   setState(update?{phase:'available',current:config.version,update,installerRestarts:config.installerRestarts}:{phase:'current',current:config.version})
  }catch{
   setState({phase:'idle',message:'检查更新失败。请检查网络后重试。'})
  }finally{flight.current=null}
 },[native])
 useEffect(()=>{void checkForUpdate()},[checkForUpdate])
 async function download(update:UpdatePackage){
  let bytes=0,total=0,progress=0
  setState({...state,phase:'downloading',message:undefined})
  try{
   await update.download(event=>{
    if(event.event==='Started')total=event.data.contentLength??0
    if(event.event!=='Progress'||!total)return
    bytes+=event.data.chunkLength
    const percent=Math.min(99,Math.floor(bytes/total*100))
    if(percent>progress){progress=percent;setState(previous=>({...previous,progress}))}
   },{timeout:600000})
   return true
  }catch{
   setState({...state,message:'下载或校验未完成。请重新下载更新。'})
   return false
  }
 }
 async function install(update:UpdatePackage,ready:State){
  let installed=false
  setState({...ready,phase:'installing'})
  try{
   const proceeded=await installGuard.current(async()=>{
    await update.install()
    installed=true
    if(!ready.installerRestarts)await relaunch()
   })
   if(!proceeded)setState({...ready,message:'请完成当前任务并保存草稿，再安装更新。'})
   else setState({phase:'installed',current:update.version})
  }catch{
   setState(installed?{phase:'installed',current:update.version,message:'新版已安装。请重启 Titan 完成更新。'}:
    {...ready,message:'安装更新未完成。请检查分析保存状态和 Titan 的安装目录权限后重试。'})
  }
 }
 async function applyUpdate(){
  const {phase,update}=state
  if(flight.current||!update||(phase!=='available'&&phase!=='ready'))return
  const ready:State={phase:'ready',current:state.current,update,installerRestarts:state.installerRestarts}
  try{
   if(phase==='available'){
    deferred.current=false
    flight.current='download'
    if(!await download(update))return
    if(deferred.current){setState(ready);return}
   }
   flight.current='install'
   await install(update,ready)
  }finally{flight.current=null}
 }
 function deferInstallation(){
  if(flight.current==='install')return false
  if(flight.current==='download')deferred.current=true
  return true
 }
 async function restart(){
  if(flight.current)return
  flight.current='install'
  setState(previous=>({...previous,phase:'installing',message:undefined}))
  try{
   if(!await installGuard.current(relaunch))setState({...state,message:'请完成当前任务并保存草稿，再重启 Titan。'})
  }catch{setState({...state,message:'新版已安装。请退出并重新打开 Titan。'})}
  finally{flight.current=null}
 }
 return {state,checkForUpdate,applyUpdate,deferInstallation,restart}
}

type UpdateControl=ReturnType<typeof useAppUpdate>
const updateLabels:Partial<Record<Phase,string>>={
 available:'更新并重启',
 downloading:'正在下载更新',
 ready:'安装更新并重启',
 installing:'正在安装更新',
 installed:'重启以更新',
}

export function AppUpdateButton({update,onOpen}:{update:UpdateControl;onOpen:()=>void}){
 const label=updateLabels[update.state.phase]
 if(!label)return null
 return <div className="sidebar-update">
  <button type="button" className="update-trigger" aria-haspopup="dialog" aria-label={label}
   title={update.state.update?`${label} · Titan ${update.state.update.version}`:label}
   onClick={()=>{onOpen();void (update.state.phase==='installed'?update.restart():update.applyUpdate())}}>
   <span className="update-icon"><Download size={14} aria-hidden="true"/></span>
  </button>
 </div>
}

export function AppUpdateDialog({update,onClose}:{update:UpdateControl;onClose:()=>void}){
 const dialog=useRef<HTMLDialogElement>(null)
 useEffect(()=>{const element=dialog.current;if(element&&!element.open)element.showModal()},[])
 const {state,checkForUpdate,applyUpdate,deferInstallation,restart}=update
 const {phase,current,update:release,progress,message}=state
 const installing=phase==='installing'
 function close(){if(deferInstallation())dialog.current?.close()}
 const status={
  idle:'',checking:'正在检查更新…',current:'已是此更新渠道的最新版本。',
  unsupported:'当前平台暂未启用应用内更新。',
  unconfigured:'此安装包尚未配置应用内更新。',
  available:release?`发现 Titan ${release.version}`:'',
  downloading:'正在下载并校验更新…',
  ready:'更新包已校验。安装前 Titan 会保存当前工作，然后重启。',
  installing:'正在准备安装并重启…',installed:'新版已安装。',
 }[phase]
 return <dialog ref={dialog} className="settings-dialog app-update-dialog" aria-labelledby="app-update-title"
  onClose={onClose} onCancel={event=>{if(!deferInstallation())event.preventDefault()}}>
  <header className="settings-header">
   <h2 id="app-update-title">软件更新</h2>
   <button type="button" className="icon-btn" aria-label="关闭软件更新" disabled={installing} onClick={close}><X size={19}/></button>
  </header>
  <div className="settings-body">
   {current&&<p>当前版本 {current}{release&&phase!=='available'&&` · 新版本 ${release.version}`}</p>}
   {status&&<p className="update-status" role="status">{status}</p>}
   {release?.body&&!installing&&<p className="update-notes">{release.body}</p>}
   {phase==='downloading'&&<progress aria-label="下载进度" value={progress} max={100}/>}
   {message&&<p role="alert">{message}</p>}
  </div>
  <footer className="settings-footer">
   <button type="button" className="btn secondary" disabled={installing} onClick={close}>{phase==='downloading'?'稍后安装':release||installing?'稍后':'关闭'}</button>
   {phase==='idle'&&<button type="button" className="btn primary" onClick={()=>void checkForUpdate()}>重新检查</button>}
   {phase==='available'&&message&&<button type="button" className="btn secondary" onClick={()=>void checkForUpdate(release)}>重新检查</button>}
   {phase==='available'&&<button type="button" className="btn primary" onClick={()=>void applyUpdate()}>{message?'重试更新':'更新并重启'}</button>}
   {phase==='ready'&&<button type="button" className="btn primary" onClick={()=>void applyUpdate()}>安装并重启</button>}
   {phase==='installed'&&<button type="button" className="btn primary" onClick={()=>void restart()}>重启 Titan</button>}
  </footer>
 </dialog>
}
