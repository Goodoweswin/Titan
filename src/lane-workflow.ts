import type {Project,Rect,LaneProposal} from './types'
import {newLane} from './workflow'

export function acceptLaneLayout(p:Project,proposal:LaneProposal,mapping:Record<string,string|null>,membraneId='M1'):string {
 if(p.read_only)throw new Error('只读项目不能编辑')
 if(proposal.project_id!==p.id||proposal.input_revision!==p.revision)throw new Error('输入已变化，请重新识别泳道')
 const image=p.images.find(a=>a.id===proposal.image_id);if(!image)throw new Error('原图不存在')
 const chosen=proposal.columns.filter(c=>Object.hasOwn(mapping,c.proposal_id)).sort((a,b)=>a.rect[0]-b.rect[0])
 if(!chosen.length)throw new Error('请保留至少一个泳道')
 const ids=chosen.map(c=>mapping[c.proposal_id]).filter((id):id is string=>!!id)
 if(new Set(ids).size!==ids.length||ids.some(id=>!p.lanes.some(l=>l.id===id&&l.membrane_id===membraneId)))throw new Error('泳道或膜对应不正确')
 chosen.forEach((c,i)=>{
  const [x0,y0,x1,y1]=c.rect
  if(!c.rect.every(Number.isInteger)||x0<0||y0<0||x1>image.width||y1>image.height||x1<=x0||y1<=y0||(i>0&&x0<chosen[i-1].rect[2]))throw new Error('泳道越界或重叠，请调整边界')
 })
 const columns=chosen.map(c=>({lane_id:mapping[c.proposal_id]??newLane(p,membraneId).id,rect:[...c.rect] as Rect}))
 const id=crypto.randomUUID();p.lane_layouts.push({id,image_id:image.id,membrane_id:membraneId,window:proposal.window,columns,excluded_regions:[],source_layout_id:null,confirmed_revision:p.revision+1})
 return id
}

function writable(p:Project){if(p.read_only)throw new Error('只读项目不能编辑')}
function layoutOf(p:Project,id:string){const l=p.lane_layouts.find(l=>l.id===id);if(!l)throw new Error('泳道布局不存在');return l}
function validRect(rect:Rect,width:number,height:number){return rect.every(Number.isInteger)&&rect[0]>=0&&rect[1]>=0&&rect[2]<=width&&rect[3]<=height&&rect[0]<rect[2]&&rect[1]<rect[3]}
function overlap(a:Rect,b:Rect){return Math.max(a[0],b[0])<Math.min(a[2],b[2])&&Math.max(a[1],b[1])<Math.min(a[3],b[3])}

export function applyPreparedDraft(p:Project,draft:Project,baseRevision:number){
 writable(p);if(p.id!==draft.id||p.revision!==baseRevision)throw new Error('输入已变化，请重新识别')
 const persistence={project_path:p.project_path,saved_revision:p.saved_revision,read_only:p.read_only,upgrade_from:p.upgrade_from}
 const images=draft.images.map(a=>{const saved=p.images.find(b=>b.id===a.id&&b.sha256===a.sha256);return saved?{...a,path:saved.path}:a})
 Object.assign(p,draft,persistence,{images})
}

export function createBandSet(p:Project,layoutId:string,analyte:string,role:'target'|'reference',referenceSetId?:string):string {
 writable(p);const layout=layoutOf(p,layoutId)
 if(!analyte.trim())throw new Error('请填写蛋白名称')
 if(p.band_sets.some(g=>g.analyte===analyte.trim()&&g.role===role&&layoutOf(p,g.layout_id).columns.some(c=>layout.columns.some(other=>other.lane_id===c.lane_id))))throw new Error('该泳道已有此蛋白，请从列表选择后重新识别')
 if(referenceSetId){const ref=p.band_sets.find(g=>g.id===referenceSetId);if(role!=='target'||!ref||ref.role!=='reference'||layoutOf(p,ref.layout_id).membrane_id!==layout.membrane_id)throw new Error('目标与内参必须属于同一张膜')}
 const id=crypto.randomUUID()
 p.band_sets.push({id,layout_id:layoutId,analyte:analyte.trim(),role,window:[...layout.window],reference_set_id:null,assignments:layout.columns.map(c=>({lane_id:c.lane_id,roi_id:null,status:'pending'}))})
 if(referenceSetId)linkReferenceSet(p,id,referenceSetId)
 return id
}

export function copyLaneLayout(p:Project,sourceId:string,imageId:string):string {
 writable(p);const source=layoutOf(p,sourceId),from=p.images.find(a=>a.id===source.image_id)!,to=p.images.find(a=>a.id===imageId)
 if(!to)throw new Error('请选择目标图像')
 const id=crypto.randomUUID(),scale=to.width/from.width
 p.lane_layouts.push({...structuredClone(source),id,image_id:imageId,window:[0,0,to.width,to.height],columns:source.columns.map(c=>({lane_id:c.lane_id,rect:[Math.round(c.rect[0]*scale),0,Math.round(c.rect[2]*scale),to.height]})),excluded_regions:[],source_layout_id:sourceId,confirmed_revision:null})
 return id
}

