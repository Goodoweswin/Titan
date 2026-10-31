import type {AnalysisResult,Project} from './types'
import {projectIssues} from './workflow'
export default function QualityPanel({project,result,onLocate}:{project:Project;result:AnalysisResult|null;onLocate:(id:string)=>void}){
 const issues=projectIssues(project,result),warnings=issues.filter(i=>i.severity==='warning')
 if(!issues.length)return null
 return <details className="quality-panel"><summary>质量问题与提示 <span>{warnings.length} 项需处理 · {issues.length-warnings.length} 项说明</span></summary><p className="hint">点击定位原始条带。计算后还会显示像素与归一化检查结果。</p><div className="issue-list">{issues.map(i=>{const roi=project.rois.find(r=>r.id===i.roiId);return <button key={`${i.roiId}:${i.code}`} className={`issue ${i.severity}`} onClick={()=>onLocate(i.roiId)}>{roi?.lane_id} · {roi?.analyte}：{i.label}</button>})}</div></details>
}
