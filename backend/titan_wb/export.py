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


def plot_results(result,root):
    os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'titan-wb-mpl'))
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    bio=result['biological'];analytes=sorted({b['analyte'] for b in bio})
    fig,axs=plt.subplots(1,max(1,len(analytes)),figsize=(5*max(1,len(analytes)),4),squeeze=False)
    for ax,analyte in zip(axs[0],analytes):
        rows=[b for b in bio if b['analyte']==analyte]
        groups=list(dict.fromkeys(b['group'] for b in rows))
        paired={}
        for i,g in enumerate(groups):
            vals=[b for b in rows if b['group']==g]
            values=[b['fold'] if b['fold'] is not None else b['value'] for b in vals]
            jitter=np.linspace(-.09,.09,len(values)) if len(values)>1 else [0]
            ax.scatter(i+np.array(jitter),values,s=45,color=['#247a68','#bf874a'][i%2],zorder=3)
            if values:ax.hlines(np.mean(values),i-.18,i+.18,color='#233b35',linewidth=2)
            for b,y in zip(vals,values):
                if b.get('pair_id'):paired.setdefault(b['pair_id'],[]).append((i,y))
        for points in paired.values():
            if len(points)==2:ax.plot(*zip(*points),color='#bac9c0',linewidth=1,zorder=1)
        ax.set_xticks(range(len(groups)),groups);ax.set_ylabel('Relative signal (fold where available)')
        ax.set_title(analyte);ax.spines[['top','right']].set_visible(False)
    if not analytes:axs[0,0].text(.5,.5,'No eligible biological values',ha='center')
    fig.tight_layout();fig.savefig(root/'plot.png',dpi=220);fig.savefig(root/'plot.svg');plt.close(fig)


def export_analysis(project,result,destination):
    if result['project_id']!=project['id'] or result['input_revision']!=project['revision']:raise ValueError('结果已过期，请重新计算后导出')
    dest=Path(destination).expanduser().resolve()
    if dest.exists():raise ValueError('导出目录已存在，请选择新目录')
    dest.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.titan-export-',dir=dest.parent))
    try:
        for name in ['measurements','normalized','biological','statistics']:csv_file(stage/(name+'.csv'),result[name])
        (stage/'analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
        config=copy.deepcopy(project);(stage/'originals').mkdir();(stage/'overlays').mkdir()
        for a in config['images']:
            pixels=read_pixels(a);source=Path(a['path']);target=stage/'originals'/(a['id']+source.suffix)
            shutil.copy2(source,target);a['path']=str(target.relative_to(stage))
            lo,hi=np.percentile(pixels,[.5,99.5]);hi=max(hi,lo+1)
            canvas=Image.fromarray(np.uint8(np.clip((pixels.astype(float)-lo)/(hi-lo),0,1)*255)).convert('RGB')
            draw=ImageDraw.Draw(canvas)
            for r in project['rois']:
                if r['image_id']!=a['id']:continue
                x0,y0,x1,y1=r['rect'];color='lime' if r['role']=='target' else 'cyan'
                draw.rectangle([x0,y0,x1-1,y1-1],outline=color,width=1)
                for x0,y0,x1,y1 in r['backgrounds']:draw.rectangle([x0,y0,x1-1,y1-1],outline='orange',width=1)
            canvas.save(stage/'overlays'/(a['id']+'.png'))
        for k in ['project_path','saved_revision','read_only']:config.pop(k,None)
        (stage/'project.json').write_text(json.dumps(config,ensure_ascii=False,indent=2,allow_nan=False))
        plot_results(result,stage)
        manifest=dict(software='Titan WB '+__version__,project_id=project['id'],revision=project['revision'],
          synthetic=bool(project.get('demo')),outputs={str(p.relative_to(stage)):file_hash(p) for p in stage.rglob('*') if p.is_file()},
          limitations=['Digitally unclipped does not prove linear response','Human review and linearity fields are declarations','Real WB validation pending'])
        (stage/'audit.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
        os.replace(stage,dest)
        return manifest
    finally:
        if stage.exists():shutil.rmtree(stage)
