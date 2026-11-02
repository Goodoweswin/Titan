"""Source-linked IF figures and descriptive result exports.

Raw planes are read by images.load_channels; display LUTs never enter measurement.
All figure formats use one point-based scene, leaving SVG annotations editable.
"""
from __future__ import annotations

import base64
import copy
import csv
import io
import json
import math
import shutil
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

import numpy as np
from PIL import Image, ImageColor, ImageDraw
from titan_wb.wb_render import font

MM = 72 / 25.4
MAX_PIXELS = 20_000_000
MAX_NATIVE_PIXELS = 40_000_000
MAX_PREVIEW_SIDE = 1600
MAX_PREVIEW_URL_BYTES = 4 * 1024**2


def _number(value, name, low=None, high=None):
    if isinstance(value, bool):
        raise ValueError(f'{name} must be a finite number')
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f'{name} must be a finite number') from error
    if not math.isfinite(number) or (low is not None and number < low) or (high is not None and number > high):
        raise ValueError(f'{name} is outside the permitted range')
    return number


def _selection(value, field):
    if isinstance(value, dict):
        if 'crop' in value:
            return value['crop']
        return value.get(field['id'])
    return value


def _box(value, width, height, name):
    if value is None:
        return [0, 0, width, height]
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError(f'{name} requires four original-pixel coordinates')
    numbers = [_number(v, name) for v in value]
    if any(v != int(v) for v in numbers):
        raise ValueError(f'{name} requires integer pixel coordinates')
    x0, y0, x1, y1 = map(int, numbers)
    if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
        raise ValueError(f'{name} is outside the original image')
    return [x0, y0, x1, y1]


def _channel_names(project, selectors):
    all_channels = [c for f in project.get('fields', []) for c in f.get('channels', [])]
    if not selectors:
        selectors = list(dict.fromkeys(c['name'] for c in all_channels))
    if not isinstance(selectors, list) or len(selectors) > 4:
        raise ValueError('Select at most four IF channels')
    names = []
    for selector in selectors:
        channel = next((c for c in all_channels if c['id'] == selector), None)
        name = channel['name'] if channel else selector
        if not isinstance(name, str) or not any(c['name'] == name for c in all_channels):
            raise ValueError(f'Unknown IF channel: {selector}')
        if name not in names:
            names.append(name)
    return names


def _range(settings, field, channel, canonical_ids):
    locked = settings.get('locked_ranges') or {}
    if not isinstance(locked, dict):
        raise ValueError('locked_ranges must be an object')
    keys = [channel['name'], channel['id'], *canonical_ids.get(channel['name'], [])]
    value = next((locked[k] for k in keys if k in locked), None)
    if isinstance(value, dict):
        if 'min' in value and 'max' in value:
            value = [value['min'], value['max']]
        else:
            value = value.get(field.get('batch_id', ''))
    if value is None:
        value = [channel.get('display_min', 0), channel.get('display_max', 65535)]
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError('Display range requires [minimum, maximum]')
    lo, hi = (_number(v, 'Display range') for v in value)
    if hi <= lo:
        raise ValueError('Display maximum must be greater than minimum')
    return [lo, hi]


def _png(image, dpi=None):
    out = io.BytesIO()
    image.save(out, format='PNG', **({'dpi': (dpi, dpi)} if dpi else {}))
    return out.getvalue()


def _url(data):
    return 'data:image/png;base64,' + base64.b64encode(data).decode('ascii')


