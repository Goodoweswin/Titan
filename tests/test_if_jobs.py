import copy
import time
from pathlib import Path
import pytest

from test_if_projects import fixture,session
from titan_if.jobs import start,status,cancel,accept


def finished(job,s):
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        result=status(job["job_id"],s)
        if result["status"] in ["completed","failed","cancelled"]:return result
        time.sleep(.04)
    raise AssertionError("background IF task did not finish")


def test_real_process_measure_is_staged_then_accepted_without_overwriting_display(tmp_path):
    p=fixture(tmp_path);s=session(tmp_path)
    j=start(p,"measure",dict(field_id="f1"),s)
    done=finished(j,s)
    assert done["status"]=="completed",done
    assert p["fields"][0]["result"] is None
    p["fields"][0]["channels"][0]["display_max"]=60
    updated=accept(p,j["job_id"],s)
    assert updated["fields"][0]["channels"][0]["display_max"]==60
    assert updated["fields"][0]["result"]["summary"][0]["raw_sum"]==2400


def test_stale_input_and_other_session_cannot_accept_task(tmp_path):
    p=fixture(tmp_path);s=session(tmp_path);j=start(p,"measure",dict(field_id="f1"),s)
    assert finished(j,s)["status"]=="completed"
    p["fields"][0]["recipe"]["thresholds"]={"c1":10}
    with pytest.raises(ValueError,match="变化|过时|失效"):accept(p,j["job_id"],s)
    with pytest.raises(ValueError,match="会话|任务"):status(j["job_id"],session(tmp_path,"other"))


def test_cancelled_task_never_activates_output(tmp_path):
    p=fixture(tmp_path);s=session(tmp_path);j=start(p,"measure",dict(field_id="f1"),s)
    cancel(j["job_id"],s)
    assert status(j["job_id"],s)["status"]=="cancelled"
    with pytest.raises(ValueError,match="取消"):accept(p,j["job_id"],s)
    assert p["fields"][0]["result"] is None


def test_segment_and_manual_revision_survive_project_save(tmp_path):
    import numpy as np
    import tifffile
    from titan_if.projects import save_project,open_project,stream_hash
    p=fixture(tmp_path);f=p["fields"][0];s=session(tmp_path)
    a=np.zeros((10,12),np.uint16);a[3:7,4:8]=100
    source=f["channels"][0]["source"];tifffile.imwrite(source["path"],a);source["sha256"]=stream_hash(source["path"])
    f["recipe"]["mode"]="nuclei";f["recipe"]["segmentation"].update(sigma=0,min_area=2,exclude_border=False)
    j=start(p,"segment",dict(field_id="f1"),s);done=finished(j,s)
    assert done["status"]=="completed",done
    p=accept(p,j["job_id"],s);assert not p["fields"][0]["mask"]["confirmed"]
    old=p["fields"][0]["mask"]["sha256"]
    action=dict(kind="add",roi=dict(id="new",role="signal",shape="rectangle",points=[[0,0],[2,2]]))
    j=start(p,"edit_mask",dict(field_id="f1",action=action),s)
    assert finished(j,s)["status"]=="completed"
    p=accept(p,j["job_id"],s)
    assert p["fields"][0]["mask"]["sha256"]!=old
    p["fields"][0]["mask"]["confirmed"]=True
    p=save_project(p,str(tmp_path/"p.titanif"),None,s)
    opened=open_project(p["project_path"],s)
    assert opened["fields"][0]["mask"]["confirmed"]
    assert len(list((Path(p["project_path"])/"masks").glob("*.tif")))>=2


def test_read_only_cannot_start_or_accept(tmp_path):
    p=fixture(tmp_path);p["read_only"]=True
    with pytest.raises(ValueError,match="只读"):start(p,"measure",dict(field_id="f1"),session(tmp_path))


def test_result_artifact_bounds_transport_and_preserves_exact_large_integers(tmp_path):
    import json
    from titan_if.jobs import stage_result
    result=dict(field_id="f1",input_signature="s",objects=[dict(object_id=i,raw_sum=9007199254740993) for i in range(750)],
                summary=[dict(raw_sum=9007199254740993)],warnings=[])
    preview=stage_result(result,tmp_path)
    assert len(preview["objects"])==500 and preview["total_objects"]==750
    assert preview["summary"][0]["raw_sum"]=="9007199254740993"
    full=json.loads(Path(preview["artifact"]["path"]).read_text())
    assert len(full["objects"])==750
    assert full["summary"][0]["raw_sum"]==9007199254740993


def test_second_job_cannot_start_during_worker_startup(tmp_path,monkeypatch):
    import json,os,subprocess,sys
    s=session(tmp_path);root=Path(s["library_root"])/"if-jobs";directory=root/("a"*32)
    directory.mkdir(parents=True)
    child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(20)"])
    try:
        (directory/"request.json").write_text(json.dumps({"owner":{"pid":s["pid"],"token":s["token"]}}))
        status_path=directory/"status.json"
        status_path.write_text(json.dumps({"status":"queued","message":"等待后台处理"},ensure_ascii=False),encoding="utf-8")
        (directory/"worker.json").write_text(json.dumps({"pid":child.pid}))
        read_text=Path.read_text
        def read_with_windows_default(path,encoding=None,errors=None):
            return read_text(path,encoding=encoding or "cp1252",errors=errors)
        monkeypatch.setattr(Path,"read_text",read_with_windows_default)
        with pytest.raises(ValueError,match="后台任务"):
            start(fixture(tmp_path),"measure",dict(field_id="f1"),s)
    finally:
        child.terminate();child.wait(timeout=5)
