import type {Project} from './types'
export default function ComparisonEditor({project,onEdit}:{project:Project;onEdit:(f:(p:Project)=>void)=>void}){
 const groups=Array.from(new Set(project.samples.filter(s=>s.kind!=='ibc').map(s=>s.group)))
 return <fieldset className="card advanced" disabled={project.read_only}><div className="card-heading"><h3>预先指定统计比较</h3><button className="btn secondary" onClick={()=>onEdit(p=>{
  let n=1;while(p.settings.comparisons.some(c=>c.id===`C${n}`))n++
  p.settings.comparisons.push({id:`C${n}`,family_id:'primary',group_a:groups[0]??'control',group_b:groups[1]??'treated',test:'descriptive',scale:'raw'})
 })}>添加比较</button></div><p className="hint">在计算前指定比较。默认仅描述；同膜支持两独立组 Welch 或明确配对的两组 t 检验。同一比较族执行 Holm 校正。</p>
 {project.settings.comparisons.map((s,i)=><div className="comparison" key={s.id}><strong>{s.id}</strong>{(['group_a','group_b'] as const).map(k=><label key={k}>{k==='group_a'?'A 组':'B 组'}<select aria-label={`${k} ${s.id}`} value={s[k]} onChange={e=>onEdit(p=>p.settings.comparisons[i][k]=e.target.value)}>{Array.from(new Set([...groups,s[k]])).map(g=><option key={g}>{g}</option>)}</select></label>)}<label>检验<select aria-label={`检验 ${s.id}`} value={s.test} onChange={e=>onEdit(p=>p.settings.comparisons[i].test=e.target.value as typeof s.test)}><option value="descriptive">仅描述</option><option value="welch">独立组 Welch t</option><option value="paired">配对 t</option></select></label><label>分析尺度<select value={s.scale} onChange={e=>onEdit(p=>p.settings.comparisons[i].scale=e.target.value as typeof s.scale)}><option value="raw">原始归一化值</option><option value="log2">log2 归一化值</option></select></label><label>比较族<input aria-label={`比较族 ${s.id}`} value={s.family_id} onChange={e=>onEdit(p=>p.settings.comparisons[i].family_id=e.target.value)}/></label><button className="text-btn" onClick={()=>onEdit(p=>p.settings.comparisons.splice(i,1))}>移除</button></div>)}
 <p className="hint">修改分析设置需重新计算，已有图像复核保持有效。多膜结果仅作描述性分析。</p></fieldset>
}
