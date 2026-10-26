import base64
import hashlib
import io
import uuid
from pathlib import Path
import numpy as np
from PIL import Image
from .models import revised

MAX_BYTES=50*1024*1024
MAX_PIXELS=25_000_000


def file_hash(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_pixels(asset):
    path=Path(asset['path'])
    if not path.is_file() or file_hash(path)!=asset['sha256']:raise ValueError('原图缺失或hash已改变，请恢复原文件')
    return decode(path)


def decode(path):
    path=Path(path)
    if path.suffix.lower() not in ['.tif','.tiff','.png']:raise ValueError('仅支持原始灰度TIFF/PNG')
    if path.stat().st_size>MAX_BYTES:raise ValueError('单文件超过50 MiB上限')
    if path.suffix.lower() in ['.tif','.tiff']:
        import tifffile
        with tifffile.TiffFile(path) as t:
            if len(t.pages)!=1:raise ValueError('请先选择并导出单个灰度平面，不自动选择多页图')
            page=t.pages[0]
            if len(page.shape)!=2 or page.shape[0]*page.shape[1]>MAX_PIXELS:raise ValueError('请使用单通道且不超过2500万像素的图像')
            if int(page.photometric)!=1:raise ValueError('请导出MINISBLACK灰度TIFF，避免显示极性歧义')
            a=page.asarray()
    else:
        with Image.open(path) as im:
            if im.mode not in ['L','I','I;16','I;16B','I;16L']:raise ValueError('彩色/调色板图请先明确导出单个检测通道')
            if im.width*im.height>MAX_PIXELS:raise ValueError('图像超过2500万像素上限')
            a=np.asarray(im).copy()
    if a.ndim!=2 or a.size==0 or a.dtype.kind not in 'uif' or not np.isfinite(a).all():raise ValueError('图像不是有限数值的单通道灰度图')
    return a


def preview(a):
    lo,hi=np.percentile(a,[0.5,99.5]);hi=max(float(hi),float(lo)+1)
    gray=np.uint8(np.clip((a.astype(float)-lo)/(hi-lo),0,1)*255)
    im=Image.fromarray(gray);im.thumbnail((1600,1200))
    buf=io.BytesIO();im.save(buf,format='PNG')
    return 'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()


def import_image(project,path):
    a=decode(path);p=revised(project)
    asset=dict(id=uuid.uuid4().hex,name=Path(path).name,path=str(Path(path).resolve()),sha256=file_hash(path),
               width=a.shape[1],height=a.shape[0],dtype=str(a.dtype),preview=preview(a),
               polarity='bright',ceiling=None,exposure='',linear_validated=False)
    p['images'].append(asset)
    return p
