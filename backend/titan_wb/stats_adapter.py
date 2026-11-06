"""Transfer WB independent units with source identities, never lane pseudoreplicates."""
from titan_stats.models import new_dataset,uid
from .export import check_result
from .figure_documents import source_signature

def datasets(project,result):
    check_result(project,result)
    if project['band_sets'] and not project['settings'].get('design_confirmed'):raise ValueError('请先在 WB 中确认独立生物学重复与分组')
    bio=result['biological']
    if not bio:raise ValueError('暂无可用的生物学单位，请先完成 WB 定量与样本设置')
    tables=[]
    for endpoint,block in sorted({(v['analyte'],v['analysis_block']) for v in bio}):
        chosen=[v for v in bio if v['analyte']==endpoint and v['analysis_block']==block]
        d=new_dataset(endpoint+' · '+block);names=list(dict.fromkeys(v['group'] for v in chosen));d['groups']=[dict(id=uid(),label=g) for g in names];lookup={g['label']:g['id'] for g in d['groups']};d['rows']=[]
        for v in chosen:
            gid=lookup[v['group']]
            d['rows'].append(dict(id=uid(),label=v.get('pair_id') or v['bio_id'],values={gid:str(v['value'])},units={gid:v['bio_id']},excluded={},origin=v))
        # Coalesce complete pairs by pair_id; independence remains validated by bio_id.
        paired={}
        for row in d['rows']:
            pair=row['origin'].get('pair_id')
            if pair and pair in paired and not (set(paired[pair]['values'])&set(row['values'])):
                paired[pair]['values'].update(row['values']);paired[pair]['units'].update(row['units'])
            else:paired[uid() if not pair or pair in paired else pair]=row
        d['rows']=list(paired.values());d['confirmed']=True;d['analysis']['control_group']=lookup.get(project['settings']['control_group'],d['groups'][0]['id'])
        d['source']=dict(kind='wb',path=project.get('project_path'),project_id=project['id'],revision=project['revision'],signature=source_signature(project),endpoint=endpoint,block=block,locked=True,
            blocked='跨膜/批次数据需要相应模型；当前仅描述' if len({v['membrane_id'] for v in chosen})!=1 or '+' in chosen[0]['membrane_id'] else '',records=chosen)
        d['style']['y_label']='Target / reference ratio';tables.append(d)
    return tables
