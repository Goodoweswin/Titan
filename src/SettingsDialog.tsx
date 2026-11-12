import {useEffect,useRef,type CSSProperties} from 'react'
import {Check,Palette,X} from 'lucide-react'
import {interfaceColors,type InterfaceColor} from './appearance'

interface Props {
 color:InterfaceColor
 onColor:(color:InterfaceColor)=>void
 textSize:string
 onTextSize:(size:string)=>void
 persisted:boolean
 onClose:()=>void
}

export default function SettingsDialog({color,onColor,textSize,onTextSize,persisted,onClose}:Props){
 const dialog=useRef<HTMLDialogElement>(null)
 useEffect(()=>{
  const element=dialog.current
  if(element&&!element.open)element.showModal()
 },[])
 return <dialog ref={dialog} className="settings-dialog" aria-labelledby="settings-title" onClose={onClose}>
  <header className="settings-header">
   <h2 id="settings-title">设置</h2>
   <button autoFocus type="button" className="icon-btn" aria-label="关闭设置" onClick={()=>dialog.current?.close()}><X size={19}/></button>
  </header>
  <section className="settings-body" aria-labelledby="appearance-title">
   <div className="settings-section-title"><Palette size={20} aria-hidden="true"/><div><h3 id="appearance-title">外观</h3><p>选择适合你的工作区配色。</p></div></div>
   <fieldset className="settings-colors"><legend>界面配色</legend>
    {interfaceColors.map(option=><label key={option.id} className="settings-color" style={{'--swatch':option.color} as CSSProperties}>
     <input type="radio" name="interface-color" value={option.id} checked={color===option.id} onChange={()=>onColor(option.id)}/>
     <span className="settings-swatch" aria-hidden="true">{color===option.id&&<Check size={18}/>}</span>
     <span>{option.name}</span>
    </label>)}
   </fieldset>
   <p className="settings-note">用于侧栏、按钮和选中状态。实验图像与导出图表沿用各自配色。</p>
   <div className="settings-row"><div><label htmlFor="settings-text-size">显示字号</label><p>调整界面文字的大小。</p></div><select id="settings-text-size" value={textSize} onChange={e=>onTextSize(e.target.value)}><option value="standard">标准字号</option><option value="large">大字号</option></select></div>
  </section>
  <footer className="settings-footer"><span role="status">{persisted?'配色即时生效，已保存在此设备':'配色已生效，但无法保存；重启后需重新选择'}</span><button type="button" className="btn secondary" onClick={()=>{onColor('neutral');onTextSize('standard')}}>恢复默认</button></footer>
 </dialog>
}
