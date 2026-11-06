"""WB design and result compatibility around the shared statistical engine."""
from titan_stats.core import group_summary, compare_multigroup as _compare, _spec

def compare_multigroup(values,spec):
    _spec(spec)
    for key in ['analyte','membrane_id']:
        if not isinstance(spec.get(key),str) or not spec[key].strip():raise ValueError('请明确蛋白与分析膜')
    if '+' in spec['membrane_id']:raise ValueError('多膜合并不能直接使用无批次项的普通多组检验')
    selected=[v for v in values if v.get('analyte')==spec['analyte'] and v.get('analysis_block',v.get('membrane_id'))==spec['membrane_id'] and v.get('group') in spec['groups']]
    if any(v.get('membrane_id')!=spec['membrane_id'] for v in selected):raise ValueError('多膜数据不能使用无批次项的独立多组检验')
    result=_compare(selected,spec)
    for row in [result['omnibus'],*result['comparisons']]:
        row.update(analyte=spec['analyte'],membrane_id=spec['membrane_id'],analysis_block=spec['membrane_id'],family_id=f"{spec['id']}:{spec['analyte']}:{spec['membrane_id']}")
    return result
