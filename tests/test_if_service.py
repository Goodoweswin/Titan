import time
from pathlib import Path
from titan_wb.engine import dispatch
from test_if_projects import session


def call(command,payload,s):
    return dispatch(dict(command=command,payload=payload,session=s))


def test_engine_creates_lists_saves_and_reopens_independent_if_project(tmp_path):
    s=session(tmp_path);p=call("if_new",{"name":"IF experiment"},s)
    assert p["module"]=="if" and p["saved_revision"]==0
    rows=call("library_list",{},s);assert rows[0]["module"]=="if"
    p["name"]="renamed";p["revision"]+=1
    saved=call("if_save",{"project":p},s)
    assert call("if_open",{"path":saved["project_path"]},s)["name"]=="renamed"


def test_synthetic_if_demo_runs_real_measurement_and_independent_figure(tmp_path):
    s=session(tmp_path);p=call("if_demo",{},s)
    assert p["synthetic"] and len(p["fields"])>=6
    assert call("if_preview",{"field":p["fields"][0]},s).startswith("data:image/png;base64,")
    fig=call("if_figure_preview",{"project":p},s)
    assert fig["png"].startswith("data:image/png;base64,")
    job=call("if_start_job",{"project":p,"operation":"measure","options":{"field_id":p["fields"][0]["id"]}},s)
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        state=call("if_job_status",job,s)
        if state["status"] in ["completed","failed"]:break
        time.sleep(.05)
    assert state["status"]=="completed",state
    updated=call("if_accept_job",{"project":p,"job_id":job["job_id"]},s)
    assert updated["fields"][0]["result"]["summary"]


def test_large_mask_overlay_is_bounded_before_color_expansion(tmp_path):
    import base64,io,tracemalloc
    import numpy as np
    import tifffile
    from PIL import Image
    from test_if_projects import fixture
    from titan_if.models import segmentation_signature
    from titan_if.projects import stream_hash
    f=fixture(tmp_path)["fields"][0];f.update(width=2048,height=2048)
    labels=np.zeros((2048,2048),np.uint32);labels[100:200,100:200]=7
    path=tmp_path/"large-mask.tif";tifffile.imwrite(path,labels)
    f["mask"]=dict(path=str(path),sha256=stream_hash(path),version=1,confirmed=True,
        segmentation_signature=segmentation_signature(f))
    tracemalloc.start()
    try:
        preview=call("if_mask_preview",{"field":f},session(tmp_path))
        _,peak=tracemalloc.get_traced_memory()
    finally:tracemalloc.stop()
    assert peak<128*1024**2
    im=Image.open(io.BytesIO(base64.b64decode(preview["png"].split(",")[1])))
    assert im.size==(1200,1200)
    assert preview["objects"][0]["id"]==7


def test_dense_mask_can_pick_labels_beyond_centroid_preview_limit(tmp_path):
    import numpy as np,tifffile
    from test_if_projects import fixture
    from titan_if.models import segmentation_signature
    from titan_if.projects import stream_hash
    f=fixture(tmp_path)["fields"][0];f.update(width=128,height=32)
    labels=np.arange(4096,dtype=np.uint32).reshape(32,128)
    path=tmp_path/"dense.tif";tifffile.imwrite(path,labels)
    f["mask"]=dict(path=str(path),sha256=stream_hash(path),version=1,confirmed=False,
        segmentation_signature=segmentation_signature(f))
    assert call("if_mask_pick",{"field":f,"x":127.2,"y":31.8},session(tmp_path))["id"]==4095
