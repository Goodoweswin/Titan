"""Atomic portable projects, optimistic versions and session locks."""
import copy,json,shutil
from pathlib import Path
from titan_wb.projects import atomic_json,check_lock,operation_lock,process_alive,writer_identity
from .models import validate

def load(path,session):
    root=Path(path).expanduser().resolve()
    if root.suffix!='.titanstats':raise ValueError('请选择 .titanstats 项目目录')
    p=json.loads((root/'project.json').read_text(encoding='utf-8'));validate(p)
    with operation_lock(root,'.save.lock'):
        lock=root/'.writer.lock'
        if lock.exists():
            owner=json.loads(lock.read_text())
            if owner!=writer_identity(session) and not process_alive(int(owner['pid'])):lock.unlink()
        check_lock(root,session)
    p.update(project_path=str(root),saved_revision=p['revision']);return p

def save(p,path,expected,session):
    validate(p);root=Path(path).expanduser().resolve()
    if root.suffix!='.titanstats':raise ValueError('项目目录名需以 .titanstats 结尾')
    root.mkdir(parents=True,exist_ok=True)
    with operation_lock(root,'.save.lock'):
        check_lock(root,session);manifest=root/'project.json'
        if manifest.exists():
            disk=json.loads(manifest.read_text(encoding='utf-8'))
            if disk['id']!=p['id'] or disk['revision']!=expected:raise ValueError('磁盘版本已改变，请重新打开，当前修改未覆盖')
            if p['revision']<disk['revision']:raise ValueError('不能回退磁盘版本')
            # Linked source tables can only be replaced through the explicit source-update command.
            if not session.get('stats_source_update'):
                for old in disk['datasets']:
                    if old.get('source',{} ) and old['source'].get('locked'):
                        new=next((d for d in p['datasets'] if d['id']==old['id']),None)
                        if new and any(new.get(k)!=old.get(k) for k in ['rows','source','groups']):raise ValueError('来源表不可修改数值，请更新来源或复制为独立表')
            (root/'backups').mkdir(exist_ok=True);shutil.copy2(manifest,root/'backups/previous.json')
        elif any(f.name not in ['.save.lock','.writer.lock'] for f in root.iterdir()):raise ValueError('请选择空目录，避免覆盖已有文件')
        data=copy.deepcopy(p)
        for k in ['project_path','saved_revision']:data.pop(k,None)
        atomic_json(manifest,data)
    return {**p,'project_path':str(root),'saved_revision':p['revision']}
