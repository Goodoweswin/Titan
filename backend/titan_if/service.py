"""IF commands exposed through Titan's existing bounded JSON transport."""
import base64
import io
import math
import uuid
from pathlib import Path

import numpy as np
import tifffile
from PIL import Image

from titan_wb.library import library_root,library_register,create_managed_analysis,register_published_export,open_registered_analysis,entry_for_path
from . import projects,jobs
from .models import new_project


def _create(name, session, *, collection_id=None, new_collection_name=None):
    return create_managed_analysis(
        new_project(name), '.titanif', projects.save_project, session,
        collection_id=collection_id, new_collection_name=new_collection_name,
    )['project']


def _demo(session):
    from .images import import_field
    p=_create("免疫荧光合成示例",session);p["synthetic"]=True
    folder=library_root(session)/"if-demo"/uuid.uuid4().hex;folder.mkdir(parents=True)
    yy,xx=np.mgrid[:256,:256]
    for index in range(6):
        raw=np.full((2,256,256),20,np.uint16)
        for y in [65,128,191]:
            for x in [65,128,191]:
                blob=np.exp(-((xx-x)**2+(yy-y)**2)/(2*8**2))
                raw[0]+=np.uint16(blob*2500)
                raw[1]+=np.uint16(blob*(500 if index<3 else 1400))
        path=folder/(f"synthetic-{index+1}.ome.tif")
        tifffile.imwrite(path,raw,photometric="minisblack",metadata=dict(axes="CYX",
            Channel=dict(Name=["DAPI","Marker"]),PhysicalSizeX=.5,PhysicalSizeY=.5))
        f=import_field([dict(path=str(path),series_index=0,channel_indices=[0,1],indexers={})],
                       dict(name=f"合成视野 {index+1}",sample_id=f"S{index+1}",bio_id=f"B{index+1}",
                       group="control" if index<3 else "treated",batch_id="synthetic"))
        f["channels"][0]["display_max"]=2600;f["channels"][1]["display_max"]=1500
        f["rois"]=[dict(id=uuid.uuid4().hex,name="分析区域",role="signal",shape="rectangle",points=[[30,30],[226,226]]),
                   dict(id=uuid.uuid4().hex,name="背景区域",role="background",shape="rectangle",points=[[0,0],[20,20]])]
        target=f["channels"][1]["id"]
        f["recipe"].update(target_channel_ids=[target],thresholds={target:100},threshold_source="合成背景与阴性参考；非真实实验",thresholds_frozen=True)
        p["fields"].append(f)
    p["revision"]+=1
    p=projects.save_project(p,p["project_path"],p["saved_revision"],session)
    library_register(p["project_path"],session)
    return p


def _mask_preview(field):
    from scipy import ndimage as ndi
    labels=jobs._load_mask(field);ids=np.unique(labels);ids=ids[ids>0]
    # A deterministic integer palette keeps zero transparent.
    scale=min(1,1200/max(labels.shape))
    h=max(1,round(labels.shape[0]*scale));w=max(1,round(labels.shape[1]*scale))
    values=labels[np.ix_(np.linspace(0,labels.shape[0]-1,h).astype(int),
                         np.linspace(0,labels.shape[1]-1,w).astype(int))]
    rgba=np.stack([((values*97)%220+35).astype(np.uint8),
                   ((values*57)%220+35).astype(np.uint8),
                   ((values*137)%220+35).astype(np.uint8),
                   np.where(values>0,110,0).astype(np.uint8)],axis=-1)
    image=Image.fromarray(rgba)
    buffer=io.BytesIO();image.save(buffer,format="PNG")
    centers=ndi.center_of_mass(np.ones_like(labels,dtype=np.uint8),labels,ids[:3000])
    return dict(png="data:image/png;base64,"+base64.b64encode(buffer.getvalue()).decode(),
                width=field["width"],height=field["height"],
                objects=[dict(id=int(i),x=float(x),y=float(y)) for i,(y,x) in zip(ids[:3000],centers)],
                label_count=len(ids))


def dispatch(command,payload,session):
    if command=="if_new":return _create(payload["name"],session,collection_id=payload.get("collection_id"),new_collection_name=payload.get("new_collection_name"))
    if command=="if_demo":return _demo(session)
    if command=="if_open":
        load = (lambda path, session: projects.open_project(path, session, True)) if payload.get("read_only") else projects.recover_project
        return open_registered_analysis(payload["path"], load, session, payload.get("entry_id"))
    if command=="if_save":
        p=payload["project"];path=payload.get("path",p.get("project_path"))
        expected=payload.get("expected_revision",p.get("saved_revision")) if path==p.get("project_path") else None
        source = entry_for_path(p.get("project_path"), session) if path != p.get("project_path") else None
        p = projects.save_project(p, path, expected, session)
        library_register(p["project_path"], session, source_entry_id=source and source["entry_id"], touch_opened=source is not None)
        return p
    if command=="if_release":projects.release_project(payload["path"],session);return True
    if command=="if_inspect":
        from .images import inspect_image
        return inspect_image(payload["path"])
    if command == "if_volume_inspect":
        from .volume import inspect_volume
        return inspect_volume(payload["path"])
    if command == "if_volume_start":
        return jobs.start(None, "volume", payload, session)
    if command == "if_volume_save_png":
        from .volume import save_png
        return save_png(payload["destination"], payload["png"])
    if command=="if_preview":
        from .images import preview_field
        return preview_field(payload["field"],payload.get("channel_id"))
    if command=="if_mask_preview":return _mask_preview(payload["field"])
    if command=="if_mask_pick":
        labels=jobs._load_mask(payload["field"])
        x,y=payload["x"],payload["y"]
        if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in [x,y]):
            raise ValueError("请选择原始图像上的有效坐标")
        return dict(id=int(labels[int(y),int(x)]) if 0<=x<labels.shape[1] and 0<=y<labels.shape[0] else 0)
    if command=="if_start_job":
        if payload["operation"] == "volume":raise ValueError("请使用独立 3D 查看入口")
        return jobs.start(payload["project"],payload["operation"],payload.get("options",{}),session)
    if command=="if_job_status":return jobs.status(payload["job_id"],session)
    if command=="if_cancel_job":return jobs.cancel(payload["job_id"],session)
    if command=="if_accept_job":return jobs.accept(payload["project"],payload["job_id"],session)
    if command in ["if_figure_preview","if_export_figure","if_export_results"]:
        from .figures import preview_figure,export_figure,export_results
        p=payload["project"]
        if command=="if_figure_preview":return preview_figure(p)
        is_figure = command == "if_export_figure"
        destination = payload["destination"]
        result = (export_figure if is_figure else export_results)(p, destination)
        kind, label = ("if_figure_export", "IF 组图") if is_figure else ("result_export", "IF 定量结果")
        return register_published_export(p, result, destination, kind, p["name"]+" · "+label, p["revision"], session)
    raise ValueError("不支持的免疫荧光命令")
