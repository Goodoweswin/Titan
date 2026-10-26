"""Explicitly synthetic example, never experimental evidence."""
import tempfile
import uuid
from pathlib import Path
import numpy as np
from PIL import Image
from .models import new_project
from .images import import_image


def make_demo():
    root=Path(tempfile.mkdtemp(prefix='titan-wb-synthetic-'))
    yy,xx=np.mgrid[:160,:520]
    rng=np.random.default_rng(42)
    pixels=1000+2*xx+yy+rng.normal(0,3,xx.shape)
    p=new_project('合成示例 · 蛋白表达分析');p['demo']=True
    for sample,ratio in enumerate([.8,1,1.2,1.6,2,2.4]):
        sid=f'S{sample+1}';group='control' if sample<3 else 'treated'
        p['samples'].append(dict(id=sid,bio_id=f'B{sample+1}',group=group,pair_id='',kind='biological',pool_id=''))
        for tech in range(2):
            lane=sample*2+tech;x0=20+40*lane;lid=f'L{lane+1}'
            p['lanes'].append(dict(id=lid,membrane_id='M1',sample_id=sid,technical_id=str(tech+1)))
            pixels[40:55,x0:x0+16]+=ratio*100+(-2 if tech==0 else 2)
            pixels[100:115,x0:x0+16]+=100
            for role,y,analyte in [('target',40,'TARGET'),('reference',100,'Loading control')]:
                p['rois'].append(dict(id=f'{role}_{lane}',image_id='',lane_id=lid,analyte=analyte,role=role,
                  rect=[x0,y,x0+16,y+15],backgrounds=[[x0,y-10,x0+16,y-5],[x0,y+20,x0+16,y+25]],
                  reference_id=f'reference_{lane}' if role=='target' else None,reviewed_revision=None))
    pixels[44,463]=4095
    path=root/'SYNTHETIC_ONLY.tif';Image.fromarray(np.round(pixels).astype(np.uint16)).save(path)
    p=import_image(p,str(path));p['images'][0]['ceiling']=4095
    for r in p['rois']:r.update(image_id=p['images'][0]['id'],reviewed_revision=p['revision'])
    return p
