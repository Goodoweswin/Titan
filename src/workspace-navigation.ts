import type {Tool} from './ToolHome'

export type Screen={kind:'home'}|{kind:'project';id:string}|{kind:'tool';tool:Tool}|{kind:'analysis'}
export interface ModuleView {
 path?:string|null
 projectId?:string
 name?:string
 view?:string
 resourceId?:string
 artifactId?:string
 versionId?:string
 runId?:string
 busy?:boolean
}
export interface AnalysisLocation extends Omit<ModuleView,'busy'> {
 kind:'analysis'
 module:Tool
 projectId:string
 view:string
 entryId?:string
 manualMode?:boolean
 activeSetId?:string
 roiId?:string
}
export type WorkspaceLocation=Exclude<Screen,{kind:'analysis'}>|AnalysisLocation
export interface NavigationHistory {entries:WorkspaceLocation[];index:number}

export function locationKey(location:WorkspaceLocation):string {
 if(location.kind==='home')return 'home'
 if(location.kind==='project')return 'project:'+location.id
 if(location.kind==='tool')return 'tool:'+location.tool
 return JSON.stringify([location.module,location.entryId??location.path??location.projectId,location.projectId,location.view,location.resourceId,
  location.artifactId,location.versionId,location.runId,location.manualMode,location.activeSetId])
}
function sameAnalysis(a:AnalysisLocation,b:AnalysisLocation):boolean {
 const identity=a.entryId&&b.entryId?a.entryId===b.entryId:a.path&&b.path?a.path===b.path:a.projectId===b.projectId
 return !!identity&&a.module===b.module&&a.projectId===b.projectId
}
export function sameLocation(a:WorkspaceLocation,b:WorkspaceLocation):boolean {
 if(a.kind!=='analysis'||b.kind!=='analysis')return locationKey(a)===locationKey(b)
 return sameAnalysis(a,b)&&locationKey({...a,entryId:b.entryId,path:b.path})===locationKey(b)
}
export function createHistory(location:WorkspaceLocation):NavigationHistory {return {entries:[location],index:0}}
export function recordLocation(history:NavigationHistory,location:WorkspaceLocation):NavigationHistory {
 if(location.kind==='analysis'&&location.path){
  // First save/registration gives earlier visits to the same live draft a
  // durable address. A separately registered saved copy keeps its own entry.
  history={...history,entries:history.entries.map(entry=>entry.kind==='analysis'&&entry.module===location.module&&
   entry.projectId===location.projectId&&!entry.entryId&&(!entry.path||entry.path===location.path)?
   {...entry,path:location.path,entryId:location.entryId}:entry)}
 }
 if(location.kind==='analysis'&&location.resourceId){
  history={...history,entries:history.entries.map(entry=>entry.kind==='analysis'&&!entry.resourceId&&sameAnalysis(entry,location)?
   {...entry,resourceId:location.resourceId}:entry)}
 }
 if(sameLocation(history.entries[history.index],location)){
  const entries=[...history.entries];entries[history.index]=location
  return {...history,entries}
 }
 const entries=[...history.entries.slice(0,history.index+1),location].slice(-100)
 return {entries,index:entries.length-1}
}
export function historyTarget(history:NavigationHistory,direction:-1|1){
 const index=history.index+direction
 return index<0||index>=history.entries.length?null:{index,location:history.entries[index]}
}
export function moveHistory(history:NavigationHistory,index:number):NavigationHistory {
 return index<0||index>=history.entries.length?history:{...history,index}
}
