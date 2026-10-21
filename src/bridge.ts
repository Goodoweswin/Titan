import {invoke} from '@tauri-apps/api/core'
export async function callEngine<T>(command:string,payload:object={}):Promise<T>{
  const request={command,payload}
  // This adapter only exists in the Vite test harness, never in a release build.
  if(import.meta.env.DEV && new URLSearchParams(location.search).has('integration')){
    const r=await fetch('/test-engine',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)})
    const envelope=await r.json()
    if(!envelope.ok)throw new Error(envelope.error)
    return envelope.data as T
  }
  return await invoke<T>('engine',{request})
}
