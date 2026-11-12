import {invoke} from '@tauri-apps/api/core'

export interface AccountProfile {id:string;name:string;email:string;createdAt:string;emailVerified:boolean;sessionId:string}
export interface AccountSession {id:string;label:string;platform:string;createdAt:string;lastSeenAt:string;expiresAt:string;current:boolean}
export interface AccountSnapshot {
 status:'unconfigured'|'guest'|'logging_in'|'authenticated'|'offline'|'reauth_required'|'unavailable'
 profile:AccountProfile|null;message:string|null;persistent:boolean;errorCode:string|null
}
export const guestSnapshot:AccountSnapshot={status:'unconfigured',profile:null,message:null,persistent:false,errorCode:null}
export const accountBridge={
 status:()=>invoke<AccountSnapshot>('auth_status'),
 login:(memoryOnly:boolean,switchAccount:boolean)=>invoke<AccountSnapshot>('auth_login',{memoryOnly,switchAccount}),
 cancel:()=>invoke<AccountSnapshot>('auth_cancel'),
 logout:()=>invoke<AccountSnapshot>('auth_logout'),
 updateProfile:(name:string)=>invoke<AccountSnapshot>('auth_update_profile',{name}),
 sessions:()=>invoke<AccountSession[]>('auth_sessions'),
 revokeSession:(id:string)=>invoke<AccountSnapshot>('auth_revoke_session',{id}),
 revokeAll:()=>invoke<AccountSnapshot>('auth_revoke_all'),
}
