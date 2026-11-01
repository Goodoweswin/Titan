"""Portable project folders, atomic manifests and session-owned writer locks."""
import copy
import time
from contextlib import contextmanager,nullcontext
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


def writer_identity(session):return {k:session[k] for k in ['pid','token']}

def check_lock(root,session,acquire=True):
    session=writer_identity(session)
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
    if project.get('upgrade_from') and root==Path(project['upgrade_from']).resolve():raise ValueError('旧项目升级需要另存新副本，原项目保持不变')
    if root.suffix!='.titanwb':raise ValueError('项目目录名需以.titanwb结尾')
    previous=Path(project['project_path']).resolve() if project.get('project_path') else None
    if previous and previous!=root and (root.is_relative_to(previous) or previous.is_relative_to(root)):raise ValueError('副本位置不能与原项目内部嵌套')
    root.mkdir(parents=True,exist_ok=True)
    manifest=root/'project.json'
    if manifest.exists():
        disk=json.loads(manifest.read_text(encoding='utf-8'))
        if disk['id']!=project['id'] or disk['revision']!=expected_revision:raise ValueError('磁盘项目版本已变化，拒绝覆盖；请重新打开')
    elif any(x.name not in ['.writer.lock'] for x in root.iterdir()):raise ValueError('请选择空项目目录，避免覆盖已有文件')
    check_lock(root,session)
    # Another writer may have committed and released between the precheck and lock.
    if manifest.exists():
        disk=json.loads(manifest.read_text(encoding='utf-8'))
        if disk['id']!=project['id'] or disk['revision']!=expected_revision:raise ValueError('磁盘项目版本已变化，拒绝覆盖；请重新打开')
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
        a['path']=dest.relative_to(root).as_posix()
    if previous and previous!=root:
        # Portable figures can reference originals no longer present in the current image list.
        figures=previous/'figures'
        with operation_lock(figures,'.catalog.lock') if figures.is_dir() else nullcontext():
            for folder in ['originals','figures']:
                source_folder=previous/folder
                if source_folder.is_dir():
                    for item in source_folder.rglob('*'):
                        relative=item.relative_to(source_folder)
                        if any(part.startswith('.figure-stage-') for part in relative.parts):continue
                        if item.is_symlink():raise ValueError('项目历史包含符号链接，不能安全另存')
                        if item.is_file() and item.name!='.catalog.lock':
                            target=root/folder/relative;target.parent.mkdir(parents=True,exist_ok=True)
                            if target.exists() and file_hash(target)!=file_hash(item):raise ValueError('副本历史文件冲突')
                            if not target.exists():shutil.copy2(item,target)
    for key in ['project_path','saved_revision','read_only','upgrade_from']:p.pop(key,None)
    if manifest.exists():
        (root/'backups').mkdir(exist_ok=True)
        shutil.copy2(manifest,root/'backups/previous.json')
    atomic_json(manifest,p)
    return open_project(str(root),session)


def open_project(path,session,read_only=False):
    root=Path(path).expanduser().resolve()
    p=json.loads((root/'project.json').read_text(encoding='utf-8'))
    legacy=p.get('schema_version')==1
    disk_revision=p['revision']
    from .migrations import migrate_project
    p=migrate_project(p)
    validate_project(p)
    for a in p['images']:
        full=(root/a['path'].replace('\\','/')).resolve()
        if not full.is_relative_to(root/'originals'):raise ValueError('项目原图路径越过originals目录')
        if not full.is_file() or file_hash(full)!=a['sha256']:raise ValueError('项目原图缺失或hash不匹配')
        a['path']=str(full)
    if not read_only:check_lock(root,session)
    p.update(project_path=str(root),saved_revision=disk_revision,read_only=read_only)
    if legacy:p['upgrade_from']=str(root)
    return p


def release_project(path,session):
    lock=Path(path)/'.writer.lock'
    if lock.exists() and json.loads(lock.read_text(encoding='utf-8'))==writer_identity(session):lock.unlink()


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
    from .migrations import migrate_project
    root=Path(path);lock=root/'.writer.lock'
    if lock.exists():
        owner=json.loads(lock.read_text(encoding='utf-8'))
        if owner!=writer_identity(session):
            if process_alive(int(owner['pid'])):raise ValueError('旧写入进程仍在运行，不能恢复锁')
            lock.unlink()
    try:
        content=json.loads((root/'project.json').read_text(encoding='utf-8'))
        validate_project(migrate_project(content))
    except (ValueError,KeyError,TypeError):
        backup=root/'backups/previous.json'
        try:
            content=json.loads(backup.read_text(encoding='utf-8'));validate_project(migrate_project(content))
        except Exception:raise ValueError('当前manifest损坏，且没有有效备份；原项目保持不变')
        dest=root.with_name(root.stem+'-恢复-'+uuid.uuid4().hex[:8]+'.titanwb')
        shutil.copytree(root,dest,ignore=shutil.ignore_patterns('.writer.lock'))
        atomic_json(dest/'project.json',content)
        return open_project(str(dest),session)
    return open_project(path,session)


@contextmanager
def operation_lock(root,name,timeout=3):
    """OS-backed metadata mutex; automatically released when a worker exits.

    Keep the lock inode in place: unlinking an active/advisory lock could let
    another process lock a different inode while the first transaction runs.
    """
    import errno
    path=Path(root)/name;started=time.monotonic()
    with path.open('a+b') as handle:
        if path.stat().st_size==0:handle.write(b'1');handle.flush()
        if os.name=='nt':
            import msvcrt
            def acquire():
                handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            def release():
                handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            def acquire():fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            def release():fcntl.flock(handle.fileno(),fcntl.LOCK_UN)
        while True:
            try:acquire();break
            except OSError as e:
                if e.errno not in (errno.EACCES,errno.EAGAIN):raise ValueError('文件系统无法锁定项目元数据，请选择支持本地文件锁的位置') from e
                if time.monotonic()-started>timeout:raise ValueError('项目列表正被其他进程更新，请稍后重试')
                time.sleep(.02)
        try:yield
        finally:release()
