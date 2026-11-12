// @vitest-environment jsdom
import {act,createElement} from 'react'
import {createRoot,type Root} from 'react-dom/client'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {invoke} from '@tauri-apps/api/core'
import useAccount,{type AccountState} from './useAccount'
import {type AccountSession,type AccountSnapshot} from './account-bridge'
vi.mock('@tauri-apps/api/core',()=>({invoke:vi.fn()}))
const guest:AccountSnapshot={status:'guest',profile:null,message:null,persistent:false,errorCode:null}
const alice:AccountSnapshot={...guest,status:'authenticated',persistent:true,profile:{id:'a',name:'Alice',email:'a@example.org',createdAt:'2026-11-01',emailVerified:true,sessionId:'session-a'}}
let root:Root,host:HTMLDivElement,state:AccountState
function Probe(){state=useAccount();return createElement('p',null,state.snapshot.profile?.name||state.snapshot.status)}
function pending<T>(){let resolve!:(value:T)=>void;const promise=new Promise<T>(r=>{resolve=r});return {promise,resolve}}
async function mount(){await act(async()=>root.render(createElement(Probe)))}
beforeEach(()=>{Object.assign(globalThis,{IS_REACT_ACT_ENVIRONMENT:true,__TAURI_INTERNALS__:{}});host=document.createElement('div');document.body.append(host);root=createRoot(host);vi.mocked(invoke).mockImplementation(async command=>command==='auth_sessions'?[]:guest as any)})
afterEach(async()=>{await act(async()=>root.unmount());host.remove();delete (window as any).__TAURI_INTERNALS__;vi.resetAllMocks()})
it('loads configured status and leaves the browser preview honestly unconfigured',async()=>{
 await mount();expect(state.snapshot.status).toBe('guest')
 await act(async()=>root.unmount());root=createRoot(host);delete (window as any).__TAURI_INTERNALS__;vi.mocked(invoke).mockClear();await mount();expect(state.snapshot.status).toBe('unconfigured');expect(invoke).not.toHaveBeenCalled()
})
it('shows login immediately and cancellation fences its delayed completion',async()=>{
 const login=pending<AccountSnapshot>();vi.mocked(invoke).mockImplementation(async command=>command==='auth_login'?login.promise:guest as any)
 await mount();await act(async()=>{void state.login()});expect(state.busy).toBe('login');expect(state.snapshot.status).toBe('logging_in')
 await act(async()=>state.cancel());expect(invoke).toHaveBeenCalledWith('auth_cancel');expect(state.snapshot.status).toBe('guest');expect(state.busy).toBeNull()
 await act(async()=>login.resolve(alice));expect(state.snapshot.profile).toBeNull()
})
it('requires a second explicit memory-only login after credential storage failure',async()=>{
 vi.mocked(invoke).mockImplementation(async command=>command==='auth_login'?{...guest,status:'unavailable',errorCode:'credential_storage_failed',message:'系统凭据存储不可用'}:guest as any)
 await mount();await act(async()=>state.login());expect(state.snapshot.errorCode).toBe('credential_storage_failed');expect(vi.mocked(invoke).mock.calls.filter(([c])=>c==='auth_login')).toHaveLength(1)
 await act(async()=>state.login(true));expect(invoke).toHaveBeenLastCalledWith('auth_login',{memoryOnly:true,switchAccount:false})
})
it('retains an honest remote-revocation notice after offline logout',async()=>{
 vi.mocked(invoke).mockImplementation(async command=>command==='auth_status'?{...alice,status:'offline',errorCode:'network_unavailable'}:command==='auth_sessions'?[]:guest as any)
 await mount();await act(async()=>state.logout());expect(state.snapshot.profile).toBeNull();expect(state.notice).toContain('未确认');expect(state.notice).toContain('其他设备')
})
it('switches accounts with forced browser auth and rejects older profile and session results',async()=>{
 const profile=pending<AccountSnapshot>(),sessions=pending<AccountSession[]>()
 vi.mocked(invoke).mockImplementation(async command=>command==='auth_status'?alice:command==='auth_update_profile'?profile.promise:command==='auth_sessions'?sessions.promise:command==='auth_login'?{...alice,profile:{...alice.profile!,id:'b',name:'Bob',sessionId:'session-b'}}:guest as any)
 await mount();await act(async()=>{void state.loadSessions();void state.updateProfile('old')});await act(async()=>state.login(false,true));expect(host.textContent).toBe('Bob');expect(invoke).toHaveBeenCalledWith('auth_login',{memoryOnly:false,switchAccount:true})
 await act(async()=>{profile.resolve({...alice,profile:{...alice.profile!,name:'late'}});sessions.resolve([{id:'old',label:'old',platform:'macos',createdAt:'2026-11-01',lastSeenAt:'2026-11-12',expiresAt:'2026-12-01',current:true}])});expect(host.textContent).toBe('Bob');expect(state.sessions).toEqual([])
})
it('does not revive authentication from delayed initial status after logout',async()=>{
 const initial=pending<AccountSnapshot>();vi.mocked(invoke).mockImplementation(async command=>command==='auth_status'?initial.promise:guest as any)
 await mount();await act(async()=>state.logout());await act(async()=>initial.resolve(alice));expect(state.snapshot.status).toBe('guest')
})
it('sanitizes IPC rejections and exposes retryable session failures by code',async()=>{
 vi.mocked(invoke).mockImplementation(async command=>{if(command==='auth_status')return alice as any;if(command==='auth_sessions')throw 'service_unavailable';throw new Error('raw credential payload')})
 await mount();await act(async()=>state.loadSessions());expect(state.sessionsError).toBe('service_unavailable');await act(async()=>state.updateProfile('Name'));expect(state.snapshot.errorCode).toBe('service_unavailable');expect(JSON.stringify(state)).not.toContain('raw credential')
})
it('leaves pending login after an IPC failure so a guest can retry',async()=>{
 vi.mocked(invoke).mockImplementation(async command=>{if(command==='auth_login')throw new Error('private IPC detail');return guest as any})
 await mount();await act(async()=>state.login());expect(state.busy).toBeNull();expect(state.snapshot.status).toBe('unavailable');expect(state.snapshot.errorCode).toBe('service_unavailable');expect(JSON.stringify(state)).not.toContain('private IPC detail')
})