def _scene(project):
    settings = project.get('figure') or {}
    all_fields = project.get('fields') or []
    ids = settings.get('field_ids') or [f['id'] for f in all_fields]
    if not isinstance(ids, list) or len(ids) > 100 or len(ids) != len(set(ids)):
        raise ValueError('Select between one and 100 distinct IF fields')
    lookup = {f['id']: f for f in all_fields}
    if not ids or any(fid not in lookup for fid in ids):
        raise ValueError('Select available IF fields before making a figure')
    fields = [lookup[fid] for fid in ids]
    names = _channel_names(project, settings.get('channel_ids'))
    merge = bool(settings.get('include_merge', True))
    columns = len(names) + int(merge)
    if not names or not columns:
        raise ValueError('Select at least one IF channel')
    width = _number(settings.get('width_mm', 180), 'Figure width', 20, 500) * MM
    dpi = _number(settings.get('dpi', 300), 'DPI', 36, 1200)
    size = _number(settings.get('font_pt', 9), 'Font size', 4, 36)
    scale_bar = settings.get('scale_bar_um')
    if scale_bar is not None:
        scale_bar = _number(scale_bar, 'Scale bar', .000001)
    pad, gap = 3 * MM, 2 * MM
    face = font(size * 4)
    label_width = max(face.getlength(str(f.get('name', f['id']))) / 4 for f in fields) + gap
    if label_width > width * .4:
        raise ValueError('Field labels are too wide; shorten labels or enlarge the figure')
    panel_width = (width - 2 * pad - label_width - gap * (columns - 1)) / columns
    if panel_width < 5 * MM:
        raise ValueError('Figure columns are too narrow; increase figure width')
    canonical_ids = {}
    for field in all_fields:
        for channel in field.get('channels', []):
            canonical_ids.setdefault(channel['name'], []).append(channel['id'])
    texts, rows, warnings = [], [], []
    for col, name in enumerate([*names, *(['Merge'] if merge else [])]):
        texts.append(dict(text=name, x=pad+label_width+(panel_width+gap)*col+panel_width/2,
                          y=pad+size, anchor='middle', fill='black'))
    y = pad + size * 1.8
    native_pixels = 0
    for field in fields:
        w = int(_number(field.get('width'), 'Image width', 1, 4096))
        h = int(_number(field.get('height'), 'Image height', 1, 4096))
        if len(field.get('channels', [])) > 4:
            raise ValueError('At most four raw channels may be loaded')
        crop = _box(_selection(settings.get('crop'), field), w, h, 'Crop')
        x0, y0, x1, y1 = crop
        height = panel_width * (y1-y0)/(x1-x0)
        inset = _selection(settings.get('inset'), field)
        if inset is not None:
            inset = _box(inset, w, h, 'Inset')
            a, b, c, d = inset
            if not (x0 <= a < c <= x1 and y0 <= b < d <= y1):
                raise ValueError('Inset must lie inside the displayed crop')
        native_pixels += (x1-x0)*(y1-y0)*columns
        if inset:
            native_pixels += (inset[2]-inset[0])*(inset[3]-inset[1])*columns
        channels = []
        for name in names:
            matches = [c for c in field.get('channels', []) if c['name'] == name]
            if len(matches) > 1:
                raise ValueError(f'{field.get("name", field["id"])} has duplicate channel name {name}')
            if not matches:
                warnings.append(f'{field.get("name", field["id"])}: missing channel {name}')
                channels.append(None)
            else:
                channel = matches[0]
                try:
                    color = ImageColor.getrgb(channel.get('color', '#ffffff'))
                except (TypeError, ValueError) as error:
                    raise ValueError('Invalid IF channel pseudocolor') from error
                if len(color) != 3:
                    raise ValueError('IF channel pseudocolor must be an RGB color')
                channels.append(dict(channel=channel, display_range=_range(settings, field, channel, canonical_ids), color=color))
        calibration = field.get('pixel_size_um')
        bar_pixels = None
        if scale_bar is not None:
            valid = isinstance(calibration, (tuple, list)) and len(calibration) == 2
            try:
                valid = valid and all(math.isfinite(float(v)) and float(v) > 0 for v in calibration)
            except (TypeError, ValueError):
                valid = False
            if not valid:
                warnings.append(f'{field.get("name", field["id"])}: no physical scale bar without calibration')
            elif scale_bar / float(calibration[0]) > (x1-x0) * .8:
                warnings.append(f'{field.get("name", field["id"])}: scale bar is longer than the displayed crop')
            else:
                bar_pixels = scale_bar / float(calibration[0])
        rows.append(dict(field=field, crop=crop, inset=inset, channels=channels, y=y, height=height,
                         bar_pixels=bar_pixels))
        texts.append(dict(text=str(field.get('name', field['id'])), x=pad, y=y+height/2+size*.35,
                          anchor='start', fill='black'))
        y += height + gap
    height = y-gap+pad
    if project.get('synthetic'):
        texts.append(dict(text='合成示例 · 非实验数据', x=pad, y=height+size, anchor='start', fill='black'))
        height += size*2
    pxw, pxh = round(width*dpi/72), round(height*dpi/72)
    if pxw < 1 or pxh < 1 or pxw*pxh > MAX_PIXELS or native_pixels > MAX_NATIVE_PIXELS:
        raise ValueError('Figure exceeds the render pixel/resource budget; reduce crop, fields, size or DPI')
    return dict(settings=settings, rows=rows, names=names, merge=merge, width=width, height=height,
                pxw=pxw, pxh=pxh, dpi=dpi, size=size, pad=pad, gap=gap, left=label_width,
                panel_width=panel_width, texts=texts, warnings=warnings, scale_bar=scale_bar)


