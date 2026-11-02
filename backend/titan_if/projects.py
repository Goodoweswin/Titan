"""Portable IF originals, immutable masks, optimistic revision and writer locks."""
import copy
import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path

from titan_wb.projects import atomic_json,check_lock,operation_lock,writer_identity,process_alive
from .models import validate_project,bound_result_previews


def stream_hash(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()


def _copy_verified(source,dest,digest):
    source=Path(source).resolve()
    if not source.is_file() or stream_hash(source)!=digest:
        raise ValueError("原图或分割结果缺失、hash 已改变")
    if dest.exists():
        if stream_hash(dest)!=digest:raise ValueError("项目原图或分割文件校验冲突")
        return
    dest.parent.mkdir(parents=True,exist_ok=True)
    temp=dest.with_name("."+dest.name+"."+uuid.uuid4().hex+".tmp")
    try:
        shutil.copyfile(source,temp)
        if stream_hash(temp)!=digest:raise ValueError("复制期间来源发生变化")
        os.replace(temp,dest)
    finally:temp.unlink(missing_ok=True)


def _check_revision(root,p,expected):
    manifest=root/"project.json"
    if manifest.exists():
        disk=json.loads(manifest.read_text(encoding="utf-8"))
        if disk["id"]!=p["id"] or disk["revision"]!=expected:
            raise ValueError("磁盘项目版本已变化，请重新打开后保存")
    elif any(x.name not in [".writer.lock",".save.lock"] for x in root.iterdir()):
        raise ValueError("请选择空项目目录")


def save_project(project,path,expected_revision,session):
    validate_project(project)
    if project.get("read_only"):raise ValueError("只读项目不能保存，请另存副本")
    root=Path(path).expanduser().resolve()
    if root.suffix!=".titanif":raise ValueError("免疫荧光项目目录需以 .titanif 结尾")
    previous=Path(project["project_path"]).resolve() if project.get("project_path") else None
    if previous and previous!=root and (root.is_relative_to(previous) or previous.is_relative_to(root)):
        raise ValueError("副本位置不能嵌套于原项目")
    root.mkdir(parents=True,exist_ok=True)
    check_lock(root,session)
    with operation_lock(root,".save.lock"):
        _check_revision(root,project,expected_revision)
        p=copy.deepcopy(project)
        for f in p["fields"]:
            for channel in f["channels"]:
                source=channel["source"];suffix=Path(source["path"]).suffix.lower()
                dest=root/"originals"/(source["sha256"]+suffix)
                _copy_verified(source["path"],dest,source["sha256"])
                source["path"]=dest.relative_to(root).as_posix()
            if f.get("mask"):
                for mask in [f["mask"],*f["mask"].get("history",[])]:
                    dest=root/"masks"/(mask["sha256"]+".tif")
                    _copy_verified(mask["path"],dest,mask["sha256"])
                    mask["path"]=dest.relative_to(root).as_posix()
            if f.get("result",{} ) and f["result"].get("artifact"):
                result=f["result"]["artifact"];dest=root/"results"/(result["sha256"]+".json")
                _copy_verified(result["path"],dest,result["sha256"])
                result["path"]=dest.relative_to(root).as_posix()
        # Preserve manual mask versions and audit manifests when saving a copy.
        if previous and previous!=root:
            for folder in ["masks","results","history"]:
                for item in (previous/folder).rglob("*") if (previous/folder).exists() else []:
                    if item.is_symlink():raise ValueError("项目历史包含不支持的符号链接")
                    if item.is_file():
                        dest=root/folder/item.relative_to(previous/folder)
                        _copy_verified(item,dest,stream_hash(item))
        for key in ["project_path","saved_revision","read_only"]:p.pop(key,None)
        history=root/"history";history.mkdir(exist_ok=True)
        manifest=root/"project.json"
        if manifest.exists():
            old=json.loads(manifest.read_text(encoding="utf-8"))
            atomic_json(history/(str(old["revision"])+"-"+uuid.uuid4().hex[:8]+".json"),old)
        atomic_json(manifest,p)
    return open_project(str(root),session)


def _resolve(root,relative,folder):
    p=(root/relative.replace("\\","/")).resolve()
    if Path(relative).is_absolute() or not p.is_relative_to(root/folder):
        raise ValueError("项目来源路径越过 "+folder+" 目录")
    return p


def open_project(path,session,read_only=False):
    root=Path(path).expanduser().resolve()
    if root.suffix!=".titanif":raise ValueError("请选择 .titanif 项目")
    p=json.loads((root/"project.json").read_text(encoding="utf-8"))
    validate_project(p);checked={}
    for f in p["fields"]:
        records=[(c["source"],"originals") for c in f["channels"]]
        if f.get("mask"):records.extend((m,"masks") for m in [f["mask"],*f["mask"].get("history",[])])
        if f.get("result") and f["result"].get("artifact"):records.append((f["result"]["artifact"],"results"))
        for record,folder in records:
            full=_resolve(root,record["path"],folder)
            if str(full) not in checked:
                if not full.is_file():raise ValueError("项目原图或分割结果缺失")
                checked[str(full)]=stream_hash(full)
            if checked[str(full)]!=record["sha256"]:raise ValueError("项目原图或分割结果 hash 校验失败")
            record["path"]=str(full)
    if not read_only:check_lock(root,session)
    p.update(project_path=str(root),saved_revision=p["revision"],read_only=read_only)
    return bound_result_previews(p)


def release_project(path,session):
    lock=Path(path)/".writer.lock"
    if lock.exists() and json.loads(lock.read_text())==writer_identity(session):lock.unlink()


def recover_project(path,session):
    root=Path(path);lock=root/".writer.lock"
    if lock.exists():
        owner=json.loads(lock.read_text())
        if owner!=writer_identity(session):
            if process_alive(int(owner["pid"])):raise ValueError("原项目仍有写入者，请关闭另一窗口或只读打开")
            lock.unlink()
    return open_project(path,session)
