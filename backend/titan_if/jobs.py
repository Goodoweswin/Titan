"""Small engine requests supervise file-backed, isolated IF calculation jobs."""
import copy
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

import numpy as np
import tifffile
from titan_wb.projects import atomic_json,operation_lock,process_alive
from .models import validate_project,analysis_signature,segmentation_signature,bound_result_previews,json_safe_integers
from .projects import stream_hash

_CHILDREN={}
_TERMINAL={"completed","failed","cancelled"}
_WINDOWS = os.name == "nt"


def _root(session):
    value=session.get("library_root")
    if not isinstance(value,str) or not value:raise ValueError("后台任务需要本地项目库")
    root=Path(value).expanduser().resolve()/"if-jobs";root.mkdir(parents=True,exist_ok=True)
    return root


def _directory(job_id,session):
    if not isinstance(job_id,str) or not re.fullmatch(r"[a-f0-9]{32}",job_id):raise ValueError("任务身份无效")
    root=_root(session)/job_id
    try:request=json.loads((root/"request.json").read_text(encoding="utf-8"))
    except (OSError,ValueError):raise ValueError("任务不存在")
    if request["owner"]!={k:session[k] for k in ["pid","token"]}:raise ValueError("此任务属于另一会话")
    return root,request


def _status_io(operation):
    # On Windows an open can race the worker's atomic rename, and an open
    # reader can briefly prevent a rename. Keep retries short and bounded.
    for delay in (.01, .02, .04, .08, .16):
        try:
            return operation()
        except PermissionError:
            if not _WINDOWS:
                raise
            time.sleep(delay)
    return operation()


def _read_status(directory):
    path = directory / "status.json"
    return json.loads(_status_io(lambda: path.read_text(encoding="utf-8")))


def _write_status(directory, state):
    _status_io(lambda: atomic_json(directory / "status.json", state))


def start(project,operation,options,session):
    if operation != "volume":
        validate_project(project)
        if project.get("read_only"):raise ValueError("只读项目不能执行修改或计算")
        if operation not in ["import","segment","measure","batch","edit_mask"]:raise ValueError("不支持的免疫荧光任务")
    options=options or {};root=_root(session)
    with operation_lock(root,".queue.lock"):
        for child_id,child in list(_CHILDREN.items()):
            if child.poll() is not None:_CHILDREN.pop(child_id,None)
        # One active IF worker per app session bounds peak working memory.
        for folder in root.iterdir():
            if not folder.is_dir():continue
            try:
                req=json.loads((folder/"request.json").read_text(encoding="utf-8"))
                state=_read_status(folder)
                if req.get("operation") == "volume" and not process_alive(req["owner"]["pid"]):
                    if state["status"] in _TERMINAL or not process_alive(state.get("pid", 0)):
                        (folder / "volume.raw").unlink(missing_ok=True)
                        (folder / "volume.part").unlink(missing_ok=True)
                if req["owner"]=={k:session[k] for k in ["pid","token"]} and state["status"] not in _TERMINAL:
                    pid=state.get("pid")
                    if not pid and (folder/"worker.json").exists():
                        pid=json.loads((folder/"worker.json").read_text(encoding="utf-8"))["pid"]
                    if pid and process_alive(pid):
                        raise ValueError("已有免疫荧光后台任务，请完成或取消后重试")
            except (OSError,KeyError,json.JSONDecodeError):continue
        job_id=uuid.uuid4().hex;directory=root/job_id;directory.mkdir()
        request=dict(job_id=job_id,owner={k:session[k] for k in ["pid","token"]},
                     project=project,operation=operation,options=options,
                     signatures={f["id"]:analysis_signature(f) for f in project["fields"]} if project else {})
        atomic_json(directory/"request.json",request)
        _write_status(directory,dict(job_id=job_id,status="queued",completed=0,total=1,message="等待后台处理"))
        if getattr(sys,"frozen",False):
            command=[sys.executable,"--if-job",str(directory)]
        else:
            command=[sys.executable,str(Path(__file__).resolve().parents[1]/"entry.py"),"--if-job",str(directory)]
        try:
            with (directory/"worker.log").open("ab") as log:
                child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=log,
                    creationflags=0x08000000 if os.name=="nt" else 0)
        except OSError as error:
            _write_status(directory,dict(job_id=job_id,status="failed",completed=0,total=1,
                        message="无法启动后台任务",error=str(error)))
            raise ValueError("无法启动免疫荧光后台任务") from error
        _CHILDREN[job_id]=child
        atomic_json(directory/"worker.json",dict(pid=child.pid))
    return dict(job_id=job_id,status="queued")


