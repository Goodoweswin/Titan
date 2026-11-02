"""Independent, versioned WB assemblies. No quantitative result is required."""
import copy
import json
import math
import os
import re
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from .images import read_pixels, read_source_pixels, file_hash
from .projects import atomic_json, check_lock, operation_lock
from .wb_render import render, display_pixels, display_values, data_url, png_bytes
from PIL import Image

DEFAULTS = dict(width_mm=85, image_width_mm=0, font_pt=8, gap_mm=3, dpi=300)


def _id(value):
    if not isinstance(value, str) or not re.fullmatch('[A-Za-z0-9_-]{1,80}', value): raise ValueError('组图ID无效')
    return value


def _text(value, name, maximum=120):
    if not isinstance(value,str) or len(value)>maximum or any(ord(c)<32 for c in value): raise ValueError(name+'文字无效或过长')
    return value


def _number(value, lo, hi):
    if type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi: raise ValueError('组图数值超出范围')
    return value


def _source(asset):
    source = {k: copy.deepcopy(v) for k,v in asset.items() if k!='preview'}
    values = display_values(source)
    lo,hi = np.percentile(values,[.5,99.5]); source['display_range']=[float(lo),max(float(hi),float(lo)+1)]
    raw=read_source_pixels(source)
    source['source_width'] = raw.shape[1]
    source['source_height'] = raw.shape[0]
    return source


def new_document(project):
    rows=[];layouts={l['id']:l for l in project.get('lane_layouts',[])};assets={a['id']:a for a in project['images']}
    sources={id:_source(asset) for id,asset in assets.items()}
    sets=sorted(project.get('band_sets',[]),key=lambda g:g['role']=='reference')
    for group in sets:
        layout=layouts.get(group['layout_id']);source=sources.get(layout['image_id']) if layout else None
        if source:
            rows.append(dict(id=uuid.uuid4().hex,protein=group['analyte'],source=copy.deepcopy(source),crop=group['window'][:],
                             confirmed=False,expected_mw='',markers=[],layout_id=layout['id']))
    if not rows:
        rows=[dict(id=uuid.uuid4().hex,protein='',source=copy.deepcopy(source),crop=[0,0,source['width'],source['height']],
                   confirmed=False,expected_mw='',markers=[]) for source in sources.values()]
    return dict(schema_version=1,id=uuid.uuid4().hex,project_id=project['id'],name='WB 条带组图',version=None,
                settings=DEFAULTS.copy(),rows=rows,labels=[],synthetic=bool(project.get('demo') or project.get('synthetic')))


def _validated(project, document, confirmed=False):
    if not isinstance(document,dict):raise ValueError('组图文档无效')
    d=copy.deepcopy(document)
    if d.get('schema_version')!=1 or d.get('project_id')!=project['id']:raise ValueError('组图版本或实验不匹配')
    _id(d.get('id'));_text(d.get('name'),'组图名称')
    if not d['name'].strip():raise ValueError('请输入组图名称')
    d['synthetic']=bool(d.get('synthetic') or project.get('synthetic') or project.get('demo'))
    settings=d.get('settings',{})
    for key,lo,hi in [('width_mm',40,300),('image_width_mm',0,280),('font_pt',5,24),('gap_mm',1,20)]:_number(settings.get(key),lo,hi)
    if type(settings.get('dpi')) is not int or settings['dpi'] not in (300,600):raise ValueError('请选择300或600 DPI')
    rows=d.get('rows')
    if not isinstance(rows,list) or not 1<=len(rows)<=40:raise ValueError('组图行数需为1到40行')
    ids=[]
    for row in rows:
        ids.append(_id(row.get('id')));_text(row.get('protein'),'蛋白名',80);_text(row.get('expected_mw'),'预期分子量',30)
        source=row.get('source',{})
        if not isinstance(source,dict):raise ValueError('缺少原图来源')
        path=Path(source.get('path','')).resolve();root=Path(project['project_path']).resolve() if project.get('project_path') else None
        known=next((a for a in project['images'] if Path(a['path']).resolve()==path and a['sha256']==source.get('sha256')),None)
        if not known and not (root and path.is_relative_to(root/'originals')):raise ValueError('组图原图不属于当前实验')
        if not path.is_file() or file_hash(path)!=source.get('sha256'):raise ValueError('组图原图缺失或hash已改变')
        source['path']=str(path)
        for key in ['width','height']:
            if type(source.get(key)) is not int or not 0<source[key]<=25_000_000:raise ValueError('原图尺寸无效')
        low,high=source.get('display_range',[None,None]);_number(low,-1e308,1e308);_number(high,-1e308,1e308)
        if high<=low:raise ValueError('灰度显示范围无效')
        rect=row.get('crop')
        if not isinstance(rect,list) or len(rect)!=4 or any(type(v) is not int for v in rect):raise ValueError('裁剪坐标需为整数')
        a,b,c,e=rect
        if not 0<=a<c<=source['width'] or not 0<=b<e<=source['height']:raise ValueError('裁剪区域超出原图范围')
        if confirmed and row.get('confirmed') is not True:raise ValueError('请在原图上确认每一行裁剪区域')
        markers=row.get('markers')
        if not isinstance(markers,list) or len(markers)>20:raise ValueError('marker标注过多')
        for marker in markers:
            _text(marker.get('text'),'marker',30)
            if not marker['text'].strip():raise ValueError('marker文字不能为空')
            _number(marker.get('y'),b,e)
    if len(ids)!=len(set(ids)):raise ValueError('组图行ID重复')
    labels=d.get('labels')
    if not isinstance(labels,list) or len(labels)>50:raise ValueError('顶部标签过多')
    for label in labels:_text(label.get('text'),'顶部标签',80);_number(label.get('x'),0,1)
    return d


