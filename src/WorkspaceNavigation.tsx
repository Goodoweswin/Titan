import {ArrowLeft,ArrowRight,PanelLeftClose,PanelLeftOpen,PanelRightClose,PanelRightOpen} from 'lucide-react'

interface Props {
 title:string
 blocked:boolean
 canBack:boolean
 canForward:boolean
 leftCollapsed:boolean
 rightCollapsed:boolean
 hasInspector:boolean
 onBack:()=>void
 onForward:()=>void
 onToggleLeft:()=>void
 onToggleRight:()=>void
}
export default function WorkspaceNavigation(props:Props){
 const LeftIcon=props.leftCollapsed?PanelLeftOpen:PanelLeftClose
 const rightOpen=props.hasInspector&&!props.rightCollapsed
 const RightIcon=rightOpen?PanelRightClose:PanelRightOpen
 return <nav className="workspace-browsing" aria-label="浏览导航">
  <button className="icon-btn" aria-label="后退" title="后退 · Alt+← / ⌘[" disabled={props.blocked||!props.canBack} onClick={props.onBack}><ArrowLeft size={16}/></button>
  <button className="icon-btn" aria-label="前进" title="前进 · Alt+→ / ⌘]" disabled={props.blocked||!props.canForward} onClick={props.onForward}><ArrowRight size={16}/></button>
  <span className="browsing-divider"/>
  <button className="icon-btn" aria-label={props.leftCollapsed?'展开左栏':'收起左栏'} title={props.leftCollapsed?'展开左栏':'收起左栏'} aria-expanded={!props.leftCollapsed} aria-controls="titan-sidebar" onClick={props.onToggleLeft}><LeftIcon size={16}/></button>
  <span className="browsing-title" title={props.title}>{props.title}</span>
  <button className="icon-btn" aria-label={rightOpen?'收起右栏':'展开右栏'} title={props.hasInspector?(rightOpen?'收起右侧设置':'展开右侧设置'):'当前页面没有右侧设置'} aria-expanded={rightOpen} disabled={!props.hasInspector} onClick={props.onToggleRight}><RightIcon size={16}/></button>
 </nav>
}