function updateColumns(p:Project,layoutId:string,columns:Project['lane_layouts'][number]['columns']) {
 const layout=layoutOf(p,layoutId),asset=p.images.find(a=>a.id===layout.image_id)!
 const sorted=[...columns].sort((a,b)=>a.rect[0]-b.rect[0])
 if(sorted.some((c,i)=>!validRect(c.rect,asset.width,asset.height)||(i>0&&c.rect[0]<sorted[i-1].rect[2])))throw new Error('泳道越界或重叠，请缩小调整幅度')
 layout.columns=columns;layout.confirmed_revision=null
 const sets=p.band_sets.filter(g=>g.layout_id===layoutId);const removed=new Set(sets.flatMap(g=>g.assignments.map(a=>a.roi_id)))
 p.rois=p.rois.filter(r=>!removed.has(r.id));for(const r of p.rois)if(removed.has(r.reference_id)){r.reference_id=null;r.reviewed_revision=null}
 sets.forEach(g=>g.assignments=g.assignments.map(a=>({...a,roi_id:null,status:'pending'})))
}

export function alignLaneLayout(p:Project,layoutId:string,{dx,dy,scaleX,anchorX}:{dx:number;dy:number;scaleX:number;anchorX:number}) {
 writable(p);if(![dx,dy,scaleX,anchorX].every(Number.isFinite)||scaleX<=0)throw new Error('对齐参数无效')
 const layout=layoutOf(p,layoutId)
 updateColumns(p,layoutId,layout.columns.map(c=>({lane_id:c.lane_id,rect:[Math.round(anchorX+(c.rect[0]-anchorX)*scaleX+dx),Math.round(c.rect[1]+dy),Math.round(anchorX+(c.rect[2]-anchorX)*scaleX+dx),Math.round(c.rect[3]+dy)]})))
}

export function setLaneRect(p:Project,layoutId:string,laneId:string,rect:Rect){writable(p);updateColumns(p,layoutId,layoutOf(p,layoutId).columns.map(c=>c.lane_id===laneId?{...c,rect}:c))}

export interface BandChoice{lane_id:string;rect?:Rect;backgrounds?:Rect[];status?:'not_detected'|'excluded'}
export function acceptBandAssignments(p:Project,setId:string,choices:BandChoice[]) {
 writable(p);const group=p.band_sets.find(g=>g.id===setId);if(!group)throw new Error('蛋白集合不存在')
 const layout=layoutOf(p,group.layout_id),asset=p.images.find(a=>a.id===layout.image_id)!
 const ids=choices.map(c=>c.lane_id)
 if(new Set(ids).size!==ids.length||ids.length!==layout.columns.length||layout.columns.some(c=>!ids.includes(c.lane_id)))throw new Error('请确认每个泳道的测量或缺失状态')
 for(const c of choices){
  if(c.status)continue
  if(p.rois.some(r=>r.band_set_id!==group.id&&r.lane_id===c.lane_id&&r.analyte===group.analyte&&r.role===group.role))throw new Error('该泳道已有此蛋白的正式测量，请检查名称')
  const column=layout.columns.find(l=>l.lane_id===c.lane_id)!
  if(!c.rect||!validRect(c.rect,asset.width,asset.height)||c.rect[0]<column.rect[0]||c.rect[2]>column.rect[2])throw new Error('峰区必须位于对应泳道内')
  if(!c.backgrounds?.length||c.backgrounds.some(b=>!validRect(b,asset.width,asset.height)||overlap(b,c.rect!)))throw new Error('请为每个峰确认不重叠的局部背景')
 }
 const previouslyApproved=new Set(p.rois.filter(r=>r.role==='target'&&r.reviewed_revision===p.revision).map(r=>r.id))
 const removed=new Set(group.assignments.map(a=>a.roi_id));p.rois=p.rois.filter(r=>!removed.has(r.id))
 for(const r of p.rois)if(removed.has(r.reference_id))r.reference_id=null
 group.assignments=choices.map(c=>{
  if(c.status)return {lane_id:c.lane_id,roi_id:null,status:c.status}
  const id=crypto.randomUUID();p.rois.push({id,image_id:asset.id,lane_id:c.lane_id,analyte:group.analyte,role:group.role,rect:c.rect!,backgrounds:c.backgrounds!,reference_id:null,reviewed_revision:p.revision+1,lane_layout_id:layout.id,band_set_id:group.id})
  return {lane_id:c.lane_id,roi_id:id,status:'accepted'}
 });layout.confirmed_revision=p.revision+1
 if(group.reference_set_id)linkReferenceSet(p,group.id,group.reference_set_id)
 if(group.role==='reference')for(const target of p.band_sets.filter(g=>g.reference_set_id===group.id)){
  linkReferenceSet(p,target.id,group.id)
  for(const a of target.assignments){const roi=p.rois.find(r=>r.id===a.roi_id);if(roi&&previouslyApproved.has(roi.id))roi.reviewed_revision=p.revision+1}
 }
}

export function linkReferenceSet(p:Project,targetId:string,referenceId:string) {
 writable(p);const target=p.band_sets.find(g=>g.id===targetId),ref=p.band_sets.find(g=>g.id===referenceId)
 if(!target||!ref||target.role!=='target'||ref.role!=='reference'||layoutOf(p,target.layout_id).membrane_id!==layoutOf(p,ref.layout_id).membrane_id)throw new Error('目标与内参必须属于同一张膜')
 target.reference_set_id=ref.id
 for(const a of target.assignments){const roi=p.rois.find(r=>r.id===a.roi_id);if(roi)roi.reference_id=ref.assignments.find(r=>r.lane_id===a.lane_id&&r.status==='accepted')?.roi_id??null}
}
