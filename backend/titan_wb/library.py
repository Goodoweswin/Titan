"""A local index of explicitly created/opened portable projects. No disk scan."""
import json
import shutil
import uuid
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
from .models import new_project
from .projects import atomic_json,save_project,operation_lock
from .figure_documents import save_figure,load_figure,source_signature,figure_catalog_metadata


def _now():return datetime.now(timezone.utc).isoformat()

def library_root(session):
    value=session.get('library_root')
    if not isinstance(value,str) or not value:raise ValueError('本地项目库路径未配置')
    root=Path(value).expanduser().resolve();root.mkdir(parents=True,exist_ok=True);return root


def _index(root):
    path=root/'index.json'
    if not path.exists():return dict(version=1,entries=[],projects=[])
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
        if data.get('version')!=1 or not isinstance(data.get('entries'),list):raise ValueError()
        ids=[r['entry_id'] for r in data['entries']]
        if len(ids)!=len(set(ids)) or any(not all(isinstance(r.get(k),str) and r[k] for k in ['entry_id','project_id','name','path','last_opened']) for r in data['entries']):raise ValueError()
        projects = data.setdefault('projects', [])
        if not isinstance(projects, list):
            raise ValueError()
        project_ids = [p['id'] for p in projects]
        if len(set(project_ids)) != len(project_ids) or any(
            not isinstance(p['id'], str) or not p['id'] or
            not isinstance(p['name'], str) or not p['name'].strip() or
            type(p['pinned']) is not bool or not isinstance(p['created_at'], str)
            for p in projects
        ):
            raise ValueError()
        return data
    except (ValueError,KeyError,TypeError,AttributeError):raise ValueError('项目列表索引损坏；原项目保持不变，可通过“打开项目”继续访问')