it.each([
 ['authenticated','offline','network_unavailable'],
 ['offline','authenticated',null],
 ['authenticated','unavailable','credential_storage_failed'],
 ['authenticated','reauth_required','refresh_ambiguous'],
] as const)('reconciles session outcome from %s to %s',async(initial,final,code)=>{
 let native:AccountSnapshot={...alice,status:initial}
 vi.mocked(invoke).mockImplementation(async command=>{
  if(command==='auth_status')return native as any
  if(command==='auth_sessions'){
   native={...alice,status:final,errorCode:code,profile:final==='unavailable'||final==='reauth_required'?null:alice.profile,persistent:final==='authenticated'||final==='offline'}
   if(code)throw code
   return [] as any
  }
  return guest as any
 })
 await mount();await act(async()=>state.loadSessions())
 expect(state.snapshot.status).toBe(final);expect(state.snapshot.errorCode).toBe(code)
 expect(state.snapshot.profile).toEqual(native.profile)
 expect(state.sessionsError).toBe(code)
})
it.each(['logout','switch'] as const)('fences delayed session snapshot after %s',async(action)=>{
 const delayed=pending<AccountSnapshot>();let statusCalls=0
 const bob={...alice,profile:{...alice.profile!,id:'b',name:'Bob',sessionId:'session-b'}}
 vi.mocked(invoke).mockImplementation(async command=>command==='auth_status'?(++statusCalls===1?alice:delayed.promise):command==='auth_sessions'?[]:command==='auth_login'?bob:guest as any)
 await mount();await act(async()=>{void state.loadSessions()})
 await act(async()=>action==='logout'?state.logout():state.login(false,true))
 await act(async()=>delayed.resolve({...alice,status:'offline'}))
 expect(state.snapshot).toEqual(action==='logout'?guest:bob);expect(state.sessions).toEqual([])
})
