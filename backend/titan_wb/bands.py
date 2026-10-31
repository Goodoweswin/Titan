"""Per-lane full-resolution profiles and reviewable band/background proposals."""
import json
import numpy as np
from scipy.signal import find_peaks,peak_widths
from .images import read_pixels
from .image_cache import CACHE
from .models import validate_project
from .quantify import _oriented,_slice

def _parts(project,layout_id,lane_id,window=None):
    layout=next(l for l in project['lane_layouts'] if l['id']==layout_id)
    column=next(c for c in layout['columns'] if c['lane_id']==lane_id)
    asset=next(a for a in project['images'] if a['id']==layout['image_id'])
    box=window or layout['window'];x0=max(box[0],column['rect'][0]);x1=min(box[2],column['rect'][2])
    y0=max(box[1],column['rect'][1]);y1=min(box[3],column['rect'][3])
    return layout,asset,[x0,y0,x1,y1]

def lane_profile(project,layout_id,lane_id,window=None):
    layout,asset,rect=_parts(project,layout_id,lane_id,window)
    pixels=read_pixels(asset);_slice(rect,pixels.shape)
    key=('lane-profile',asset['sha256'],asset.get('page_index',0),asset['polarity'],asset.get('ceiling'),tuple(rect))
    def calculate():
        signal=_oriented(pixels,asset['polarity'],asset.get('ceiling'));x0,y0,x1,y1=rect
        sub=signal[y0:y1,x0:x1];rows=sub.sum(axis=1);step=max(1,int(np.ceil(len(rows)/1200)))
        samples=[dict(y=y0+(i+min(i+step,len(rows))-1)/2,sum=float(rows[i:i+step].mean()),mean=float(sub[i:i+step].mean()),min=float(rows[i:i+step].min()),max=float(rows[i:i+step].max())) for i in range(0,len(rows),step)]
        return json.dumps(dict(samples=samples,total=float(rows.sum()),width=x1-x0),allow_nan=False)
    data=json.loads(CACHE.get_value(key,calculate))
    return dict(project_id=project['id'],input_revision=project['revision'],layout_id=layout_id,lane_id=lane_id,window=rect,**data)

def _overlaps(a,b):return max(a[0],b[0])<min(a[2],b[2]) and max(a[1],b[1])<min(a[3],b[3])

def propose_bands(project,band_set_id,settings):
    validate_project(project)
    group=next(g for g in project['band_sets'] if g['id']==band_set_id)
    layout=next(l for l in project['lane_layouts'] if l['id']==group['layout_id'])
    if layout['confirmed_revision'] is None:raise ValueError('请先确认泳道位置')
    asset=next(a for a in project['images'] if a['id']==layout['image_id'])
    pixels=read_pixels(asset);signal=_oriented(pixels,asset['polarity'],asset.get('ceiling'))
    results=[]
    for column in layout['columns']:
        _,_,rect=_parts(project,layout['id'],column['lane_id'],group['window']);x0,y0,x1,y1=rect
        candidates=[]
        if x1>x0 and y1>y0:
            curve=signal[y0:y1,x0:x1].mean(axis=1)
            flanks=np.r_[signal[max(0,y0-10):y0,x0:x1].ravel(),signal[y1:min(signal.shape[0],y1+10),x0:x1].ravel()]
            baseline=min(float(np.percentile(curve,10)),float(np.median(flanks))) if flanks.size else float(np.percentile(curve,10))
            smooth=np.convolve(np.pad(curve,(1,1),mode='edge'),np.ones(3)/3,mode='valid')-baseline
            noise=np.median(abs(np.diff(smooth)-np.median(np.diff(smooth))))*1.4826 if len(smooth)>1 else 0
            padded=np.r_[0,smooth,0]
            indices,properties=find_peaks(padded,prominence=max(noise*4,float(settings.get('min_prominence',0)),1e-9),width=1)
            if len(indices):
                _,_,left,right=peak_widths(padded,indices,rel_height=.95)
                for i,index in enumerate(indices):
                    top=max(y0,y0+int(np.floor(left[i]-1)));bottom=min(y1,y0+int(np.ceil(right[i]-1))+1)
                    if bottom<=top:continue
                    band=[x0,top,x1,bottom];height=max(2,int(np.ceil((bottom-top)/3)))
                    backgrounds=[]
                    for a,b in [(max(0,top-height-2),max(0,top-2)),(min(signal.shape[0],bottom+2),min(signal.shape[0],bottom+height+2))]:
                        bg=[x0,a,x1,b]
                        if b<=a or _overlaps(bg,band):continue
                        if any(r['image_id']==asset['id'] and _overlaps(bg,r['rect']) for r in project['rois']):continue
                        # Do not use another proposed peak as background.
                        if any(a<=y0+int(other)-1<b for other in indices if other!=index):continue
                        backgrounds.append(bg)
                    candidates.append(dict(rect=band,backgrounds=backgrounds))
        status='not_detected' if not candidates else 'proposed' if len(candidates)==1 else 'ambiguous'
        results.append(dict(lane_id=column['lane_id'],status=status,candidates=candidates,reasons=['未检出，保留此泳道位置'] if not candidates else ['存在多个峰，请选择目标峰'] if len(candidates)>1 else []))
    return results
