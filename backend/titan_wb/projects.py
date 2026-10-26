"""Portable project folders, atomic manifests and session-owned writer locks."""
import copy
import json
import os
import re
import shutil
import uuid
from pathlib import Path
from .models import validate_project
from .images import file_hash


def atomic_json(path,data):
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temp.open('w',encoding='utf-8') as f:
            json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        temp.unlink(missing_ok=True)


def check_lock(root,session,acquire=True):
    lock=root/'.writer.lock'
    if lock.exists():
        owner=json.loads(lock.read_text(encoding='utf-8'))
        if owner!=session:raise ValueError('项目已有写入者。可只读打开；确认旧进程退出后再恢复锁。')
    elif acquire:
        try:
            with lock.open('x') as f:json.dump(session,f)
        except FileExistsError:raise ValueError('另一窗口刚刚取得项目写入权')


def save_project(project,path,expected_revision,session):
    validate_project(project)
    if project.get('read_only'):raise ValueError('只读项目不能保存，请另存副本')
    root=Path(path).expanduser().resolve()
    if root.suffix!='.titanwb':raise ValueError('项目目录名需以.titanwb结尾')
    root.mkdir(parents=True,exist_ok=True)
    manifest=root/'project.json'
    if manifest.exists():
        disk=json.loads(manifest.read_text(encoding='utf-8'))
        if disk['id']!=project['id'] or disk['revision']!=expected_revision:raise ValueError('磁盘项目版本已变化，拒绝覆盖；请重新打开')
    elif any(x.name not in ['.writer.lock'] for x in root.iterdir()):raise ValueError('请选择空项目目录，避免覆盖已有文件')
    check_lock(root,session)
    p=copy.deepcopy(project)
    (root/'originals').mkdir(exist_ok=True)
    for a in p['images']:
        if not re.fullmatch('[A-Za-z0-9_-]{1,80}',a['id']):raise ValueError('图像ID不能作为安全文件名')
        source=Path(a['path'])
        if not source.is_file() or file_hash(source)!=a['sha256']:raise ValueError('原始文件不存在或已改变')
        dest=root/'originals'/(a['id']+source.suffix.lower())
        if source.resolve()!=dest.resolve():
            if dest.exists() and file_hash(dest)!=a['sha256']:raise ValueError('项目原图冲突')
            if not dest.exists():shutil.copy2(source,dest)
        a['path']=str(dest.relative_to(root))
    for key in ['project_path','saved_revision','read_only']:p.pop(key,None)
    if manifest.exists():
        (root/'backups').mkdir(exist_ok=True)
        shutil.copy2(manifest,root/'backups/previous.json')
    atomic_json(manifest,p)
    return open_project(str(root),session)


def open_project(path,session,read_only=False):
    root=Path(path).expanduser().resolve()
    p=json.loads((root/'project.json').read_text(encoding='utf-8'))
    validate_project(p)
    for a in p['images']:
        full=(root/a['path']).resolve()
        if not full.is_relative_to(root/'originals'):raise ValueError('项目原图路径越过originals目录')
        if not full.is_file() or file_hash(full)!=a['sha256']:raise ValueError('项目原图缺失或hash不匹配')
        a['path']=str(full)
    if not read_only:check_lock(root,session)
    p.update(project_path=str(root),saved_revision=p['revision'],read_only=read_only)
    return p


def release_project(path,session):
    lock=Path(path)/'.writer.lock'
    if lock.exists() and json.loads(lock.read_text(encoding='utf-8'))==session:lock.unlink()


def process_alive(pid):
    # A Windows os.kill(pid, 0) is not a POSIX liveness probe. Query only.
    if pid <= 0:
        return True
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        handle=kernel.OpenProcess(0x1000,False,pid)
        if not handle:
            # Invalid PID means absent; access denied/unknown is conservatively live.
            return ctypes.get_last_error()!=87
        try:
            code=wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)):
                return True
            return code.value==259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid,0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def recover_project(path,session):
    root=Path(path);lock=root/'.writer.lock'
    if lock.exists():
        owner=json.loads(lock.read_text(encoding='utf-8'))
        if owner!=session:
            if process_alive(int(owner['pid'])):raise ValueError('旧写入进程仍在运行，不能恢复锁')
            lock.unlink()
    try:
        content=json.loads((root/'project.json').read_text(encoding='utf-8'))
        validate_project(content)
    except (ValueError,KeyError,TypeError):
        backup=root/'backups/previous.json'
        try:
            content=json.loads(backup.read_text(encoding='utf-8'));validate_project(content)
        except Exception:raise ValueError('当前manifest损坏，且没有有效备份；原项目保持不变')
        dest=root.with_name(root.stem+'-恢复-'+uuid.uuid4().hex[:8]+'.titanwb')
        shutil.copytree(root,dest,ignore=shutil.ignore_patterns('.writer.lock'))
        atomic_json(dest/'project.json',content)
        return open_project(str(dest),session)
    return open_project(path,session)
