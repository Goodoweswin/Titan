import type {AnalysisResult,Project} from './types'

export interface ResearchActivity {
 version:1
 startedAt:string
 images:Record<string,string>
 bands:Record<string,string>
}
export const activityStorageKey='titan-research-activity-v1'
export function localDay(date=new Date()) {
 return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`
}
export function newActivity(now=new Date()):ResearchActivity {
 return {version:1,startedAt:now.toISOString(),images:{},bands:{}}
}
export function parseActivity(raw:string):ResearchActivity {
 const data=JSON.parse(raw)
 const validMap=(value:unknown)=>!!value&&typeof value==='object'&&!Array.isArray(value)&&Object.values(value).every(day=>typeof day==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(day)&&Number.isFinite(new Date(day+'T12:00:00').getTime()))
 if(data?.version!==1||typeof data.startedAt!=='string'||!Number.isFinite(Date.parse(data.startedAt))||!validMap(data.images)||!validMap(data.bands))throw new Error('研究足迹记录无法读取，原记录已保留。')
 return data
}
/** Count completed measurements once per project/image/ROI identity, not per recomputation. */
export function recordAnalysis(activity:ResearchActivity,project:Project,result:AnalysisResult,now=new Date()):ResearchActivity {
 if((project as Project&{demo?:boolean;synthetic?:boolean}).demo||(project as Project&{synthetic?:boolean}).synthetic||result.project_id!==project.id||result.input_revision!==project.revision)return activity
 const images={...activity.images},bands={...activity.bands},day=localDay(now)
 let changed=false
 for(const measurement of result.measurements){
  if(!Number.isFinite(measurement.corrected_sum))continue
  const roi=project.rois.find(roi=>roi.id===measurement.id&&roi.image_id===measurement.image_id)
  const image=project.images.find(image=>image.id===measurement.image_id)
  if(!roi||!image)continue
  const imageKey=JSON.stringify([project.id,image.sha256||image.id,image.page_index??0])
  const bandKey=JSON.stringify([imageKey,roi.id])
  if(!images[imageKey]){images[imageKey]=day;changed=true}
  if(!bands[bandKey]){bands[bandKey]=day;changed=true}
 }
 return changed?{...activity,images,bands}:activity
}
export function activitySummary(activity:ResearchActivity,now=new Date()) {
 const images=Object.values(activity.images),bands=Object.values(activity.bands)
 const days=new Set([...images,...bands]),today=localDay(now),month=today.slice(0,7)
 const cursor=new Date(now.getFullYear(),now.getMonth(),now.getDate(),12)
 // Yesterday still belongs to an ongoing streak until today ends.
 if(!days.has(today))cursor.setDate(cursor.getDate()-1)
 let streak=0
 while(days.has(localDay(cursor))){streak++;cursor.setDate(cursor.getDate()-1)}
 return {images:images.length,bands:bands.length,days:days.size,streak,monthImages:images.filter(day=>day.startsWith(month)).length,monthBands:bands.filter(day=>day.startsWith(month)).length}
}
export function activityCalendar(activity:ResearchActivity,metric:'images'|'bands',now=new Date()) {
 const counts=new Map<string,number>()
 Object.values(activity[metric]).forEach(day=>counts.set(day,(counts.get(day)??0)+1))
 const end=new Date(now.getFullYear(),now.getMonth(),now.getDate(),12)
 end.setDate(end.getDate()+6-(end.getDay()+6)%7)
 const start=new Date(end);start.setDate(start.getDate()-139)
 const today=localDay(now),started=localDay(new Date(activity.startedAt))
 return Array.from({length:140},(_,index)=>{
  const date=new Date(start);date.setDate(start.getDate()+index)
  const day=localDay(date)
  return {day,count:counts.get(day)??0,untracked:day<started,future:day>today}
 })
}
