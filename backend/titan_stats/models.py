"""Versioned tables. Values remain editable drafts until explicitly analysed."""
import copy,hashlib,json,uuid,math

def uid():return uuid.uuid4().hex

def new_dataset(name='数据表 1'):
    groups=[dict(id=uid(),label=g) for g in ['Control','Treatment']]
    return dict(id=uid(),name=name,groups=groups,rows=[dict(id=uid(),label=str(i+1),values={},excluded={}) for i in range(3)],
        confirmed=False,source=None,analysis=dict(method='descriptive',scale='raw',scope='control',control_group=groups[0]['id']),
        style=dict(kind='bar_points',error='sd',width_mm=80,height_mm=65,font_size=9,dpi=300,title='',y_label='Value',annotations='none',colors={},y_min=None,y_max=None,text_mode='editable',point_size=4,point_marker='circle',hollow=False,axis_width=.8,error_width=.8,error_cap=3,bar_width=.6,label_angle=30,group_order=[],labels={}),runs=[])

def new_project(name):
    return dict(id=uid(),module='stats',schema_version=1,revision=0,name=name,datasets=[new_dataset()],figures=[])

def validate(p):
    if p.get('module')!='stats' or p.get('schema_version')!=1:raise ValueError('不支持的统计项目格式')
    if not isinstance(p.get('name'),str) or not p['name'].strip():raise ValueError('项目名称不能为空')
    if not isinstance(p.get('revision'),int) or p['revision']<0:raise ValueError('项目版本无效')
    if not isinstance(p.get('datasets'),list) or not p['datasets']:raise ValueError('项目需要至少一张数据表')
    figures = p.setdefault('figures', [])
    if not isinstance(figures, list) or any(
        not isinstance(f, dict)
        or not all(isinstance(f.get(key), str) for key in ('id', 'name'))
        or not all(isinstance(f.get(key), dict) for key in ('dataset', 'style'))
        or 'run' not in f
        for f in figures
    ):
        raise ValueError('统计图形记录损坏')
    ids=[]
    for d in p['datasets']:
        ids.append(d['id']);gids=[g['id'] for g in d['groups']]
        if not 1<=len(gids)<=30 or len(gids)!=len(set(gids)):raise ValueError('分组数量或身份无效')
        if any(not isinstance(g.get('label'),str) or not g['label'].strip() for g in d['groups']):raise ValueError('组名不能为空')
        if len(d['rows'])>10000:raise ValueError('每表最多10000行')
        rowids=[row['id'] for row in d['rows']]
        if len(set(rowids))!=len(rowids):raise ValueError('观测身份重复')
        for row in d['rows']:
            if any(k not in gids for k in row['values']):raise ValueError('数值引用未知组')
    if len(ids)!=len(set(ids)):raise ValueError('数据表身份重复')
    json.dumps(p,allow_nan=False)
    return p

def signature(d):
    data={k:d.get(k) for k in ('id','groups','rows','confirmed','analysis','source')}
    # Labels are display metadata, not experimental identity.
    data['groups']=[g['id'] for g in d['groups']]
    return hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()).hexdigest()

def prepared(d):
    values=[];missing=0;excluded=0
    for row in d['rows']:
        for g in d['groups']:
            key=g['id'];raw=row['values'].get(key,'')
            if row.get('excluded',{}).get(key):excluded+=1;continue
            if raw is None or str(raw).strip()=='':missing+=1;continue
            try:v=float(raw)
            except (ValueError,TypeError):raise ValueError(f"第 {row['label']} 行 / {g['label']} 不是有效数值")
            if not math.isfinite(v):raise ValueError('数值必须有限，不能输入 NaN 或 Infinity')
            label=str(row['label']).strip()
            if not label:raise ValueError('请填写独立单位/配对 ID')
            values.append(dict(value=v,group=key,bio_id=row.get('units',{}).get(key,label+':'+key),pair_id=label,observation_id=row['id']))
    return values,missing,excluded

def snapshot(d):
    return copy.deepcopy({k:v for k,v in d.items() if k!='runs'})
