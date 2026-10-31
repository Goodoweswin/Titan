"""Lane geometry proposals. Identity is assigned only after human confirmation."""
import uuid
import numpy as np
from .quantify import _oriented,_slice
from .images import read_pixels
from .models import validate_project

def propose_lanes(pixels,window,*,excluded_regions,expected_count,polarity,ceiling):
    if expected_count is not None and (type(expected_count) is not int or not 1<=expected_count<=100):raise ValueError('泳道数应为 1–100 的整数')
    signal=_oriented(pixels,polarity,ceiling);_slice(window,signal.shape)
    x0,y0,x1,y1=window;sub=signal[y0:y1,x0:x1].copy();excluded=np.zeros(sub.shape,dtype=bool)
    for box in excluded_regions:
        _slice(box,signal.shape);a,b,c,d=box
        excluded[max(0,b-y0):min(y1-y0,d-y0),max(0,a-x0):min(x1-x0,c-x0)]=True
    valid=~excluded
    baseline=np.percentile(sub,20,axis=0)
    height=y1-y0
    flanks=np.concatenate([signal[max(0,y0-height):y0,x0:x1],signal[y1:min(signal.shape[0],y1+height),x0:x1]],axis=0)
    if flanks.size:baseline=np.minimum(baseline,np.median(flanks,axis=0))
    sub=np.where(valid,sub-baseline,0)
    profile=sub.mean(axis=0)
    profile=np.maximum(profile-np.percentile(profile,10),0)
    smooth=max(3,((x1-x0)//100)|1)
    profile=np.convolve(np.pad(profile,(smooth//2,smooth//2),mode='edge'),np.ones(smooth)/smooth,mode='valid')
    # Local maxima are grouped above a robust noise floor, independent of the brightest lane.
    noise=np.median(np.abs(np.diff(profile)-np.median(np.diff(profile))))*1.4826 if len(profile)>1 else 0
    positive=profile[profile>0]
    floor=max(noise*4,float(np.percentile(positive,25))*.03 if positive.size else 0,1e-9)
    from scipy.signal import find_peaks
    indices,properties=find_peaks(profile,prominence=floor,width=3,distance=max(3,(x1-x0)//40))
    peaks=[]
    for i,center in enumerate(indices):
        if properties['prominences'][i]<profile[center]*.25:continue
        peaks.append((float((properties['left_ips'][i]+properties['right_ips'][i])/2),float(properties['widths'][i])))
    centers=[p[0] for p in peaks]
    inferred=set();requires_review=False
    # Broad, well-separated reference bands establish pitch. Bright edges within
    # one band must not become extra sample lanes; weak slots stay uncertain.
    if len(peaks)>=3:
        typical=float(np.median(sorted(p[1] for p in peaks)[len(peaks)//2:]))
        anchors=[p[0] for p in peaks if p[1]>=typical*.65]
        if len(anchors)>=3:
            differences=np.diff(anchors);pitch=float(np.median(np.sort(differences)[:max(1,len(differences)//2+1)]))
            regular=pitch>typical*.8 and all(abs(d/pitch-round(d/pitch))<.25 for d in differences)
            if regular:
                start=anchors[0]
                while start-pitch>pitch*.35:start-=pitch
                grid=list(np.arange(start,x1-x0-pitch*.3,pitch))
                if expected_count is None:
                    grid=[c for c in grid if profile[max(0,int(c-pitch*.35)):min(len(profile),int(c+pitch*.35))].max(initial=0)>floor*2]
                if grid and (expected_count is None or len(grid)==expected_count):
                    centers=grid;inferred={i for i,c in enumerate(grid) if min(abs(c-a) for a in anchors)>pitch*.3}
                    peaks=[(c,typical) for c in anchors]
    if expected_count and len(centers)!=expected_count:
        requires_review=True
        if len(centers)>=2 and len(centers)<expected_count:
            diffs=np.diff(centers);spacing=float(np.median(np.sort(diffs)[:max(1,len(diffs)//2+1)]))
            grid=[centers[0]+i*spacing for i in range(expected_count)]
            if grid[-1]<x1-x0:
                inferred={i for i,c in enumerate(grid) if min(abs(c-p) for p in centers)>spacing*.28};centers=grid
        elif not centers:
            centers=[(i+.5)*(x1-x0)/expected_count for i in range(expected_count)];inferred=set(range(expected_count))
    columns=[]
    spacing=float(np.median(np.diff(centers))) if len(centers)>1 else max(8,(x1-x0)*.8)
    for i,center in enumerate(centers):
        width=min(peaks,key=lambda p:abs(p[0]-center))[1] if peaks else spacing*.6
        half=min(spacing*.45,max(2,width*.6));left=max(0,int(round(center-half)));right=min(x1-x0,int(round(center+half)))
        if i:left=max(left,int(round((centers[i-1]+center)/2)))
        if i+1<len(centers):right=min(right,int(round((centers[i+1]+center)/2)))
        low=i in inferred or (expected_count is not None and len(centers)!=expected_count)
        columns.append(dict(proposal_id=uuid.uuid4().hex,rect=[x0+left,y0,x0+right,y1],confidence='low' if low else 'high',reasons=['弱信号或缺失，请确认此泳道位置'] if low else []))
    return dict(columns=columns,expected_count=expected_count,requires_review=requires_review or not columns or any(c['confidence']=='low' for c in columns))

def detect_lanes(project,image_id,window,excluded_regions=None,expected_count=None):
    validate_project(project);asset=next(a for a in project['images'] if a['id']==image_id)
    return dict(project_id=project['id'],input_revision=project['revision'],image_id=image_id,window=window,
        **propose_lanes(read_pixels(asset),window,excluded_regions=excluded_regions or [],expected_count=expected_count,polarity=asset['polarity'],ceiling=asset.get('ceiling')))
