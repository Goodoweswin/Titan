"""Project contract shared by persistence and numerical commands."""
import copy
import uuid
import numpy as np
from .quantify import _slice


def new_project(name):
    if not isinstance(name,str) or not name.strip():raise ValueError('请输入实验名称')
    return dict(id=uuid.uuid4().hex,name=name.strip(),schema_version=2,revision=0,
                images=[],samples=[],lanes=[],rois=[],lane_layouts=[],band_sets=[],settings=dict(control_group='control',
                normalization_mode='within',ibc_by_membrane={},analysis_blocks=[],comparisons=[]))


def validate_project(p):
    if p.get('schema_version')!=2:raise ValueError('不支持此项目版本，请使用兼容版本打开')
    if not isinstance(p.get('revision'),int) or p['revision']<0:raise ValueError('项目版本无效')
    if not p.get('id') or not p.get('name','').strip():raise ValueError('项目身份缺失')
    multi=p.get('settings',{}).get('multigroup_comparisons',[])
    if not isinstance(multi,list) or any(not isinstance(s,dict) or not isinstance(s.get('id'),str) or not s['id'].strip() for s in multi):raise ValueError('多组比较ID缺失或格式无效')
    if len({s['id'] for s in multi})!=len(multi):raise ValueError('多组比较ID不能重复')
    maps={}
    for key in ['images','samples','lanes','rois']:
        rows=p.get(key)
        if not isinstance(rows,list):raise ValueError(f'项目缺少{key}')
        ids=[r.get('id') for r in rows]
        if len(set(ids))!=len(ids) or not all(ids):raise ValueError(f'{key}含重复/空ID')
        maps[key]={r['id']:r for r in rows}
    for a in p['images']:
        if 'page_index' in a and (type(a['page_index']) is not int or a['page_index']<0):raise ValueError('图像页码无效')
        if 'page_count' in a and (type(a['page_count']) is not int or a['page_count']<1 or a.get('page_index',0)>=a['page_count']):raise ValueError('图像总页数无效')
        if a.get('polarity') not in ['bright','dark']:raise ValueError('图像极性无效')
        c=a.get('ceiling')
        if c is not None and (not isinstance(c,(float,int)) or not np.isfinite(c) or c<=0):raise ValueError('编码上界无效')
    for sample in p['samples']:
        if sample.get('kind','biological') not in ['biological','ibc']:raise ValueError('样本类型无效')
        if not sample.get('bio_id') or not sample.get('group'):raise ValueError('样本缺少生物学编号/组别')
    for lane in p['lanes']:
        if lane.get('sample_id') not in maps['samples'] or not lane.get('membrane_id'):raise ValueError('泳道样本/膜对应缺失')
    unique=set()
    for r in p['rois']:
        if r.get('image_id') not in maps['images'] or r.get('lane_id') not in maps['lanes']:raise ValueError('ROI图像/泳道引用缺失')
        if r.get('role') not in ['target','reference'] or not r.get('analyte','').strip():raise ValueError('ROI终点/角色无效')
        a=maps['images'][r['image_id']];shape=(a['height'],a['width'])
        s=_slice(r['rect'],shape)
        for b in r.get('backgrounds',[]):
            _slice(b,shape)
            if max(r['rect'][0],b[0])<min(r['rect'][2],b[2]) and max(r['rect'][1],b[1])<min(r['rect'][3],b[3]):raise ValueError('背景与目标ROI重叠')
        key=(r['lane_id'],r['analyte'],r['role'])
        if key in unique:raise ValueError('同泳道同终点存在多个正式ROI')
        unique.add(key)
        ref=r.get('reference_id')
        if ref:
            if ref not in maps['rois'] or maps['rois'][ref]['role']!='reference':raise ValueError('上样参考引用无效')
    if 'figure_settings' in p:
        from .figures import validate_figure_settings
        validate_figure_settings(p['figure_settings'])
    if 'plot_settings' in p:
        from .export import plot_settings
        plot_settings(p['plot_settings'])
    from .lane_models import validate_lanes
    validate_lanes(p,maps)
    return p


def revised(p):
    p=copy.deepcopy(p);p['revision']+=1
    for r in p['rois']:r['reviewed_revision']=None
    return p
