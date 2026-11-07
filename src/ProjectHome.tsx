import {useState} from 'react'
import {BarChart3,ChevronRight,File,FlaskConical,Folder,Package,Plus,Upload} from 'lucide-react'
import type {LibraryArtifact,LibraryCollection,LibraryEntry,LibraryMaterial} from './types'
import type {Tool} from './ToolHome'

const moduleLabel=(module:LibraryEntry['module'])=>module==='if'?'IF':module==='stats'?'统计':'WB'
const fileSize=(bytes:number)=>bytes<1024?bytes+' B':bytes<1024**2?(bytes/1024).toFixed(1)+' KB':(bytes/1024**2).toFixed(1)+' MB'

export default function ProjectHome({project,entries,onNew,onAdd,onRemove,onUse,onOpen,onLocate,onArtifact,onExport}:{
 project:LibraryCollection;entries:LibraryEntry[];onNew:()=>void;onAdd:()=>void;
 onRemove:(material:LibraryMaterial)=>void;onUse:(materials:LibraryMaterial[],tool:Tool)=>void;
 onOpen:(entry:LibraryEntry)=>void;onLocate:(entry:LibraryEntry)=>void;onArtifact:(entry:LibraryEntry,artifact:LibraryArtifact)=>void;onExport:()=>void;
}){
 const materials=project.materials??[]
 const [checked,setChecked]=useState<string[]>([])
 const [tool,setTool]=useState<Tool>('wb')
 const selection=materials.filter(file=>checked.includes(file.id))
 const outputs=entries.flatMap(entry=>[
  ...entry.figures.filter(figure=>!entry.artifacts?.some(artifact=>artifact.kind==='result_export'&&artifact.document_id===figure.id))
   .map(figure=>({entry,artifact:{id:figure.id,entry_id:entry.entry_id,title:figure.name,kind:'wb_plot' as const,source_revision:figure.source_revision,
    document_id:figure.id,version_id:figure.selected_version,available:entry.available}})),
  ...(entry.artifacts??[]).map(artifact=>({entry,artifact})),
 ])
 return <main className="main-shell project-workspace" aria-label="项目主页">
  <header className="project-intro"><Folder size={24}/><div><h1>{project.name}</h1><p>{materials.length} 份资料 · {entries.length} 个分析 · {outputs.length} 项图表与导出</p></div>
   <button className="btn secondary" onClick={onExport}><Package size={16}/>导出项目包</button>
  </header>
  <section className="project-section" aria-labelledby="project-materials-title">
   <div className="project-section-header"><h2 id="project-materials-title">资料</h2><button className="btn secondary" onClick={onAdd}><Upload size={15}/>添加资料</button></div>
   <p className="hint">Titan 会在项目中保存原文件的副本。可选取资料开始新的分析。</p>
   {materials.length===0?<p className="project-empty">这个项目还没有资料。</p>:
    <ul className="project-list">{materials.map(file=><li key={file.id} className="project-list-row">
     <label className="project-file-label"><input type="checkbox" aria-label={`选择资料 ${file.name}`} checked={checked.includes(file.id)}
      onChange={event=>setChecked(previous=>event.target.checked?[...previous,file.id]:previous.filter(id=>id!==file.id))}/><File size={15}/><span>{file.name}</span></label>
     <small>{fileSize(file.size)}</small><button className="text-btn" aria-label={`移除资料 ${file.name}`} onClick={()=>onRemove(file)}>移除</button>
    </li>)}</ul>}
   {selection.length>0&&<div className="project-material-actions">
    <label>分析工具<select value={tool} onChange={event=>setTool(event.target.value as Tool)}>
     <option value="wb">Western blot</option><option value="if">免疫荧光</option><option value="stats">统计与绘图</option>
    </select></label>
    <button className="btn primary" disabled={tool==='stats'&&selection.length!==1} onClick={()=>onUse(selection,tool)}>用所选资料新建分析</button>
    {tool==='stats'&&selection.length!==1&&<span className="hint">每次选择一个表格。</span>}
   </div>}
  </section>
  <section className="project-section" aria-labelledby="project-analyses-title">
   <div className="project-section-header"><h2 id="project-analyses-title">分析</h2><button className="btn primary" onClick={onNew}><Plus size={16}/>新建分析</button></div>
   {entries.length===0?<p className="project-empty">这个项目还没有分析。</p>:<ul className="project-list">{entries.map(entry=><li key={entry.entry_id}>
    <button className="project-list-row project-open-row" aria-label={`打开分析 ${entry.name}`} onClick={()=>entry.available?onOpen(entry):onLocate(entry)}>
     <FlaskConical size={16}/><span>{entry.name}</span><small>{moduleLabel(entry.module)}{!entry.available&&' · 需定位'}</small><ChevronRight size={15}/>
    </button>
   </li>)}</ul>}
  </section>
  <section className="project-section" aria-labelledby="project-outputs-title">
   <div className="project-section-header"><h2 id="project-outputs-title">图表与导出</h2></div>
   {outputs.length===0?<p className="project-empty">分析中保存的图表和导出会显示在这里。</p>:<ul className="project-list">{outputs.map(({entry,artifact})=><li key={entry.entry_id+':'+artifact.id}>
    <button className="project-list-row project-open-row" disabled={!artifact.available&&!artifact.document_id} onClick={()=>onArtifact(entry,artifact)}>
     <BarChart3 size={16}/><span>{artifact.title}<small>{entry.name}</small></span>
     <small>{artifact.source_revision===null?'图形':`版本 ${artifact.source_revision}`}{!artifact.available&&!artifact.document_id&&' · 文件缺失'}</small><ChevronRight size={15}/>
    </button>
   </li>)}</ul>}
  </section>
 </main>
}
