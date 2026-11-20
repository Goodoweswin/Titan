// @vitest-environment jsdom
import {StrictMode,act,createElement,useState} from 'react'
import {createRoot} from 'react-dom/client'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {AppUpdateButton,AppUpdateDialog,useAppUpdate} from '../../src/AppUpdate'

const mocks=vi.hoisted(()=>({
 check:vi.fn(),invoke:vi.fn(),relaunch:vi.fn(),download:vi.fn(),install:vi.fn(),close:vi.fn(),
}))
vi.mock('@tauri-apps/plugin-updater',()=>({check:mocks.check}))
vi.mock('@tauri-apps/api/core',()=>({invoke:mocks.invoke,Channel:class{}}))
vi.mock('@tauri-apps/plugin-process',()=>({relaunch:mocks.relaunch}))

;(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true
let host:HTMLDivElement,root:ReturnType<typeof createRoot>
let allowInstall:boolean
function Harness({canInstall}:{canInstall:boolean}){
 const [show,setShow]=useState(false)
 const update=useAppUpdate(true,async install=>{
  if(!canInstall)return false
  await install()
  return true
 })
 return createElement('div',null,
  createElement(AppUpdateButton,{update,onOpen:()=>setShow(true)}),
  show&&createElement(AppUpdateDialog,{update,onClose:()=>setShow(false)}),
 )
}
async function click(label:string){
 const button=Array.from(host.querySelectorAll('button')).find(element=>(element.getAttribute('aria-label')??element.textContent)===label)
 expect(button?.disabled).toBe(false)
 await act(async()=>button?.click())
}
beforeEach(()=>{
 vi.resetAllMocks()
 mocks.close.mockResolvedValue(undefined)
 mocks.invoke.mockResolvedValue({enabled:true,supported:true,version:'0.4.2'})
 mocks.check.mockResolvedValue({version:'0.4.3',body:'修复说明',download:mocks.download,install:mocks.install,close:mocks.close})
 allowInstall=true
 HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','')}
 HTMLDialogElement.prototype.close=function(){this.removeAttribute('open');this.dispatchEvent(new Event('close'))}
 host=document.createElement('div')
 document.body.append(host)
 root=createRoot(host)
})
async function render(){
 await act(async()=>root.render(createElement(StrictMode,null,createElement(Harness,{canInstall:allowInstall}))))
}
afterEach(async()=>{await act(async()=>root.unmount());host.remove()})

it('checks once at startup and downloads, verifies, installs and restarts from one click',async()=>{
 let finishDownload!:()=>void
 mocks.download.mockReturnValueOnce(new Promise<void>(resolve=>{finishDownload=resolve}))
 await render()
 expect(mocks.check).toHaveBeenCalledOnce()
 expect(host.querySelector('dialog')).toBeNull()
 expect(mocks.download).not.toHaveBeenCalled()
 await click('更新并重启')
 expect(host.textContent).toContain('0.4.3')
 expect(host.textContent).toContain('修复说明')
 expect(mocks.download).toHaveBeenCalledOnce()
 expect(mocks.install).not.toHaveBeenCalled()
 await act(async()=>finishDownload())
 expect(mocks.install).toHaveBeenCalledOnce()
 expect(mocks.relaunch).toHaveBeenCalledOnce()
})

it('leaves Windows restart to the verified installer and allows retry if it cannot launch',async()=>{
 let attempts=0
 mocks.invoke.mockImplementation(async command=>{
  if(command==='update_configuration')return {enabled:true,supported:true,version:'0.4.2',installerRestarts:true}
  if(command==='check_windows_update')return {version:'0.4.3',body:'修复说明'}
  if(command==='download_windows_update')return
  if(command==='install_windows_update'&&attempts++>0)return
  throw Error('could not launch installer')
 })
 await render()
 await click('更新并重启')
 expect(host.textContent).toContain('安装更新未完成')
 await click('安装并重启')
 expect(mocks.invoke.mock.calls.filter(([command])=>command==='download_windows_update')).toHaveLength(1)
 expect(mocks.invoke.mock.calls.filter(([command])=>command==='install_windows_update')).toEqual([
  ['install_windows_update',{version:'0.4.3'}],['install_windows_update',{version:'0.4.3'}],
 ])
 expect(mocks.check).not.toHaveBeenCalled()
 expect(mocks.install).not.toHaveBeenCalled()
 expect(mocks.relaunch).not.toHaveBeenCalled()
})

it('keeps a verified download when current work prevents installation',async()=>{
 let finishDownload!:()=>void
 mocks.download.mockReturnValueOnce(new Promise<void>(resolve=>{finishDownload=resolve}))
 await render()
 await click('更新并重启')
 allowInstall=false
 await render()
 await act(async()=>finishDownload())
 expect(host.textContent).toContain('请完成当前任务')
 expect(mocks.install).not.toHaveBeenCalled()
 await click('稍后')
 allowInstall=true
 await render()
 await click('安装更新并重启')
 expect(mocks.download).toHaveBeenCalledOnce()
 expect(mocks.install).toHaveBeenCalledOnce()
 expect(mocks.relaunch).toHaveBeenCalledOnce()
})

it('defers automatic installation when the user closes the download dialog',async()=>{
 let finishDownload!:()=>void
 mocks.download.mockReturnValueOnce(new Promise<void>(resolve=>{finishDownload=resolve}))
 await render()
 await click('更新并重启')
 await click('稍后安装')
 expect(host.querySelector('dialog')).toBeNull()
 await act(async()=>finishDownload())
 expect(mocks.install).not.toHaveBeenCalled()
 await click('安装更新并重启')
 expect(mocks.download).toHaveBeenCalledOnce()
 expect(mocks.install).toHaveBeenCalledOnce()
})

it('keeps a failed download retryable and never offers installation',async()=>{
 mocks.download.mockRejectedValueOnce(new Error('signature mismatch'))
 await render()
 await click('更新并重启')
 expect(host.textContent).toContain('下载或校验未完成')
 expect(mocks.install).not.toHaveBeenCalled()
 await click('重试更新')
 expect(mocks.install).toHaveBeenCalledOnce()
})

it('can replace a stale manifest after a failed download',async()=>{
 mocks.download.mockRejectedValueOnce(new Error('asset replaced'))
 await render()
 await click('更新并重启')
 mocks.check.mockResolvedValueOnce({version:'0.4.4',download:mocks.download,install:mocks.install,close:mocks.close})
 await click('重新检查')
 expect(mocks.close).toHaveBeenCalledOnce()
 expect(host.textContent).toContain('发现 Titan 0.4.4')
 expect(mocks.install).not.toHaveBeenCalled()
})

it('hides the entry while checking and when the app is current',async()=>{
 let finish!:(result:null)=>void
 mocks.check.mockReturnValueOnce(new Promise(resolve=>{finish=resolve}))
 await render()
 expect(mocks.check).toHaveBeenCalledOnce()
 expect(host.querySelector('button,dialog')).toBeNull()
 await act(async()=>finish(null))
 expect(host.querySelector('button,dialog')).toBeNull()
})

it('keeps a failed startup check quiet',async()=>{
 mocks.check.mockRejectedValueOnce(new Error('offline'))
 await render()
 expect(mocks.check).toHaveBeenCalledOnce()
 expect(host.querySelector('button,dialog')).toBeNull()
})

it('hides the entry and skips the network when the channel is unconfigured',async()=>{
 mocks.invoke.mockResolvedValue({enabled:false,supported:true,version:'0.4.2'})
 await render()
 expect(host.querySelector('button,dialog')).toBeNull()
 expect(mocks.check).not.toHaveBeenCalled()
})

it('does not check an update source on an unsupported platform',async()=>{
 mocks.invoke.mockResolvedValue({enabled:false,supported:false,version:'0.4.2'})
 await render()
 expect(host.querySelector('button,dialog')).toBeNull()
 expect(mocks.check).not.toHaveBeenCalled()
})

it('offers a restart after installation succeeds but relaunch fails',async()=>{
 mocks.relaunch.mockRejectedValueOnce(new Error('relaunch error'))
 await render()
 await click('更新并重启')
 expect(host.textContent).toContain('新版已安装')
 await click('重启 Titan')
 expect(mocks.install).toHaveBeenCalledOnce()
 expect(mocks.relaunch).toHaveBeenCalledTimes(2)
})
