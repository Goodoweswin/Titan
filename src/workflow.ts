import type {AnalysisResult,Project,Rect,ROI} from './types'
export type BatchAction={type:'move';dx:number;dy:number}|{type:'size';width:number;height:number}|{type:'background'}|{type:'copy'}
const overlaps=(a:Rect,b:Rect)=>Math.max(a[0],b[0])<Math.min(a[2],b[2])&&Math.max(a[1],b[1])<Math.min(a[3],b[3])
function writable(p:Project){if(p.read_only)throw new Error('只读项目不能编辑，请另存副本')}
function bounds(r:Rect,width:number,height:number){return r.every(Number.isInteger)&&r[0]>=0&&r[1]>=0&&r[2]<=width&&r[3]<=height&&r[0]<r[2]&&r[1]<r[3]}
export function newLane(p:Project,membrane='M1'){
 let n=1;while(p.lanes.some(l=>l.id===`L${n}`)||p.samples.some(s=>s.id===`S${n}`||s.bio_id===`B${n}`))n++
 const lane={id:`L${n}`,sample_id:`S${n}`,membrane_id:membrane,technical_id:'1'}
 p.samples.push({id:lane.sample_id,bio_id:`B${n}`,group:p.settings.control_group,pair_id:'',kind:'biological',pool_id:''});p.lanes.push(lane)
 return lane
}
export function batchROIs(p:Project,ids:string[],action:BatchAction){
 writable(p)
 const draft=structuredClone(p),selected=draft.rois.filter(r=>ids.includes(r.id))
 if(!selected.length)throw new Error('请先选择条带')
 for(const r of selected){
  const image=draft.images.find(a=>a.id===r.image_id)!
  if(action.type==='copy'){
   const lane=newLane(draft,draft.lanes.find(l=>l.id===r.lane_id)?.membrane_id)
   draft.rois.push({...structuredClone(r),id:crypto.randomUUID(),lane_id:lane.id,reference_id:null,reviewed_revision:null})
   continue
  }
  if(action.type==='move'){
   const shift=(rect:Rect)=>rect.map((v,i)=>v+(i%2?action.dy:action.dx)) as Rect
   r.rect=shift(r.rect);r.backgrounds=r.backgrounds.map(shift)
  }
  if(action.type==='size'){
   r.rect=[r.rect[0],r.rect[1],r.rect[0]+action.width,r.rect[1]+action.height];r.backgrounds=[]
  }
  if(action.type==='background'){
   const [x0,y0,x1,y1]=r.rect,h=Math.max(2,Math.round((y1-y0)/3))
   r.backgrounds=([[x0,y0-h-3,x1,y0-3],[x0,y1+3,x1,y1+h+3]] as Rect[]).filter(b=>bounds(b,image.width,image.height)&&!draft.rois.some(other=>other.image_id===r.image_id&&overlaps(b,other.rect)))
  }
  if(!bounds(r.rect,image.width,image.height)||r.backgrounds.some(b=>!bounds(b,image.width,image.height)))throw new Error(`${r.lane_id}：区域超出图像或尺寸不是正整数；未应用本次操作`)
 }
 p.rois=draft.rois;p.samples=draft.samples;p.lanes=draft.lanes
}
export function matchReferences(p:Project){
 writable(p);let matched=0,ambiguous=0
 for(const r of p.rois.filter(r=>r.role==='target'&&!r.reference_id)){
  const refs=p.rois.filter(ref=>ref.role==='reference'&&ref.lane_id===r.lane_id)
  if(refs.length===1){r.reference_id=refs[0].id;matched++}else ambiguous++
 }
 return {matched,ambiguous}
}
export function pasteSamples(p:Project,text:string){
 writable(p)
 const lines=text.replace(/^\uFEFF/,'').split(/\r?\n/).filter(l=>l.trim())
 if(/^(泳道|lane_id)\t/.test(lines[0]??''))lines.shift()
 if(!lines.length)throw new Error('请粘贴样本数据')
 const draft=structuredClone(p),seen=new Set<string>(),samples=new Map<string,string>()
 for(const [i,line] of lines.entries()){
  const columns=line.split('\t').map(c=>c.trim())
  if(columns.length!==6)throw new Error(`第 ${i+1} 行应包含 6 列（用制表符分隔）`)
  const [id,sid,bio_id,group,pair_id,membrane_id]=columns
  const lane=draft.lanes.find(l=>l.id===id)
  if(!lane||seen.has(id))throw new Error(`泳道 ${id} 不存在或重复`)
  if(!sid||!bio_id||!group||!membrane_id)throw new Error(`第 ${i+1} 行缺少必填标识或组别`)
  const identity=JSON.stringify([bio_id,group,pair_id])
  if(samples.has(sid)&&samples.get(sid)!==identity)throw new Error(`样本 ${sid} 的生物学编号、组别或配对信息冲突`)
  samples.set(sid,identity);seen.add(id)
  let sample=draft.samples.find(s=>s.id===sid)
  if(!sample){sample={id:sid,bio_id,group,pair_id,kind:'biological',pool_id:''};draft.samples.push(sample)}
  Object.assign(sample,{bio_id,group,pair_id});Object.assign(lane,{sample_id:sid,membrane_id})
 }
 p.samples=draft.samples;p.lanes=draft.lanes
 return seen.size
}
export const flagLabels:Record<string,string>={missing_background:'缺少背景',missing_reference:'缺少参考',reference_lane_mismatch:'参考泳道不匹配',review_required:'待复核',signal_clipped:'像素端点饱和',background_clipped:'背景像素饱和',nonpositive_signal:'净信号非正',linearity_not_validated:'线性范围未验证',clipping_unknown:'编码范围未知',missing_control:'缺少对照组',nonpositive_ratio_input:'归一化输入非正'}
export function flagLabel(flag:string):string{
 if(flag.startsWith('reference:'))return '参考：'+flagLabel(flag.slice(10))
 if(flag.startsWith('ibc:'))return '跨膜参考：'+flagLabel(flag.slice(4))
 if(flag.startsWith('measurement_error:'))return '测量失败：'+flag.slice(18)
 return flagLabels[flag]??flag
}
export function flagSource(p:Project,roiId:string,flag:string):{roiId:string;code:string}{
 const roi=p.rois.find(r=>r.id===roiId)
 if(flag.startsWith('reference:')&&roi?.reference_id)return flagSource(p,roi.reference_id,flag.slice(10))
 if(flag.startsWith('ibc:')&&roi){
  const lane=p.lanes.find(l=>l.id===roi.lane_id),ref=lane&&p.settings.ibc_by_membrane[lane.membrane_id]?.[roi.analyte]
  if(ref)return flagSource(p,ref,flag.slice(4))
 }
 return {roiId,code:flag}
}
export interface QualityIssue{roiId:string;code:string;label:string;severity:'warning'|'info'}
export function projectIssues(p:Project,result:AnalysisResult|null):QualityIssue[]{
 const issues:QualityIssue[]=[]
 function add(roiId:string,code:string){if(!issues.some(i=>i.roiId===roiId&&i.code===code))issues.push({roiId,code,label:flagLabel(code),severity:['linearity_not_validated','clipping_unknown'].includes(code)?'info':'warning'})}
 for(const r of p.rois){
  if(!r.backgrounds.length)add(r.id,'missing_background')
  if(r.role==='target'){
   const ref=p.rois.find(x=>x.id===r.reference_id&&x.role==='reference')
   if(!ref)add(r.id,'missing_reference');else if(ref.lane_id!==r.lane_id)add(r.id,'reference_lane_mismatch')
  }
  if(r.reviewed_revision!==p.revision)add(r.id,'review_required')
 }
 if(result?.project_id===p.id&&result.input_revision===p.revision){
  for(const row of [...result.measurements,...result.normalized])for(const flag of row.flags){
   const r=p.rois.find(r=>r.id===row.id);if(!r)continue
   const source=flagSource(p,r.id,flag);add(source.roiId,source.code)
  }
 }
 return issues
}
export function sourceROIs(p:Project,sampleId:string,analyte:string,analysisBlock:string):ROI[]{
 const block=p.settings.normalization_mode==='ibc'?p.settings.analysis_blocks.find(b=>b.id===analysisBlock&&b.merge_same_sample):undefined
 const membranes=block?.membrane_ids??[analysisBlock]
 const ids=p.lanes.filter(l=>l.sample_id===sampleId&&membranes.includes(l.membrane_id)).map(l=>l.id)
 return p.rois.filter(r=>r.role==='target'&&r.analyte===analyte&&ids.includes(r.lane_id))
}
export function numberLanes(p:Project,ids:string[],start:number){
 writable(p)
 if(!Number.isSafeInteger(start)||start<1)throw new Error('起始编号须为正整数')
 const selected=p.rois.filter(r=>ids.includes(r.id)).sort((a,b)=>a.rect[0]-b.rect[0])
 if(!selected.length||new Set(selected.map(r=>r.image_id)).size!==1)throw new Error('请选择同一图像的条带')
 const lanes=Array.from(new Set(selected.map(r=>r.lane_id)))
 const mapping=new Map(lanes.map((id,i)=>[id,`L${start+i}`]))
 if(p.lanes.some(l=>!mapping.has(l.id)&&[...mapping.values()].includes(l.id)))throw new Error('编号与未选泳道冲突；未应用本次操作')
 for(const l of p.lanes)l.id=mapping.get(l.id)??l.id
 for(const r of p.rois)r.lane_id=mapping.get(r.lane_id)??r.lane_id
}

export function appendCandidates(p:Project,imageId:string,boxes:Rect[],analyte:string,role:ROI['role'],included?:number[]){
 writable(p);let added=0
 const originalLanes=[...p.lanes]
 boxes.forEach((rect,index)=>{
  if(included&&!included.includes(index))return
  const lane=originalLanes[index]??newLane(p)
  if(p.rois.some(r=>r.lane_id===lane.id&&r.analyte===analyte&&r.role===role))return
  p.rois.push({id:crypto.randomUUID(),image_id:imageId,lane_id:lane.id,analyte,role,rect,backgrounds:[],reference_id:null,reviewed_revision:null});added++
 })
 return added
}
