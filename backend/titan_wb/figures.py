"""Validated display-only settings and traceable data for publication figures."""
import copy,json,math,re
import numpy as np
from .multigroup import group_summary

PALETTE=['#F1D21B','#A7A7AF','#4C78A8','#E45756','#54A24B','#B279A2','#F58518','#72B7B2']
DEFAULTS=dict(kind='bar_points',value_mode='normalized',error='sd',error_direction='both',colors={},borders={},display_labels={},group_order=[],point_marker='circle',hollow=True,point_size=4,jitter=.08,error_width=1,error_cap=3,bar_width=.6,bar_gap=.3,axis_width=1,title='',title_italic=True,x_label='',y_label='',label_angle=45,y_min=None,y_max=None,y_step=None,annotations='none',comparison_ids=[],panel_key='',show_n=True)
ENUMS=dict(kind=['bar_points','bar','scatter'],value_mode=['normalized','fold'],error=['none','sd','sem','ci95'],error_direction=['both','above'],point_marker=['circle','square','triangle'],annotations=['none','p','stars'])
BOUNDS=dict(point_size=(1,14),jitter=(0,.3),error_width=(.2,4),error_cap=(0,12),bar_width=(.1,.95),bar_gap=(0,2),axis_width=(.2,4),label_angle=(-90,90))


def validate_figure_settings(settings=None):
    if settings is not None and not isinstance(settings,dict):raise ValueError('图形设置须为对象')
    result=copy.deepcopy(DEFAULTS)
    for key,value in (settings or {}).items():
        if key not in DEFAULTS:raise ValueError('未知图形参数：'+str(key))
        if key in ENUMS:
            if value not in ENUMS[key]:raise ValueError('图形选项无效：'+key)
        elif key in BOUNDS:
            lo,hi=BOUNDS[key]
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not lo<=value<=hi:raise ValueError(f'{key} 须在 {lo}–{hi} 内')
        elif key in ['y_min','y_max','y_step']:
            if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or abs(value)>1e12 or (key=='y_step' and value<=0)):raise ValueError('Y轴范围或刻度间隔无效')
        elif key in ['hollow','title_italic','show_n']:
            if type(value) is not bool:raise ValueError('图形开关无效')
        elif key in ['group_order','comparison_ids']:
            if not isinstance(value,list) or len(value)>1000 or any(not isinstance(v,str) or len(v)>600 for v in value) or len(value)!=len(set(value)):raise ValueError('组顺序或比较标记重复/无效')
        elif key in ['colors','borders','display_labels']:
            if not isinstance(value,dict) or len(value)>1000 or any(not isinstance(k,str) or len(k)>300 or not isinstance(v,str) or len(v)>120 for k,v in value.items()):raise ValueError('组颜色或名称无效')
            if key!='display_labels' and any(not re.fullmatch(r'#[0-9A-Fa-f]{6}',v) for v in value.values()):raise ValueError('颜色须为 #RRGGBB')
        elif not isinstance(value,str) or len(value)>600:raise ValueError('图形文字过长或格式无效')
        result[key]=copy.deepcopy(value)
    if result['y_min'] is not None and result['y_max'] is not None and result['y_min']>=result['y_max']:raise ValueError('Y轴上界须大于下界')
    return result


def resolve_figure_settings(project,settings=None):
    return validate_figure_settings(settings if settings is not None else (project or {}).get('figure_settings'))


def jitter_positions(n,width):
    return np.linspace(-width,width,n).tolist() if n>1 else [0.0]*n


def panel_key(analyte,block):return json.dumps([analyte,block],ensure_ascii=False,separators=(',',':'))
def comparison_key(row):return json.dumps([row['comparison_id'],row['analyte'],row['membrane_id'],row['group_a'],row['group_b']],ensure_ascii=False,separators=(',',':'))