def preview_document(project, document):
    d=_validated(project,document);output=render(d)
    return {**{k:v for k,v in output.items() if k not in ('png','svg')},'png':data_url(output['png'])}


def source_preview(project, source):
    row=dict(id='preview',protein='',source=source,crop=[0,0,source['width'],source['height']],confirmed=False,expected_mw='',markers=[])
    doc=dict(schema_version=1,id='preview',project_id=project['id'],name='preview',settings=DEFAULTS,rows=[row],labels=[])
    checked=_validated(project,doc)['rows'][0]['source'];image=Image.fromarray(display_pixels(checked));image.thumbnail((1600,1200))
    return dict(png=data_url(png_bytes(image)))


def _root(project):
    if not project.get('project_path'):raise ValueError('请先保存实验')
    root=Path(project['project_path']).resolve()
    if json.loads((root/'project.json').read_text(encoding='utf-8'))['id']!=project['id']:raise ValueError('组图与磁盘实验不匹配')
    return root


def _catalog(root):
    path=root/'figures/wb/catalog.json'
    if not path.exists():return dict(version=1,documents=[])
    try:
        catalog=json.loads(path.read_text(encoding='utf-8'));assert catalog['version']==1 and isinstance(catalog['documents'],list)
        ids=[]
        for doc in catalog['documents']:
            ids.append(_id(doc['id']));_id(doc['version'])
            assert isinstance(doc['versions'],list) and doc['version'] in [v['version'] for v in doc['versions']]
            for v in doc['versions']:_id(v['version']);assert re.fullmatch('[a-f0-9]{64}',v['sha256'])
        assert len(ids)==len(set(ids));return catalog
    except (ValueError,KeyError,TypeError,AssertionError):raise ValueError('WB组图索引损坏，原文档保留，未重置索引')


def list_documents(project):
    return _catalog(_root(project))['documents']


def save_document(project, document, session, expected_version=None):
    if project.get('read_only'):raise ValueError('只读项目不能保存组图')
    root=_root(project);d=_validated(project,document,True);render(d)
    for row in d['rows']:
        source=row['source'];path=Path(source['path'])
        if not path.is_relative_to(root/'originals'):raise ValueError('请先保存实验，将原图归档后再保存组图')
        source['path']=path.relative_to(root).as_posix()
    folder=root/'figures';folder.mkdir(exist_ok=True);check_lock(root,session)
    with operation_lock(folder,'.catalog.lock'):
        catalog=_catalog(root);prior=next((v for v in catalog['documents'] if v['id']==d['id']),None)
        if (prior and expected_version!=prior['version']) or (not prior and expected_version is not None):raise ValueError('组图版本已变化，请重新打开')
        d['version']=uuid.uuid4().hex;d['updated_at']=datetime.now(timezone.utc).isoformat()
        target=folder/'wb'/d['id'];target.mkdir(parents=True,exist_ok=True)
        output=target/(d['version']+'.json');atomic_json(output,d)
        entry=dict(id=d['id'],name=d['name'],version=d['version'],updated_at=d['updated_at'],versions=(prior['versions'][:] if prior else [])+[dict(version=d['version'],sha256=file_hash(output))])
        catalog['documents']=[v for v in catalog['documents'] if v['id']!=d['id']]+[entry];atomic_json(folder/'wb/catalog.json',catalog)
    return load_document(project,d['id'])


def load_document(project, document_id, version_id=None):
    root=_root(project);id=_id(document_id);catalog=_catalog(root)
    entry=next((d for d in catalog['documents'] if d['id']==id),None)
    if not entry:raise ValueError('组图文档不存在')
    version=_id(version_id or entry['version']);record=next((v for v in entry['versions'] if v['version']==version),None)
    path=root/'figures/wb'/id/(version+'.json')
    if not record or not path.resolve().is_relative_to(root/'figures/wb') or not path.is_file() or file_hash(path)!=record['sha256']:raise ValueError('组图文档缺失或hash不匹配')
    d=json.loads(path.read_text(encoding='utf-8'))
    for row in d['rows']:
        source=row['source'];path=(root/source['path'].replace('\\','/')).resolve()
        if not path.is_relative_to(root/'originals'):raise ValueError('组图原图路径越界')
        source['path']=str(path)
    return _validated(project,d,True)


def export_document(project, document, destination):
    d=_validated(project,document,True);output=render(d);dest=Path(destination).expanduser().resolve()
    if dest.exists():raise ValueError('导出目录已存在，请选择新目录')
    dest.parent.mkdir(parents=True,exist_ok=True);stage=Path(tempfile.mkdtemp(prefix='.wb-export-',dir=dest.parent))
    try:
        (stage/'figure.png').write_bytes(output['png']);(stage/'figure.svg').write_text(output['svg'],encoding='utf-8')
        for row in d['rows']:row['source']['path']=Path(row['source']['path']).name
        atomic_json(stage/'source.json',dict(document=d,width_mm=output['width_mm'],height_mm=output['height_mm'],
                    coordinate_system='half-open pixels after clockwise rotation, origin at top left',software='Titan WB',
                    note='Expected molecular weights are user annotations; marker labels are user-positioned, not automatic estimates.'))
        os.replace(stage,dest)
        return dict(path=str(dest),outputs={p.name:file_hash(p) for p in dest.iterdir()})
    finally:
        if stage.exists():shutil.rmtree(stage)
