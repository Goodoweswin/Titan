import {useEffect,useLayoutEffect,useRef,useState} from 'react'
import {callEngine} from './bridge'
import type {ImageAsset,Project,Rect,LaneProposal,BandProposal,BandCandidate,LaneColumn} from './types'
import {acceptLaneLayout,createBandSet,copyLaneLayout,alignLaneLayout,setLaneRect,acceptBandAssignments,applyPreparedDraft,renameBandSet} from './lane-workflow'
import LaneLayoutEditor from './LaneLayoutEditor'
import LaneProfilePanel from './LaneProfilePanel'
import ImageRotationDialog from './ImageRotationDialog'

export interface CanvasHistory{canUndo:boolean;canRedo:boolean;dirty:boolean;undo:()=>void;redo:()=>void}
type Mapping={proposal:LaneProposal;values:Record<string,string>}
type Snapshot={preview:Preview|null;region:Rect|null;mapping:Mapping|null;referenceId:string}
type Preview={baseRevision:number;draft:Project;setId:string;bands:BandProposal[]|null;choices:Record<string,number>;uncertain?:string[]}
interface Props{project:Project;stage:'reference'|'targets';activeSetId:string;onSet:(id:string)=>void;onEdit:(f:(draft:Project)=>void)=>void;onImport:()=>void;onTarget:()=>void;onManual:()=>void;onHistory:(value:CanvasHistory|null)=>void}
export default function LaneSetup({project,stage,activeSetId,onSet,onEdit,onImport,onTarget,onManual,onHistory}:Props){
 const role=stage==='reference'?'reference':'target'
 const existing=project.band_sets.find(g=>g.id===activeSetId&&g.role===role)??(role==='reference'?project.band_sets.find(g=>g.role==='reference'):undefined)
 const existingLayout=project.lane_layouts.find(l=>l.id===existing?.layout_id)
 const references=project.band_sets.filter(g=>g.role==='reference')
 const [imageId,setImageId]=useState(existingLayout?.image_id??''),[name,setName]=useState(role==='reference'?'内参':''),[count,setCount]=useState('')
 const [referenceId,setReferenceId]=useState(references[0]?.id??''),[region,setRegion]=useState<Rect|null>(null)
 const [preview,setPreview]=useState<Preview|null>(null),[selected,setSelected]=useState(''),[message,setMessage]=useState(''),[busy,setBusy]=useState(false)
 const [mapping,setMapping]=useState<Mapping|null>(null),[rotating,setRotating]=useState(false)
 const [past,setPast]=useState<Snapshot[]>([]),[future,setFuture]=useState<Snapshot[]>([])
 function snapshot():Snapshot{return structuredClone({preview,region,mapping,referenceId})}
 function remember(){setPast(v=>[...v.slice(-49),snapshot()]);setFuture([])}
 function restore(redo=false){const list=redo?future:past;if(!list.length)return;generation.current++;busyJob.current++;setBusy(false);setMessage('');const next=list.at(-1)!;if(redo){setFuture(list.slice(0,-1));setPast(v=>[...v,snapshot()])}else{setPast(list.slice(0,-1));setFuture(v=>[...v,snapshot()])}setPreview(structuredClone(next.preview));setRegion(next.region);setMapping(next.mapping);setReferenceId(next.referenceId);if(next.preview&&!next.preview.bands)void work(()=>measurePreview(structuredClone(next.preview!)))}
 const historyActions=useRef({undo:()=>{},redo:()=>{}});historyActions.current={undo:()=>restore(),redo:()=>restore(true)}
 useLayoutEffect(()=>{onHistory({canUndo:!rotating&&past.length>0,canRedo:!rotating&&future.length>0,dirty:!!preview||!!mapping||rotating,undo:()=>historyActions.current.undo(),redo:()=>historyActions.current.redo()})},[past,future,preview,region,busy,mapping,rotating])
 useEffect(()=>()=>onHistory(null),[])
 const lastReference=useRef(existing?.reference_set_id??null),knownImages=useRef(new Set(project.images.map(a=>a.id))),lastLayout=useRef(existing?.layout_id),generation=useRef(0),busyJob=useRef(0),latest=useRef(project);latest.current=project
 useEffect(()=>{
  lastReference.current=existing?.reference_set_id??null
  generation.current++;busyJob.current++;setBusy(false);setPreview(null);setPast([]);setFuture([]);setSelected('');setMapping(null);setRotating(false);setMessage('');setRegion(existing?.window??null);setName(existing?.analyte??(role==='reference'?'内参':''));setImageId(existingLayout?.image_id??'');setReferenceId(existing?.reference_set_id??references[0]?.id??'');setCount('')
  return()=>{generation.current++;busyJob.current++}
 },[project.id,stage,activeSetId])
 useEffect(()=>{
  generation.current++;busyJob.current++;setBusy(false);setPast([]);setFuture([]);setPreview(null);setMapping(null)
  const added=project.images.filter(a=>!knownImages.current.has(a.id));knownImages.current=new Set(project.images.map(a=>a.id))
  const linked=existing?.reference_set_id??null
  if(lastReference.current!==linked)setReferenceId(linked??references[0]?.id??'')
  lastReference.current=linked
  const changed=lastLayout.current!==existing?.layout_id;lastLayout.current=existing?.layout_id
  const id=added.at(-1)?.id??(changed&&existingLayout?existingLayout.image_id:project.images.some(a=>a.id===imageId)?imageId:existingLayout?.image_id??project.images.at(-1)?.id??'')
  setImageId(id);setRegion(existingLayout?.image_id===id?existing?.window??null:null)
 },[project.revision])

 const referenceChanged=role==='target'&&!!existing&&(preview?.draft.band_sets.find(g=>g.id===preview.setId)?.reference_set_id??existing.reference_set_id)!==referenceId
 const reference=project.band_sets.find(g=>g.id===referenceId&&g.role==='reference'),referenceLayout=project.lane_layouts.find(l=>l.id===reference?.layout_id)
 const mappingColumns=role==='target'?referenceLayout?.columns:existingLayout?.columns
 const shownProject=preview?.draft??project
 const asset=shownProject.images.find(a=>a.id===imageId)??shownProject.images.at(-1)
 const group=shownProject.band_sets.find(g=>g.id===(preview?.setId??existing?.id)),layout=shownProject.lane_layouts.find(l=>l.id===group?.layout_id)
 const columns=layout&&layout.image_id===asset?.id?layout.columns:[]
 const official:Record<string,BandCandidate>={}
 if(!preview&&group&&layout?.image_id===asset?.id)for(const a of group.assignments){const r=project.rois.find(r=>r.id===a.roi_id);if(r)official[a.lane_id]={rect:r.rect,backgrounds:r.backgrounds}}
 const visibleBands=preview?Object.fromEntries((preview.bands??[]).flatMap(b=>{const c=b.candidates[preview.choices[b.lane_id]??-1];return c?[[b.lane_id,c]]:[]})):official
 async function work(fn:()=>Promise<void>){const token=++busyJob.current;setBusy(true);setMessage('');try{await fn()}catch(e){if(token===busyJob.current)setMessage(String(e))}finally{if(token===busyJob.current)setBusy(false)}}
 function clearSet(draft:Project,setId:string){const g=draft.band_sets.find(g=>g.id===setId)!;const removed=new Set(g.assignments.map(a=>a.roi_id));draft.rois=draft.rois.filter(r=>!removed.has(r.id));for(const r of draft.rois)if(removed.has(r.reference_id))r.reference_id=null;g.assignments=g.assignments.map(a=>({...a,roi_id:null,status:'pending'}))}
 function preparedTarget():Preview {
  if(!asset||!region)throw new Error('请在原图上选择目标所在区域')
  if(!name.trim())throw new Error('请填写目标名称')
  const ref=project.band_sets.find(g=>g.id===referenceId&&g.role==='reference')
  if(!ref)throw new Error('请先确认内参')
  const draft=structuredClone(project)
  const layoutId=copyLaneLayout(draft,ref.layout_id,asset.id,region,ref.window)
  const setId=existing?.id??createBandSet(draft,layoutId,name,'target',ref.id)
  if(existing){clearSet(draft,setId);const g=draft.band_sets.find(g=>g.id===setId)!;g.layout_id=layoutId;g.analyte=name.trim();g.reference_set_id=ref.id}
  draft.band_sets.find(g=>g.id===setId)!.window=region
  draft.lane_layouts.find(l=>l.id===layoutId)!.confirmed_revision=draft.revision+1
  return {baseRevision:project.revision,draft,setId,bands:null,choices:{}}
 }
 function targetPreview():Preview {
  const next=preview??(existing&&!referenceChanged&&existingLayout?.image_id===asset?.id?editable():preparedTarget())
  const g=next.draft.band_sets.find(g=>g.id===next.setId)!,l=next.draft.lane_layouts.find(l=>l.id===g.layout_id)!
  if(region&&(g.window.join(',')!==region.join(',')||l.columns.some(c=>c.rect[1]!==region[1]||c.rect[3]!==region[3]))){
   g.layout_id=copyLaneLayout(next.draft,l.id,asset!.id,region);g.window=[...region]
   clearSet(next.draft,g.id);next.draft.lane_layouts.find(l=>l.id===g.layout_id)!.confirmed_revision=next.draft.revision+1
  }
  return next
 }
 function editable():Preview {
  if(preview)return structuredClone(preview)
  if(!existing||!existingLayout||existingLayout.image_id!==asset?.id)return preparedTarget()
  const draft=structuredClone(project),layoutId=crypto.randomUUID()
  draft.lane_layouts.push({...structuredClone(existingLayout),id:layoutId,source_layout_id:existingLayout.id,confirmed_revision:draft.revision+1})
  const g=draft.band_sets.find(g=>g.id===existing.id)!;g.layout_id=layoutId;clearSet(draft,g.id)
  return {baseRevision:project.revision,draft,setId:g.id,bands:existingLayout.columns.map(c=>({lane_id:c.lane_id,status:official[c.lane_id]?'proposed':'not_detected',candidates:official[c.lane_id]?[structuredClone(official[c.lane_id])]:[],reasons:[]})),choices:Object.fromEntries(existingLayout.columns.map(c=>[c.lane_id,official[c.lane_id]?0:-1]))}
 }
 async function measurePreview(next:Preview){
  const token=++generation.current,baseId=project.id
  const bands=await callEngine<BandProposal[]>('propose_bands',{project:next.draft,band_set_id:next.setId})
  if(token!==generation.current||latest.current.id!==baseId||latest.current.revision!==next.baseRevision)return
  setPreview({...next,bands,choices:Object.fromEntries(bands.map(b=>[b.lane_id,b.candidates.length===1?0:-1]))})
 }
 async function identify(){await work(async()=>{
  if(!asset||!region)throw new Error('先点击“选择区域”，拖选蛋白所在的横向区域，并避开 marker')
  if(!name.trim())throw new Error('请填写蛋白名称')
  if(asset.polarity==='dark'&&!asset.ceiling)throw new Error('请在“图像信息”中填写有效编码上界后再识别。仅改变画面黑白可直接使用“显示反色”。')
  if(role==='target'){const next=targetPreview();remember();setPreview({...next,bands:null});await measurePreview(next);return}
  const token=++generation.current,baseId=project.id,baseRevision=project.revision
  // Re-identification uses the confirmed template and its explicit identities.
  // A different crop or translation must never trigger coordinate-based remapping.
  if(existing&&existingLayout&&existingLayout.image_id===asset.id){
   const draft=structuredClone(project),layoutId=copyLaneLayout(draft,existingLayout.id,asset.id)
   clearSet(draft,existing.id)
   const g=draft.band_sets.find(g=>g.id===existing.id)!
   g.layout_id=layoutId;g.window=region;renameBandSet(draft,g.id,name)
   draft.lane_layouts.find(l=>l.id===layoutId)!.confirmed_revision=draft.revision+1
   const next={baseRevision,draft,setId:g.id,bands:null,choices:{}}
   remember();setPreview(next);await measurePreview(next);return
  }
  const proposal=await callEngine<LaneProposal>('detect_lanes',{project,image_id:asset.id,window:region,excluded_regions:[],expected_count:count?Number(count):null})
  if(token!==generation.current||latest.current.id!==baseId||latest.current.revision!==baseRevision)return
  if(!proposal.columns.length)throw new Error('没有找到清晰泳道，请调整区域，或填写预计泳道数后重试')
  if(existingLayout&&existingLayout.image_id!==asset.id){remember();setMapping({proposal,values:{}});return}
  await prepareProposal(proposal,Object.fromEntries(proposal.columns.map(c=>[c.proposal_id,null])))
 })}
 async function reuseTarget(){await work(async()=>{const next=preparedTarget();remember();setMapping(null);setPreview(next);await measurePreview(next)})}
 async function identifyTargetLanes(){await work(async()=>{
  if(!asset||!region)throw new Error('请先框选目标蛋白所在区域')
  if(!name.trim())throw new Error('请填写目标名称')
  if(!referenceLayout)throw new Error('请先确认内参')
  const token=++generation.current,baseId=project.id,revision=project.revision
  const proposal=await callEngine<LaneProposal>('detect_lanes',{project,image_id:asset.id,window:region,excluded_regions:[],expected_count:referenceLayout.columns.length})
  if(token!==generation.current||latest.current.id!==baseId||latest.current.revision!==revision)return
  if(proposal.columns.length!==referenceLayout.columns.length)throw new Error(`识别出 ${proposal.columns.length} 条，内参为 ${referenceLayout.columns.length} 条。请调整区域，或沿用内参位置手动调整；未检出的泳道也需保留。`)
  remember();setPreview(null);setMapping({proposal,values:{}})
 })}
 async function prepareProposal(proposal:LaneProposal,identities:Record<string,string|null>){
  if(role==='target'&&(!referenceLayout||Object.values(identities).length!==referenceLayout.columns.length||new Set(Object.values(identities)).size!==referenceLayout.columns.length||referenceLayout.columns.some(c=>!Object.values(identities).includes(c.lane_id))))throw new Error('请为每个内参泳道指定唯一对应，未检出的位置也需保留')
  const draft=structuredClone(project),layoutId=acceptLaneLayout(draft,proposal,identities,(role==='target'?referenceLayout:existingLayout)?.membrane_id??'M1')
  if(role==='target')draft.lane_layouts.find(l=>l.id===layoutId)!.source_layout_id=reference!.layout_id
  const setId=existing?.id??createBandSet(draft,layoutId,name,role,role==='target'?reference!.id:undefined)
  if(existing){clearSet(draft,setId);const g=draft.band_sets.find(g=>g.id===setId)!;g.layout_id=layoutId;g.analyte=name.trim();g.window=region!;if(role==='target')g.reference_set_id=reference!.id}
  const newLayout=draft.lane_layouts.find(l=>l.id===layoutId)!
  const uncertain=newLayout.columns.filter(c=>proposal.columns.some(s=>s.confidence==='low'&&s.rect.join(',')===c.rect.join(','))).map(c=>c.lane_id)
  const next={baseRevision:project.revision,draft,setId,bands:null,choices:{},uncertain}
  remember();setMapping(null);setPreview(next);await measurePreview(next)
 }
 async function rotate(degrees:number){
  const token=++generation.current,revision=project.revision,id=project.id
  const corrected=await callEngine<ImageAsset>('rotate_image',{project,image_id:asset!.id,degrees})
  if(token!==generation.current||latest.current.id!==id||latest.current.revision!==revision)return
  onEdit(p=>{p.images.push(corrected)});setImageId(corrected.id);setRegion(null);setPreview(null);setMapping(null);setRotating(false);setSelected('')
 }
 function changeRegion(r:Rect){remember();generation.current++;setRegion(r);setPreview(null);setMapping(null);setMessage('')}
 async function adjust(change:(p:Project,layoutId:string)=>void){await work(async()=>{
  const next=editable(),g=next.draft.band_sets.find(g=>g.id===next.setId)!,l=next.draft.lane_layouts.find(l=>l.id===g.layout_id)!,before=structuredClone(l.columns)
  change(next.draft,g.layout_id);l.confirmed_revision=next.draft.revision+1
  if(next.bands){
   for(const b of next.bands){const old=before.find(c=>c.lane_id===b.lane_id)?.rect,now=l.columns.find(c=>c.lane_id===b.lane_id)?.rect
    if(!old||!now||old.every((v,i)=>v===now[i]))continue
    const x=(value:number)=>Math.max(0,Math.min(asset!.width,Math.round(now[0]+(value-old[0])*(now[2]-now[0])/(old[2]-old[0]))))
    const transform=(r:Rect):Rect=>[x(r[0]),r[1],x(r[2]),r[3]]
    b.candidates=b.candidates.map(c=>({rect:transform(c.rect),backgrounds:c.backgrounds.map(transform)}))
   }
   remember();setPreview(next)
  }else{remember();setPreview(next);await measurePreview(next)}
 })}
 function updateBand(id:string,rect:Rect,background?:Rect){
  try{
   const next=editable(),b=next.bands?.find(b=>b.lane_id===id);if(!b)return
   let index=next.choices[id]??-1
   if(index<0){b.candidates.push({rect,backgrounds:[]});index=b.candidates.length-1;next.choices[id]=index}
   const candidate=b.candidates[index]
   if(background)candidate.backgrounds.push(background)
   else {candidate.rect=rect;candidate.backgrounds=candidate.backgrounds.filter(bg=>!(Math.max(bg[1],rect[1])<Math.min(bg[3],rect[3])))}
   b.status=b.candidates.length>1?'ambiguous':'proposed';remember();setPreview(next);setMessage('')
  }catch(e){setMessage(String(e))}
 }
 function confirm(){try{
  if(!preview?.bands)return
  if(preview.baseRevision!==project.revision)throw new Error('输入已改变，请重新识别后确认')
  const draft=structuredClone(preview.draft)
  const choices=preview.bands.map(b=>{
   if(!b.candidates.length)return {lane_id:b.lane_id,status:'not_detected' as const}
   const c=b.candidates[preview.choices[b.lane_id]??-1];if(!c)throw new Error(`${b.lane_id} 有多个峰，请先选择目标峰`)
   return {lane_id:b.lane_id,rect:c.rect,backgrounds:c.backgrounds}
  })
  if(role==='reference'&&!choices.some(c=>c.rect))throw new Error('没有可用的内参峰，请调整区域')
  renameBandSet(draft,preview.setId,name)
  acceptBandAssignments(draft,preview.setId,choices)
  onEdit(p=>applyPreparedDraft(p,draft,preview.baseRevision));setPreview(null);setPast([]);setFuture([]);onSet(preview.setId);setMessage('')
 }catch(e){setMessage(String(e))}}
 const hasAccepted=!!existing&&existingLayout?.image_id===asset?.id&&!preview&&!mapping&&existing.assignments.some(a=>a.status==='accepted')
 const confirmed=hasAccepted&&!referenceChanged
 const displayRegion=region??(existingLayout?.image_id===asset?.id?existing?.window??null:null)
 const selectedPeak=visibleBands[selected]?.rect
 const selectedSample=shownProject.samples.find(s=>s.id===shownProject.lanes.find(l=>l.id===selected)?.sample_id)
 return <div className="lane-workspace"><div className="lane-main">
  {!asset?<div className="lane-empty"><h2>先导入内参图像</h2><p>建立一次泳道与样本对应，后续目标可以直接复用。</p></div>:<LaneLayoutEditor asset={asset} region={displayRegion} columns={columns} laneBounds={layout?.window} bands={visibleBands} selected={selected} readOnly={!!project.read_only||busy||referenceChanged} onSelect={setSelected} onRegion={changeRegion} onColumn={(id,r)=>adjust((p,l)=>setLaneRect(p,l,id,r))} onAlign={dx=>adjust((p,l)=>alignLaneLayout(p,l,{dx,dy:0,scaleX:1,anchorX:0}))} onBand={(id,r)=>updateBand(id,r)} onBackground={(id,r)=>{const c=visibleBands[id];if(c)updateBand(id,c.rect,r)}} onRotate={()=>setRotating(true)} onInvert={()=>{if(preview){remember();setPreview(current=>{if(!current)return current;const next=structuredClone(current),a=next.draft.images.find(a=>a.id===asset.id)!;a.display_inverted=!a.display_inverted;return next})}else onEdit(p=>{const a=p.images.find(a=>a.id===asset.id)!;a.display_inverted=!a.display_inverted})}}/>}
  {rotating&&asset&&<ImageRotationDialog asset={asset} onApply={rotate} onClose={()=>{generation.current++;setRotating(false)}}/>}
  {mapping&&<section className="lane-mapping"><strong>{role==='target'?'核对目标泳道对应':'核对泳道对应'}</strong><p className="hint">请明确每个候选对应的原泳道，未检出的位置也需保留，避免样本错配。</p>{mapping.proposal.columns.map((c,i)=><label key={c.proposal_id}>候选 {i+1}<select aria-label={`候选 ${i+1} 对应泳道`} value={mapping.values[c.proposal_id]??''} onChange={e=>{remember();setMapping({...mapping,values:{...mapping.values,[c.proposal_id]:e.target.value}})}}><option value="">请选择</option>{mappingColumns?.map(l=><option key={l.lane_id} value={l.lane_id}>{l.lane_id}</option>)}{role==='reference'&&<><option value="new">新泳道</option><option value="exclude">不使用</option></>}</select></label>)}<button className="btn primary" disabled={busy||mapping.proposal.columns.some(c=>!mapping.values[c.proposal_id])} onClick={()=>work(()=>prepareProposal(mapping.proposal,Object.fromEntries(mapping.proposal.columns.filter(c=>mapping.values[c.proposal_id]!=='exclude').map(c=>[c.proposal_id,mapping.values[c.proposal_id]==='new'?null:mapping.values[c.proposal_id]]))))}>确认泳道对应</button><button className="text-btn" disabled={busy} onClick={()=>{remember();setMapping(null)}}>取消泳道识别</button></section>}
  {columns.length>0&&<div className="lane-check-list" aria-label="泳道检查">{columns.map(c=>{
   const b=preview?.bands?.find(b=>b.lane_id===c.lane_id),assignment=group?.assignments.find(a=>a.lane_id===c.lane_id)
   const missing=b?b.candidates.length===0:assignment?.status==='not_detected'
   return <div key={c.lane_id}><button className={selected===c.lane_id?'selected':''} onClick={()=>setSelected(selected===c.lane_id?'':c.lane_id)}>{c.lane_id}{missing?' · 未检出':b?.status==='ambiguous'?' · 选择峰':preview?.uncertain?.includes(c.lane_id)?' · 检查位置':''}</button>{b&&b.candidates.length>1&&<select aria-label={`${c.lane_id} 选择峰`} value={preview?.choices[c.lane_id]??-1} onChange={e=>{remember();setPreview(p=>p?{...p,choices:{...p.choices,[c.lane_id]:Number(e.target.value)}}:p)}}><option value={-1}>请选择峰</option>{b.candidates.map((candidate,i)=><option key={i} value={i}>峰 {i+1} · y {candidate.rect[1]}–{candidate.rect[3]}</option>)}</select>}</div>
  })}</div>}
  {preview&&role==='reference'&&selected&&<button className="text-btn" disabled={busy||project.read_only||columns.length<=1} onClick={()=>work(async()=>{
   const next=structuredClone(preview),g=next.draft.band_sets.find(g=>g.id===next.setId)!,l=next.draft.lane_layouts.find(l=>l.id===g.layout_id)!,column=l.columns.find(c=>c.lane_id===selected)!
   l.excluded_regions.push(column.rect);l.columns=l.columns.filter(c=>c.lane_id!==selected);g.assignments=g.assignments.filter(a=>a.lane_id!==selected)
   remember();setSelected('');setPreview(next);await measurePreview(next)
  })}>排除选中泳道（如 marker）</button>}
  {selected&&layout&&displayRegion&&<LaneProfilePanel project={shownProject} layoutId={layout.id} laneId={selected} window={displayRegion} peak={selectedPeak}/>}
 </div><aside className="lane-task" data-testid="task-panel"><h2>{role==='reference'?'确认内参':'添加目标'}</h2><p className="hint">{role==='reference'?'框选内参所在区域，避开 marker。检查泳道、绿框和背景后一起确认。':'导入目标图像，框选目标区域。沿用内参编号；位置可单独识别、移动或微调。'}</p>
  {asset&&<fieldset disabled={!!project.read_only||busy}><label>{role==='reference'?'内参名称':'目标名称'}<input aria-label={role==='reference'?'内参名称':'目标名称'} value={name} onChange={e=>setName(e.target.value)} placeholder={role==='reference'?'如 ACTIN':'如 AKT'}/></label><label>图像<select aria-label="当前图像" value={asset.id} onChange={e=>{generation.current++;setPast([]);setFuture([]);setMapping(null);setImageId(e.target.value);setRegion(null);setPreview(null)}}>{project.images.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>{role==='reference'?<label>预计泳道数<input aria-label="预计泳道数" disabled={!!existingLayout&&existingLayout.image_id===asset.id} type="number" min="1" max="100" value={count} placeholder="自动识别，可手动指定" onChange={e=>setCount(e.target.value)}/></label>:references.length>1?<label>对应内参<select aria-label="对应内参" value={referenceId} onChange={e=>{remember();generation.current++;setReferenceId(e.target.value);setPreview(null);setMapping(null)}}>{references.map(g=><option key={g.id} value={g.id}>{g.analyte}</option>)}</select></label>:null}</fieldset>}
  {role==='target'&&<><button className="btn secondary full" disabled={busy||project.read_only} onClick={onImport}>导入目标图像</button><div className="target-lane-actions"><button className="btn secondary" disabled={busy||project.read_only||!region||!referenceLayout} onClick={reuseTarget}>沿用内参位置</button><button className="btn secondary" disabled={busy||project.read_only||!region||!referenceLayout} onClick={identifyTargetLanes}>重新识别泳道位置</button></div></>}
  {referenceChanged&&<p className="hint">对应内参已切换，请重新识别目标后确认。</p>}
  {existingLayout&&role==='reference'&&<p className="hint">拖动泳道直接微调，确认后保存；重新识别会生成新的峰区建议。</p>}
  {columns.length>0&&<p className="lane-count">{columns.length} 条泳道</p>}
  {selectedSample&&<label>样本名称<input aria-label="样本名称" disabled={project.read_only||busy} value={selectedSample.name??selectedSample.id} onChange={e=>{
   const name=e.target.value
   if(preview){remember();setPreview(p=>{if(!p)return p;const next=structuredClone(p);next.draft.samples.find(s=>s.id===selectedSample.id)!.name=name;return next})}
   else onEdit(p=>{p.samples.find(s=>s.id===selectedSample.id)!.name=name})
  }}/></label>}
  {confirmed&&<p className="lane-confirmed">{role==='reference'?'内参已确认':'目标已确认'}</p>}
  {message&&<p role="alert" className="lane-message">{message}</p>}
  <button className="btn primary full" disabled={busy||!!mapping||!!project.read_only||(role==='target'&&!references.length)} onClick={()=>!asset?onImport():preview?.bands?confirm():confirmed?(onSet(''),onTarget()):identify()}>{busy?'正在识别…':mapping?'先核对泳道':!asset?'导入内参图':preview?.bands?(role==='reference'?'确认内参':'确认目标'):confirmed?(role==='reference'?'添加目标':'添加下一个目标'):(role==='reference'?'识别泳道':'识别目标')}</button>
  {hasAccepted&&<button className="btn secondary full" disabled={busy||project.read_only} onClick={identify}>重新识别</button>}
  {preview&&<button className="text-btn" disabled={busy} onClick={()=>{remember();generation.current++;setPreview(null)}}>取消本次建议</button>}
  {busy&&<button className="text-btn" onClick={()=>{generation.current++;busyJob.current++;setBusy(false);setPreview(null);setMessage('已取消识别，本次建议不会加入实验。')}}>取消识别</button>}
  {role==='target'&&!references.length&&<p className="hint">先在“内参”步骤确认泳道和内参。</p>}
  <details className="lane-advanced"><summary>手动调整与图像信息</summary><button className="btn secondary" onClick={onManual}>打开手动条带编辑</button>{asset&&<><label>原始信号方向<select aria-label="原始信号方向" value={asset.polarity} disabled={project.read_only} onChange={e=>onEdit(p=>p.images.find(a=>a.id===asset.id)!.polarity=e.target.value as 'bright'|'dark')}><option value="bright">数值越大，信号越强</option><option value="dark">数值越小，信号越强</option></select></label><label>有效编码上界<input type="number" value={asset.ceiling??''} disabled={project.read_only} placeholder="按采集记录填写" onChange={e=>onEdit(p=>p.images.find(a=>a.id===asset.id)!.ceiling=e.target.value?Number(e.target.value):null)}/></label><p className="hint">显示反色只改变画面。原始信号方向参与计算；暗信号需提供有效编码上界。</p><p className="hint">原始文件：{asset.name}；第 {(asset.page_index??0)+1} 页。</p></>}{role==='target'&&<><button className="btn secondary" disabled={!region||busy||project.read_only} onClick={()=>adjust((p,l)=>alignLaneLayout(p,l,{dx:0,dy:0,scaleX:.97,anchorX:(asset?.width??0)/2}))}>缩小泳道间距</button><button className="btn secondary" disabled={!region||busy||project.read_only} onClick={()=>adjust((p,l)=>alignLaneLayout(p,l,{dx:0,dy:0,scaleX:1.03,anchorX:(asset?.width??0)/2}))}>增大泳道间距</button></>}</details>
 </aside></div>
}
