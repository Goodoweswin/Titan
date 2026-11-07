import {BarChart3,Box,CircleHelp,FolderOpen,ImagePlus,Microscope,Plus,ScanLine,Sparkles} from 'lucide-react'

export type Tool='wb'|'if'|'stats'
export const toolInfo={
 wb:{label:'Western blot',icon:ScanLine,description:'从原始条带图像开始，确认泳道、测量内参和目标蛋白，并制作条带组图。',formats:'TIFF（含多页）、PNG',action:'导入图像',demo:'体验合成示例'},
 if:{label:'免疫荧光',icon:Microscope,description:'导入同一视野的图像，确认通道和样本，测量区域信号或细胞核。',formats:'二维 TIFF、OME-TIFF、分通道图像',action:'导入 IF 视野',demo:'体验 IF 合成示例'},
 stats:{label:'统计与绘图',icon:BarChart3,description:'整理独立样本或配对数据，运行统计检验，制作可编辑的图形。',formats:'Excel、CSV、TSV、粘贴数据',action:'导入 / 粘贴',demo:'体验合成示例'},
} as const

export default function ToolHome({tool,hasCurrent,onImport,onNew,onResume,onDemo,onGuide,onSource,onVolume}:{
 tool:Tool;hasCurrent:boolean;onImport:()=>void;onNew:()=>void;onResume:()=>void;onDemo:()=>void;onGuide:()=>void;onSource:()=>void;onVolume:()=>void;
}){
 const {icon:Icon,label,description,formats,action,demo}=toolInfo[tool]
 return <main className="main-shell project-workspace">
  <header className="project-intro"><Icon size={26}/><div><h1>{label}</h1><p>{description}</p></div></header>
  <div className="tool-entry-actions">
   <button className="btn primary" onClick={onImport}><ImagePlus size={16}/>{action}</button>
   <button className="btn secondary" onClick={onNew}><Plus size={16}/>新建分析</button>
   {tool==='stats'&&<button className="btn secondary" onClick={onSource}><FolderOpen size={16}/>从项目读取结果</button>}
  </div>
  <p className="hint">支持 {formats}。从这里导入会创建独立分析，可稍后移到项目。</p>
  <div className="tool-entry-links">
   {hasCurrent&&<button className="text-btn" onClick={onResume}>{tool==='wb'?'继续当前实验':'继续上次分析'}</button>}
   <button className="text-btn" onClick={onDemo}><Sparkles size={15}/>{demo}</button>
   {tool==='if'&&<button className="text-btn" onClick={onVolume}><Box size={15}/>3D 查看（原型）</button>}
   {tool==='wb'&&<button className="text-btn" onClick={onGuide}><CircleHelp size={15}/>图像操作指引</button>}
  </div>
 </main>
}
