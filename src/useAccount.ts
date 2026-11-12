import {useCallback,useEffect,useRef,useState} from 'react'
import {accountBridge,guestSnapshot,type AccountSession,type AccountSnapshot} from './account-bridge'

const codes=new Set(['forbidden','not_found','unconfigured','guest','login_in_progress','stale_generation','network_unavailable','unauthorized','refresh_ambiguous','invalid_response','service_unavailable','rate_limited','credential_storage_failed','credential_cleanup_failed','credential_invalidation_failed','recent_auth_required','invalid_profile','invalid_request','invalid_discovery','invalid_id_token','invalid_token_response','browser_unavailable','callback_unavailable','login_failed','login_denied','login_cancelled','login_timeout'])
const errorCode=(error:unknown)=>typeof error==='string'&&codes.has(error)?error:'service_unavailable'
export function accountErrorText(code:string){
 switch(code){
  case 'service_unavailable':return '账户服务暂时不可用，请稍后重试。本地功能仍可使用。'
  case 'forbidden':return '当前操作未获授权，请重新验证身份或稍后重试。本地功能仍可使用。'
  case 'not_found':return '设备记录已不存在，请刷新设备列表。'
  case 'rate_limited':return '操作过于频繁，请稍后重试。本地功能仍可使用。'
  case 'network_unavailable':return '账户服务暂时无法连接，本地功能仍可使用。'
  case 'recent_auth_required':return '请在浏览器中重新验证身份，再退出所有设备。'
  case 'unauthorized':case 'refresh_ambiguous':return '登录已失效，请重新登录。本地功能仍可使用。'
  case 'invalid_profile':return '请输入1至60个字符的昵称。'
  case 'credential_storage_failed':return '系统凭据存储不可用，请重试或选择仅本次登录。'
  case 'credential_cleanup_failed':return '凭据清理未全部完成；已阻止自动恢复，请重试清理。'
  case 'credential_invalidation_failed':return '无法清除登录凭据或禁用自动恢复；重启后可能再次登录，请重试退出。'
  case 'login_cancelled':return '已取消登录。'
  case 'login_timeout':return '登录等待超时，请重试。'
  default:return '账户操作未完成，请稍后重试。本地功能仍可使用。'
 }
}
export default function useAccount(){
 const [snapshot,setSnapshot]=useState<AccountSnapshot>(guestSnapshot)
 const [busy,setBusy]=useState<string|null>(null),[sessions,setSessions]=useState<AccountSession[]>([])
 const [sessionsError,setSessionsError]=useState<string|null>(null),[notice,setNotice]=useState<string|null>(null)
 const current=useRef(snapshot),generation=useRef(0),sessionRequest=useRef(0),mounted=useRef(false)
 const apply=useCallback((next:AccountSnapshot)=>{current.current=next;setSnapshot(next)},[])
 const run=useCallback(async(action:string,command:()=>Promise<AccountSnapshot>,reset=false)=>{
  const epoch=++generation.current
  if(reset){setSessions([]);setSessionsError(null);sessionRequest.current++}
  setBusy(action);setNotice(null)
  if(action==='login')apply({...guestSnapshot,status:'logging_in'})
  try{
   const next=await command()
   if(mounted.current&&epoch===generation.current){
    apply(next)
    if(!next.profile){setSessions([]);setSessionsError(null);sessionRequest.current++}
    // Native logout only confirms local invalidation; remote revocation is best effort.
    if(action==='logout')setNotice('已退出当前运行的账户。服务端撤销未确认；其他设备请在重新联网后登录并管理。')
   }
  }catch(error){
   if(mounted.current&&epoch===generation.current){const code=errorCode(error);apply({...current.current,...(action==='login'?{status:'unavailable' as const}:{}),errorCode:code,message:accountErrorText(code)})}
  }finally{if(mounted.current&&epoch===generation.current)setBusy(null)}
 },[apply])
 const refresh=useCallback(async()=>{
  if(!('__TAURI_INTERNALS__' in window))return
  await run('status',accountBridge.status)
 },[run])
 useEffect(()=>{mounted.current=true;void refresh();return()=>{mounted.current=false;generation.current++;sessionRequest.current++}},[refresh])
 const loadSessions=useCallback(async()=>{
  const epoch=generation.current,request=++sessionRequest.current,identity=current.current.profile?.sessionId
  if(!identity)return
  setSessionsError(null)
  const ownsRequest=()=>mounted.current&&epoch===generation.current&&request===sessionRequest.current&&current.current.profile?.sessionId===identity
  let rows:AccountSession[]=[],failure:string|null=null
  try{rows=await accountBridge.sessions()}catch(error){failure=errorCode(error)}
  if(!ownsRequest())return
  // Listing devices can refresh, recover, or invalidate native credentials. Read the
  // sanitized state on either outcome, with fences around this second IPC await.
  try{
   const next=await accountBridge.status()
   if(!ownsRequest())return
   if(next.profile&&next.profile.sessionId!==identity)return
   apply(next)
   setSessions(next.profile?rows:[])
   setSessionsError(failure)
  }catch(error){
   if(ownsRequest()){setSessions([]);setSessionsError(errorCode(error))}
  }
 },[apply])
 return {snapshot,busy,sessions,sessionsError,notice,refresh,
  login:(memoryOnly=false,switchAccount=false)=>run('login',()=>accountBridge.login(memoryOnly,switchAccount),true),
  cancel:()=>run('cancel',accountBridge.cancel,true),
  logout:()=>run('logout',accountBridge.logout,true),
  updateProfile:(name:string)=>run('profile',()=>accountBridge.updateProfile(name)),
  loadSessions,
  revokeSession:async(id:string)=>{await run('revoke',()=>accountBridge.revokeSession(id));await loadSessions()},
  revokeAll:()=>run('revokeAll',accountBridge.revokeAll,true),
 }
}
export type AccountState=ReturnType<typeof useAccount>
