"""Explicit two-group inference; no automatic test selection."""
import numpy as np


def holm(values):
    order=np.argsort(values);out=[0.0]*len(values);last=0.0
    for rank,index in enumerate(order):
        last=max(last,min(1.0,float(values[index])*(len(values)-rank)));out[int(index)]=last
    return out


def compare(values,spec):
    from scipy import stats
    method=spec['test'];scale=spec['scale']
    if method not in ['welch','paired'] or scale not in ['raw','log2']:raise ValueError('请选择明确支持的检验与尺度')
    if spec['group_a']==spec['group_b']:raise ValueError('比较需要两个不同组别')
    a=[v for v in values if v['group']==spec['group_a']];b=[v for v in values if v['group']==spec['group_b']]
    if min(len(a),len(b))<2:raise ValueError('每组至少2个独立单位或完整配对才可计算；这不代表样本量充分')
    if len({v['membrane_id'] for v in a+b})!=1 or '+' in a[0]['membrane_id']:raise ValueError('多膜数据不能使用无批次项的普通t检验')
    for group in [a,b]:
        if len({v['bio_id'] for v in group})!=len(group):raise ValueError('重复生物学单位不能重复计入n')
    if method=='welch' and {v['bio_id'] for v in a}&{v['bio_id'] for v in b}:raise ValueError('两组有共享生物学单位，应明确配对设计')
    if method=='paired':
        pa={v.get('pair_id'):v for v in a};pb={v.get('pair_id'):v for v in b}
        if '' in pa or '' in pb or None in pa or None in pb or len(pa)!=len(a) or len(pb)!=len(b) or pa.keys()!=pb.keys():raise ValueError('配对缺失/重复，不能静默丢弃')
        a=[pa[k] for k in sorted(pa)];b=[pb[k] for k in sorted(pa)]
    x=np.array([v['value'] for v in a],float);y=np.array([v['value'] for v in b],float)
    if not np.isfinite(x).all() or not np.isfinite(y).all():raise ValueError('统计数据含无效值')
    if scale=='log2':
        if min(x.min(),y.min())<=0:raise ValueError('log2仅适用于正值')
        x=np.log2(x);y=np.log2(y)
    if method=='paired':
        d=y-x
        if d.std(ddof=1)==0:raise ValueError('配对差值方差为零，无法进行此t检验')
        test=stats.ttest_rel(y,x);effect=float(d.mean());se=float(d.std(ddof=1)/np.sqrt(len(d)))
    else:
        if x.var(ddof=1)+y.var(ddof=1)==0:raise ValueError('两组方差均为零，无法进行此t检验')
        test=stats.ttest_ind(y,x,equal_var=False);effect=float(y.mean()-x.mean());se=float(np.sqrt(x.var(ddof=1)/len(x)+y.var(ddof=1)/len(y)))
    df=float(test.df);margin=float(stats.t.ppf(.975,df)*se)
    if not np.isfinite(test.statistic) or not np.isfinite(test.pvalue):raise ValueError('检验数值退化')
    return dict(comparison_id=spec['id'],family_id=spec.get('family_id','default'),test=method,scale=scale,
      n_a=len(a),n_b=len(b),effect=effect,statistic=float(test.statistic),df=df,p_raw=float(test.pvalue),
      p_adjusted=None,ci95=[effect-margin,effect+margin],warnings=[])
