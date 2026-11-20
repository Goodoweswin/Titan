import type {AnalysisResult,Project} from './types'

export type TutorialView='workspace'|'samples'|'results'|'wb'|'other'
export interface WbEditorState{
 projectId:string;revision:number;imageId:string;setId:string;regionEdits:number;laneSelections:number;identifications:number
 selectedLane:string;hasRegion:boolean;hasPreview:boolean;unresolved:number;backgroundsReady:boolean;busy:boolean
}
export interface WbFigureState{projectId:string;revision:number;documentId:string|null;version:string|null;allConfirmed:boolean;saved:boolean;ready:boolean}
export interface WbExportProof{projectId:string;revision:number;documentId:string;version:string}
export interface TutorialRun{projectId:string;step:number;status:'active'|'dismissed'|'completed';baseline:{regionEdits:number;laneSelections:number;identifications:number}}
export interface TutorialContext{project:Project;view:TutorialView;active:boolean;editor:WbEditorState|null;figure:WbFigureState|null;result:AnalysisResult|null;exported:WbExportProof|null}
export const tutorialSteps=[
 {title:'查看原图',text:'先看清第 2 页的中间条带和两侧 Marker。9 条蓝框是供检查的教学模板，蛋白和样本信息留空。'},
 {title:'框选条带区域',text:'点击“选择区域”，在原图上拖出覆盖中间一整行条带的矩形，避开两侧 Marker。建议原图范围 x 800–2040，y 1200–1380。'},
 {title:'核对泳道',text:'点击“调整泳道”，再点选一条蓝色泳道或下方的泳道编号，核对蓝框是否覆盖对应条带。正确的位置可以保留。'},
 {title:'识别峰区',text:'点击右侧“识别目标”。等待绿框建议；出现“选择峰”的泳道，需要根据原图和曲线选择正确的主峰。'},
 {title:'检查峰区与背景',text:'核对绿框是否包住信号，背景框是否避开条带。需要修正时，展开右栏「手动调整与图像信息」。'},
 {title:'确认测量',text:'核对每条泳道的峰区与背景后，点击右侧“确认目标”。这一步才会把建议写入当前分析，并记录人工复核。'},
 {title:'查看正式结果',text:'点击“结果”，查看目标净积分和状态。本示范未提供配套内参，因此比值保留为空并提示缺少参考。样本设置、统计与图表均使用正式页面。'},
 {title:'组图与导出',text:'进入“WB 组图”，创建组图并确认裁剪，然后保存组图、导出文件。教程只在实际导出成功后完成。'},
] as const
const zero=()=>({regionEdits:0,laneSelections:0,identifications:0})
export function createTutorial(projectId:string):TutorialRun{return {projectId,step:0,status:'active',baseline:zero()}}
export function tutorialStepState(run:TutorialRun,c:TutorialContext){
 const required:TutorialView=run.step===6?'results':run.step===7?'wb':'samples'
 const out={ready:false,target:'canvas',message:'请完成当前操作后继续。',recovery:false,required}
 if(!c.active||run.projectId!==c.project.id||run.status!=='active')return out
 if(c.view!==required)return {...out,target:'nav-'+required,message:`请先前往${required==='results'?'结果':required==='wb'?'WB 组图':'目标'}页。`}
 if(c.project.read_only)return {...out,message:'当前分析为只读，请先另存可写副本再练习。'}
 const group=c.project.band_sets.find(g=>g.role==='target'),layout=c.project.lane_layouts.find(l=>l.id===group?.layout_id)
 const e=c.editor&&c.editor.projectId===c.project.id&&c.editor.revision===c.project.revision&&c.editor.imageId===layout?.image_id&&c.editor.setId===group?.id?c.editor:null
 const committed=!!group&&group.assignments.some(a=>a.status==='accepted')&&group.assignments.every(a=>a.status!=='pending'&&(a.status!=='accepted'||c.project.rois.some(r=>r.id===a.roi_id&&r.band_set_id===group.id&&r.reviewed_revision===c.project.revision)))
 if(run.step===0)return {...out,ready:true,target:'canvas',message:'查看后，点击“下一步”开始实际操作。'}
 if(run.step===1)return {...out,ready:!!e&&!e.busy&&e.hasRegion&&e.regionEdits>run.baseline.regionEdits,target:'tool-region',message:'请亲自在画布上拖选一次区域；预设框不会自动算作完成。'}
 if(run.step===2)return {...out,ready:!!e&&!e.busy&&!!e.selectedLane&&e.laneSelections>run.baseline.laneSelections,target:'lane-list',message:'请点选一条泳道，核对它与原图的对应。'}
 if(run.step===3)return {...out,ready:!!e&&!e.busy&&e.hasPreview&&e.identifications>0&&e.unresolved===0,target:e?.hasPreview?'lane-list':'identify-target',message:e?.unresolved?'仍有多个峰的泳道，请先选择目标峰。':'请识别目标，等待建议返回并核对所有峰。'}
 if(run.step===4)return {...out,ready:!!e&&!e.busy&&e.hasPreview&&e.unresolved===0&&e.backgroundsReady,target:e?.hasPreview&&!e.backgroundsReady?'lane-correction':'lane-list',recovery:!e?.hasPreview,message:!e?.hasPreview?'本次未确认的峰区建议已不在编辑器中，请返回识别步骤。':e.unresolved?'请先选择目标峰。':!e.backgroundsReady?'有峰区缺少可用背景，请在右栏展开手动调整并补画背景。':'核对自动建议后，点击“下一步”。'}
 if(run.step===5){const ready=committed&&!!e&&!e.busy&&!e.hasPreview;return {...out,ready,target:'confirm-target',recovery:!committed&&!e?.hasPreview,message:ready?'当前测量已确认。':'请使用正式“确认目标”按钮；新的建议仍需确认，浏览建议不会记录复核。'}}
 if(run.step===6){const r=c.result;return {...out,ready:committed&&!!r&&r.project_id===c.project.id&&r.input_revision===c.project.revision&&!!r.lane_results?.some(row=>row.band_set_id===group?.id&&row.target_roi_id),target:'result-table',message:'等待当前版本的正式结果。缺少内参的空比值不是零值。'}}
 const f=c.figure&&c.figure.projectId===c.project.id&&c.figure.revision===c.project.revision?c.figure:null
 const x=c.exported
 const ready=!!f?.saved&&!!x&&x.projectId===c.project.id&&x.revision===c.project.revision&&x.documentId===f.documentId&&x.version===f.version
 if(!f?.documentId)return {...out,target:'figure-new',message:'点击“新建组图”，使用当前原图创建条带组图。'}
 if(!f.allConfirmed)return {...out,target:'figure-confirm',message:'检查原图裁剪；可拖动裁剪框或填写坐标，然后逐行点击“确认本行裁剪”。'}
 if(!f.saved)return {...out,target:'figure-save',message:'点击“保存组图”。首次保存会先让你选择分析保存位置；请使用新目录。'}
 return {...out,ready,target:'figure-export',message:ready?'PNG、PDF、SVG 与来源说明已成功导出。':f.ready?'点击“导出组图”并选择新文件夹；取消或失败不会完成教程。':'正在生成组图预览，请稍候。'}
}
export function advanceTutorial(run:TutorialRun,c:TutorialContext):TutorialRun{
 if(!tutorialStepState(run,c).ready)return run
 if(run.step===7)return {...run,status:'completed'}
 const e=c.editor
 return {...run,step:run.step+1,baseline:e?{regionEdits:e.regionEdits,laneSelections:e.laneSelections,identifications:e.identifications}:zero()}
}
export function wbExportProof(project:Project,figure:WbFigureState|null,receipt:unknown):WbExportProof|null{
 if(!figure?.saved||!figure.documentId||!figure.version||figure.projectId!==project.id||figure.revision!==project.revision)return null
 const r=receipt as {path?:unknown;outputs?:Record<string,unknown>}|null
 if(typeof r?.path!=='string'||!r.path||!r.outputs||!['figure.png','figure.pdf','figure.svg','source.json'].every(k=>typeof r.outputs![k]==='string'&&!!r.outputs![k]))return null
 return {projectId:project.id,revision:project.revision,documentId:figure.documentId,version:figure.version}
}

