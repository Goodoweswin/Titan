"""Physical WB layout shared by raster preview and portable editable SVG."""
import base64
import io
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from .images import read_pixels, read_source_pixels

MM = 72 / 25.4


def font(size):
    bundled = Path(__file__).parent / 'assets/NotoSansSC.ttf'
    if bundled.is_file():
        face=ImageFont.truetype(str(bundled), max(1, round(size)))
        face.set_variation_by_name('Regular')
        return face
    from matplotlib.font_manager import findfont
    return ImageFont.truetype(findfont('DejaVu Sans'), max(1, round(size)))


def display_values(source):
    """Decode palette intensities before spatial interpolation, never indices."""
    lut = source.get('gray_lut')
    if lut is None:return read_pixels(source).astype(float)
    raw=read_source_pixels(source);indices=raw.astype(int)
    if not np.array_equal(indices,raw) or indices.min()<0 or indices.max()>=len(lut):
            raise ValueError('原图灰度映射范围无效')
    values=np.asarray(lut,dtype=float)[indices]
    if source.get('rotation_degrees'):
        from .image_rotation import rotate_pixels
        values=rotate_pixels(values,source['rotation_degrees'])
    return values


def display_pixels(source):
    values=display_values(source)
    if values.shape != (source['height'], source['width']):
        raise ValueError('原图尺寸与组图来源不一致')
    lut = source.get('gray_lut')
    lo, hi = source['display_range']
    gray = np.uint8(np.clip((values - lo) / (hi - lo), 0, 1) * 255)
    if source.get('display_inverted') and lut is None:
        gray = 255 - gray
    return gray


def png_bytes(image, dpi=None):
    out = io.BytesIO()
    image.save(out, format='PNG', **({'dpi': (dpi, dpi)} if dpi else {}))
    return out.getvalue()


def data_url(raw):
    return 'data:image/png;base64,' + base64.b64encode(raw).decode('ascii')


def render(document):
    settings = document['settings']; width = settings['width_mm'] * MM
    size = settings['font_pt']; gap = settings['gap_mm'] * MM
    pad = 3 * MM; measure = font(size * 4)
    text_width = lambda text: measure.getlength(text) / 4
    left = max([text_width(r['protein']) for r in document['rows']] + [0]) + 2 * MM
    right = max([text_width(t + ' kDa') for r in document['rows'] for t in
                 [r['expected_mw'], *[m['text'] for m in r['markers']]] if t] + [0]) + 3 * MM
    available = width - 2 * pad - left - right
    requested = settings['image_width_mm'] * MM
    image_width = requested or available
    if image_width < 5 * MM or image_width > available + .01:
        raise ValueError('图像区或标签超出画布，请增大组图宽度、减小图像区宽度或缩短标签')
    x = pad + left; y = pad + (size * 1.7 if document['labels'] else 0)
    rows = []; texts = []
    for label in document['labels']:
        if text_width(label['text']) > width - 2 * pad:
            raise ValueError('顶部标签过长，请缩短文字或增大组图宽度')
        texts.append(dict(text=label['text'], x=x + label['x'] * image_width, y=pad + size, anchor='middle'))
    full_images = {}
    for row in document['rows']:
        source = row['source']; key = (source['sha256'], source.get('page_index', 0), source.get('rotation_degrees', 0),
                                      tuple(source['display_range']), source.get('display_inverted', False))
        if key not in full_images: full_images[key] = display_pixels(source)
        a, b, c, d = row['crop']; crop = Image.fromarray(full_images[key][b:d, a:c])
        height = image_width * (d - b) / (c - a)
        rows.append(dict(id=row['id'], x_pt=x, y_pt=y, width_pt=image_width, height_pt=height,
                         effective_dpi=(c-a)/(image_width/72), png=data_url(png_bytes(crop))))
        texts.append(dict(text=row['protein'], x=pad, y=y + height/2 + size*.35, anchor='start'))
        if row['expected_mw']:
            texts.append(dict(text=row['expected_mw']+' kDa', x=x+image_width+2*MM, y=y+height/2+size*.35, anchor='start'))
        for marker in row['markers']:
            my = y + (marker['y'] - b) / (d-b) * height
            texts.append(dict(text=marker['text']+' kDa', x=x+image_width+2*MM, y=my+size*.35, anchor='start'))
        y += height + gap
    height = y - gap + pad
    if document.get('synthetic'):
        texts.append(dict(text='合成示例 · 非实验数据', x=pad, y=height+size, anchor='start')); height += size*2
    dpi = settings['dpi']; scale = dpi/72
    pxw, pxh = round(width*scale), round(height*scale)
    if not rows or pxw < 1 or pxh < 1 or pxw * pxh > 20_000_000:
        raise ValueError('组图超过2000万像素或尺寸无效，请减少行数、尺寸或DPI')
    canvas = Image.new('RGB', (pxw, pxh), 'white'); draw = ImageDraw.Draw(canvas); face = font(size*scale)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width/MM:g}mm" height="{height/MM:g}mm" viewBox="0 0 {width:g} {height:g}">',
           f'<rect width="{width:g}" height="{height:g}" fill="white"/>']
    for row in rows:
        crop = Image.open(io.BytesIO(base64.b64decode(row['png'].split(',')[1])))
        x0, y0 = round(row['x_pt']*scale), round(row['y_pt']*scale)
        x1, y1 = round((row['x_pt']+row['width_pt'])*scale), round((row['y_pt']+row['height_pt'])*scale)
        canvas.paste(crop.resize((max(1,x1-x0),max(1,y1-y0)),Image.Resampling.LANCZOS),(x0,y0))
        svg.append(f'<image x="{row["x_pt"]:g}" y="{row["y_pt"]:g}" width="{row["width_pt"]:g}" height="{row["height_pt"]:g}" href={quoteattr(row["png"])} preserveAspectRatio="none"/>')
    for text in texts:
        draw.text((text['x']*scale,text['y']*scale),text['text'],font=face,fill='black',anchor='ms' if text['anchor']=='middle' else 'ls')
        svg.append(f'<text x="{text["x"]:g}" y="{text["y"]:g}" text-anchor="{text["anchor"]}" font-family="Noto Sans SC, Arial, sans-serif" font-size="{size:g}" fill="black">{escape(text["text"])}</text>')
    svg.append('</svg>')
    return dict(png=png_bytes(canvas,dpi),svg='\n'.join(svg),width_mm=width/MM,height_mm=height/MM,
                layout=dict(rows=rows,texts=texts),width=pxw,height=pxh)