def status(job_id,session):
    directory,_=_directory(job_id,session)
    state=_read_status(directory)
    if (directory/".cancel").exists():
        return dict(state,status="cancelled",message="任务已取消，计算结果不会写入项目")
    pid=state.get("pid")
    if not pid and (directory/"worker.json").exists():
        pid=json.loads((directory/"worker.json").read_text(encoding="utf-8"))["pid"]
    if state["status"] not in _TERMINAL and pid and not process_alive(pid):
        state.update(status="failed",error="后台进程已退出，请重新执行；原结果保留",message="任务中断")
        _write_status(directory,state)
    return state


def cancel(job_id,session):
    directory,request=_directory(job_id,session)
    # Cooperative cancellation remains valid across short-lived integration engines.
    (directory/".cancel").touch()
    if request["operation"] == "volume":
        (directory / "volume.raw").unlink(missing_ok=True)
    return status(job_id,session)


def _mask(labels,field,directory):
    masks=directory/"masks";masks.mkdir(exist_ok=True)
    path=masks/(uuid.uuid4().hex+".tif");tifffile.imwrite(path,labels.astype(np.uint32),photometric="minisblack")
    old=field.get("mask");history=[]
    if old:
        history=copy.deepcopy(old.get("history",[]))+[{k:v for k,v in old.items() if k!="history"}]
    return dict(path=str(path),sha256=stream_hash(path),version=(old or {}).get("version",0)+1,
                segmentation_signature=segmentation_signature(field),confirmed=False,history=history)


def stage_result(result,directory):
    """Keep the authoritative table on disk; bound UI rows and JSON integers."""
    folder=Path(directory)/"results";folder.mkdir(exist_ok=True)
    path=folder/(uuid.uuid4().hex+".json");atomic_json(path,result)
    preview=copy.deepcopy(result)
    preview["total_objects"]=len(result.get("objects",[]))
    preview["objects_truncated"]=preview["total_objects"]>500
    preview["objects"]=preview.get("objects",[])[:500]
    preview=json_safe_integers(preview)
    preview["artifact"]=dict(path=str(path),sha256=stream_hash(path))
    return preview


def _load_mask(field,require_confirmed=False):
    mask=field.get("mask")
    if not mask:raise ValueError("请先分割细胞核")
    if require_confirmed and not mask.get("confirmed"):raise ValueError("请先检查并确认分割结果")
    if mask.get("segmentation_signature")!=segmentation_signature(field):raise ValueError("分割参数或区域已变化，请重新分割")
    if not Path(mask["path"]).is_file() or stream_hash(mask["path"])!=mask["sha256"]:raise ValueError("分割结果缺失或校验失败")
    labels=tifffile.imread(mask["path"])
    if labels.shape!=(field["height"],field["width"]) or labels.dtype.kind not in "ui":
        raise ValueError("分割标签尺寸或类型无效")
    return labels


def _remap_recipe(recipe,source,target):
    result=copy.deepcopy(recipe)
    names={c["id"]:c["name"] for c in source["channels"]}
    dest={c["name"]:c["id"] for c in target["channels"]}
    def mapped(channel):
        if names.get(channel) not in dest:raise ValueError("批处理视野缺少模板通道 "+names.get(channel,channel))
        return dest[names[channel]]
    result["nuclear_channel_id"]=mapped(recipe["nuclear_channel_id"])
    result["target_channel_ids"]=[mapped(c) for c in recipe["target_channel_ids"]]
    result["thresholds"]={mapped(c):v for c,v in recipe.get("thresholds",{}).items()}
    if recipe.get("thresholds_frozen") and source.get("batch_id")!=target.get("batch_id"):
        raise ValueError("冻结阈值只能应用于同一成像批次")
    return result


