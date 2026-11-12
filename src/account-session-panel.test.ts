// @vitest-environment jsdom
import {act,createElement} from 'react'
import {createRoot,type Root} from 'react-dom/client'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {invoke} from '@tauri-apps/api/core'
import useAccount from './useAccount'
import AccountSessionPanel from './AccountSessionPanel'
import {type AccountSnapshot} from './account-bridge'
vi.mock('@tauri-apps/api/core',()=>({invoke:vi.fn()}))
const guest:AccountSnapshot={status:'guest',profile:null,message:null,persistent:false,errorCode:null}
const alice:AccountSnapshot={...guest,status:'authenticated',persistent:true,profile:{id:'a',name:'Alice',email:'a@example.org',createdAt:'2026-11-01',emailVerified:true,sessionId:'one'}}
let root:Root,host:HTMLDivElement
function Harness(){return createElement(AccountSessionPanel,{account:useAccount()})}
const button=(text:string)=>[...host.querySelectorAll('button')].find(b=>b.textContent===text)!
async function click(text:string){await act(async()=>button(text).click())}
async function mount(){await act(async()=>root.render(createElement(Harness)))}
beforeEach(()=>{Object.assign(globalThis,{IS_REACT_ACT_ENVIRONMENT:true,__TAURI_INTERNALS__:{}});host=document.createElement('div');document.body.append(host);root=createRoot(host);vi.mocked(invoke).mockImplementation(async command=>command==='auth_sessions'?[]:guest as any)})
afterEach(async()=>{await act(async()=>root.unmount());host.remove();delete (window as any).__TAURI_INTERNALS__;vi.resetAllMocks()})
it('offers system-browser login for configured guests without password inputs',async()=>{
 await mount();expect(button('登录 / 注册').disabled).toBe(false);expect(host.textContent).toContain('系统浏览器');expect(host.querySelector('input[type=password]')).toBeNull()
})
it('offers only an explanatory service notice when unconfigured',async()=>{
 vi.mocked(invoke).mockResolvedValue({...guest,status:'unconfigured'});await mount();await click('登录 / 注册');expect(host.textContent).toContain('登录服务尚未开放');expect(invoke).not.toHaveBeenCalledWith('auth_login',expect.anything())
})
it('keeps cancel enabled during browser login and exposes memory-only choice after storage failure',async()=>{
 let finish!:(s:AccountSnapshot)=>void
 vi.mocked(invoke).mockImplementation(async command=>command==='auth_login'?new Promise<AccountSnapshot>(r=>{finish=r}):guest as any)
 await mount();await click('登录 / 注册');expect(button('取消登录').disabled).toBe(false);expect(host.textContent).toContain('等待浏览器')
 await act(async()=>finish({...guest,status:'unavailable',errorCode:'credential_storage_failed',message:'系统凭据存储不可用'}));expect(button('仅本次登录')).toBeTruthy();expect(invoke).toHaveBeenCalledTimes(2)
 await click('仅本次登录');expect(invoke).toHaveBeenLastCalledWith('auth_login',{memoryOnly:true,switchAccount:false})
 await click('取消登录');expect(host.textContent).not.toContain('等待浏览器')
})
it('shows only returned devices and confirms account-wide logout inside the product',async()=>{
 vi.mocked(invoke).mockImplementation(async command=>command==='auth_status'?alice:command==='auth_sessions'?[{id:'one',label:'MacBook',platform:'macos',createdAt:'2026-11-01',lastSeenAt:'2026-11-12',expiresAt:'2026-12-01',current:true}]:guest as any)
 await mount();expect(host.textContent).toContain('MacBook');expect(host.textContent).toContain('当前设备');await click('退出所有设备');expect(invoke).not.toHaveBeenCalledWith('auth_revoke_all');expect(host.querySelector('[role=alertdialog]')).not.toBeNull();await click('暂不退出');expect(invoke).not.toHaveBeenCalledWith('auth_revoke_all');await click('退出所有设备');await click('确认退出所有设备');expect(invoke).toHaveBeenCalledWith('auth_revoke_all')
})
it('requires fresh browser authentication before retrying sensitive revocation',async()=>{
 vi.mocked(invoke).mockImplementation(async command=>command==='auth_sessions'?[]:command==='auth_revoke_all'?{...alice,errorCode:'recent_auth_required',message:'请重新登录后再退出所有设备。'}:alice as any)
 await mount();await click('退出所有设备');await click('确认退出所有设备');expect(button('在浏览器中重新验证')).toBeTruthy();await click('在浏览器中重新验证');expect(invoke).toHaveBeenCalledWith('auth_login',{memoryOnly:false,switchAccount:true});expect(vi.mocked(invoke).mock.calls.filter(([c])=>c==='auth_revoke_all')).toHaveLength(1)
})
it('shows honest invalidation failure and an actionable logout retry',async()=>{
 vi.mocked(invoke).mockResolvedValue({...guest,errorCode:'credential_invalidation_failed',message:'重启后可能再次登录，请重试退出。'});await mount();expect(host.textContent).toContain('重启后可能再次登录');expect(host.textContent).not.toContain('已阻止自动恢复');await click('重试退出');expect(invoke).toHaveBeenLastCalledWith('auth_logout')
})
it('edits nickname through the native command and waits for confirmed profile',async()=>{
 let finish!:(s:AccountSnapshot)=>void
 vi.mocked(invoke).mockImplementation(async command=>command==='auth_sessions'?[]:command==='auth_update_profile'?new Promise<AccountSnapshot>(r=>{finish=r}):alice as any)
 await mount();const input=host.querySelector('input')!
 await act(async()=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(input,'新昵称');input.dispatchEvent(new Event('input',{bubbles:true}))});await click('保存昵称');expect(invoke).toHaveBeenCalledWith('auth_update_profile',{name:'新昵称'});expect(button('保存昵称').disabled).toBe(true);await act(async()=>finish({...alice,profile:{...alice.profile!,name:'新昵称'}}));expect(input.value).toBe('新昵称')
})
it.each([['rate_limited','操作过于频繁'],['forbidden','当前操作未获授权'],['service_unavailable','账户服务暂时不可用']])('makes %s retryable while retaining account controls',async(code,text)=>{
 vi.mocked(invoke).mockImplementation(async command=>{if(command==='auth_sessions')throw code;return alice as any});await mount();expect(host.textContent).toContain(text);expect(button('重试设备列表')).toBeTruthy();expect(button('退出本机')).toBeTruthy()
})
