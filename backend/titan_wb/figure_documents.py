"""Versioned, frozen-source figures contained in a portable project folder."""
import base64,copy,hashlib,json,os,re,shutil,tempfile,uuid
from datetime import datetime,timezone
from pathlib import Path
from .models import validate_project
from .projects import atomic_json,check_lock,operation_lock
from .images import file_hash
from .export import check_result,plot_settings,plot_results


def _now():return datetime.now(timezone.utc).isoformat()

def source_signature(project):
    revision=project.get('revision')
    rois=[{k:v for k,v in r.items() if k!='reviewed_revision'}|dict(reviewed=r.get('reviewed_revision')==revision) for r in project.get('rois',[])]
    layouts=[{k:v for k,v in l.items() if k!='confirmed_revision'}|dict(confirmed=l.get('confirmed_revision')==revision) for l in project.get('lane_layouts',[])]
    images=[{k:v for k,v in a.items() if k not in ['path','preview','display_inverted']} for a in project.get('images',[])]
    value=dict(id=project['id'],images=images,rois=rois,lane_layouts=layouts,band_sets=project.get('band_sets',[]),samples=project.get('samples',[]),lanes=project.get('lanes',[]),settings=project.get('settings',{}))
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _id(value):
    if not isinstance(value,str) or not re.fullmatch('[A-Za-z0-9_-]{1,80}',value):raise ValueError('图形或版本ID无效')
    return value


def _catalog(root):
    path=root/'figures/catalog.json'
    if not path.exists():return dict(version=1,figures=[])
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
        if data.get('version')!=1 or not isinstance(data.get('figures'),list):raise ValueError()
        ids=[_id(d['id']) for d in data['figures']]
        if len(ids)!=len(set(ids)):raise ValueError()
        for d in data['figures']:
            _id(d['current_version'])
            if not isinstance(d.get('versions'),list) or not any(v['version_id']==d['current_version'] for v in d['versions']):raise ValueError()
        return data
    except (ValueError,KeyError,TypeError,AttributeError):raise ValueError('图形历史索引损坏，原图形版本保留；未重置历史')


def _public(doc,current_signature=None,version_id=None):
    version=next(v for v in doc['versions'] if v['version_id']==(version_id or doc['current_version']))
    history=[{k:v.get(k) for k in ['version_id','source_revision','created_at','name']} for v in doc['versions']]
    return dict(id=doc['id'],name=version['name'],current_version=doc['current_version'],selected_version=version['version_id'],source_revision=version['source_revision'],source_signature=version['source_signature'],source_stale=current_signature is not None and version['source_signature']!=current_signature,created_at=doc['created_at'],updated_at=version['created_at'],kind=version['figure_settings']['kind'],panel_key=version['figure_settings']['panel_key'],default_key=doc.get('default_key'),versions=history)


def figure_catalog_metadata(root,current_signature=None):
    return [_public(d,current_signature) for d in _catalog(Path(root))['figures']]


