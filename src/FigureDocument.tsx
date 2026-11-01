import PublicationFigure from './PublicationFigure'
import type {ArchiveFigureRequest,LiveFigurePreview} from './PublicationFigure'
import type {FigureDocumentMetadata,FrozenFigure} from './types'
export default function FigureDocument({figure,onArchive,onPreview,onUpdate,onWorkspace,onVersion,canUpdate}:{figure:FrozenFigure;onArchive:(r:ArchiveFigureRequest)=>Promise<FigureDocumentMetadata|undefined>;onPreview:(v:LiveFigurePreview|null)=>void;onUpdate:()=>void;onWorkspace:()=>void;onVersion:(version:string)=>void;canUpdate:boolean}){
 return <div className="figure-document"><div className="section-title"><div><h2>{figure.document.name}</h2><p>源分析版本 {figure.document.source_revision} · {figure.document.source_stale?'当前实验已变化，这张图保留原数据。':'已保存的图形文档。'}</p></div><button className="btn secondary" onClick={onWorkspace}>返回分析工作台</button></div>
 <div className="figure-document-actions"><label>历史版本<select aria-label="图形历史版本" value={figure.document.selected_version} onChange={e=>onVersion(e.target.value)}>{figure.document.versions.map((v,i)=><option key={v.version_id} value={v.version_id}>图形版本 {i+1} · 源分析 {v.source_revision}</option>)}</select></label>{figure.document.source_stale&&<button className="btn secondary" disabled={figure.project.read_only||!canUpdate} onClick={onUpdate}>用当前分析更新源数据</button>}</div>
 <PublicationFigure key={figure.document.id+':'+figure.document.selected_version} project={figure.project} result={figure.result} document={figure.document} onArchive={onArchive} onPreview={onPreview} frozen/>
 </div>
}
