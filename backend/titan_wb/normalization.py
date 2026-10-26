"""Ratio and hierarchical summaries. No pseudocounts or hidden exclusions."""
from collections import defaultdict
import numpy as np


def normalize(project,measurements):
    samples={s['id']:s for s in project['samples']};lanes={l['id']:l for l in project['lanes']}
    by_id={r['id']:r for r in measurements}
    rows=[]
    for r in measurements:
        if r['role']!='target':continue
        lane=lanes[r['lane_id']];sample=samples[lane['sample_id']]
        flags=list(r['flags']);ref=by_id.get(r.get('reference_id'));value=None
        if ref is None or ref['role']!='reference':flags.append('missing_reference')
        elif ref['lane_id']!=r['lane_id']:flags.append('reference_lane_mismatch')
        else:
            flags.extend('reference:'+f for f in ref['flags'])
            invalid={'signal_clipped','background_clipped','nonpositive_signal','review_required'}
            all_flags=r['flags']+ref['flags']
            if invalid.intersection(all_flags) or any(f.startswith('measurement_error:') for f in all_flags):pass
            elif r['corrected_sum'] is not None and ref['corrected_sum'] is not None and r['corrected_sum']>0 and ref['corrected_sum']>0:
                value=float(r['corrected_sum']/ref['corrected_sum'])
            else:flags.append('nonpositive_ratio_input')
        rows.append(dict(id=r['id'],sample_id=sample['id'],bio_id=sample['bio_id'],pair_id=sample.get('pair_id',''),
           group=sample['group'],membrane_id=lane['membrane_id'],analyte=r['analyte'],normalized=value,bridged=None,
           kind=sample.get('kind','biological'),pool_id=sample.get('pool_id',''),flags=sorted(set(flags))))
    grouped=defaultdict(list)
    for r in rows:
        if r['normalized'] is not None and r['kind']=='biological':grouped[(r['sample_id'],r['membrane_id'],r['analyte'])].append(r)
    bio=[]
    for (sid,membrane,analyte),units in grouped.items():
        s=samples[sid];value=float(np.mean([u['normalized'] for u in units]));flags=sorted({f for u in units for f in u['flags']})
        bio.append(dict(sample_id=sid,bio_id=s['bio_id'],pair_id=s.get('pair_id',''),group=s['group'],analyte=analyte,
          membrane_id=membrane,analysis_block=membrane,value=value,n_technical=len(units),flags=flags))
    if project['settings'].get('normalization_mode')=='ibc':
        indexed={r['id']:r for r in rows};ibcs=project['settings'].get('ibc_by_membrane',{})
        for r in bio:
            ref=indexed.get(ibcs.get(r['membrane_id'],{}).get(r['analyte']))
            if ref is None or ref['kind']!='ibc' or ref['membrane_id']!=r['membrane_id'] or ref['analyte']!=r['analyte'] or ref['normalized'] is None:
                raise ValueError('缺少有效的同膜同终点IBC，无法桥接')
            r['value']/=ref['normalized'];r['pool_id']=ref['pool_id']
            ibc_flags=['ibc:'+f for f in ref['flags']]
            r['flags']=sorted(set(r['flags']+ibc_flags))
            for u in rows:
                if u['sample_id']==r['sample_id'] and u['membrane_id']==r['membrane_id'] and u['analyte']==r['analyte']:
                    u['bridged']=u['normalized']/ref['normalized'] if u['normalized'] is not None else None
                    u['flags']=sorted(set(u['flags']+ibc_flags))
        used=set()
        for block in project['settings'].get('analysis_blocks',[]):
            if not block.get('merge_same_sample'):continue
            membranes=set(block['membrane_ids'])
            if used.intersection(membranes):raise ValueError('跨膜分析块不能重复使用同一膜')
            used.update(membranes)
            members=[r for r in bio if r['membrane_id'] in membranes]
            if not members or any(r['pool_id']!=block['pooled_reference_id'] for r in members):raise ValueError('跨膜共同参考pool_id不一致')
            all_groups={r['group'] for r in members}
            if len(all_groups)>1 and not any(len({r['group'] for r in members if r['membrane_id']==m})>1 for m in membranes):
                raise ValueError('组别与膜完全混杂，不能合并处理效应')
            merged=defaultdict(list)
            for r in members:merged[(r['sample_id'],r['analyte'])].append(r)
            bio=[r for r in bio if r['membrane_id'] not in membranes]
            for _,values in merged.items():
                bio.append({**values[0],'value':float(np.mean([v['value'] for v in values])),
                  'membrane_id':'+'.join(sorted(v['membrane_id'] for v in values)),
                  'analysis_block':block['id'],'n_technical':sum(v['n_technical'] for v in values),
                  'flags':sorted({f for v in values for f in v['flags']})})
    # Multiple specimens from one biological unit in one endpoint/group are ambiguous.
    identities=defaultdict(set)
    for r in bio:identities[(r['analyte'],r['group'],r['bio_id'])].add(r['sample_id'])
    if any(len(v)>1 for v in identities.values()):raise ValueError('同组同终点的bio对应多个样本，请明确生物学/技术重复关系')
    controls=defaultdict(list)
    for r in bio:
        if r['group']==project['settings']['control_group']:controls[(r['analysis_block'],r['analyte'])].append(r['value'])
    for r in bio:
        base=controls[(r['analysis_block'],r['analyte'])]
        r['fold']=float(r['value']/np.mean(base)) if base else None
        if not base:r['flags'].append('missing_control')
    return rows,bio
