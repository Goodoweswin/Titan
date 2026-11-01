import base64
import io
import copy
import csv
import json
import os
import shutil
import tempfile
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from . import __version__
from .images import file_hash,read_pixels


def csv_file(path,rows):
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader()
        for r in rows:writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})


def plot_groups(biological):
    groups={}
    for b in biological:groups.setdefault((b['analyte'],b['analysis_block']),[]).append(b)
    return groups


def plot_settings(settings=None):
    defaults = dict(panel_width=5, height=4, font_size=11, dpi=220)
    bounds = dict(panel_width=(3,8), height=(3,8), font_size=(8,24), dpi=(72,300))
    for key, value in (settings or {}).items():
        if key not in bounds or isinstance(value, bool) or not isinstance(value, (int,float)):
            raise ValueError('图表参数无效')
        lo, hi = bounds[key]
        if not np.isfinite(value) or not lo <= value <= hi:
            raise ValueError(f'图表参数 {key} 必须在 {lo}–{hi} 范围内')
        defaults[key] = value
    return defaults


def check_result(project,result):
    if result['project_id']!=project['id'] or result['input_revision']!=project['revision']:
        raise ValueError('结果已过期，请重新计算后导出')


def export_preview(project,result,settings=None,figure_settings=None):
    check_result(project,result)
    settings=plot_settings(settings if settings is not None else project.get('plot_settings'))
    with tempfile.TemporaryDirectory(prefix='titan-preview-') as tmp:
        root=Path(tmp)
        data,figure=plot_results(result,root,settings,figure_settings,project)
        raw=(root/'plot.png').read_bytes()
        with Image.open(io.BytesIO(raw)) as image:
            width,height=image.size
        return dict(png='data:image/png;base64,'+base64.b64encode(raw).decode(),
                    width=width,height=height,settings=settings,figure_settings=figure,figure_data=data)


def plot_results(result,root,settings=None,figure_settings=None,project=None):
    os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'titan-wb-mpl'))
    from .figure_render import render_figure
    return render_figure(result,root,plot_settings(settings),figure_settings,project)


def export_analysis(project,result,destination,settings=None,figure_settings=None):
    check_result(project,result)
    settings=plot_settings(settings if settings is not None else project.get('plot_settings'))
    dest=Path(destination).expanduser().resolve()
    if dest.exists():raise ValueError('导出目录已存在，请选择新目录')
    dest.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.titan-export-',dir=dest.parent))
    try:
        for name in ['measurements','normalized','biological','statistics']:csv_file(stage/(name+'.csv'),result[name])
        if result.get('lane_results'):csv_file(stage/'lanes.csv',result['lane_results'])
        (stage/'analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        config=copy.deepcopy(project);(stage/'originals').mkdir();(stage/'overlays').mkdir()
        for a in config['images']:
            pixels=read_pixels(a);source=Path(a['path']);target=stage/'originals'/(a['id']+source.suffix)
            shutil.copy2(source,target);a['path']=target.relative_to(stage).as_posix()
            lo,hi=np.percentile(pixels,[.5,99.5]);hi=max(hi,lo+1)
            canvas=Image.fromarray(np.uint8(np.clip((pixels.astype(float)-lo)/(hi-lo),0,1)*255)).convert('RGB')
            draw=ImageDraw.Draw(canvas)
            for r in project['rois']:
                if r['image_id']!=a['id']:continue
                x0,y0,x1,y1=r['rect'];color='lime' if r['role']=='target' else 'cyan'
                draw.rectangle([x0,y0,x1-1,y1-1],outline=color,width=1)
                for x0,y0,x1,y1 in r['backgrounds']:draw.rectangle([x0,y0,x1-1,y1-1],outline='orange',width=1)
            canvas.save(stage/'overlays'/(a['id']+'.png'))
        figure_data,figure=plot_results(result,stage,settings,figure_settings,project)
        config.update(figure_settings=figure,plot_settings=settings)
        for k in ['project_path','saved_revision','read_only','upgrade_from']:config.pop(k,None)
        (stage/'project.json').write_text(json.dumps(config,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        from .workbook import write_workbook,group_rows
        write_workbook(config,result,stage,figure_data)
        csv_file(stage/'group_summaries.csv',group_rows(figure_data))
        for key in ['multigroup_omnibus','multigroup_comparisons']:csv_file(stage/(key+'.csv'),result.get(key,[]))
        manifest=dict(software='Titan WB '+__version__,project_id=project['id'],revision=project['revision'],
          synthetic=bool(project.get('demo') or project.get('synthetic')),plot_settings=settings,figure_settings=figure,figure_data=figure_data,outputs={str(p.relative_to(stage)):file_hash(p) for p in stage.rglob('*') if p.is_file()},
          limitations=['Digitally unclipped does not prove linear response','Human review and linearity fields are declarations','Real WB validation pending'])
        (stage/'audit.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        os.replace(stage,dest)
        return manifest
    finally:
        if stage.exists():shutil.rmtree(stage)
