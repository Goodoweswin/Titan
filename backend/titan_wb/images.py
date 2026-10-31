import base64
import hashlib
import io
import uuid
from pathlib import Path
import numpy as np
from PIL import Image
from .models import revised
from .image_cache import CACHE

MAX_BYTES=50*1024*1024
MAX_PIXELS=25_000_000


def file_hash(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_pixels(asset):
    path=Path(asset['path'])
    if not path.is_file() or file_hash(path)!=asset['sha256']:raise ValueError('原图缺失或hash已改变，请恢复原文件')
    return cached_pixels(path,asset.get('page_index'),asset['sha256'])


def cached_pixels(path,index,digest):
    if Path(path).suffix.lower() in ['.tif','.tiff']:
        import tifffile
        with tifffile.TiffFile(path) as t:index=checked_page_index(index,len(t.pages))
    else:index=checked_page_index(index,1)
    return CACHE.get_pixels((digest,index),lambda:decode(path,index))


def checked_path(path):
    path=Path(path)
    if path.suffix.lower() not in ['.tif','.tiff','.png']:raise ValueError('仅支持原始灰度TIFF/PNG')
    if path.stat().st_size>MAX_BYTES:raise ValueError('单文件超过50 MiB上限')
    return path


def checked_page_index(index,count):
    if index is None:
        if count!=1:raise ValueError('此文件含多页图像，请先预览并选择要导入的页面')
        return 0
    if type(index) is not int or not 0<=index<count:raise ValueError('图像页码无效或超出范围')
    return index


def validate_tiff_page(page):
    if len(page.shape)!=2 or not 0<page.shape[0]*page.shape[1]<=MAX_PIXELS:raise ValueError('请使用单通道且不超过2500万像素的图像')
    if int(page.photometric)!=1:raise ValueError('请导出MINISBLACK灰度TIFF，避免显示极性歧义')
    if page.dtype.kind not in 'uif':raise ValueError('图像不是数值灰度图')


def inspect_image(path):
    path=checked_path(path);pages=[]
    if path.suffix.lower() in ['.tif','.tiff']:
        import tifffile
        with tifffile.TiffFile(path) as t:
            for index,page in enumerate(t.pages):
                error=None
                try:validate_tiff_page(page)
                except ValueError as e:error=str(e)
                pages.append(dict(page_index=index,width=page.imagewidth,height=page.imagelength,dtype=str(page.dtype),error=error))
    else:
        a=decode(path)
        pages.append(dict(page_index=0,width=a.shape[1],height=a.shape[0],dtype=str(a.dtype),error=None))
    return dict(name=path.name,sha256=file_hash(path),page_count=len(pages),pages=pages)


def decode(path,page_index=None):
    path=checked_path(path)
    if path.suffix.lower() in ['.tif','.tiff']:
        import tifffile
        with tifffile.TiffFile(path) as t:
            page=t.pages[checked_page_index(page_index,len(t.pages))]
            validate_tiff_page(page)
            a=page.asarray()
    else:
        checked_page_index(page_index,1)
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


def preview_image_page(path,page_index,expected_sha256=None):
    digest=file_hash(checked_path(path))
    if expected_sha256 is not None and digest!=expected_sha256:raise ValueError('原图在选择期间已改变，请重新导入')
    a=cached_pixels(path,page_index,digest)
    return CACHE.get_value(('preview',digest,page_index),lambda:preview(a))


def import_image(project,path,page_index=None,expected_sha256=None):
    info=inspect_image(path)
    if expected_sha256 is not None and info['sha256']!=expected_sha256:raise ValueError('原图在选择期间已改变，请重新导入')
    index=checked_page_index(page_index,info['page_count'])
    a=CACHE.get_pixels((info['sha256'],index),lambda:decode(path,index));p=revised(project)
    name=Path(path).name
    if info['page_count']>1:name+=f' · 第 {index+1} 页'
    asset=dict(id=uuid.uuid4().hex,name=name,path=str(Path(path).resolve()),sha256=info['sha256'],
               width=a.shape[1],height=a.shape[0],dtype=str(a.dtype),preview=CACHE.get_value(('preview',info['sha256'],index),lambda:preview(a)),
               polarity='bright',ceiling=None,exposure='',linear_validated=False)
    if info['page_count']>1:asset.update(page_index=index,page_count=info['page_count'])
    p['images'].append(asset)
    return p
