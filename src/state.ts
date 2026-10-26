import type {Project,Rect,AnalysisResult,ROI} from './types'
export function createProject(name:string):Project{
 if(!name.trim())throw new Error('请输入实验名称')
 return {id:crypto.randomUUID(),name:name.trim(),revision:0,schema_version:1,images:[],samples:[],lanes:[],rois:[],settings:{control_group:'control',normalization_mode:'within',ibc_by_membrane:{},analysis_blocks:[],comparisons:[]}}
}
export function editProject(project:Project,mutate:(draft:Project)=>void):Project{
 if(project.read_only)throw new Error('只读项目不能编辑，请另存副本')
 const p=structuredClone(project);mutate(p);p.revision=project.revision+1
 carryReviews(project,p)
 return p
}
export function screenToImage(r:Rect,screenWidth:number,screenHeight:number,width:number,height:number):Rect{
 const [a,b,c,d]=r
 return [Math.round(Math.min(a,c)*width/screenWidth),Math.round(Math.min(b,d)*height/screenHeight),Math.round(Math.max(a,c)*width/screenWidth),Math.round(Math.max(b,d)*height/screenHeight)]
}
export function commitResult(project:Project,result:AnalysisResult):AnalysisResult|null{
 return project.id===result.project_id&&project.revision===result.input_revision?result:null
}
export function mergeSaved(current:Project|null,saved:Project):Project|null{
 if(!current||current.id!==saved.id)return current
 const images=current.images.map(a=>{const disk=saved.images.find(b=>b.id===a.id&&b.sha256===a.sha256);return disk?{...a,path:disk.path}:a})
 return {...current,images,project_path:saved.project_path,saved_revision:saved.saved_revision,read_only:saved.read_only}
}
export function restoreHistory(current:Project,old:Project):Project{
 const p=structuredClone(old);p.revision=current.revision+1;p.project_path=current.project_path;p.saved_revision=current.saved_revision;p.read_only=current.read_only
 carryReviews(current,p);return p
}
export function acceptReview(current:Project|null,input:Project,checked:Project):Project|null{
 return current?.id===input.id&&current.revision===input.revision?checked:null
}
export function mergeImported(current:Project|null,base:Project,incoming:Project):Project|null{
 if(!current||current.id!==base.id)return current
 const added=incoming.images.filter(a=>!base.images.some(b=>a.id===b.id))
 return editProject(current,p=>{for(const a of added)if(!p.images.some(b=>b.id===a.id))p.images.push(a)})
}

// Review covers the pixels, annotation, and sample identity the operator saw.
// Comparison/normalization settings affect calculation, not image approval.
function reviewInput(p:Project,r:ROI):string {
 const {reviewed_revision:_,...annotation}=r
 const image=p.images.find(a=>a.id===r.image_id)
 const lane=p.lanes.find(l=>l.id===r.lane_id)
 const sample=p.samples.find(s=>s.id===lane?.sample_id)
 const ref=p.rois.find(x=>x.id===r.reference_id)
 return JSON.stringify([annotation,image&&[image.id,image.sha256,image.width,image.height,image.dtype,image.polarity,image.ceiling],lane,sample,
  ref&&{...ref,reviewed_revision:undefined},ref&&p.images.find(a=>a.id===ref.image_id)?.sha256])
}
function carryReviews(previous:Project,next:Project){
 for(const roi of next.rois){
  const old=previous.rois.find(r=>r.id===roi.id)
  // The reference itself must also retain its pixel/calibration approval.
  const ref=previous.rois.find(r=>r.id===roi.reference_id),newRef=next.rois.find(r=>r.id===roi.reference_id)
  const referenceUnchanged=!ref||!!newRef&&reviewInput(previous,ref)===reviewInput(next,newRef)
  roi.reviewed_revision=old?.reviewed_revision===previous.revision&&reviewInput(previous,old)===reviewInput(next,roi)&&referenceUnchanged?next.revision:null
 }
}
function calculationInput(p:Project){
 return JSON.stringify({images:p.images.map(({path,preview,...a})=>a),samples:p.samples,lanes:p.lanes,settings:p.settings,
  rois:p.rois.map(r=>({...r,reviewed_revision:r.reviewed_revision===p.revision}))})
}
export function retainResult(previous:Project,next:Project,result:AnalysisResult|null):AnalysisResult|null {
 if(!result||!commitResult(previous,result)||previous.id!==next.id||calculationInput(previous)!==calculationInput(next))return null
 // A name-only edit keeps numerical inputs identical. Rebase provenance to the
 // current saved revision, including the raw annotation copied by the engine.
 return {...result,input_revision:next.revision,measurements:result.measurements.map(m=>({...m,reviewed_revision:next.rois.find(r=>r.id===m.id)?.reviewed_revision}))}
}
