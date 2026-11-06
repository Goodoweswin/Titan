"""WB design boundary around the shared statistical engine."""
from titan_stats.core import holm, compare as _compare

def compare(values,spec):
    selected=[v for v in values if v['group'] in (spec['group_a'],spec['group_b'])]
    if selected and (len({v['membrane_id'] for v in selected})!=1 or '+' in selected[0]['membrane_id']):
        raise ValueError('多膜数据不能使用无批次项的普通t检验')
    return _compare(values,spec)