def _display(raw, bounds, color):
    values = np.asarray(raw)
    if values.ndim != 2 or values.dtype.kind not in 'uifb' or not np.all(np.isfinite(values)):
        raise ValueError('IF channel must contain finite two-dimensional numeric original pixels')
    low, high = bounds
    scaled = np.subtract(values, low, dtype=np.float32)
    scaled /= high-low
    np.clip(scaled, 0, 1, out=scaled)
    return np.uint8(scaled[:, :, None] * np.asarray(color, dtype=np.float32))


def _render(project, preview=False):
    from .images import load_channels
    scene = _scene(project)
    dpi, size = scene['dpi'], scene['size']
    scale = dpi/72
    if preview:
        scale = min(scale, MAX_PREVIEW_SIDE/max(scene['width'], scene['height']))
        dpi = scale*72
    canvas = Image.new('RGB', (round(scene['width']*scale), round(scene['height']*scale)), 'white')
    draw = ImageDraw.Draw(canvas)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{scene["width"]/MM:g}mm" height="{scene["height"]/MM:g}mm" viewBox="0 0 {scene["width"]:g} {scene["height"]:g}">',
           f'<rect width="{scene["width"]:g}" height="{scene["height"]:g}" fill="white"/>']
    texts = list(scene['texts'])
    provenance = dict(module='if', schema_version=1, project_id=project.get('id'),
                      project_name=project.get('name'), synthetic=bool(project.get('synthetic')),
                      figure=copy.deepcopy(scene['settings']), fields=[], warnings=scene['warnings'])

    def image(array, x, y, width, height, role='panel'):
        pil = Image.fromarray(array)
        x0, y0 = round(x*scale), round(y*scale)
        x1, y1 = round((x+width)*scale), round((y+height)*scale)
        canvas.paste(pil.resize((max(1, x1-x0), max(1, y1-y0)), Image.Resampling.LANCZOS), (x0, y0))
        if not preview:
            svg.append(f'<image data-role="{role}" x="{x:g}" y="{y:g}" width="{width:g}" height="{height:g}" href={quoteattr(_url(_png(pil)))} preserveAspectRatio="none"/>')

    def rectangle(x, y, width, height, role):
        draw.rectangle((round(x*scale), round(y*scale), round((x+width)*scale), round((y+height)*scale)),
                       outline='white', width=max(1, round(scale)))
        svg.append(f'<rect data-role="{role}" x="{x:g}" y="{y:g}" width="{width:g}" height="{height:g}" fill="none" stroke="white" stroke-width="1"/>')

    for row in scene['rows']:
        field = row['field']
        # The image subsystem verifies hashes, axis/indexer selections and decoded budgets.
        raw = load_channels(field) if field.get('channels') else {}
        if sum(a.nbytes for a in raw.values()) > 256 * 1024**2:
            raise ValueError('Raw channel decode exceeds the resource budget')
        x0, y0, x1, y1 = row['crop']
        arrays, descriptions = [], []
        for selected in row['channels']:
            if selected is None:
                arrays.append(np.zeros((y1-y0, x1-x0, 3), dtype=np.uint8))
                continue
            channel = selected['channel']
            values = raw.get(channel['id'])
            if values is None or values.shape != (field['height'], field['width']):
                raise ValueError('Original channel dimensions do not match the field')
            arrays.append(_display(values[y0:y1, x0:x1], selected['display_range'], selected['color']))
            descriptions.append(dict(id=channel['id'], name=channel['name'], color=channel.get('color', '#ffffff'),
                                     display_range=selected['display_range'], source=copy.deepcopy(channel['source'])))
        del raw
        if scene['merge']:
            merged = np.zeros_like(arrays[0], dtype=np.uint16)
            for array in arrays:
                merged += array
            arrays.append(np.uint8(np.minimum(merged, 255)))
            del merged
        provenance['fields'].append(dict(field_id=field['id'], name=field.get('name'),
            sample_id=field.get('sample_id'), bio_id=field.get('bio_id'), group=field.get('group'),
            batch_id=field.get('batch_id'), pixel_size_um=field.get('pixel_size_um'),
            crop=row['crop'], inset=row['inset'], channels=descriptions))
        for col, array in enumerate(arrays):
            x = scene['pad']+scene['left']+col*(scene['panel_width']+scene['gap'])
            y, width, height = row['y'], scene['panel_width'], row['height']
            image(array, x, y, width, height)
            if row['inset']:
                a, b, c, d = row['inset']
                rectangle(x+(a-x0)/(x1-x0)*width, y+(b-y0)/(y1-y0)*height,
                          (c-a)/(x1-x0)*width, (d-b)/(y1-y0)*height, 'inset-source')
                iw = width*.35
                ih = iw*(d-b)/(c-a)
                if ih > height*.5:
                    ih = height*.5
                    iw = ih*(c-a)/(d-b)
                ix, iy = x+width-iw-2, y+2
                image(array[b-y0:d-y0, a-x0:c-x0], ix, iy, iw, ih, 'inset')
                rectangle(ix, iy, iw, ih, 'inset-border')
            if row['bar_pixels'] is not None:
                length = row['bar_pixels']/(x1-x0)*width
                bx, by = x+width-width*.08-length, y+height-height*.1
                draw.line((bx*scale, by*scale, (bx+length)*scale, by*scale), fill='white', width=max(1, round(2*scale)))
                svg.append(f'<line data-role="scale-bar" x1="{bx:g}" y1="{by:g}" x2="{bx+length:g}" y2="{by:g}" stroke="white" stroke-width="2"/>')
                texts.append(dict(text=f'{scene["scale_bar"]:g} µm', x=bx+length/2, y=by-size*.5,
                                  anchor='middle', fill='white'))
    face = font(size*scale)
    for text in texts:
        draw.text((text['x']*scale, text['y']*scale), text['text'], font=face, fill=text['fill'],
                  anchor='ms' if text['anchor'] == 'middle' else 'ls')
        svg.append(f'<text x="{text["x"]:g}" y="{text["y"]:g}" text-anchor="{text["anchor"]}" font-family="Noto Sans SC, Arial, sans-serif" font-size="{size:g}" fill="{text["fill"]}">{escape(text["text"])}</text>')
    svg.append('</svg>')
    png = _png(canvas, dpi)
    # A dimension limit alone cannot bound a high-entropy RGB PNG. Bound the
    # actual base64 transport payload too, preserving the scene's aspect ratio.
    if preview:
        raw_budget = (MAX_PREVIEW_URL_BYTES-len('data:image/png;base64,'))*3//4
        while len(png) > raw_budget:
            factor = min(.9, math.sqrt(raw_budget/len(png))*.95)
            canvas = canvas.resize((max(1, math.floor(canvas.width*factor)),
                                    max(1, math.floor(canvas.height*factor))), Image.Resampling.LANCZOS)
            dpi *= factor
            png = _png(canvas, dpi)
    return dict(canvas=canvas, png=png, svg='\n'.join(svg), width=canvas.width,
                height=canvas.height, export_width=scene['pxw'], export_height=scene['pxh'],
                warnings=scene['warnings'], provenance=provenance, dpi=dpi)


