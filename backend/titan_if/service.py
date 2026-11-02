"""IF commands exposed through Titan's existing bounded JSON transport."""
import base64
import io
import math
import uuid
from pathlib import Path

import numpy as np
import tifffile
from PIL import Image

from titan_wb.library import library_root,library_register,library_list
from . import projects,jobs
from .models import new_project


def _create(name,session):
    library_list(session)  # Validate the existing catalog before creating files.
    p=new_project(name);path=library_root(session)/"Projects"/(p["id"]+".titanif")
    p=projects.save_project(p,str(path),None,session);library_register(p["project_path"],session)
    return p


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
    if command=="if_new":return _create(payload["name"],session)
    if command=="if_demo":return _demo(session)
    if command=="if_open":
        path=payload["path"]
        p=projects.open_project(path,session,True) if payload.get("read_only") else projects.recover_project(path,session)
        library_register(path,session);return p
    if command=="if_save":
        p=payload["project"];path=payload.get("path",p.get("project_path"))
        expected=payload.get("expected_revision",p.get("saved_revision")) if path==p.get("project_path") else None
        p=projects.save_project(p,path,expected,session);library_register(p["project_path"],session);return p
    if command=="if_release":projects.release_project(payload["path"],session);return True
    if command=="if_inspect":
        from .images import inspect_image
        return inspect_image(payload["path"])
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
    if command=="if_start_job":return jobs.start(payload["project"],payload["operation"],payload.get("options",{}),session)
    if command=="if_job_status":return jobs.status(payload["job_id"],session)
    if command=="if_cancel_job":return jobs.cancel(payload["job_id"],session)
    if command=="if_accept_job":return jobs.accept(payload["project"],payload["job_id"],session)
    if command in ["if_figure_preview","if_export_figure","if_export_results"]:
        from .figures import preview_figure,export_figure,export_results
        p=payload["project"]
        if command=="if_figure_preview":return preview_figure(p)
        return (export_figure if command=="if_export_figure" else export_results)(p,payload["destination"])
    raise ValueError("不支持的免疫荧光命令")
