import type {Project,Rect,AnalysisResult,ROI} from './types'
export function createProject(name:string):Project{
 if(!name.trim())throw new Error('请输入实验名称')
 return {id:crypto.randomUUID(),name:name.trim(),revision:0,schema_version:2,lane_layouts:[],band_sets:[],images:[],samples:[],lanes:[],rois:[],settings:{control_group:'control',normalization_mode:'within',ibc_by_membrane:{},analysis_blocks:[],comparisons:[]}}
}
export function editProject(project:Project,mutate:(draft:Project)=>void):Project{
 if(project.read_only)throw new Error('只读项目不能编辑，请另存副本')
 const p=structuredClone(project);mutate(p);reconcileLinkedMeasurements(p);p.revision=project.revision+1
 carryReviews(project,p)
 return p
}
function reconcileLinkedMeasurements(p:Project){
 const rois=new Map(p.rois.map(r=>[r.id,r]))
 for(const g of p.band_sets)for(const a of g.assignments){
  if(a.roi_id&&!rois.has(a.roi_id)){a.roi_id=null;a.status='pending'}
 }
 for(const r of p.rois)if(r.reference_id&&!rois.has(r.reference_id))r.reference_id=null
 for(const g of p.band_sets){
  const layout=p.lane_layouts.find(l=>l.id===g.layout_id)
  if(!layout)throw new Error('测量集合缺少泳道布局')
  for(const a of g.assignments){
   if(a.status!=='accepted')continue
   const r=rois.get(a.roi_id!)
   if(!r||r.band_set_id!==g.id||r.lane_layout_id!==layout.id||r.image_id!==layout.image_id||r.lane_id!==a.lane_id||r.role!==g.role||r.analyte!==g.analyte)throw new Error('请在内参或目标步骤修改蛋白集合身份')
   if(g.role==='target'){
    const ref=p.band_sets.find(s=>s.id===g.reference_set_id)
    const expected=ref?.assignments.find(s=>s.lane_id===a.lane_id&&s.status==='accepted')?.roi_id??null
    if(r.reference_id!==expected)throw new Error('请在目标步骤选择对应内参集合')
   }
  }
 }
 for(const r of p.rois)if(r.band_set_id&&!p.band_sets.some(g=>g.id===r.band_set_id&&g.assignments.some(a=>a.roi_id===r.id&&a.status==='accepted')))throw new Error('条带未归入所属测量集合')
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
 const layout=p.lane_layouts.find(l=>l.id===r.lane_layout_id)
 const sampleIdentity=sample?{...sample,name:undefined}:undefined
 return JSON.stringify([annotation,layout&&[layout.image_id,layout.window,layout.columns.find(c=>c.lane_id===r.lane_id)],image&&[image.id,image.sha256,image.page_index??0,image.width,image.height,image.dtype,image.polarity,image.ceiling],lane,sampleIdentity,
  ref&&{...ref,reviewed_revision:undefined},ref&&p.images.find(a=>a.id===ref.image_id)?.sha256])
}
function carryReviews(previous:Project,next:Project){
 for(const layout of next.lane_layouts){
  const old=previous.lane_layouts.find(l=>l.id===layout.id)
  if(layout.confirmed_revision===next.revision)continue
  if(old){const {confirmed_revision:_,...a}=old,{confirmed_revision:__,...b}=layout;layout.confirmed_revision=old.confirmed_revision===previous.revision&&JSON.stringify(a)===JSON.stringify(b)?next.revision:null}
 }
 for(const roi of next.rois){
  const old=previous.rois.find(r=>r.id===roi.id)
  if(roi.band_set_id&&roi.reviewed_revision===next.revision)continue
  // The reference itself must also retain its pixel/calibration approval.
  const ref=previous.rois.find(r=>r.id===roi.reference_id),newRef=next.rois.find(r=>r.id===roi.reference_id)
  const referenceUnchanged=!ref||!!newRef&&reviewInput(previous,ref)===reviewInput(next,newRef)
  roi.reviewed_revision=old?.reviewed_revision===previous.revision&&reviewInput(previous,old)===reviewInput(next,roi)&&referenceUnchanged?next.revision:null
 }
}
function calculationInput(p:Project){
 return JSON.stringify({lane_layouts:p.lane_layouts.map(l=>({...l,confirmed_revision:l.confirmed_revision===p.revision})),band_sets:p.band_sets,images:p.images.map(({path,preview,display_inverted,...a})=>a),samples:p.samples,lanes:p.lanes,settings:p.settings,
  rois:p.rois.map(r=>({...r,reviewed_revision:r.reviewed_revision===p.revision}))})
}
export function retainResult(previous:Project,next:Project,result:AnalysisResult|null):AnalysisResult|null {
 if(!result||!commitResult(previous,result)||previous.id!==next.id||calculationInput(previous)!==calculationInput(next))return null
 // A name-only edit keeps numerical inputs identical. Rebase provenance to the
 // current saved revision, including the raw annotation copied by the engine.
 return {...result,input_revision:next.revision,measurements:result.measurements.map(m=>({...m,reviewed_revision:next.rois.find(r=>r.id===m.id)?.reviewed_revision}))}
}
