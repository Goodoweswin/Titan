"""A local index of explicitly created/opened portable projects. No disk scan."""
import json,uuid
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
    if not path.exists():return dict(version=1,entries=[])
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
        if data.get('version')!=1 or not isinstance(data.get('entries'),list):raise ValueError()
        ids=[r['entry_id'] for r in data['entries']]
        if len(ids)!=len(set(ids)) or any(not all(isinstance(r.get(k),str) and r[k] for k in ['entry_id','project_id','name','path','last_opened']) for r in data['entries']):raise ValueError()
        return data
    except (ValueError,KeyError,TypeError,AttributeError):raise ValueError('项目列表索引损坏；原项目保持不变，可通过“打开项目”继续访问')


def _project(path):
    root=Path(path).expanduser().resolve()
    if root.suffix not in ('.titanwb','.titanif','.titanstats'):raise ValueError('请选择 .titanwb、.titanif 或 .titanstats 项目文件夹')
    try:p=json.loads((root/'project.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):raise ValueError('项目文件夹不存在、已移动或清单损坏，请重新定位')
    if not isinstance(p,dict) or not isinstance(p.get('id'),str) or not isinstance(p.get('name'),str):raise ValueError('项目清单身份无效')
    return root,p


def _public(entry):
    row=dict(entry,module=entry.get('module','wb'),available=True,figures=[])
    try:
        root,p=_project(entry['path']);row.update(name=p['name'],project_id=p['id'],revision=p.get('revision'),module=p.get('module','wb'))
        if row['module']=='wb':
            try:row['figures']=figure_catalog_metadata(root,source_signature(p))
            except ValueError as e:row['figure_error']=str(e)
    except ValueError as e:row.update(available=False,error=str(e))
    return row


def library_list(session):
    root=library_root(session)
    return [_public(r) for r in sorted(_index(root)['entries'],key=lambda r:r.get('last_opened',''),reverse=True)]


def library_register(path,session,entry_id=None):
    root=library_root(session);folder,p=_project(path)
    with operation_lock(root,'.index.lock'):
        data=_index(root)
        if entry_id:
            entry=next((r for r in data['entries'] if r['entry_id']==entry_id),None)
            if not entry or entry['project_id']!=p['id']:raise ValueError('重新定位的项目身份不匹配')
            if any(r['entry_id']!=entry_id and r['path']==str(folder) for r in data['entries']):raise ValueError('此位置已登记为另一条项目记录')
        else:entry=next((r for r in data['entries'] if r['path']==str(folder)),None)
        if not entry:
            entry=dict(entry_id=uuid.uuid4().hex,created_at=_now());data['entries'].append(entry)
        entry.update(project_id=p['id'],name=p['name'],path=str(folder),last_opened=_now(),module=p.get('module','wb'))
        atomic_json(root/'index.json',data)
    return _public(entry)


def library_create(name,session):
    root=library_root(session);_index(root)  # Do not create orphan projects behind a corrupt index.
    p=new_project(name);path=root/'Projects'/(p['id']+'.titanwb')
    p=save_project(p,str(path),None,session)
    return dict(project=p,entry=library_register(str(path),session))


def library_remove(entry_id,session):
    root=library_root(session)
    with operation_lock(root,'.index.lock'):
        data=_index(root);data['entries']=[r for r in data['entries'] if r['entry_id']!=entry_id];atomic_json(root/'index.json',data)
    return True
