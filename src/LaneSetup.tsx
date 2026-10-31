import {useEffect,useRef,useState} from 'react'
import {callEngine} from './bridge'
import type {Project,Rect,LaneProposal,BandProposal,BandCandidate,LaneColumn} from './types'
import {acceptLaneLayout,createBandSet,copyLaneLayout,alignLaneLayout,setLaneRect,acceptBandAssignments,applyPreparedDraft} from './lane-workflow'
import LaneLayoutEditor from './LaneLayoutEditor'
import LaneProfilePanel from './LaneProfilePanel'

type Preview={baseRevision:number;draft:Project;setId:string;bands:BandProposal[]|null;choices:Record<string,number>;uncertain?:string[]}
interface Props{project:Project;stage:'reference'|'targets';activeSetId:string;onSet:(id:string)=>void;onEdit:(f:(draft:Project)=>void)=>void;onImport:()=>void;onTarget:()=>void;onManual:()=>void}
export default function LaneSetup({project,stage,activeSetId,onSet,onEdit,onImport,onTarget,onManual}:Props){
 const role=stage==='reference'?'reference':'target'
 const existing=project.band_sets.find(g=>g.id===activeSetId&&g.role===role)??(role==='reference'?project.band_sets.find(g=>g.role==='reference'):undefined)
 const existingLayout=project.lane_layouts.find(l=>l.id===existing?.layout_id)
 const references=project.band_sets.filter(g=>g.role==='reference')
 const [imageId,setImageId]=useState(existingLayout?.image_id??''),[name,setName]=useState(role==='reference'?'内参':''),[count,setCount]=useState('')
 const [referenceId,setReferenceId]=useState(references[0]?.id??''),[region,setRegion]=useState<Rect|null>(null)
 const [preview,setPreview]=useState<Preview|null>(null),[selected,setSelected]=useState(''),[message,setMessage]=useState(''),[busy,setBusy]=useState(false)
 const generation=useRef(0),busyJob=useRef(0),latest=useRef(project);latest.current=project
 useEffect(()=>{
  generation.current++;busyJob.current++;setBusy(false);setPreview(null);setSelected('');setMessage('');setRegion(existing?.window??null);setName(existing?.analyte??(role==='reference'?'内参':''));setImageId(existingLayout?.image_id??'');setReferenceId(existing?.reference_set_id??references[0]?.id??'');setCount('')
  return()=>{generation.current++;busyJob.current++}
 },[project.id,stage,activeSetId])
 const asset=project.images.find(a=>a.id===imageId)??project.images.at(-1)
 const shownProject=preview?.draft??project,group=shownProject.band_sets.find(g=>g.id===(preview?.setId??existing?.id)),layout=shownProject.lane_layouts.find(l=>l.id===group?.layout_id)
 const columns=layout&&layout.image_id===asset?.id?layout.columns:[]
 const official:Record<string,BandCandidate>={}
 if(!preview&&group)for(const a of group.assignments){const r=project.rois.find(r=>r.id===a.roi_id);if(r)official[a.lane_id]={rect:r.rect,backgrounds:r.backgrounds}}
 const visibleBands=preview?Object.fromEntries((preview.bands??[]).flatMap(b=>{const c=b.candidates[preview.choices[b.lane_id]??-1];return c?[[b.lane_id,c]]:[]})):official
 async function work(fn:()=>Promise<void>){const token=++busyJob.current;setBusy(true);setMessage('');try{await fn()}catch(e){if(token===busyJob.current)setMessage(String(e))}finally{if(token===busyJob.current)setBusy(false)}}
 function clearSet(draft:Project,setId:string){const g=draft.band_sets.find(g=>g.id===setId)!;const removed=new Set(g.assignments.map(a=>a.roi_id));draft.rois=draft.rois.filter(r=>!removed.has(r.id));for(const r of draft.rois)if(removed.has(r.reference_id))r.reference_id=null;g.assignments=g.assignments.map(a=>({...a,roi_id:null,status:'pending'}))}
 function preparedTarget():Preview {
  if(!asset||!region)throw new Error('请在原图上选择目标所在区域')
  if(!name.trim())throw new Error('请填写目标名称')
  const ref=project.band_sets.find(g=>g.id===referenceId&&g.role==='reference')
  if(!ref)throw new Error('请先确认内参')
  const draft=structuredClone(project)
  const layoutId=copyLaneLayout(draft,ref.layout_id,asset.id)
  const setId=existing?.id??createBandSet(draft,layoutId,name,'target',ref.id)
  if(existing){clearSet(draft,setId);const g=draft.band_sets.find(g=>g.id===setId)!;g.layout_id=layoutId;g.analyte=name.trim();g.reference_set_id=ref.id}
  draft.band_sets.find(g=>g.id===setId)!.window=region
  draft.lane_layouts.find(l=>l.id===layoutId)!.confirmed_revision=draft.revision+1
  return {baseRevision:project.revision,draft,setId,bands:null,choices:{}}
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
  if(role==='target'){await measurePreview(preview??preparedTarget());return}
  const token=++generation.current,baseId=project.id,baseRevision=project.revision
  const proposal=await callEngine<LaneProposal>('detect_lanes',{project,image_id:asset.id,window:region,excluded_regions:existingLayout?.excluded_regions??[],expected_count:count?Number(count):existingLayout?.columns.length??null})
  if(token!==generation.current||latest.current.id!==baseId||latest.current.revision!==baseRevision)return
  if(!proposal.columns.length)throw new Error('没有找到清晰泳道，请调整区域，或填写预计泳道数后重试')
  const draft=structuredClone(project),mapping:Record<string,string|null>={}
  const used=new Set<string>()
  for(const c of proposal.columns){
   if(existingLayout){
    const center=(c.rect[0]+c.rect[2])/2
    const nearest=[...existingLayout.columns].filter(x=>!used.has(x.lane_id)).sort((a,b)=>Math.abs((a.rect[0]+a.rect[2])/2-center)-Math.abs((b.rect[0]+b.rect[2])/2-center))[0]
    if(!nearest||proposal.columns.length!==existingLayout.columns.length)throw new Error('泳道数量与已有样本不同，请检查区域和预计泳道数')
    mapping[c.proposal_id]=nearest.lane_id;used.add(nearest.lane_id)
   }else mapping[c.proposal_id]=null
  }
  const layoutId=acceptLaneLayout(draft,proposal,mapping,existingLayout?.membrane_id??'M1')
  const setId=existing?.id??createBandSet(draft,layoutId,name,'reference')
  if(existing){clearSet(draft,setId);const g=draft.band_sets.find(g=>g.id===setId)!;g.layout_id=layoutId;g.analyte=name.trim();g.window=region}
  const newLayout=draft.lane_layouts.find(l=>l.id===layoutId)!
  const uncertain=newLayout.columns.filter(c=>proposal.columns.some(s=>s.confidence==='low'&&s.rect.join(',')===c.rect.join(','))).map(c=>c.lane_id)
  const next={baseRevision,draft,setId,bands:null,choices:{},uncertain}
  setPreview(next)
  await measurePreview(next)
 })}
 function changeRegion(r:Rect){generation.current++;setRegion(r);setPreview(null);setMessage('')}
 async function adjust(change:(p:Project,layoutId:string)=>void){await work(async()=>{
  const next=preview?structuredClone(preview):role==='target'?preparedTarget():null
  if(!next)throw new Error('请先识别泳道')
  const g=next.draft.band_sets.find(g=>g.id===next.setId)!;change(next.draft,g.layout_id)
  next.draft.lane_layouts.find(l=>l.id===g.layout_id)!.confirmed_revision=next.draft.revision+1
  setPreview({...next,bands:null});await measurePreview(next)
 })}
 function updateBand(id:string,rect:Rect,background?:Rect){
  if(!preview){setMessage('请先点击“重新识别”，再调整峰区或背景');return}
  setPreview(current=>{
   if(!current)return current
   const next=structuredClone(current),b=next.bands?.find(b=>b.lane_id===id);if(!b)return current
   let index=next.choices[id]??-1
   if(index<0){b.candidates.push({rect,backgrounds:[]});index=b.candidates.length-1;next.choices[id]=index}
   const candidate=b.candidates[index]
   if(background)candidate.backgrounds.push(background)
   else {candidate.rect=rect;candidate.backgrounds=candidate.backgrounds.filter(bg=>!(Math.max(bg[1],rect[1])<Math.min(bg[3],rect[3])))}
   b.status=b.candidates.length>1?'ambiguous':'proposed';return next
  })
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
  acceptBandAssignments(draft,preview.setId,choices)
  onEdit(p=>applyPreparedDraft(p,draft,preview.baseRevision));setPreview(null);onSet(preview.setId);setMessage('')
 }catch(e){setMessage(String(e))}}
 const confirmed=!!existing&&!preview&&existing.assignments.some(a=>a.status==='accepted')
 const displayRegion=region??existing?.window??null
 const selectedPeak=visibleBands[selected]?.rect
 const selectedSample=shownProject.samples.find(s=>s.id===shownProject.lanes.find(l=>l.id===selected)?.sample_id)
 return <div className="lane-workspace"><div className="lane-main">
  {!asset?<div className="lane-empty"><h2>先导入内参图像</h2><p>建立一次泳道与样本对应，后续目标可以直接复用。</p></div>:<LaneLayoutEditor asset={asset} region={displayRegion} columns={columns} bands={visibleBands} selected={selected} readOnly={!!project.read_only||busy} onSelect={setSelected} onRegion={changeRegion} onColumn={(id,r)=>adjust((p,l)=>setLaneRect(p,l,id,r))} onAlign={dx=>adjust((p,l)=>alignLaneLayout(p,l,{dx,dy:0,scaleX:1,anchorX:0}))} onBand={(id,r)=>updateBand(id,r)} onBackground={(id,r)=>{const c=visibleBands[id];if(c)updateBand(id,c.rect,r)}} onInvert={()=>onEdit(p=>{const a=p.images.find(a=>a.id===asset.id)!;a.display_inverted=!a.display_inverted})}/>}
  {columns.length>0&&<div className="lane-check-list" aria-label="泳道检查">{columns.map(c=>{
   const b=preview?.bands?.find(b=>b.lane_id===c.lane_id),assignment=group?.assignments.find(a=>a.lane_id===c.lane_id)
   const missing=b?b.candidates.length===0:assignment?.status==='not_detected'
   return <div key={c.lane_id}><button className={selected===c.lane_id?'selected':''} onClick={()=>setSelected(selected===c.lane_id?'':c.lane_id)}>{c.lane_id}{missing?' · 未检出':b?.status==='ambiguous'?' · 选择峰':preview?.uncertain?.includes(c.lane_id)?' · 检查位置':''}</button>{b&&b.candidates.length>1&&<select aria-label={`${c.lane_id} 选择峰`} value={preview?.choices[c.lane_id]??-1} onChange={e=>setPreview(p=>p?{...p,choices:{...p.choices,[c.lane_id]:Number(e.target.value)}}:p)}><option value={-1}>请选择峰</option>{b.candidates.map((candidate,i)=><option key={i} value={i}>峰 {i+1} · y {candidate.rect[1]}–{candidate.rect[3]}</option>)}</select>}</div>
  })}</div>}
  {preview&&role==='reference'&&selected&&<button className="text-btn" disabled={busy||project.read_only||columns.length<=1} onClick={()=>work(async()=>{
   const next=structuredClone(preview),g=next.draft.band_sets.find(g=>g.id===next.setId)!,l=next.draft.lane_layouts.find(l=>l.id===g.layout_id)!,column=l.columns.find(c=>c.lane_id===selected)!
   l.excluded_regions.push(column.rect);l.columns=l.columns.filter(c=>c.lane_id!==selected);g.assignments=g.assignments.filter(a=>a.lane_id!==selected)
   setSelected('');setPreview(next);await measurePreview(next)
  })}>排除选中泳道（如 marker）</button>}
  {selected&&layout&&displayRegion&&<LaneProfilePanel project={shownProject} layoutId={layout.id} laneId={selected} window={displayRegion} peak={selectedPeak}/>}
 </div><aside className="lane-task" data-testid="task-panel"><h2>{role==='reference'?'确认内参':'添加目标'}</h2><p className="hint">{role==='reference'?'框选内参所在区域，避开 marker。检查泳道、绿框和背景后一起确认。':'使用相同泳道身份，框选此目标所在区域；有偏移时移动泳道或调整间距。'}</p>
  {asset&&<fieldset disabled={!!project.read_only||busy}><label>{role==='reference'?'内参名称':'目标名称'}<input aria-label={role==='reference'?'内参名称':'目标名称'} value={name} onChange={e=>setName(e.target.value)} placeholder={role==='reference'?'如 ACTIN':'如 AKT'}/></label><label>图像<select aria-label="当前图像" value={asset.id} onChange={e=>{setImageId(e.target.value);setRegion(null);setPreview(null)}}>{project.images.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>{role==='reference'?<label>预计泳道数<input aria-label="预计泳道数" type="number" min="1" max="100" value={count} placeholder="自动识别，可手动指定" onChange={e=>setCount(e.target.value)}/></label>:references.length>1?<label>对应内参<select value={referenceId} onChange={e=>{setReferenceId(e.target.value);setPreview(null)}}>{references.map(g=><option key={g.id} value={g.id}>{g.analyte}</option>)}</select></label>:null}</fieldset>}
  {columns.length>0&&<p className="lane-count">{columns.length} 条泳道</p>}
  {selectedSample&&<label>样本名称<input aria-label="样本名称" disabled={project.read_only||busy} value={selectedSample.name??selectedSample.id} onChange={e=>{
   const name=e.target.value
   if(preview)setPreview(p=>{if(!p)return p;const next=structuredClone(p);next.draft.samples.find(s=>s.id===selectedSample.id)!.name=name;return next})
   else onEdit(p=>{p.samples.find(s=>s.id===selectedSample.id)!.name=name})
  }}/></label>}
  {confirmed&&<p className="lane-confirmed">{role==='reference'?'内参已确认':'目标已确认'}</p>}
  {message&&<p role="alert" className="lane-message">{message}</p>}
  <button className="btn primary full" disabled={busy||!!project.read_only||(role==='target'&&!references.length)} onClick={()=>!asset?onImport():preview?.bands?confirm():confirmed?(onSet(''),onTarget()):identify()}>{busy?'正在识别…':!asset?'导入内参图':preview?.bands?(role==='reference'?'确认内参':'确认目标'):confirmed?(role==='reference'?'添加目标':'添加下一个目标'):(role==='reference'?'识别泳道':'识别目标')}</button>
  {confirmed&&<button className="btn secondary full" disabled={busy||project.read_only} onClick={identify}>重新识别</button>}
  {preview&&<button className="text-btn" disabled={busy} onClick={()=>{generation.current++;setPreview(null)}}>取消本次建议</button>}
  {busy&&<button className="text-btn" onClick={()=>{generation.current++;busyJob.current++;setBusy(false);setPreview(null);setMessage('已取消识别，本次建议不会加入实验。')}}>取消识别</button>}
  {role==='target'&&!references.length&&<p className="hint">先在“内参”步骤确认泳道和内参。</p>}
  <details className="lane-advanced"><summary>手动调整与图像信息</summary><button className="btn secondary" onClick={onManual}>打开手动条带编辑</button>{asset&&<><label>原始信号方向<select aria-label="原始信号方向" value={asset.polarity} disabled={project.read_only} onChange={e=>onEdit(p=>p.images.find(a=>a.id===asset.id)!.polarity=e.target.value as 'bright'|'dark')}><option value="bright">数值越大，信号越强</option><option value="dark">数值越小，信号越强</option></select></label><label>有效编码上界<input type="number" value={asset.ceiling??''} disabled={project.read_only} placeholder="按采集记录填写" onChange={e=>onEdit(p=>p.images.find(a=>a.id===asset.id)!.ceiling=e.target.value?Number(e.target.value):null)}/></label><p className="hint">显示反色只改变画面。原始信号方向参与计算；暗信号需提供有效编码上界。</p><p className="hint">原始文件：{asset.name}；第 {(asset.page_index??0)+1} 页。</p></>}{role==='target'&&<><button className="btn secondary" disabled={!region||busy||project.read_only} onClick={()=>adjust((p,l)=>alignLaneLayout(p,l,{dx:0,dy:0,scaleX:.97,anchorX:(asset?.width??0)/2}))}>缩小泳道间距</button><button className="btn secondary" disabled={!region||busy||project.read_only} onClick={()=>adjust((p,l)=>alignLaneLayout(p,l,{dx:0,dy:0,scaleX:1.03,anchorX:(asset?.width??0)/2}))}>增大泳道间距</button></>}</details>
 </aside></div>
}
