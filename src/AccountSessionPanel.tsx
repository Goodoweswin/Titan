import {useEffect,useRef,useState} from 'react'
import {LogIn} from 'lucide-react'
import {accountErrorText,type AccountState} from './useAccount'

const date=(value:string)=>Number.isFinite(Date.parse(value))?new Date(value).toLocaleString('zh-CN'):'—'
export default function AccountSessionPanel({account}:{account:AccountState}){
 const {snapshot,busy,sessions,sessionsError,notice,loadSessions}=account
 const profile=snapshot.profile,code=snapshot.errorCode
 const [info,setInfo]=useState(false),[name,setName]=useState(profile?.name||''),[confirm,setConfirm]=useState(false)
 const confirmButton=useRef<HTMLButtonElement>(null),revokeButton=useRef<HTMLButtonElement>(null),switching=useRef(false)
 const logging=busy==='login'||snapshot.status==='logging_in'
 const ownerUnavailable=code==='account_owner_unavailable'
 const disabled=!!busy||ownerUnavailable
 const signedIn=!!profile&&(snapshot.status==='authenticated'||snapshot.status==='offline')
 useEffect(()=>{setName(profile?.name||'');setConfirm(false)},[profile?.id,profile?.name])
 useEffect(()=>{if(profile?.sessionId)void loadSessions()},[profile?.sessionId,loadSessions])
 useEffect(()=>{if(confirm)confirmButton.current?.focus()},[confirm])
 const login=(memoryOnly=false,switchAccount=false)=>{switching.current=switchAccount;void account.login(memoryOnly,switchAccount)}
 function closeConfirm(){setConfirm(false);revokeButton.current?.focus()}
 return <div className="account-session-panel">
  {logging?<div className="account-login-info" role="status"><strong>等待浏览器完成登录</strong><p>请在系统浏览器中登录或注册，完成后返回 Titan。取消后仍可使用本地功能。</p><button className="text-btn" type="button" onClick={()=>void account.cancel()} disabled={busy==='cancel'}>取消登录</button></div>:!signedIn?<div className="account-login-actions">
   <button className="btn primary" type="button" disabled={disabled} aria-expanded={snapshot.status==='unconfigured'?info:undefined} aria-controls={snapshot.status==='unconfigured'?'account-login-info':undefined} onClick={()=>snapshot.status==='unconfigured'?setInfo(v=>!v):login()}><LogIn size={16}/>登录 / 注册</button>
   <small>未登录 · 本地功能可正常使用</small>
   {snapshot.status==='unconfigured'?<div id="account-login-info" className="account-login-info" hidden={!info} role="status"><strong>登录服务尚未开放</strong><p>此版本尚未配置账户服务。当前可继续使用本地项目，账户资料暂不保存。</p><button className="text-btn" type="button" onClick={()=>setInfo(false)}>知道了</button></div>:!ownerUnavailable&&<p>在系统浏览器中完成登录 / 注册，Titan 不收集密码。</p>}
  </div>:<>
   <form className="account-name-form" onSubmit={event=>{event.preventDefault();void account.updateProfile(name)}}><label htmlFor="account-nickname">昵称</label><div><input id="account-nickname" autoComplete="nickname" maxLength={60} value={name} onChange={event=>setName(event.target.value)} disabled={disabled}/><button className="btn" type="submit" disabled={disabled||!name.trim()||name.trim()===profile!.name}>保存昵称</button></div></form>
   <div className="account-session-actions"><span>{snapshot.status==='offline'?'离线 · 资料为上次确认结果':snapshot.persistent?'已登录 · 此设备安全保存登录':'已登录 · 仅本次使用，退出应用后需重新登录'}</span><button className="text-btn" type="button" disabled={disabled} onClick={()=>login(false,true)}>切换账户</button><button className="text-btn" type="button" disabled={disabled} onClick={()=>void account.logout()}>退出本机</button></div>
  </>}
  {code&&<div className="account-login-info account-auth-error" role="alert"><p>{snapshot.message||accountErrorText(code)}</p>
   {code==='credential_storage_failed'&&<div className="account-session-actions"><button className="btn" type="button" disabled={disabled} onClick={()=>login(false,switching.current)}>重试安全存储登录</button><button className="btn" type="button" disabled={disabled} onClick={()=>login(true,switching.current)}>仅本次登录</button><small>仅在当前运行期间保持登录，不保存凭据。</small></div>}
   {(code==='credential_cleanup_failed'||code==='credential_invalidation_failed')&&<button className="text-btn" type="button" disabled={disabled} onClick={()=>void account.logout()}>重试退出</button>}
   {code==='recent_auth_required'&&<button className="btn" type="button" disabled={disabled} onClick={()=>login(false,true)}>在浏览器中重新验证</button>}
   {!['account_owner_unavailable','credential_storage_failed','credential_cleanup_failed','credential_invalidation_failed','recent_auth_required','login_cancelled'].includes(code)&&<button className="text-btn" type="button" disabled={disabled} onClick={()=>void account.refresh()}>重试连接</button>}
  </div>}
  {notice&&<p className="account-session-note" role="status">{notice}</p>}
  {signedIn&&!logging&&<section className="account-device-section" aria-labelledby="account-devices-title">
   <div className="account-section-heading"><h3 id="account-devices-title">登录设备</h3><button className="text-btn" type="button" disabled={disabled} onClick={()=>void loadSessions()}>刷新设备</button></div>
   {sessionsError?<p className="account-error" role="alert">{accountErrorText(sessionsError)}<button type="button" disabled={disabled} onClick={()=>void loadSessions()}>重试设备列表</button></p>:sessions.length?<ul className="account-devices">{sessions.map(session=><li key={session.id}><div><strong>{session.label}</strong>{session.current&&<span className="account-current-device">当前设备</span>}<p>{session.platform} · 最近活动 {date(session.lastSeenAt)}</p><small>登录 {date(session.createdAt)} · 到期 {date(session.expiresAt)}</small></div><button type="button" className="text-btn" disabled={disabled} onClick={()=>void account.revokeSession(session.id)}>{session.current?'退出此设备':'撤销登录'}</button></li>)}</ul>:<p className="account-empty-note">暂无已确认的设备记录。</p>}
   <div className="account-session-actions"><button ref={revokeButton} className="text-btn" type="button" disabled={disabled} onClick={()=>setConfirm(true)}>退出所有设备</button><small>包含此设备，需最近一次身份验证。</small></div>
   {confirm&&<div className="account-revoke-confirm" role="alertdialog" aria-modal="false" aria-labelledby="account-revoke-title" aria-describedby="account-revoke-description" onKeyDown={event=>{if(event.key==='Escape'){event.preventDefault();event.stopPropagation();closeConfirm()}}}><h4 id="account-revoke-title">退出所有设备？</h4><p id="account-revoke-description">所有设备的登录将失效，包括当前设备。本地项目和未保存的工作仍保留。</p><div className="account-session-actions"><button ref={confirmButton} className="btn" type="button" onClick={closeConfirm}>暂不退出</button><button className="btn" type="button" disabled={disabled} onClick={()=>{setConfirm(false);void account.revokeAll()}}>确认退出所有设备</button></div></div>}
  </section>}
 </div>
}
