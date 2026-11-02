import type {ActiveJob,IFField,IFProject,Point} from './types'
export function originalPoint(x:number,y:number,b:{left:number;top:number;width:number;height:number},width:number,height:number):Point{return [Math.max(0,Math.min(width,(x-b.left)/b.width*width)),Math.max(0,Math.min(height,(y-b.top)/b.height*height))]}
export function editField(p:IFProject,id:string,change:(f:IFField)=>void,kind:'display'|'analysis'|'segmentation'='analysis'){
 const next=structuredClone(p),field=next.fields.find(f=>f.id===id);if(!field||p.read_only)return p;change(field);next.revision++
 if(kind!=='display')field.result=null;const old=p.fields.find(f=>f.id===id)!;const segmentationChanged=JSON.stringify([old.rois,old.channels.map(c=>[c.id,c.name,c.source]),old.recipe.nuclear_channel_id,old.recipe.segmentation])!==JSON.stringify([field.rois,field.channels.map(c=>[c.id,c.name,c.source]),field.recipe.nuclear_channel_id,field.recipe.segmentation]);if(kind==='segmentation'||segmentationChanged)field.mask=null;return next
}
export function canAcceptJob(id:string,epoch:number,active:ActiveJob|null,p:IFProject|null){return !!active&&active.job_id===id&&active.epoch===epoch&&active.project_id===p?.id}
export function mergeSaved(current:IFProject,before:IFProject,saved:IFProject){if(current.id!==before.id||current.project_path!==before.project_path)return current;return current.revision===before.revision?saved:{...current,project_path:saved.project_path,saved_revision:saved.saved_revision}}
function exactAdd(a:number|string,b:number|string):number|string{
 if((typeof a==='string'||Number.isInteger(a))&&(typeof b==='string'||Number.isInteger(b))){const sum=BigInt(a)+BigInt(b);return sum>BigInt(Number.MAX_SAFE_INTEGER)||sum<BigInt(Number.MIN_SAFE_INTEGER)?sum.toString():Number(sum)}return Number(a)+Number(b)
}
export function aggregateRows(p:IFProject):{objects:any[];fields:any[];samples:any[];issues:string[]}{
 const objects:any[]=[],fields:any[]=[],samples:any[]=[];const groups=new Map<string,any>(),thresholds=new Map<string,string>(),conflicts=new Set<string>()
 for(const f of p.fields){if(!f.result)continue;const meta={field_id:f.id,field_name:f.name,sample_id:f.sample_id,bio_id:f.bio_id,group:f.group,batch_id:f.batch_id}
  for(const row of f.result.objects)objects.push({...meta,...row,channel_name:f.channels.find(c=>c.id===row.channel_id)?.name??row.channel_id})
  for(const row of f.result.summary){const channel=f.channels.find(c=>c.id===row.channel_id)?.name??row.channel_id;fields.push({...meta,...row,channel_name:channel});if(!f.bio_id?.trim())continue;const comparable=JSON.stringify([f.batch_id,channel]),setting=JSON.stringify([f.recipe.mode,f.recipe.thresholds[row.channel_id]??null,f.recipe.thresholds_frozen,row.positive_pixels==null?'':f.recipe.threshold_source]);if(thresholds.has(comparable)&&thresholds.get(comparable)!==setting)conflicts.add(comparable);thresholds.set(comparable,setting);const key=JSON.stringify([f.bio_id,f.group,f.batch_id,channel]);let g=groups.get(key);if(!g){g={bio_id:f.bio_id,group:f.group,batch_id:f.batch_id,channel_name:channel,field_count:0,object_count:0,area_px:0,raw_sum:0,corrected_sum:0,area_um2:0,positive_count:0,positive_pixels:0};groups.set(key,g)}g.field_count++;g.object_count+=row.object_count??0;g.area_px+=row.area_px;g.raw_sum=exactAdd(g.raw_sum,row.raw_sum)
   for(const k of ['corrected_sum','area_um2','positive_count','positive_pixels'] as const){if(row[k]==null)g[k]=null;else if(g[k]!==null)g[k]=exactAdd(g[k],row[k]!)}
  }
 }
 for(const g of groups.values()){if(conflicts.has(JSON.stringify([g.batch_id,g.channel_name])))continue;samples.push({...g,mean:g.area_px?Number(g.raw_sum)/g.area_px:null,positive_fraction:g.positive_count==null||!g.object_count?null:g.positive_count/g.object_count,positive_area_fraction:g.positive_pixels==null||!g.area_px?null:g.positive_pixels/g.area_px})}
 return {objects,fields,samples,issues:[...conflicts].map(key=>{const [batch,channel]=JSON.parse(key);return `批次 ${batch} 的 ${channel} 分析方式或阳性阈值不一致，暂不合并生物学样本。`})}
}

export function copyRecipe(p:IFProject,sourceId:string,targetIds:string[]):IFProject{
 if(p.read_only)throw new Error('只读实验不能应用模板');const next=structuredClone(p),source=next.fields.find(f=>f.id===sourceId);if(!source)throw new Error('模板来源视野不存在')
 for(const id of targetIds){const f=next.fields.find(f=>f.id===id);if(!f)throw new Error('目标视野不存在');if(source.recipe.thresholds_frozen&&source.batch_id!==f.batch_id)throw new Error('冻结阈值只能应用于相同采集批次')
  const map=(id:string)=>{const name=source.channels.find(c=>c.id===id)?.name,matches=f.channels.filter(c=>c.name===name);if(matches.length!==1)throw new Error(`${f.name} 的 ${name??id} 通道缺失或名称重复`);return matches[0].id}
  const recipe=structuredClone(source.recipe);recipe.nuclear_channel_id=map(recipe.nuclear_channel_id);recipe.target_channel_ids=recipe.target_channel_ids.map(map);recipe.thresholds=Object.fromEntries(Object.entries(recipe.thresholds).map(([id,value])=>[map(id),value]));const changed=JSON.stringify(f.recipe.segmentation)!==JSON.stringify(recipe.segmentation)||f.recipe.nuclear_channel_id!==recipe.nuclear_channel_id;f.recipe=recipe;f.result=null;if(changed)f.mask=null
 }
 next.revision++;return next
}

export function undoMask(p:IFProject,id:string):IFProject{if(p.read_only)return p;const next=structuredClone(p),field=next.fields.find(f=>f.id===id),mask=field?.mask,previous=mask?.history?.at(-1);if(!field||!mask||!previous)return p;field.mask={...previous,version:mask.version+1,history:mask.history!.slice(0,-1),confirmed:false};field.result=null;next.revision++;return next}
