import type {ImageAsset,Project,Rect} from './types'

export interface WbSource extends ImageAsset {display_range:[number,number];source_width?:number|null;source_height?:number|null}
export interface WbRow {id:string;protein:string;source:WbSource;crop:Rect;confirmed:boolean;expected_mw:string;markers:{text:string;y:number}[];layout_id?:string}
export interface WbLabel {text:string;x:number}
export interface WbSettings {width_mm:number;image_width_mm:number;font_pt:number;gap_mm:number;dpi:300|600}
export interface WbDocument {schema_version:1;id:string;project_id:string;name:string;version:string|null;updated_at?:string;settings:WbSettings;rows:WbRow[];labels:WbLabel[];synthetic?:boolean}
export interface WbEntry {id:string;name:string;version:string;updated_at:string}
export interface WbPreview {png:string;width_mm:number;height_mm:number;layout:{rows:{id:string;effective_dpi:number}[]}}
export const defaultWbSettings:WbSettings={width_mm:85,image_width_mm:0,font_pt:8,gap_mm:3,dpi:300}
export function resetWbStyle(document:WbDocument):WbDocument{return {...document,settings:{...defaultWbSettings}}}
export function rebindWbSources(document:WbDocument,project:Project,previousPath?:string):WbDocument{
 const next=structuredClone(document),normal=(path:string)=>path.replaceAll('\\','/').replace(/\/$/,'')
 for(const row of next.rows){
  const asset=project.images.find(a=>a.id===row.source.id&&a.sha256===row.source.sha256)
  if(asset)row.source.path=asset.path
  else if(previousPath&&project.project_path){
   const prefix=normal(previousPath)+'/originals/',path=normal(row.source.path)
   if(path.startsWith(prefix))row.source.path=normal(project.project_path)+'/originals/'+path.slice(prefix.length)
  }
 }
 return next
}
export function cropRect(from:[number,number],to:[number,number],width:number,height:number):Rect|null{
 const clamp=(v:number,max:number)=>Math.min(max,Math.max(0,Math.round(v)))
 const [a,b]=[clamp(from[0],width),clamp(from[1],height)],[c,d]=[clamp(to[0],width),clamp(to[1],height)]
 if(a===c||b===d)return null
 return [Math.min(a,c),Math.min(b,d),Math.max(a,c),Math.max(b,d)]
}
export function proposedLabels(project:Project,rows:WbRow[]):{labels:WbLabel[];warning:string}{
 if(!rows.length)return {labels:[],warning:''}
 const proposals=rows.map(row=>{
  const layout=project.lane_layouts.find(l=>l.id===row.layout_id)
  if(!layout)return null
  return layout.columns.filter(c=>c.rect[0]>=row.crop[0]&&c.rect[2]<=row.crop[2]).map(column=>{
   const lane=project.lanes.find(l=>l.id===column.lane_id),sample=project.samples.find(s=>s.id===lane?.sample_id)
   return {text:sample?.name||sample?.id||'',x:((column.rect[0]+column.rect[2])/2-row.crop[0])/(row.crop[2]-row.crop[0]),sample_id:sample?.id}
  })
 })
 if(proposals.every(p=>p===null))return {labels:[],warning:''}
 const first=proposals[0]
 if(!first?.length||proposals.some(p=>!p||p.length!==first.length||p.some((c,i)=>!c.sample_id||c.sample_id!==first[i].sample_id||Math.abs(c.x-first[i].x)>.01)))return {labels:[],warning:'各行的样本顺序或位置不同，请核对后手动填写顶部标签。'}
 return {labels:first.map(({text,x})=>({text,x})),warning:''}
}