def _project(path):
    root=Path(path).expanduser().resolve()
    if root.suffix not in ('.titanwb','.titanif'):raise ValueError('请选择 .titanwb 或 .titanif 项目文件夹')
    try:p=json.loads((root/'project.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):raise ValueError('项目文件夹不存在、已移动或清单损坏，请重新定位')
    if not isinstance(p,dict) or not isinstance(p.get('id'),str) or not isinstance(p.get('name'),str):raise ValueError('项目清单身份无效')
    return root,p


def _public(entry):
    row=dict(entry,module=entry.get('module','wb'),available=True,figures=[],collection_id=entry.get('collection_id'))
    try:
        root,p=_project(entry['path']);row.update(name=p['name'],project_id=p['id'],revision=p.get('revision'),module=p.get('module','wb'))
        if row['module']=='wb':
            try:row['figures']=figure_catalog_metadata(root,source_signature(p))
            except ValueError as e:row['figure_error']=str(e)
    except ValueError as e:row.update(available=False,error=str(e))
    return row


def _rows(data):
    return [_public(row) for row in sorted(data['entries'], key=lambda row: row['last_opened'], reverse=True)]


def library_list(session):
    return _rows(_index(library_root(session)))


def library_workspace(session):
    data = _index(library_root(session))
    return dict(projects=data['projects'], entries=_rows(data))


@contextmanager
def _edit_index(session):
    root = library_root(session)
    with operation_lock(root, '.index.lock'):
        data = _index(root)
        yield data
        atomic_json(root / 'index.json', data)


def _find(rows, key, value, error):
    for row in rows:
        if row[key] == value:
            return row
    raise ValueError(error)


def _entry(data, entry_id):
    return _find(data['entries'], 'entry_id', entry_id, '找不到该分析记录')


def _collection(data, collection_id):
    return _find(data['projects'], 'id', collection_id, '找不到该课题项目')


def _name(name):
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
        raise ValueError('请输入 1–120 个字符的名称')
    return name.strip()


def _new_collection(data, name):
    project = dict(id=uuid.uuid4().hex, name=_name(name), pinned=False, created_at=_now())
    data['projects'].append(project)
    return project


def library_create_collection(name, session):
    with _edit_index(session) as data:
        return _new_collection(data, name)


def library_update_collection(collection_id, patch, session):
    if not isinstance(patch, dict) or not patch.keys() <= {'name', 'pinned'}:
        raise ValueError('课题项目设置无效')
    patch = dict(patch)
    if 'name' in patch:
        patch['name'] = _name(patch['name'])
    if 'pinned' in patch and type(patch['pinned']) is not bool:
        raise ValueError('置顶设置无效')
    with _edit_index(session) as data:
        project = _collection(data, collection_id)
        project.update(patch)
        return project


def library_remove_collection(collection_id, session):
    with _edit_index(session) as data:
        data['projects'].remove(_collection(data, collection_id))
        for entry in data['entries']:
            if entry.get('collection_id') == collection_id:
                entry['collection_id'] = None
    return True


def library_assign(entry_id, collection_id, session):
    with _edit_index(session) as data:
        if collection_id is not None:
            _collection(data, collection_id)
        _entry(data, entry_id)['collection_id'] = collection_id
    return True


def library_set_resume(entry_id, resume, session):
    if not isinstance(resume, dict) or resume.get('view') not in ('workspace', 'results', 'figure'):
        raise ValueError('续做位置无效')
    value = dict(view=resume['view'])
    if 'artifact_id' in resume:
        identifier = resume['artifact_id']
        if value['view'] != 'figure' or not isinstance(identifier, str) or not 0 < len(identifier) <= 200:
            raise ValueError('图表续做位置无效')
        value['artifact_id'] = identifier
    with _edit_index(session) as data:
        _entry(data, entry_id)['resume'] = value
    return True


def _register(data, folder, manifest, *, entry_id=None, source_entry_id=None, touch_opened=True):
    path = str(folder)
    project_id = manifest['id']
    module = manifest.get('module', 'wb')
    existing = next((entry for entry in data['entries'] if entry['path'] == path), None)
    entry = existing
    if entry_id is not None:
        entry = _entry(data, entry_id)
        if entry['project_id'] != project_id or entry.get('module', 'wb') != module:
            raise ValueError('重新定位的项目身份不匹配')
        if existing is not None and existing is not entry:
            raise ValueError('此位置已登记为另一条项目记录')
    if entry is not None and (entry['project_id'] != project_id or entry.get('module', 'wb') != module):
        raise ValueError('此路径已登记给其他分析，请先重新定位旧分析')
    if entry is None:
        stamp = _now()
        entry = dict(entry_id=uuid.uuid4().hex, created_at=stamp, last_opened=stamp)
        if source_entry_id is not None:
            source = _entry(data, source_entry_id)
            if source['project_id'] != project_id or source.get('module', 'wb') != module:
                raise ValueError('分析副本与来源身份不一致')
            entry['collection_id'] = source.get('collection_id')
        data['entries'].append(entry)
    entry.update(project_id=project_id, name=manifest['name'], path=path, module=module)
    if touch_opened:
        entry['last_opened'] = _now()
    return entry


def library_register(path, session, entry_id=None, *, source_entry_id=None, touch_opened=True):
    folder, manifest = _project(path)
    with _edit_index(session) as data:
        entry = _register(data, folder, manifest, entry_id=entry_id,
                          source_entry_id=source_entry_id, touch_opened=touch_opened)
    return _public(entry)


def create_managed_analysis(project, suffix, save, session, *, collection_id=None, new_collection_name=None):
    if collection_id is not None and new_collection_name is not None:
        raise ValueError('请选择已有课题或新建课题')
    root = library_root(session)
    path = root / 'Projects' / (project['id'] + suffix)
    created = False
    try:
        with _edit_index(session) as data:
            if new_collection_name is not None:
                collection_id = _new_collection(data, new_collection_name)['id']
            elif collection_id is not None:
                _collection(data, collection_id)
            path.mkdir(parents=True)
            created = True
            saved = save(project, str(path), None, session)
            entry = _register(data, path, saved)
            entry['collection_id'] = collection_id
    except Exception:
        if created:
            shutil.rmtree(path)
        raise
    return dict(project=saved, entry=_public(entry))


def library_create(name, session, *, collection_id=None, new_collection_name=None):
    return create_managed_analysis(new_project(_name(name)), '.titanwb', save_project, session,
                                   collection_id=collection_id, new_collection_name=new_collection_name)


def library_remove(entry_id, session):
    with _edit_index(session) as data:
        data['entries'] = [entry for entry in data['entries'] if entry['entry_id'] != entry_id]
    return True
