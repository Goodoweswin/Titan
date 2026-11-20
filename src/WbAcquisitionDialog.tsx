import {useEffect,useId,useRef,useState} from 'react'
import type {ImageAsset} from './types'

type Props={
 asset:ImageAsset
 readOnly:boolean
 onApply:(polarity:ImageAsset['polarity'],ceiling:number|null)=>void
 onClose:()=>void
}

export default function WbAcquisitionDialog({asset,readOnly,onApply,onClose}:Props){
 const title=useId()
 const dialog=useRef<HTMLDialogElement>(null)
 const [polarity,setPolarity]=useState(asset.polarity)
 const [ceiling,setCeiling]=useState(String(asset.ceiling??''))
 const ceilingValue=ceiling===''?null:Number(ceiling)
 const validCeiling=ceilingValue===null||(Number.isFinite(ceilingValue)&&ceilingValue>0)
 const canApply=!readOnly&&validCeiling&&(polarity!==asset.polarity||ceilingValue!==asset.ceiling)
 useEffect(()=>{if(dialog.current&&!dialog.current.open)dialog.current.showModal()},[])
 return <dialog ref={dialog} className="export-dialog wb-acquisition-dialog" aria-labelledby={title} onClose={onClose}>
  <h2 id={title}>采集信息</h2>
  <p className="hint">{asset.name}{asset.page_count&&asset.page_count>1?` · 第 ${(asset.page_index??0)+1} 页`:''}</p>
  <form onSubmit={event=>{
   event.preventDefault()
   if(!canApply)return
   onApply(polarity,ceilingValue)
   dialog.current?.close()
  }}>
   <fieldset disabled={readOnly}>
    <label>原始信号方向<select value={polarity} onChange={event=>setPolarity(event.target.value as ImageAsset['polarity'])}>
     <option value="bright">数值越大，信号越强</option>
     <option value="dark">数值越小，信号越强</option>
    </select></label>
    <label>有效编码上界<input type="number" min={0} step="any" value={ceiling} onChange={event=>setCeiling(event.target.value)} placeholder="按采集记录填写"/></label>
   </fieldset>
   <p className="hint">{validCeiling?'这两项参与定量。暗信号需要有效编码上界。':'有效编码上界需大于零。'}</p>
   <div className="export-actions">
    <button type="button" className="btn secondary" onClick={()=>dialog.current?.close()}>关闭</button>
    {!readOnly&&<button type="submit" className="btn primary" disabled={!canApply}>应用</button>}
   </div>
  </form>
 </dialog>
}