def preview_figure(project):
    rendered = _render(project, preview=True)
    return dict(png=_url(rendered['png']), width=rendered['width'], height=rendered['height'],
                export_width=rendered['export_width'], export_height=rendered['export_height'],
                warnings=rendered['warnings'])


def _publish(destination, names, writer):
    """Write complete output to a sibling staging directory before publication."""
    destination = Path(destination).expanduser().resolve()
    if names is None:
        if destination.exists():
            raise ValueError('Export destination already exists')
        parent = destination.parent
    else:
        parent = destination.parent
        if any((parent/name).exists() for name in names):
            raise ValueError('An export file already exists')
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.titan-if-export-', dir=parent))
    try:
        files = writer(staging)
        if names is None:
            # rename does not replace an existing non-empty directory.
            if destination.exists():
                raise ValueError('Export destination already exists')
            staging.rename(destination)
            return dict(files=[str(destination/name) for name in files])
        created = []
        try:
            for name in files:
                # Exclusive creation protects existing user exports. Roll back only
                # files this call created if publication is interrupted.
                with (parent/name).open('xb') as target:
                    created.append(parent/name)
                    with (staging/name).open('rb') as source:
                        shutil.copyfileobj(source, target)
        except BaseException:
            for path in created:
                path.unlink(missing_ok=True)
            raise
        return dict(files=[str(parent/name) for name in files])
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def export_figure(project, destination):
    destination = Path(destination).expanduser().resolve()
    suffix = destination.suffix.lower()
    if suffix and suffix not in ('.png', '.tif', '.tiff', '.svg'):
        raise ValueError('IF figure export supports PNG, TIFF or SVG')
    rendered = _render(project)
    names = [destination.name, destination.stem+'.source.json'] if suffix else None

    def write(root):
        outputs = [destination.name] if suffix else ['figure.png', 'figure.tiff', 'figure.svg']
        for name in outputs:
            path = root/name
            ext = path.suffix.lower()
            if ext == '.png':
                path.write_bytes(rendered['png'])
            elif ext == '.svg':
                path.write_text(rendered['svg'], encoding='utf-8')
            else:
                rendered['canvas'].save(path, format='TIFF', compression='tiff_deflate', dpi=(rendered['dpi'], rendered['dpi']))
        meta = destination.stem+'.source.json' if suffix else 'source.json'
        (root/meta).write_text(json.dumps(rendered['provenance'], ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        return [*outputs, meta]

    return _publish(destination, names, write)


_OBJECT_COLUMNS = ['field_id', 'channel_id', 'object_id', 'area_px', 'area_um2', 'raw_sum', 'mean',
                   'background_mean', 'corrected_sum', 'positive_pixels', 'positive']
_FIELD_COLUMNS = ['field_id', 'channel_id', 'object_count', 'area_px', 'area_um2', 'raw_sum', 'mean',
                  'background_mean', 'corrected_sum', 'positive_pixels', 'positive_area_fraction',
                  'positive_count', 'positive_fraction']
_SAMPLE_COLUMNS = ['bio_id', 'group', 'batch_id', 'channel_id', 'channel_name', 'field_count',
                   'sample_ids', 'object_count', 'area_px', 'area_um2', 'raw_sum', 'mean',
                   'background_mean', 'corrected_sum', 'positive_pixels', 'positive_area_fraction',
                   'positive_count', 'positive_fraction']


def _columns(rows, defaults):
    return list(dict.fromkeys([*defaults, *(key for row in rows for key in row)]))


def _cell(value, csv_mode=False, xlsx_mode=False):
    if value is None:
        return None
    if isinstance(value, (dict, list, tuple)):
        value = json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    if isinstance(value, (np.integer, np.floating)):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('Results contain a non-finite numeric value')
    if xlsx_mode and isinstance(value, int) and not isinstance(value, bool) and abs(value) > 2**53-1:
        # Excel numeric cells use binary64. Preserve exact original-pixel sums
        # as decimal text instead of silently rounding their low bits.
        value = str(value)
    if csv_mode and isinstance(value, str) and value.startswith(('=', '+', '-', '@', '\t', '\r')):
        return "'"+value
    return value


def _scatter(samples, synthetic=False):
    """One plotted point per aggregate biological sample, without field/cell n."""
    panels = {}
    for row in samples:
        key = (str(row.get('channel_name') or row.get('channel_id', '')), str(row.get('batch_id', '')))
        panels.setdefault(key, []).append(row)
    if len(panels) > 24 or len(samples) > 10000:
        raise ValueError('Sample scatter exceeds the render budget; export a smaller project')
    width, panel_height = 1000, 320
    height = 85 + max(1, len(panels))*panel_height
    image = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(image)
    title, regular, small = font(23), font(17), font(14)
    heading = 'Synthetic example · not experimental data' if synthetic else 'Biological sample measurements'
    draw.text((30, 20), heading, font=title, fill='#142336')
    draw.text((30, 53), 'Each point is one biological sample. Descriptive data; no inferential tests.', font=small, fill='#526277')
    points = []
    if not panels:
        draw.text((50, 140), 'No available biological sample measurements', font=regular, fill='#526277')
    for index, ((channel, batch), rows) in enumerate(panels.items()):
        top = 85+index*panel_height
        metric = next((metric for metric in ('positive_fraction', 'positive_area_fraction', 'mean', 'corrected_sum', 'raw_sum')
                       if any(isinstance(row.get(metric), (int, float)) and not isinstance(row.get(metric), bool)
                              and math.isfinite(row[metric]) for row in rows)), None)
        metric_labels = dict(positive_fraction='Positive fraction', positive_area_fraction='Positive area fraction',
                             mean='Mean original intensity', corrected_sum='Background-corrected sum', raw_sum='Raw intensity sum')
        draw.text((30, top), f'{channel}  |  Batch: {batch or "unspecified"}  |  {metric_labels.get(metric, "No available metric")}',
                  font=regular, fill='#142336')
        usable = [row for row in rows if metric and isinstance(row.get(metric), (int, float))
                  and not isinstance(row.get(metric), bool) and math.isfinite(row[metric])]
        if not usable:
            draw.text((60, top+90), 'No available measurements; missing data are omitted.', font=small, fill='#526277')
            continue
        groups = list(dict.fromkeys(str(row.get('group', '')) for row in usable))
        low = min(0, min(row[metric] for row in usable))
        high = max(0, max(row[metric] for row in usable))
        if high == low:
            high = low+1
        if metric in ('positive_fraction', 'positive_area_fraction'):
            low, high = 0, 1
        left, right, bottom, plot_top = 105, width-45, top+235, top+55
        draw.line((left, plot_top, left, bottom, right, bottom), fill='#738297', width=1)
        for fraction in (0, .5, 1):
            value = low+fraction*(high-low)
            y = bottom-fraction*(bottom-plot_top)
            draw.line((left, y, right, y), fill='#e0e5eb', width=1)
            draw.text((left-12, y), f'{value:.4g}', font=small, fill='#526277', anchor='rm')
        for group_index, group in enumerate(groups):
            x = left+(group_index+.5)*(right-left)/len(groups)
            group_rows = [row for row in usable if str(row.get('group', '')) == group]
            draw.text((x, bottom+15), f'{group or "unspecified"}  (n={len(group_rows)})',
                      font=small, fill='#142336', anchor='mt')
            for offset, row in enumerate(group_rows):
                # Deterministic spread makes repeated values visible without random state.
                spread = 0 if len(group_rows) == 1 else ((offset % 9)-4)*5
                px = x+spread
                py = bottom-(row[metric]-low)/(high-low)*(bottom-plot_top)
                draw.ellipse((px-4, py-4, px+4, py+4), fill='#2865a8', outline='white')
                label = str(row.get('bio_id', ''))
                if len(group_rows) <= 12:
                    draw.text((px+7, py-4), label, font=small, fill='#142336')
                points.append(dict(bio_id=row.get('bio_id'), group=row.get('group'), channel=channel,
                                   batch_id=batch, metric=metric, value=row[metric]))
        if len(usable) != len(rows):
            draw.text((left, top+285), f'{len(rows)-len(usable)} unavailable sample measurements omitted.', font=small, fill='#526277')
    return _png(image, 150), dict(unit='biological_sample', point_count=len(points), points=points,
                                 inferential_tests=False)


def export_results(project, destination):
    from .analysis import aggregate_results
    # This call rejects stale signatures before the destination is created.
    tables = aggregate_results(project)
    if set(tables) != {'objects', 'fields', 'samples'}:
        raise ValueError('Unexpected IF aggregate result tables')
    defaults = dict(objects=_OBJECT_COLUMNS, fields=_FIELD_COLUMNS, samples=_SAMPLE_COLUMNS)
    columns = {name: _columns(rows, defaults[name]) for name, rows in tables.items()}
    if any(len(rows) > 500000 for rows in tables.values()) or sum(len(rows)*len(columns[name]) for name, rows in tables.items()) > 5_000_000:
        raise ValueError('Result export exceeds the table resource budget')
    # Validate values before making any files, including null handling and finite values.
    for rows in tables.values():
        for row in rows:
            for value in row.values():
                _cell(value)
    scatter, scatter_manifest = _scatter(tables['samples'], synthetic=bool(project.get('synthetic')))
    provenance = dict(module='if', schema_version=1, project_id=project.get('id'),
        project_name=project.get('name'), synthetic=bool(project.get('synthetic')),
        table_rows={name: len(rows) for name, rows in tables.items()}, scatter=scatter_manifest, fields=[])
    for field in project.get('fields', []):
        provenance['fields'].append(dict(field_id=field['id'], name=field.get('name'), sample_id=field.get('sample_id'),
            bio_id=field.get('bio_id'), group=field.get('group'), batch_id=field.get('batch_id'),
            pixel_size_um=field.get('pixel_size_um'), recipe=copy.deepcopy(field.get('recipe', {})),
            mask=copy.deepcopy(field.get('mask')), rois=copy.deepcopy(field.get('rois', [])),
            result_signature=(field.get('result') or {}).get('input_signature'),
            result_warnings=(field.get('result') or {}).get('warnings', []),
            channels=[dict(id=c['id'], name=c['name'], source=copy.deepcopy(c['source'])) for c in field.get('channels', [])]))
    destination = Path(destination).expanduser().resolve()
    suffix = destination.suffix.lower()
    if suffix and suffix != '.xlsx':
        raise ValueError('Results destination must be a directory or XLSX filename')
    prefix = destination.stem+'_' if suffix else ''
    workbook_name = destination.name if suffix else 'results.xlsx'
    csv_names = {name: prefix+name+'.csv' for name in tables}
    scatter_name = prefix+'sample_scatter.png'
    meta_name = destination.stem+'.source.json' if suffix else 'source.json'
    output_names = [*csv_names.values(), workbook_name, scatter_name, meta_name]

    def write(root):
        from openpyxl import Workbook
        from openpyxl.cell import WriteOnlyCell
        from openpyxl.styles import Font
        book = Workbook(write_only=True)
        for name in ('objects', 'fields', 'samples'):
            rows, headers = tables[name], columns[name]
            with (root/csv_names[name]).open('w', encoding='utf-8-sig', newline='') as handle:
                writer = csv.writer(handle)
                writer.writerow(headers)
                for row in rows:
                    writer.writerow([_cell(row.get(key), csv_mode=True) for key in headers])
            sheet = book.create_sheet(name)
            sheet.freeze_panes = 'A2'
            header_cells = []
            for key in headers:
                cell = WriteOnlyCell(sheet, value=key)
                cell.font = Font(bold=True)
                header_cells.append(cell)
            sheet.append(header_cells)
            for row in rows:
                cells = []
                for key in headers:
                    value = _cell(row.get(key), xlsx_mode=True)
                    cell = WriteOnlyCell(sheet, value=value)
                    if isinstance(value, str):
                        cell.data_type = 's'
                    cells.append(cell)
                sheet.append(cells)
        book.save(root/workbook_name)
        (root/scatter_name).write_bytes(scatter)
        (root/meta_name).write_text(json.dumps(provenance, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        return output_names

    return _publish(destination, output_names if suffix else None, write)