def figure_data(project,result,settings=None):
    f=validate_figure_settings(settings);project=project or {};bio=result.get('biological',[]);lane_rows=result.get('lane_results',[])
    lane_mode=not bio and not project.get('settings',{}).get('design_confirmed',False) and bool(lane_rows)
    lanes={l['id']:l for l in project.get('lanes',[])};samples={s['id']:s for s in project.get('samples',[])}
    expected={};registry=[]
    merged={m:b['id'] for b in project.get('settings',{}).get('analysis_blocks',[]) if b.get('merge_same_sample') for m in b['membrane_ids']}
    def add(panel,group):
        if group not in registry:registry.append(group)
        if group not in expected.setdefault(panel,[]):expected[panel].append(group)
    if lane_mode:
        for row in lane_rows:add((row['analyte'],row['membrane_id']),row['lane_id']+'/'+row['sample_id'])
    else:
        # Register all known group identities before selecting a panel or filtering values.
        registry=list(dict.fromkeys(s['group'] for s in project.get('samples',[]) if s.get('kind','biological')=='biological'))
        endpoints=[(r['analyte'],r['lane_id']) for r in project.get('rois',[]) if r['role']=='target']
        endpoints.extend((g['analyte'],a['lane_id']) for g in project.get('band_sets',[]) if g['role']=='target' for a in g['assignments'])
        for analyte,lane_id in endpoints:
            lane=lanes.get(lane_id);sample=samples.get(lane['sample_id']) if lane else None
            if sample and sample.get('kind','biological')=='biological':add((analyte,merged.get(lane['membrane_id'],lane['membrane_id'])),sample['group'])
        for row in bio:add((row['analyte'],row['analysis_block']),row['group'])
    panels=[];notes=[]
    if lane_mode and f['value_mode']=='fold':raise ValueError('先确认生物学设计和有效对照，才能显示相对对照倍数')
    for (analyte,block),keys in sorted(expected.items()):
        key=panel_key(analyte,block)
        if f['panel_key'] and key!=f['panel_key']:continue
        ordered=[g for g in f['group_order'] if g in keys]+[g for g in keys if g not in f['group_order']]
        rows=[r for r in (lane_rows if lane_mode else bio) if r['analyte']==analyte and r.get('analysis_block',r.get('membrane_id'))==block]
        if not lane_mode and f['value_mode']=='fold' and (not rows or any(r.get('fold') is None or not math.isfinite(r['fold']) for r in rows)):raise ValueError('此面板缺少完整有效的对照倍数；不能混用倍数和原始比值')
        groups=[];warnings=[]
        for group in ordered:
            chosen=[r for r in rows if (r['lane_id']+'/'+r['sample_id'] if lane_mode else r['group'])==group]
            values=[r.get('normalized') if lane_mode else r.get('fold' if f['value_mode']=='fold' else 'value') for r in chosen]
            values=[v for v in values if v is not None]
            summary=group_summary(values)
            status='valid' if values else ('not_detected' if chosen and all(r.get('status')=='not_detected' for r in chosen) else 'unavailable')
            if not values and not lane_mode:
                matching=[r for r in lane_rows if r['analyte']==analyte and merged.get(r['membrane_id'],r['membrane_id'])==block and samples.get(lanes.get(r['lane_id'],{}).get('sample_id'),{}).get('group')==group]
                if matching and all(r['status']=='not_detected' for r in matching):status='not_detected'
            groups.append(dict(key=group,label=f['display_labels'].get(group,group),color=f['colors'].get(group,PALETTE[registry.index(group)%len(PALETTE)]),border=f['borders'].get(group,'#202020'),values=values,status=status,**summary))
        comparisons=[]
        if f['annotations']!='none':
            if lane_mode:raise ValueError('逐泳道图不能标注生物学组间显著性')
            for row in result.get('multigroup_comparisons',[]):
                if row['analyte']==analyte and row['membrane_id']==block and row.get('status')=='valid' and comparison_key(row) in f['comparison_ids']:
                    if row['group_a'] in ordered and row['group_b'] in ordered:comparisons.append({**row,'key':comparison_key(row)})
        limits=[]
        for group in groups:
            limits.extend(group['values'])
            if not lane_mode and group['n']>1 and f['error']!='none':
                error=group['ci95'] if f['error']=='ci95' else [group['mean']-group[f['error']],group['mean']+group[f['error']]]
                limits.extend(error if f['error_direction']=='both' else error[1:])
        if f['kind']!='scatter' and f['y_min'] is not None and f['y_min']>0:warnings.append('Y轴截断柱形零基线')
        if any((f['y_min'] is not None and v<f['y_min']) or (f['y_max'] is not None and v>f['y_max']) for v in limits):warnings.append('自定义Y轴范围隐藏了数据或误差端点')
        panels.append(dict(key=key,analyte=analyte,analysis_block=block,groups=groups,comparisons=comparisons,warnings=warnings,limits=limits))
    if f['panel_key'] and not panels:raise ValueError('所选蛋白/分析膜没有当前图形数据')
    if f['value_mode']=='fold':notes.append('倍数及误差按观测对照均值缩放，未传播该分母估计的不确定性')
    return dict(unit='lane' if lane_mode else 'biological',value_mode=f['value_mode'],error=f['error'],panels=panels,notes=notes,group_registry=[dict(key=g,label=f['display_labels'].get(g,g),color=f['colors'].get(g,PALETTE[i%len(PALETTE)])) for i,g in enumerate(registry)])
