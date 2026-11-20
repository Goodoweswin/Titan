import base64
import hashlib
import io
import uuid
from pathlib import Path
import numpy as np
from PIL import Image
from .models import revised
from .image_cache import CACHE

MAX_BYTES=256*1024*1024
MAX_PIXELS=25_000_000


def file_hash(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read_source_pixels(asset):
    path=Path(asset['path'])
    if not path.is_file() or file_hash(path)!=asset['sha256']:raise ValueError('原图缺失或hash已改变，请恢复原文件')
    return cached_pixels(path,asset.get('page_index'),asset['sha256'])


def read_pixels(asset):
    from .image_rotation import checked_degrees,rotate_pixels
    angle=checked_degrees(asset.get('rotation_degrees',0));raw=read_source_pixels(asset)
    if not angle:return raw
    return CACHE.get_pixels(('rotation',asset['sha256'],asset.get('page_index',0),angle),lambda:rotate_pixels(raw,angle))


def cached_pixels(path,index,digest):
    if Path(path).suffix.lower() in ['.tif','.tiff']:
        import tifffile
        with tifffile.TiffFile(path) as t:index=checked_page_index(index,len(t.pages))
    else:index=checked_page_index(index,1)
    return verified_pixels(path,index,digest)


def verified_pixels(path,index,digest):
    def load():
        pixels=decode(path,index)
        if file_hash(path)!=digest:
            raise ValueError('原图在读取期间已改变，请重新导入')
        return pixels
    return CACHE.get_pixels((digest,index),load)


def checked_path(path):
    path=Path(path)
    if path.suffix.lower() not in ['.tif','.tiff','.png']:raise ValueError('仅支持原始灰度TIFF/PNG')
    if path.stat().st_size>MAX_BYTES:raise ValueError(f'文件超过 WB 单文件 {MAX_BYTES // 1024**2} MiB 上限')
    return path


def checked_page_index(index,count):
    if index is None:
        if count!=1:raise ValueError('此文件含多页图像，请先预览并选择要导入的页面')
        return 0
    if type(index) is not int or not 0<=index<count:raise ValueError('图像页码无效或超出范围')
    return index


def validate_tiff_page(page):
    if len(page.shape)!=2:raise ValueError('此页不是单通道灰度图')
    if not 0<page.imagewidth*page.imagelength<=MAX_PIXELS:raise ValueError('此页超过 WB 单页 2500 万像素上限')
    photo=int(page.photometric)
    if photo==3:
        lut=page.colormap
        if lut is None or not (np.array_equal(lut[0],lut[1]) and np.array_equal(lut[0],lut[2])):raise ValueError('此页为彩色调色板，请选择原始灰度页')
    elif photo not in (0,1):raise ValueError('此页不是单通道灰度图')
    if page.dtype.kind not in 'uif':raise ValueError('图像不是数值灰度图')


def inspect_image(path):
    path=checked_path(path);pages=[];digest=file_hash(path)
    if path.suffix.lower() in ['.tif','.tiff']:
        import tifffile
        with tifffile.TiffFile(path) as t:
            for index,page in enumerate(t.pages):
                error=None
                try:validate_tiff_page(page)
                except ValueError as e:error=str(e)
                inverted=int(page.photometric)==0 or (int(page.photometric)==3 and error is None and bool(page.colormap[0,0]>page.colormap[0,-1]))
                pages.append(dict(page_index=index,width=page.imagewidth,height=page.imagelength,dtype=str(page.dtype),error=error,display_inverted=inverted))
    else:
        a=verified_pixels(path,0,digest)
        pages.append(dict(page_index=0,width=a.shape[1],height=a.shape[0],dtype=str(a.dtype),error=None))
    return dict(name=path.name,sha256=digest,page_count=len(pages),pages=pages)


def png_pixels(path):
    with path.open('rb') as stream:
        header=stream.read(26)
        stream.seek(0)
        with Image.open(stream) as image:
            if image.format!='PNG' or len(header)!=26:raise ValueError('文件不是有效的 PNG')
            if getattr(image,'n_frames',1)!=1:raise ValueError('请将动画 PNG 导出为单张原始灰度图')
            if image.width*image.height>MAX_PIXELS:raise ValueError('图像超过 WB 单页 2500 万像素上限')
            # Preserve the encoded values of single-channel gray PNGs, including
            # older images with a display-only transparency hint.
            if image.mode in ('L','I','I;16','I;16B','I;16L'):
                return np.array(image)
            # Pillow reduces 16-bit multichannel PNGs to 8 bit on load.
            if header[24]==16:
                import imagecodecs
                stream.seek(0)
                pixels=imagecodecs.png_decode(stream.read())
                if pixels.dtype!=np.uint16:raise ValueError('此 PNG 无法保留原始 16 位数值')
            elif image.mode in ('RGB','RGBA','LA','P'):
                pixels=np.asarray(image.convert('RGBA'))
            else:
                raise ValueError('此 PNG 格式不支持，请导出单通道灰度图')
    if pixels.ndim==2:return pixels
    channels=pixels.shape[2]
    if channels in (2,4) and not np.all(pixels[...,-1]==np.iinfo(pixels.dtype).max):
        raise ValueError('此 PNG 含透明像素，请使用不透明的原始灰度图')
    gray=pixels[...,0]
    if channels in (3,4) and not (np.array_equal(gray,pixels[...,1]) and np.array_equal(gray,pixels[...,2])):
        raise ValueError('此 PNG 含颜色，请导出单个检测通道')
    return gray.copy()


def decode(path,page_index=None):
    path=checked_path(path)
    if path.suffix.lower() in ['.tif','.tiff']:
        import tifffile
        with tifffile.TiffFile(path) as t:
            page=t.pages[checked_page_index(page_index,len(t.pages))]
            validate_tiff_page(page)
            try:a=page.asarray()
            except ValueError as e:
                if 'imagecodecs' not in str(e):raise
                with Image.open(path) as im:
                    im.seek(checked_page_index(page_index,len(t.pages)))
                    a=np.asarray(im).copy()
                    # Pillow applies the white-is-zero display transform to L,
                    # but leaves I;16 samples encoded. Undo only that L path.
                    if int(page.photometric)==0 and im.mode=='L' and page.dtype==np.dtype('uint8'):
                        a=np.uint8(255)-a
                if a.shape!=page.shape or a.dtype.itemsize!=page.dtype.itemsize:raise ValueError('此压缩页无法无损读取，请导出原始灰度 TIFF')
    else:
        checked_page_index(page_index,1)
        a=png_pixels(path)
    if a.ndim!=2 or a.size==0 or a.dtype.kind not in 'uif' or not np.isfinite(a).all():raise ValueError('图像不是有限数值的单通道灰度图')
    return a


def display_metadata(path,index):
    meta=dict(display_inverted=False)
    if Path(path).suffix.lower() in ['.tif','.tiff']:
        import tifffile
        with tifffile.TiffFile(path) as t:
            page=t.pages[index];photo=int(page.photometric)
            meta['photometric']={0:'miniswhite',1:'minisblack',3:'palette'}.get(photo,'unknown')
            if photo==0:meta['display_inverted']=True
            elif photo==3:
                lut=page.colormap[0];meta['gray_lut']=lut.tolist()
                meta['display_inverted']=bool(lut[0]>lut[-1])
    return meta


def preview(a,brightness=0,contrast=0):
    lo,hi=np.percentile(a,[0.5,99.5])
    unit=a.astype(float)
    unit-=lo
    unit/=max(float(hi-lo),1)
    if brightness or contrast:
        unit+=brightness/100-.5
        unit*=2**(contrast/50)
        unit+=.5
    np.clip(unit,0,1,out=unit)
    unit*=255
    gray=unit.astype(np.uint8)
    im=Image.fromarray(gray);im.thumbnail((1600,1200))
    buf=io.BytesIO();im.save(buf,format='PNG')
    return 'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()


def display_preview(asset,brightness,contrast):
    if any(type(value) not in (int,float) or not -100<=value<=100 for value in (brightness,contrast)):
        raise ValueError('亮度与对比度范围为 -100 至 100')
    # The canvas applies the same visual inversion as the default preview.
    # Keep the brightness direction consistent with what the user sees.
    if asset.get('display_inverted'):
        brightness=-brightness
    pixels=read_pixels(asset)
    key=('wb-display',asset['sha256'],asset.get('page_index',0),asset.get('rotation_degrees',0),brightness,contrast)
    return CACHE.get_value(key,lambda:preview(pixels,brightness,contrast))


def preview_image_page(path,page_index,expected_sha256=None):
    digest=file_hash(checked_path(path))
    if expected_sha256 is not None and digest!=expected_sha256:raise ValueError('原图在选择期间已改变，请重新导入')
    a=cached_pixels(path,page_index,digest)
    return CACHE.get_value(('preview',digest,page_index),lambda:preview(a))


def import_image(project,path,page_index=None,expected_sha256=None):
    info=inspect_image(path)
    if expected_sha256 is not None and info['sha256']!=expected_sha256:raise ValueError('原图在选择期间已改变，请重新导入')
    index=checked_page_index(page_index,info['page_count'])
    a=verified_pixels(path,index,info['sha256']);p=revised(project)
    name=Path(path).name
    if info['page_count']>1:name+=f' · 第 {index+1} 页'
    asset=dict(id=uuid.uuid4().hex,name=name,path=str(Path(path).resolve()),sha256=info['sha256'],
               width=a.shape[1],height=a.shape[0],dtype=str(a.dtype),preview=CACHE.get_value(('preview',info['sha256'],index),lambda:preview(a)),
               polarity='bright',ceiling=None,exposure='',linear_validated=False)
    if info['page_count']>1:asset.update(page_index=index,page_count=info['page_count'])
    asset.update(display_metadata(path,index))
    p['images'].append(asset)
    return p
