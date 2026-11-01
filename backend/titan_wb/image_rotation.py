"""Corrected image coordinates; quantitative sums always use source samples."""
import copy
import uuid
import numpy as np
from .quantify import _slice,measure


def checked_degrees(value):
    if type(value) not in (int,float) or not np.isfinite(value) or abs(value)>360:
        raise ValueError('旋转角度必须为 -360 到 360 之间的有限数值')
    return float(value)


def rotate_pixels(raw,degrees):
    degrees=checked_degrees(degrees)
    if degrees%90==0:return np.rot90(raw,-int(degrees/90)).copy()
    from scipy.ndimage import rotate
    # Preview/detection only. This resampling is never used for integrated signal.
    return rotate(raw.astype(np.float64),-degrees,reshape=True,order=1,mode='constant',cval=float(np.median(raw)),prefilter=False)


def rotate_image(project,image_id,degrees):
    from .models import validate_project
    from .images import read_source_pixels,preview,MAX_PIXELS
    validate_project(project)
    if project.get('read_only'):raise ValueError('只读项目不能旋转图像')
    degrees=checked_degrees(degrees)
    source=next((a for a in project['images'] if a['id']==image_id),None)
    if source is None:raise ValueError('图像不存在')
    angle=(source.get('rotation_degrees',0)+degrees+180)%360-180
    raw=read_source_pixels(source)
    rad=np.deg2rad(angle);c,s=abs(np.cos(rad)),abs(np.sin(rad));h,w=raw.shape
    if int(h*c+w*s+.5)*int(w*c+h*s+.5)>MAX_PIXELS:raise ValueError('旋转后的画面超过2500万像素，请先使用较小图像')
    pixels=rotate_pixels(raw,angle)
    asset=copy.deepcopy(source)
    asset.update(id=uuid.uuid4().hex,source_image_id=source.get('source_image_id',source['id']),source_name=source.get('source_name',source['name']),rotation_degrees=angle,
                 width=pixels.shape[1],height=pixels.shape[0],preview=preview(pixels))
    asset['name']=f"{asset['source_name']} · 校正 {angle:g}°"
    return asset


def _source_values(raw,shape,degrees,boxes):
    """Select original pixel centers inside the union of corrected half-open boxes."""
    h,w=raw.shape;vh,vw=shape;rad=np.deg2rad(degrees);c,s=np.cos(rad),np.sin(rad)
    for box in boxes:_slice(box,shape)
    corners=np.array([(x,y) for a,b,d,e in boxes for x in [a,d] for y in [b,e]],dtype=float)
    u=corners[:,0]-vw/2;v=corners[:,1]-vh/2
    x=c*u+s*v+w/2;y=-s*u+c*v+h/2
    x0=max(0,int(np.floor(x.min())));x1=min(w,int(np.ceil(x.max())))
    y0=max(0,int(np.floor(y.min())));y1=min(h,int(np.ceil(y.max())))
    if x1<=x0 or y1<=y0:return np.array([],dtype=raw.dtype)
    yy,xx=np.ogrid[y0:y1,x0:x1];dx=xx+.5-w/2;dy=yy+.5-h/2
    qx=c*dx-s*dy+vw/2;qy=s*dx+c*dy+vh/2
    mask=np.zeros((y1-y0,x1-x0),dtype=bool)
    for a,b,d,e in boxes:mask|=(qx>=a)&(qx<d)&(qy>=b)&(qy<e)
    return raw[y0:y1,x0:x1][mask]


def measure_original(asset,roi,backgrounds):
    from .images import read_source_pixels,read_pixels
    angle=checked_degrees(asset.get('rotation_degrees',0))
    if angle%90==0:return measure(read_pixels(asset),roi,backgrounds,polarity=asset['polarity'],ceiling=asset.get('ceiling'))
    if not backgrounds:raise ValueError('请提供局部背景')
    for bg in backgrounds:
        if max(roi[0],bg[0])<min(roi[2],bg[2]) and max(roi[1],bg[1])<min(roi[3],bg[3]):raise ValueError('背景与条带重叠')
    raw=read_source_pixels(asset);shape=(asset['height'],asset['width'])
    band=_source_values(raw,shape,angle,[roi]);bg=_source_values(raw,shape,angle,backgrounds)
    if not band.size or not bg.size:raise ValueError('选框没有覆盖原始图像像素，请避开旋转产生的空白边缘')
    samples=np.concatenate([band,bg]).reshape(1,-1)
    return measure(samples,[0,0,int(band.size),1],[[int(band.size),0,int(samples.size),1]],polarity=asset['polarity'],ceiling=asset.get('ceiling'))
