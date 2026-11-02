import copy
import hashlib
import json
import os
import shutil
from pathlib import Path

import numpy as np
import pytest
import tifffile

from titan_if.models import new_project, validate_project, analysis_signature
from titan_if.projects import save_project, open_project, release_project


def session(tmp_path, token="if-tests"):
    return dict(pid=os.getpid(), token=token, library_root=str(tmp_path/"library"))


def fixture(tmp_path):
    source=tmp_path/"raw.tif"
    tifffile.imwrite(source,np.full((10,12),20,np.uint16))
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    p=new_project("免疫荧光实验")
    p["fields"]=[dict(id="f1",name="视野",sample_id="S1",bio_id="B1",group="control",batch_id="batch1",
        width=12,height=10,pixel_size_um=[.5,.5],quantitative=True,
        channels=[dict(id="c1",name="DAPI",color="#4090ff",display_min=0,display_max=100,
            source=dict(path=str(source),sha256=digest,series_index=0,axes="YX",indexers={}))],
        rois=[],recipe=dict(mode="region",nuclear_channel_id="c1",target_channel_ids=["c1"],
            thresholds={},threshold_source="",thresholds_frozen=False,
            segmentation=dict(sigma=1,threshold_method="otsu",threshold=None,min_area=2,max_area=1000,min_distance=2,exclude_border=True,rolling_ball_radius=0)),
        mask=None,result=None)]
    return p


def test_display_and_identity_edits_do_not_change_measurement_signature(tmp_path):
    p=fixture(tmp_path);f=p["fields"][0];before=analysis_signature(f)
    f["channels"][0].update(display_min=12,display_max=80,color="#ff00ff")
    f["name"]="改名";f["result"]={"anything":1}
    assert analysis_signature(f)==before
    f["recipe"]["thresholds"]={"c1":35}
    assert analysis_signature(f)!=before


def test_portable_project_keeps_original_and_manual_mask_after_move(tmp_path):
    p=fixture(tmp_path);mask=tmp_path/"manual.tif"
    labels=np.zeros((10,12),np.uint32);labels[2:4,3:5]=7;tifffile.imwrite(mask,labels)
    p["fields"][0]["mask"]=dict(path=str(mask),sha256=hashlib.sha256(mask.read_bytes()).hexdigest(),
        version=1,segmentation_signature="base",confirmed=True)
    s=session(tmp_path);saved=save_project(p,str(tmp_path/"first.titanif"),None,s)
    assert Path(saved["fields"][0]["channels"][0]["source"]["path"]).is_relative_to(tmp_path/"first.titanif"/"originals")
    release_project(saved["project_path"],s)
    moved=tmp_path/"moved.titanif";shutil.move(saved["project_path"],moved)
    Path(p["fields"][0]["channels"][0]["source"]["path"]).unlink();mask.unlink()
    opened=open_project(str(moved),s)
    np.testing.assert_array_equal(tifffile.imread(opened["fields"][0]["mask"]["path"]),labels)
    assert opened["fields"][0]["mask"]["confirmed"]
    manifest=json.loads((moved/"project.json").read_text())
    assert not Path(manifest["fields"][0]["mask"]["path"]).is_absolute()


def test_project_rejects_stale_save_foreign_lock_and_source_tampering(tmp_path):
    p=fixture(tmp_path);s=session(tmp_path);path=str(tmp_path/"p.titanif")
    saved=save_project(p,path,None,s)
    with pytest.raises(ValueError,match="写入|锁"):open_project(path,session(tmp_path,"other"))
    newer=copy.deepcopy(saved);newer["revision"]+=1
    save_project(newer,path,saved["saved_revision"],s)
    with pytest.raises(ValueError,match="版本"):save_project(saved,path,saved["saved_revision"],s)
    raw=Path(saved["fields"][0]["channels"][0]["source"]["path"]);raw.write_bytes(b"changed")
    with pytest.raises(ValueError,match="原图|校验|hash"):open_project(path,s,True)


def test_open_rejects_paths_escaping_project(tmp_path):
    p=fixture(tmp_path);s=session(tmp_path);path=tmp_path/"p.titanif"
    save_project(p,str(path),None,s)
    manifest=json.loads((path/"project.json").read_text())
    manifest["fields"][0]["channels"][0]["source"]["path"]="../raw.tif"
    (path/"project.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match="越|路径|originals"):open_project(str(path),s,True)


def test_project_validation_rejects_duplicate_channels_and_invalid_geometry(tmp_path):
    p=fixture(tmp_path);f=p["fields"][0]
    f["channels"].append(copy.deepcopy(f["channels"][0]))
    with pytest.raises(ValueError):validate_project(p)
    f["channels"].pop();f["rois"]=[dict(id="x",name="bad",role="signal",shape="rectangle",points=[[1,1],[40,40]])]
    with pytest.raises(ValueError):validate_project(p)


def test_if_and_legacy_wb_projects_share_module_aware_library(tmp_path):
    from titan_wb.library import library_create,library_register,library_list
    s=session(tmp_path);wb=library_create("WB",s)
    p=save_project(new_project("IF"),str(tmp_path/"if.titanif"),None,s)
    library_register(p["project_path"],s)
    entries=library_list(s)
    assert {e["module"] for e in entries}=={"wb","if"}
    assert next(e for e in entries if e["module"]=="if")["figures"]==[]
    assert next(e for e in entries if e["module"]=="wb")["project_id"]==wb["project"]["id"]


def test_project_preview_budget_preserves_authoritative_result_references(tmp_path):
    from titan_if.models import bound_result_previews
    p=new_project("large batch")
    for i in range(20):
        p["fields"].append(dict(id=str(i),result=dict(objects=[{"object_id":j} for j in range(500)],
            total_objects=700,artifact=dict(path=f"result-{i}.json",sha256="x"))))
    result=bound_result_previews(p)
    assert sum(len(f["result"]["objects"]) for f in result["fields"])<=5000
    assert all(f["result"]["total_objects"]==700 for f in result["fields"])
    assert all(f["result"]["artifact"]["path"]==f"result-{i}.json" for i,f in enumerate(result["fields"]))
