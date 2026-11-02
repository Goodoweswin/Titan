"""IF project contracts and numerical dependency signatures."""
import hashlib
import json
import math
import re
import uuid

MAX_PIXELS = 4096**2
MAX_CHANNELS = 4


def new_project(name):
    if not isinstance(name,str) or not name.strip():
        raise ValueError("请输入实验名称")
    return dict(module="if",schema_version=1,id=uuid.uuid4().hex,name=name.strip(),revision=0,
                fields=[],figure=dict(field_ids=[],channel_ids=[],include_merge=True,crop=None,inset=None,
                width_mm=180,dpi=300,font_pt=9,scale_bar_um=None,locked_ranges={}))


def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def _sources(field):
    return [dict(id=c["id"],name=c["name"],source={k:v for k,v in c["source"].items() if k!="path"})
            for c in field["channels"]]


def segmentation_signature(field):
    return _digest(dict(sources=_sources(field),width=field["width"],height=field["height"],
        rois=field.get("rois",[]),nuclear_channel_id=field.get("recipe",{}).get("nuclear_channel_id"),
        segmentation=field.get("recipe",{}).get("segmentation",{})))


def analysis_signature(field):
    mask=field.get("mask")
    return _digest(dict(sources=_sources(field),width=field["width"],height=field["height"],
        quantitative=field.get("quantitative",True),pixel_size_um=field.get("pixel_size_um"),
        rois=field.get("rois",[]),recipe=field.get("recipe",{}),
        mask={k:mask.get(k) for k in ["sha256","version","segmentation_signature","confirmed"]} if mask else None))


def bound_result_previews(project):
    """Bound the aggregate IPC table, retaining every full-result artifact."""
    results=[f["result"] for f in project["fields"] if f.get("result") and f["result"].get("artifact")]
    limit=min(500,5000//len(results)) if results else 500
    for result in results:
        rows=result.get("objects",[])
        result.setdefault("total_objects",len(rows))
        if len(rows)>limit:result["objects"]=rows[:limit]
        result["objects_truncated"]=result.get("total_objects",0)>len(result.get("objects",[]))
    return project


def _finite(v):
    return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)


def validate_project(p):
    if not isinstance(p,dict) or p.get("module")!="if" or p.get("schema_version")!=1:
        raise ValueError("不支持此免疫荧光项目版本")
    if not isinstance(p.get("id"),str) or not p["id"] or not isinstance(p.get("name"),str) or not p["name"].strip():
        raise ValueError("项目身份或名称缺失")
    if type(p.get("revision")) is not int or p["revision"]<0:
        raise ValueError("项目版本无效")
    fields=p.get("fields")
    if not isinstance(fields,list) or len({f.get("id") for f in fields})!=len(fields):
        raise ValueError("视野列表包含重复身份")
    for f in fields:
        if not isinstance(f.get("id"),str) or not f["id"]:raise ValueError("视野身份缺失")
        if any(type(f.get(k)) is not int or f[k]<=0 for k in ["width","height"]) or f["width"]*f["height"]>MAX_PIXELS:
            raise ValueError("视野超过二维像素上限，请先使用 Fiji 拆分")
        calibration=f.get("pixel_size_um")
        if calibration is not None and (not isinstance(calibration,list) or len(calibration)!=2 or
                any(not _finite(v) or v<=0 for v in calibration)):
            raise ValueError("像素空间标定必须为两个正数")
        channels=f.get("channels",[])
        ids=[c.get("id") for c in channels]
        if not 1<=len(channels)<=MAX_CHANNELS or len(set(ids))!=len(ids) or not all(ids):
            raise ValueError("通道数或通道身份无效")
        for c in channels:
            if not isinstance(c.get("name"),str) or not c["name"].strip():raise ValueError("通道名称缺失")
            if not re.fullmatch(r"#[0-9a-fA-F]{6}",c.get("color","")):raise ValueError("通道颜色无效")
            if not all(_finite(c.get(k)) for k in ["display_min","display_max"]) or c["display_max"]<=c["display_min"]:
                raise ValueError("显示上限必须大于下限")
            s=c.get("source",{})
            if not isinstance(s.get("path"),str) or not re.fullmatch(r"[0-9a-f]{64}",s.get("sha256","")):
                raise ValueError("原图来源或校验值缺失")
            if type(s.get("series_index",0)) is not int or s.get("series_index",0)<0:raise ValueError("图像序列无效")
        rois=f.get("rois",[])
        if not isinstance(rois,list) or len({r.get("id") for r in rois})!=len(rois):raise ValueError("区域身份重复")
        for r in rois:
            points=r.get("points",[]);kind=r.get("shape")
            if r.get("role") not in ["signal","background"] or kind not in ["rectangle","ellipse","polygon"]:
                raise ValueError("区域类型无效")
            if len(points)<(3 if kind=="polygon" else 2) or (kind!="polygon" and len(points)!=2):
                raise ValueError("区域顶点数无效")
            for point in points:
                if len(point)!=2 or not all(_finite(v) for v in point) or not 0<=point[0]<=f["width"] or not 0<=point[1]<=f["height"]:
                    raise ValueError("区域超出原始图像坐标范围")
            if kind!="polygon" and (points[0][0]==points[1][0] or points[0][1]==points[1][1]):
                raise ValueError("区域面积为空")
        recipe=f.get("recipe",{})
        if recipe.get("mode") not in ["region","nuclei"]:raise ValueError("分析方式无效")
        if recipe.get("nuclear_channel_id") not in ids or any(c not in ids for c in recipe.get("target_channel_ids",[])):
            raise ValueError("分析引用的通道不存在")
        thresholds=recipe.get("thresholds",{})
        if not isinstance(thresholds,dict) or any(c not in ids or not _finite(v) for c,v in thresholds.items()):
            raise ValueError("阳性阈值无效")
        if recipe.get("thresholds_frozen") and (not thresholds or not recipe.get("threshold_source","").strip()):
            raise ValueError("冻结阳性阈值前请填写数值及阴性对照来源")
        if f.get("mask") and (not isinstance(f["mask"].get("path"),str) or not re.fullmatch(r"[0-9a-f]{64}",f["mask"].get("sha256",""))):
            raise ValueError("分割结果来源或校验值缺失")
    return p
