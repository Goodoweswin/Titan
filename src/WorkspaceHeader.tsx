import type {ReactNode} from 'react'
import type {Project} from './types'

interface Props {
 project:Project|null
 dirty:boolean
 switching:boolean
 textSize:string
 onTextSize:(size:string)=>void
 onName:(name:string)=>void
 children:ReactNode
}

export default function WorkspaceHeader({project,dirty,switching,textSize,onTextSize,onName,children}:Props){
 return <header className="app-header">
  <div className="workspace-title">
   {project?<><input aria-label="实验名称" className="project-name" readOnly={project.read_only||switching} value={project.name} title={project.name} onChange={e=>onName(e.target.value)}/><span className="workspace-save-state">{project.read_only?'只读':dirty?'有未保存修改':'已保存'}</span></>:<span className="workspace-home-title">实验工作区</span>}
  </div>
  <div className="header-actions"><select className="text-size" aria-label="显示字号" value={textSize} onChange={e=>onTextSize(e.target.value)}><option value="standard">标准字号</option><option value="large">大字号</option></select>{children}</div>
 </header>
}
