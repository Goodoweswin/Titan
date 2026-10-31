from .quantify import _slice

def validate_lanes(p,maps):
    layouts=p.get('lane_layouts');sets=p.get('band_sets')
    if not isinstance(layouts,list) or not isinstance(sets,list):raise ValueError('项目缺少泳道布局或蛋白测量集合')
    layout_map={r['id']:r for r in layouts};set_map={r['id']:r for r in sets}
    if len(layout_map)!=len(layouts) or len(set_map)!=len(sets):raise ValueError('布局或测量集合 ID 重复')
    for layout in layouts:
        asset=maps['images'].get(layout['image_id'])
        if not asset:raise ValueError('泳道布局原图不存在')
        _slice(layout['window'],(asset['height'],asset['width']))
        for rect in layout.get('excluded_regions',[]):_slice(rect,(asset['height'],asset['width']))
        columns=layout['columns'];ids=[c['lane_id'] for c in columns]
        if not columns or len(ids)!=len(set(ids)):raise ValueError('泳道重复或布局为空')
        previous_end=None
        for c in sorted(columns,key=lambda c:c['rect'][0]):
            lane=maps['lanes'].get(c['lane_id'])
            if not lane or lane['membrane_id']!=layout['membrane_id']:raise ValueError('泳道与膜编号不匹配')
            _slice(c['rect'],(asset['height'],asset['width']))
            x0,y0,x1,y1=c['rect'];a,b,d,e=layout['window']
            if x0<a or x1>d or y0<b or y1>e:raise ValueError('泳道超出分析区域')
            if previous_end is not None and x0<previous_end:raise ValueError('泳道边界重叠')
            previous_end=x1
        source=layout.get('source_layout_id')
        if source and (source not in layout_map or layout_map[source]['membrane_id']!=layout['membrane_id']):raise ValueError('模板来源膜不匹配')
    for group in sets:
        layout=layout_map.get(group['layout_id'])
        if not layout or group['role'] not in ('target','reference') or not group.get('analyte','').strip():raise ValueError('蛋白集合身份无效')
        asset=maps['images'][layout['image_id']];_slice(group['window'],(asset['height'],asset['width']))
        assignments=group['assignments'];ids=[r['lane_id'] for r in assignments]
        if len(ids)!=len(set(ids)) or set(ids)!={c['lane_id'] for c in layout['columns']}:raise ValueError('测量集合与泳道对应不完整')
        ref=group.get('reference_set_id')
        if ref:
            other=set_map.get(ref)
            if group['role']!='target' or not other or other['role']!='reference' or layout_map[other['layout_id']]['membrane_id']!=layout['membrane_id']:raise ValueError('上样参考必须来自同膜的内参集合')
        for assignment in assignments:
            status=assignment['status'];roi=maps['rois'].get(assignment.get('roi_id'))
            if status not in ('pending','accepted','not_detected','excluded'):raise ValueError('泳道测量状态无效')
            if status=='accepted':
                if not roi or roi['lane_id']!=assignment['lane_id'] or roi['image_id']!=layout['image_id'] or roi['role']!=group['role'] or roi['analyte']!=group['analyte']:raise ValueError('条带与泳道/蛋白集合不一致')
                if roi.get('band_set_id')!=group['id'] or roi.get('lane_layout_id')!=layout['id']:raise ValueError('条带所属测量集合不一致')
                if group['role']=='target':
                    expected=next((a.get('roi_id') for a in set_map[ref]['assignments'] if a['lane_id']==assignment['lane_id'] and a['status']=='accepted'),None) if ref else None
                    if roi.get('reference_id')!=expected:raise ValueError('目标条带的内参与测量集合不一致')
            elif assignment.get('roi_id') is not None:raise ValueError('未确认泳道不能引用正式测量')
    for roi in maps['rois'].values():
        if roi.get('band_set_id'):
            group=set_map.get(roi['band_set_id'])
            if not group or not any(a.get('roi_id')==roi['id'] and a['status']=='accepted' for a in group['assignments']):raise ValueError('条带未归入所属测量集合')
