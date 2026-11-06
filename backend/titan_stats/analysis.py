"""Explicit analysis runs with immutable inputs and shared numerical methods."""
from datetime import datetime,timezone
from scipy import __version__ as scipy_version
from .models import prepared,signature,snapshot,uid
from .core import compare,compare_multigroup,group_summary

def analyze(d):
    values,missing,excluded=prepared(d);s=d['analysis'];method=s['method'];groups=[g['id'] for g in d['groups']]
    if method not in ['descriptive','welch','paired','anova','welch_anova']:raise ValueError('不支持的统计方法')
    if method!='descriptive' and not d.get('confirmed'):raise ValueError('请先确认每个数值代表独立生物学单位，或已明确配对')
    if method!='descriptive' and d.get('source',{} ) and d['source'].get('blocked'):raise ValueError(d['source']['blocked'])
    summaries=[dict(group=g['id'],label=g['label'],**group_summary([v['value'] for v in values if v['group']==g['id']])) for g in d['groups']]
    comparisons=[];omnibus=None
    if method in ['welch','paired']:
        if len(groups)!=2:raise ValueError('两组检验需要恰好两个组')
        row=compare(values,dict(id='two',family_id='two',test=method,scale=s['scale'],group_a=groups[0],group_b=groups[1]))
        row.update(group_a=groups[0],group_b=groups[1],p_adjusted=row['p_raw'],adjustment_method='none',ci_method='pointwise_95',status='valid',scale=s['scale'])
        comparisons=[row]
    elif method in ['anova','welch_anova']:
        result=compare_multigroup(values,dict(id='multi',**s,groups=groups))
        omnibus=result['omnibus'];comparisons=result['comparisons']
    names={'descriptive':'仅描述统计','welch':'双侧 Welch 独立样本 t 检验','paired':'双侧配对 t 检验','anova':'普通单因素 ANOVA','welch_anova':'Welch 单因素 ANOVA'}
    correction=comparisons[0]['adjustment_method'] if comparisons else '无'
    method_text=f"{names[method]}；分析尺度：{s['scale']}；组对校正：{correction}。效应方向 B−A。缺失单元格 {missing}，排除单元格 {excluded}。"
    if correction=='games_howell':method_text+=' Games–Howell 按所选组的全部两两比较校正，即使只显示与对照比较。'
    if correction=='dunnett':method_text+=' Dunnett 使用固定种子 0 的数值积分近似。'
    if method in ['welch','paired']:method_text+=' 单一预设对比未作多重校正；95% CI 为该差值的普通区间。'
    return dict(id=uid(),signature=signature(d),created_at=datetime.now(timezone.utc).isoformat(),dataset=snapshot(d),summaries=summaries,comparisons=comparisons,omnibus=omnibus,method_text=method_text,scipy_version=scipy_version)