def _root(project):
    if not project.get('project_path'):raise ValueError('请先保存项目后再保存正式图表')
    root=Path(project['project_path']).resolve()
    try:disk=json.loads((root/'project.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):raise ValueError('项目源文件不存在或损坏')
    if disk.get('id')!=project['id']:raise ValueError('图表与项目身份不匹配')
    return root,disk


def _snapshot(project,root):
    p=copy.deepcopy(project)
    for key in ['project_path','saved_revision','read_only','upgrade_from']:p.pop(key,None)
    for image in p['images']:
        path=Path(image['path']).resolve()
        if not path.is_relative_to(root/'originals') or not path.is_file() or file_hash(path)!=image['sha256']:raise ValueError('图形源图必须是项目内未改变的原始文件')
        image['path']=path.relative_to(root).as_posix();image['preview']=''
    return p


def save_figure(project,result,figure_settings,name,session,*,figure_id=None,expected_version=None,settings=None,update_source=False,default_key=None):
    if project.get('read_only'):raise ValueError('只读项目不能修改图形历史')
    if not isinstance(name,str) or not name.strip() or len(name)>120:raise ValueError('请提供不超过120字的图形名称')
    validate_project(project);check_result(project,result);root,disk=_root(project);check_lock(root,session);root,disk=_root(project)
    signature=source_signature(project);dimensions=plot_settings(settings if settings is not None else project.get('plot_settings'))
    folder=root/'figures';folder.mkdir(exist_ok=True)
    with operation_lock(folder,'.catalog.lock'):
        catalog=_catalog(root)
        if default_key:
            if not isinstance(default_key,str) or len(default_key)>600:raise ValueError('默认图形键无效')
            existing=next((d for d in catalog['figures'] if d.get('default_key')==default_key),None)
            if existing:return _public(existing,signature)
        doc=next((d for d in catalog['figures'] if d['id']==_id(figure_id)),None) if figure_id else None
        if figure_id and not doc:raise ValueError('图形不存在')
        if doc and expected_version!=doc['current_version']:raise ValueError('图形版本已变化，请重新打开')
        if doc and not update_source:
            prior=next(v for v in doc['versions'] if v['version_id']==doc['current_version'])
            if signature!=prior['source_signature']:raise ValueError('源分析已改变，请明确选择“用当前结果更新”')
        known=any(v['source_signature']==signature for d in catalog['figures'] for v in d['versions'])
        saved_current=project.get('saved_revision')==project['revision']==disk['revision'] and signature==source_signature(disk)
        if not saved_current and not (known and not update_source):raise ValueError('此分析尚未保存或不是已有冻结源，请先等待项目保存')
        snapshot=_snapshot(project,root)
        stage=Path(tempfile.mkdtemp(prefix='.figure-stage-',dir=folder))
        try:
            data,figure=plot_results(result,stage,dimensions,figure_settings,project)
            atomic_json(stage/'source.json',dict(project=snapshot,result=result))
            version_id=uuid.uuid4().hex;figure_id=doc['id'] if doc else uuid.uuid4().hex
            version=dict(version_id=version_id,name=name.strip(),source_revision=project['revision'],source_signature=signature,created_at=_now(),figure_settings=figure,plot_settings=dimensions,outputs={name:file_hash(stage/name) for name in ['source.json','plot.png','plot.svg']},notes=data['notes'])
            atomic_json(stage/'figure.json',version)
            destination=folder/figure_id/version_id;destination.parent.mkdir(exist_ok=True);os.replace(stage,destination)
            if not doc:
                doc=dict(id=figure_id,created_at=version['created_at'],versions=[],default_key=default_key);catalog['figures'].append(doc)
            doc['versions'].append(version);doc['current_version']=version_id
            atomic_json(folder/'catalog.json',catalog)
            return _public(doc,source_signature(disk))
        finally:
            if stage.exists():shutil.rmtree(stage)


def load_figure(path,figure_id,session,version_id=None):
    root=Path(path).resolve();catalog=_catalog(root);doc=next((d for d in catalog['figures'] if d['id']==_id(figure_id)),None)
    if not doc:raise ValueError('图形不存在')
    selected=_id(version_id or doc['current_version']);version=next((v for v in doc['versions'] if v['version_id']==selected),None)
    if not version:raise ValueError('图形版本不存在')
    folder=root/'figures'/doc['id']/selected
    if not folder.resolve().is_relative_to(root/'figures'):raise ValueError('图形路径越界')
    for name in ['source.json','plot.png','plot.svg']:
        if file_hash(folder/name)!=version['outputs'][name]:raise ValueError('图形文件缺失或哈希不一致')
    content=json.loads((folder/'source.json').read_text(encoding='utf-8'));project=content['project'];result=content['result']
    if source_signature(project)!=version['source_signature']:raise ValueError('冻结分析源哈希不一致')
    for image in project['images']:
        full=(root/image['path'].replace('\\','/')).resolve()
        if not full.is_relative_to(root/'originals') or not full.is_file() or file_hash(full)!=image['sha256']:raise ValueError('冻结图形的原图缺失或已改变')
        image['path']=str(full)
    read_only=False
    try:check_lock(root,session,acquire=False)
    except ValueError:read_only=True
    project.update(project_path=str(root),saved_revision=project['revision'],read_only=read_only,figure_settings=version['figure_settings'],plot_settings=version['plot_settings'])
    validate_project(project);check_result(project,result)
    _,disk=_root(project)
    return dict(document=_public(doc,source_signature(disk),selected),project=project,result=result,figure_settings=version['figure_settings'],settings=version['plot_settings'],png='data:image/png;base64,'+base64.b64encode((folder/'plot.png').read_bytes()).decode())
