import {useEffect,useRef,useState} from 'react'
import {callEngine} from './bridge'
import type {ImageAsset} from './types'
import './wb-image-display.css'

type Tuning={brightness:number;contrast:number}
const defaults:Tuning={brightness:0,contrast:0}

export function useWbImageDisplay(asset:ImageAsset|undefined){
 const [tuning,setTuning]=useState<Record<string,Tuning>>({})
 const [rendered,setRendered]=useState<{key:string;png:string}|null>(null)
 const [failed,setFailed]=useState(false)
 const pending=useRef(Promise.resolve())
 const imageId=asset?.id??''
 const settings=tuning[imageId]??defaults
 const key=JSON.stringify(asset&&[asset.id,asset.path,asset.sha256,asset.page_index,asset.rotation_degrees,asset.display_inverted])
 const adjusted=!!(settings.brightness||settings.contrast)
 useEffect(()=>{
  setFailed(false)
  if(!asset||!adjusted){setRendered(null);return}
  let live=true
  const {path,sha256,page_index,rotation_degrees,display_inverted}=asset
  const timer=setTimeout(()=>{
   pending.current=pending.current.then(async()=>{
    if(!live)return
    try{
     const png=await callEngine<string>('wb_display_preview',{
      asset:{path,sha256,page_index,rotation_degrees,display_inverted},...settings,
     })
     if(live)setRendered({key,png})
    }catch{
     if(live)setFailed(true)
    }
   })
  },100)
  return()=>{live=false;clearTimeout(timer)}
 },[key,settings,adjusted])
 return {
  src:adjusted&&rendered?.key===key?rendered?.png:asset?.preview,
  settings,adjusted,failed,
  adjust:(next:Tuning)=>setTuning(current=>({...current,[imageId]:next})),
 }
}

export default function WbImageDisplay({display}:{display:ReturnType<typeof useWbImageDisplay>}){
 return <section className="wb-display-panel" aria-label="图像调节">
  <h3>图像调节</h3>
   {(['brightness','contrast'] as const).map(key=><label key={key}>
    <span>{key==='brightness'?'亮度':'对比度'} <output>{display.settings[key]}</output></span>
    <input type="range" aria-label={key==='brightness'?'亮度':'对比度'} min={-100} max={100}
     value={display.settings[key]} onChange={event=>display.adjust({...display.settings,[key]:Number(event.target.value)})}/>
   </label>)}
   <button type="button" className="text-btn" disabled={!display.adjusted} onClick={()=>display.adjust(defaults)}>重置显示</button>
   <p className="hint">仅调整预览，定量使用原始像素。</p>
   {display.failed&&<p className="hint" role="status">显示预览未更新，请重新调节或重置。</p>}
 </section>
}
