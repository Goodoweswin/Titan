"""Explicit independent-group inference, separate from legacy Holm families."""
import itertools
import math
import numpy as np
from scipy import stats,__version__ as scipy_version


def group_summary(values):
    data=np.asarray(values,dtype=float)
    if data.ndim!=1 or not np.isfinite(data).all():raise ValueError('描述统计含非有限值')
    n=int(data.size)
    result=dict(n=n,mean=float(data.mean()) if n else None,sd=None,sem=None,ci95=None)
    if n>1:
        sd=float(data.std(ddof=1));sem=sd/math.sqrt(n);margin=float(stats.t.ppf(.975,n-1))*sem
        if not all(math.isfinite(v) for v in [sd,sem,margin]):raise ValueError('描述统计数值超出可计算范围')
        result.update(sd=sd,sem=sem,ci95=[result['mean']-margin,result['mean']+margin])
    return result


def _spec(spec):
    if not isinstance(spec,dict):raise ValueError('多组比较设置无效')
    for key in ['id','analyte','membrane_id']:
        if not isinstance(spec.get(key),str) or not spec[key].strip():raise ValueError('请明确比较ID、蛋白与分析膜')
    groups=spec.get('groups')
    if not isinstance(groups,list) or len(groups)<3 or any(not isinstance(g,str) or not g.strip() for g in groups) or len(set(groups))!=len(groups):raise ValueError('独立多组比较需要至少三个不重复的组')
    if spec.get('method') not in ['descriptive','anova','welch_anova']:raise ValueError('请选择明确的多组检验方法')
    if spec.get('scale') not in ['raw','log2'] or spec.get('scope') not in ['control','all']:raise ValueError('请明确分析尺度与比较范围')
    if spec['scope']=='control' and spec.get('control_group') not in groups:raise ValueError('对照组必须在本次所选组中')
    if '+' in spec['membrane_id']:raise ValueError('多膜合并不能直接使用无批次项的普通多组检验')
    return groups


def _ratio(value):
    result=float(np.exp2(value))
    if not math.isfinite(result) or result<=0:raise ValueError('log2效应反变换超出可表示范围')
    return result


def compare_multigroup(values,spec):
    groups=_spec(spec)
    selected=[v for v in values if v.get('analyte')==spec['analyte'] and v.get('analysis_block',v.get('membrane_id'))==spec['membrane_id'] and v.get('group') in groups]
    if any(v.get('membrane_id')!=spec['membrane_id'] for v in selected):raise ValueError('多膜数据不能使用无批次项的独立多组检验')
    ids=[v.get('bio_id') for v in selected]
    if any(not id for id in ids) or len(set(ids))!=len(ids):raise ValueError('同一生物学单位不能重复计入n或跨独立组共享；请确认独立设计')
    arrays=[np.asarray([v['value'] for v in selected if v['group']==group],dtype=float) for group in groups]
    if any(not np.isfinite(a).all() for a in arrays):raise ValueError('统计数据含非有限值，不能静默剔除')
    n_by_group={g:len(a) for g,a in zip(groups,arrays)}
    base=dict(comparison_id=spec['id'],analyte=spec['analyte'],membrane_id=spec['membrane_id'],analysis_block=spec['membrane_id'],scale=spec['scale'],method=spec['method'],groups=groups,n_by_group=n_by_group,family_id=f"{spec['id']}:{spec['analyte']}:{spec['membrane_id']}",scipy_version=scipy_version)
    omnibus={**base,'status':'descriptive','statistic':None,'df_num':None,'df_den':None,'p_raw':None,'warnings':[]}
    if spec['method']=='descriptive':return dict(omnibus=omnibus,comparisons=[])
    if any(len(a)<2 for a in arrays):raise ValueError('每组至少需要2个有效独立单位；缺失不能补零或静默丢组（不代表样本量充分）')
    if spec['scale']=='log2':
        if any(np.any(a<=0) for a in arrays):raise ValueError('log2分析仅接受正值')
        arrays=[np.log2(a) for a in arrays]
    variances=np.asarray([a.var(ddof=1) for a in arrays]);sizes=np.asarray([len(a) for a in arrays],float);k=len(groups)
    if not np.isfinite(variances).all() or variances.sum()<=0:raise ValueError('组内方差均为零或数值退化，无法进行此检验')
    equal=spec['method']=='anova'
    if not equal and np.any(variances<=0):raise ValueError('Welch/Games–Howell需要各组非零方差，当前输入退化')
    result=stats.f_oneway(*arrays,equal_var=equal)
    if not math.isfinite(float(result.statistic)) or not math.isfinite(float(result.pvalue)):raise ValueError('多组检验数值退化')
    if equal:df_den=float(sizes.sum()-k)
    else:
        weights=sizes/variances
        term=np.sum((1-weights/weights.sum())**2/(sizes-1))
        df_den=float((k*k-1)/(3*term))
    omnibus.update(status='valid',statistic=float(result.statistic),df_num=k-1,df_den=df_den,p_raw=float(result.pvalue))
    rows=[]
    if equal and spec['scope']=='control':
        control=groups.index(spec['control_group']);treatments=[i for i in range(k) if i!=control]
        test=stats.dunnett(*(arrays[i] for i in treatments),control=arrays[control],alternative='two-sided',rng=np.random.default_rng(0))
        ci=test.confidence_interval(.95)
        for index,b in enumerate(treatments):
            rows.append(dict(group_a=groups[control],group_b=groups[b],effect=float(arrays[b].mean()-arrays[control].mean()),statistic=float(test.statistic[index]),p_adjusted=float(test.pvalue[index]),ci95=[float(ci.low[index]),float(ci.high[index])],adjustment_method='dunnett',family_scope='treatments_vs_control',rng_seed=0))
    else:
        test=stats.tukey_hsd(*arrays,equal_var=equal);ci=test.confidence_interval(.95)
        control=groups.index(spec['control_group']) if spec['scope']=='control' else None
        # Compute the full all-pairs family even when the UI shows only control pairs.
        pairs=itertools.combinations(range(k),2) if control is None else ((control,b) for b in range(k) if b!=control)
        for a,b in pairs:
            rows.append(dict(group_a=groups[a],group_b=groups[b],effect=float(arrays[b].mean()-arrays[a].mean()),statistic=None,p_adjusted=float(test.pvalue[a,b]),ci95=[-float(ci.high[a,b]),-float(ci.low[a,b])],adjustment_method='tukey' if equal else 'games_howell',family_scope='all_pairs'))
    for row in rows:
        if not all(math.isfinite(v) for v in [row['effect'],row['p_adjusted'],*row['ci95']]) or not 0<=row['p_adjusted']<=1:raise ValueError('多重比较的效应、区间或p值数值退化')
        row.update(base,display_scope=spec['scope'],p_raw=None,ci_method='simultaneous_95',alternative='two-sided',effect_ratio=_ratio(row['effect']) if spec['scale']=='log2' else None,ratio_ci95=[_ratio(v) for v in row['ci95']] if spec['scale']=='log2' else None,status='valid',warnings=['Dunnett p和同时CI采用数值积分近似；固定随机种子0以便复现，不代表精确解析值。'] if row['adjustment_method']=='dunnett' else [])
    return dict(omnibus=omnibus,comparisons=rows)