def run(directory):
    """Child-process entry; never writes the live project manifest."""
    directory=Path(directory);request=json.loads((directory/"request.json").read_text(encoding="utf-8"))
    state=dict(job_id=request["job_id"],status="running",pid=os.getpid(),completed=0,total=1,message="准备处理")
    def publish(**changes):
        state.update(changes);_write_status(directory,state)
    def cancelled():
        return (directory/".cancel").exists() or not process_alive(request["owner"]["pid"])
    try:
        if cancelled():return
        publish();operation=request["operation"];options=request["options"]
        if operation == "volume":
            from .volume import prepare_volume
            result = prepare_volume(options, directory / "volume.raw",
                                    lambda done, total: publish(completed=done, total=total, message="读取 Z 层"),
                                    cancelled)
            if result is not None and not cancelled():
                publish(status="completed", message="体数据已就绪", volume=result)
            return
        p=copy.deepcopy(request["project"])
        from .images import import_field
        from .analysis import segment_nuclei,measure_field,edit_labels
        failures=[];changed=[]
        if operation=="import":
            publish(message="读取通道、校验并复制原图")
            f=import_field(options["selections"],options.get("metadata"))
            from .projects import _copy_verified
            for c in f["channels"]:
                source=c["source"];dest=directory/"originals"/(source["sha256"]+Path(source["path"]).suffix.lower())
                _copy_verified(source["path"],dest,source["sha256"]);source["path"]=str(dest)
            p["fields"].append(f);changed.append(f["id"]);publish(completed=1)
        else:
            ids=options.get("field_ids",[options.get("field_id")]) if operation=="batch" else [options.get("field_id")]
            if not ids or any(not any(f["id"]==i for f in p["fields"]) for i in ids):
                raise ValueError("任务引用的视野不存在")
            publish(total=len(ids))
            template=options.get("recipe")
            template_source=next((f for f in p["fields"] if f["id"]==options.get("template_field_id")),None)
            if template and not template_source:
                template_source=next((f for f in p["fields"] if any(c["id"]==template.get("nuclear_channel_id") for c in f["channels"])),None)
            for index,field_id in enumerate(ids):
                if cancelled():return
                f=next(f for f in p["fields"] if f["id"]==field_id)
                publish(message="处理 "+f.get("name",field_id))
                try:
                    if template:
                        if template_source is None:raise ValueError("找不到模板来源视野")
                        f["recipe"]=_remap_recipe(template,template_source,f)
                    action=options.get("action","measure") if operation=="batch" else operation
                    if action=="segment":
                        f["mask"]=_mask(segment_nuclei(f),f,directory);f["result"]=None
                    elif action=="edit_mask":
                        labels=edit_labels(_load_mask(f),options["action"])
                        f["mask"]=_mask(labels,f,directory);f["result"]=None
                    elif action=="measure":
                        labels=_load_mask(f,True) if f["recipe"]["mode"]=="nuclei" else None
                        result=measure_field(f,labels)
                        result["input_signature"]=analysis_signature(f)
                        f["result"]=stage_result(result,directory)
                    else:raise ValueError("批处理操作无效")
                    changed.append(field_id)
                except Exception as error:
                    if operation!="batch":raise
                    failures.append(dict(field_id=field_id,error=str(error)))
                publish(completed=index+1)
        if cancelled():return
        atomic_json(directory/"output.json",dict(project=p,changed=changed,failures=failures))
        publish(status="completed",message="处理完成"+("，部分视野失败" if failures else ""),failures=failures)
    except Exception as error:
        publish(status="failed",error=str(error),message="处理失败，原结果保留")
    finally:
        (directory/".finished").touch()
        if cancelled():
            if request["operation"] == "volume":
                (directory / "volume.raw").unlink(missing_ok=True)
            publish(status="cancelled",message="任务已取消")


def accept(project,job_id,session):
    validate_project(project)
    if project.get("read_only"):raise ValueError("只读项目不能接收计算结果")
    directory,request=_directory(job_id,session);state=status(job_id,session)
    if request["operation"] == "volume":raise ValueError("3D 查看任务不写入项目")
    if state["status"]=="cancelled":raise ValueError("任务已取消")
    if state["status"]!="completed":raise ValueError("任务尚未完成")
    if project["id"]!=request["project"]["id"]:raise ValueError("任务对应的项目已变化")
    output=json.loads((directory/"output.json").read_text(encoding="utf-8"));p=copy.deepcopy(project)
    if request["operation"]=="import":
        for f in output["project"]["fields"]:
            if f["id"] in output["changed"] and not any(x["id"]==f["id"] for x in p["fields"]):p["fields"].append(f)
    else:
        for field_id in output["changed"]:
            current=next((f for f in p["fields"] if f["id"]==field_id),None)
            if current is None or analysis_signature(current)!=request["signatures"].get(field_id):
                raise ValueError("分析输入已变化，此任务结果已过时，请重新计算")
        for field_id in output["changed"]:
            current=next(f for f in p["fields"] if f["id"]==field_id)
            result=next(f for f in output["project"]["fields"] if f["id"]==field_id)
            for key in ["mask","result","recipe"]:current[key]=result.get(key)
    p["revision"]+=1
    p["last_job_failures"]=output.get("failures",[])
    return bound_result_previews(p)