const storageKey='titan-wb-tutorial-v1'
type StorageAccess=Pick<Storage,'getItem'|'setItem'>
type Stored={projectId:string;step:number;status:TutorialRun['status'];updated:number}
function records(storage:StorageAccess):Stored[]{
 try{const raw=JSON.parse(storage.getItem(storageKey)??'[]');return Array.isArray(raw)?raw.filter((r:Stored)=>r&&typeof r.projectId==='string'&&Number.isInteger(r.step)&&r.step>=0&&r.step<8&&['active','dismissed','completed'].includes(r.status)&&Number.isFinite(r.updated)).slice(-20):[]}catch{return []}
}
export function loadTutorial(storage:StorageAccess,projectId:string):TutorialRun{
 const record=records(storage).find(r=>r.projectId===projectId)
 return record?{...createTutorial(projectId),step:record.step,status:record.status}:createTutorial(projectId)
}
export function saveTutorial(storage:StorageAccess,run:TutorialRun,now=Date.now()){
 try{const all=records(storage).filter(r=>r.projectId!==run.projectId);all.push({projectId:run.projectId,step:run.step,status:run.status,updated:now});storage.setItem(storageKey,JSON.stringify(all.sort((a,b)=>a.updated-b.updated).slice(-20)))}catch{/* In-memory teaching remains usable. */}
}
