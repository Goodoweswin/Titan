"""Metadata-first TIFF import and verified original-channel access for 2D IF."""
from __future__ import annotations

import base64
import hashlib
import io
import math
from pathlib import Path
import uuid
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image, ImageColor
import tifffile

MAX_FILE_BYTES = 2 * 1024**3
MAX_RAW_BYTES = 256 * 1024**2
MAX_WORK_BYTES = 1024**3
MAX_SIDE = 4096
COLORS = ['#4090ff', '#40d080', '#ff5050', '#e0b040']


def file_sha256(path: str | Path) -> str:
    """Hash originals without allocating a file-sized bytes object."""
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _path(path) -> Path:
    result = Path(path).expanduser().resolve(strict=True)
    if not result.is_file():
        raise ValueError('Image source must be a file')
    if result.stat().st_size > MAX_FILE_BYTES:
        raise ValueError('Image file exceeds 2 GiB limit')
    return result


def _index(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < 0:
        raise ValueError(f'{name} index must be a nonnegative integer')
    return int(value)


def _calibration(value):
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError('pixel_size_um must contain X and Y calibration')
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in value):
        raise ValueError('pixel_size_um must be finite and positive')
    return [float(v) for v in value]


def _ome_info(tiff, index):
    if not tiff.ome_metadata:
        return [], None
    try:
        root = ET.fromstring(tiff.ome_metadata)
        images = [node for node in root if node.tag.rsplit('}', 1)[-1] == 'Image']
        pixels = next(node for node in images[index] if node.tag.rsplit('}', 1)[-1] == 'Pixels')
        names = [node.get('Name', '') for node in pixels if node.tag.rsplit('}', 1)[-1] == 'Channel']
        # OME's default physical size unit is micrometres.
        units = {'µm': 1, 'μm': 1, 'um': 1, 'nm': .001, 'mm': 1000, 'cm': 10000, 'm': 1e6}
        calibration = []
        for axis in 'XY':
            scale = units.get(pixels.get(f'PhysicalSize{axis}Unit', 'µm'))
            value = pixels.get(f'PhysicalSize{axis}')
            if scale is None or value is None:
                return names, None
            calibration.append(float(value) * scale)
        return names, _calibration(calibration)
    except (ET.ParseError, IndexError, StopIteration, TypeError, ValueError):
        return [], None


def _validate_manifest(tiff, path):
    """External OME planes need independent selections and independent hashes."""
    if not tiff.ome_metadata:
        return
    try:
        root = ET.fromstring(tiff.ome_metadata)
    except ET.ParseError as exc:
        raise ValueError('Invalid OME metadata') from exc
    for node in root.iter():
        referenced = node.get('FileName')
        if referenced and (Path(path).parent / referenced).resolve() != Path(path).resolve():
            raise ValueError('Multi-file OME external planes require explicit 2D channel files for verified provenance')


def _axes(series, override=None):
    axes = (override if override is not None else series.axes).upper()
    if len(axes) != len(series.shape) or len(set(axes)) != len(axes) or axes.count('X') != 1 or axes.count('Y') != 1:
        raise ValueError('Invalid axes mapping: length, unique axes, and exactly one X/Y are required')
    if any(axis not in 'XYZTCS' for axis in axes):
        raise ValueError('Ambiguous axes require an explicit axes_override mapping; pages are not channels')
    if 'C' in axes and 'S' in axes:
        raise ValueError('Simultaneous C and sample axes are unsupported')
    return axes


def _series_info(tiff, series, index):
    axes = series.axes
    shape = list(series.shape)
    names, calibration = _ome_info(tiff, index)
    channel_axis = 'C' if 'C' in axes else 'S' if 'S' in axes else None
    count = shape[axes.index(channel_axis)] if channel_axis else 1
    rgb = int(series.pages[0].photometric) == 2 or 'S' in axes
    return {'index': index, 'axes': axes, 'shape': shape, 'dtype': str(series.dtype),
            'width': shape[axes.index('X')] if 'X' in axes else None,
            'height': shape[axes.index('Y')] if 'Y' in axes else None,
            'channel_count': count, 'channel_names': [names[i] if i < len(names) and names[i] else f'Channel {i + 1}' for i in range(count)],
            'pixel_size_um': calibration, 'quantitative': not rgb,
            'requires_axes_mapping': any(axis not in 'XYZTCS' for axis in axes)}


def inspect_image(path):
    """Inspect TIFF series metadata, without decoding pixels or hashing the file."""
    source = _path(path)
    with tifffile.TiffFile(source) as tiff:
        _validate_manifest(tiff, source)
        return {'name': source.name, 'size_bytes': source.stat().st_size,
                'series': [_series_info(tiff, series, index) for index, series in enumerate(tiff.series)]}


def _validate_geometry(series, axes):
    dtype = np.dtype(series.dtype)
    if dtype.kind not in 'uif' or dtype.itemsize > 8 or (dtype.kind in 'ui' and dtype.itemsize > 4):
        raise ValueError(f'Unsupported quantitative image dtype {dtype}')
    width, height = (int(series.shape[axes.index(axis)]) for axis in 'XY')
    if min(width, height) < 1 or max(width, height) > MAX_SIDE:
        raise ValueError('Image dimensions exceed 4096 pixels per side limit')
    return width, height


def _plane(series, axes, indexers):
    """Decode one page and select its in-page sample, never the entire series."""
    width, height = _validate_geometry(series, axes)
    if width * height * series.dtype.itemsize > MAX_RAW_BYTES:
        raise ValueError('Raw plane exceeds 256 MiB decode limit')
    page_shape = tuple(series.pages[0].shape)
    page_ndim = len(page_shape)
    if tuple(series.shape[-page_ndim:]) != page_shape:
        raise ValueError('Unsupported TIFF page layout; export explicit 2D channel TIFF files')
    page_bytes = math.prod(page_shape) * series.dtype.itemsize
    if page_bytes > MAX_RAW_BYTES:
        raise ValueError('TIFF page exceeds 256 MiB decode limit')
    outer_axes = axes[:-page_ndim]
    outer_shape = series.shape[:-page_ndim]
    page_index = int(np.ravel_multi_index(tuple(indexers[axis] for axis in outer_axes), outer_shape)) if outer_axes else 0
    if page_index >= len(series.pages):
        raise ValueError('Selected TIFF plane is missing')
    array = series.pages[page_index].asarray()
    inner_axes = axes[-page_ndim:]
    selection = tuple(slice(None) if axis in 'YX' else indexers[axis] for axis in inner_axes)
    array = array[selection]
    remaining = ''.join(axis for axis in inner_axes if axis in 'YX')
    if remaining == 'XY':
        array = array.T
    if array.shape != (height, width):
        raise ValueError('Selected image plane is not two-dimensional YX')
    if not np.isfinite(array).all():
        raise ValueError('Image contains non-finite (NaN or infinity) pixels')
    return np.ascontiguousarray(array)


def _selection(series, selection):
    axes = _axes(series, selection.get('axes_override'))
    width, height = _validate_geometry(series, axes)
    incoming = selection.get('indexers') or {}
    if not isinstance(incoming, dict) or any(axis not in axes or axis in 'XYCS' for axis in incoming):
        raise ValueError('Unknown or invalid axis indexer; use channel_indices for channels')
    indexers = {}
    for axis, size in zip(axes, series.shape):
        if axis in 'XYCS':
            continue
        if size > 1 and axis not in incoming:
            raise ValueError(f'Explicit {axis} plane index is required')
        indexers[axis] = _index(incoming.get(axis, 0), axis)
        if indexers[axis] >= size:
            raise ValueError(f'{axis} plane index is outside the image')
    channel_axis = 'C' if 'C' in axes else 'S' if 'S' in axes else None
    count = series.shape[axes.index(channel_axis)] if channel_axis else 1
    chosen = selection.get('channel_indices')
    chosen = list(range(count)) if chosen is None else chosen
    if not isinstance(chosen, (list, tuple)) or not chosen or len(set(chosen)) != len(chosen):
        raise ValueError('channel_indices must be a nonempty unique list')
    chosen = [_index(index, 'channel') for index in chosen]
    if any(index >= count for index in chosen):
        raise ValueError('Selected channel index is outside the image')
    return axes, indexers, channel_axis, chosen, width, height


def import_field(selections, metadata=None):
    if not isinstance(selections, list) or not selections:
        raise ValueError('At least one image selection is required')
    metadata = metadata or {}
    channels, calibrations = [], []
    geometry = None
    raw_bytes = 0
    quantitative = True
    override_calibration = _calibration(metadata.get('pixel_size_um'))
    for selection in selections:
        path = _path(selection['path'])
        with tifffile.TiffFile(path) as tiff:
            _validate_manifest(tiff, path)
            series_index = _index(selection.get('series_index', 0), 'series')
            if series_index >= len(tiff.series):
                raise ValueError('Selected series index is outside the image')
            series = tiff.series[series_index]
            axes, indexers, channel_axis, chosen, width, height = _selection(series, selection)
            if len(channels) + len(chosen) > 4:
                raise ValueError('A field supports at most four channels')
            if geometry is not None and geometry != (width, height):
                raise ValueError('Split-channel image dimensions must match')
            geometry = width, height
            raw_bytes += width * height * series.dtype.itemsize * len(chosen)
            if raw_bytes > MAX_RAW_BYTES or raw_bytes * 4 > MAX_WORK_BYTES:
                raise ValueError('Selected channels exceed raw decode or working memory limit')
            info = _series_info(tiff, series, series_index)
            quantitative &= info['quantitative']
            calibrations.append(info['pixel_size_um'])
            digest = file_sha256(path)
            for chosen_index in chosen:
                selected = {**indexers, **({channel_axis: chosen_index} if channel_axis else {})}
                plane = _plane(series, axes, selected)
                ordinal = len(channels)
                name = info['channel_names'][chosen_index] if chosen_index < len(info['channel_names']) else f'Channel {ordinal + 1}'
                color = COLORS[ordinal]
                if not info['quantitative']:
                    name = ['Red', 'Green', 'Blue', 'Alpha'][chosen_index] if chosen_index < 4 else name
                    color = ['#ff0000', '#00ff00', '#0000ff', '#000000'][chosen_index]
                if len(selections) > 1 and name == 'Channel 1':
                    name = path.name.split('.')[0]
                high = float(np.iinfo(plane.dtype).max) if plane.dtype.kind in 'ui' else float(plane.max())
                low = 0.0 if plane.dtype.kind in 'ui' else float(plane.min())
                channels.append({'id': uuid.uuid4().hex, 'name': name, 'color': color,
                                 'display_min': low, 'display_max': high if high > low else low + 1,
                                 'source': {'path': str(path), 'sha256': digest, 'series_index': series_index,
                                            'axes': axes, 'indexers': selected}})
    if override_calibration is None:
        reference = calibrations[0]
        if any((reference is None) != (value is None) or (value is not None and not np.allclose(value, reference, rtol=1e-6, atol=0)) for value in calibrations):
            raise ValueError('Split-channel calibration differs; supply confirmed pixel_size_um')
        calibration = reference
    else:
        calibration = override_calibration
    return {'id': uuid.uuid4().hex, 'name': metadata.get('name') or Path(selections[0]['path']).stem,
            **{key: str(metadata.get(key, '')) for key in ('sample_id', 'bio_id', 'group', 'batch_id')},
            'width': geometry[0], 'height': geometry[1], 'pixel_size_um': calibration,
            'quantitative': bool(quantitative), 'channels': channels, 'rois': [], 'mask': None, 'result': None,
            'recipe': {'mode': 'region', 'nuclear_channel_id': channels[0]['id'], 'target_channel_ids': [c['id'] for c in channels],
                       'thresholds': {}, 'threshold_source': '', 'thresholds_frozen': False,
                       'segmentation': {'sigma': 1, 'threshold_method': 'otsu', 'threshold': None,
                                        'min_area': 20, 'max_area': 100000, 'min_distance': 5,
                                        'exclude_border': True, 'rolling_ball_radius': 0}}}


def load_channels(field):
    """Load hash-verified selected original planes; display settings are ignored."""
    channels = field.get('channels', [])
    if not 1 <= len(channels) <= 4:
        raise ValueError('A field requires one to four channels')
    output, hashes = {}, {}
    raw_bytes = 0
    for channel in channels:
        source = channel['source']
        path = _path(source['path'])
        if str(path) not in hashes:
            hashes[str(path)] = file_sha256(path)
        if hashes[str(path)] != source['sha256']:
            raise ValueError('Source SHA256 hash changed; original pixels cannot be trusted')
        with tifffile.TiffFile(path) as tiff:
            _validate_manifest(tiff, path)
            index = _index(source.get('series_index', 0), 'series')
            if index >= len(tiff.series):
                raise ValueError('Selected series index is outside the image')
            series = tiff.series[index]
            if field.get('quantitative', True) and (int(series.pages[0].photometric) == 2 or 'S' in series.axes):
                raise ValueError('RGB/sample-axis sources are figure-only, not quantitative')
            axes = _axes(series, source['axes'])
            indexers = source.get('indexers', {})
            expected = {axis for axis in axes if axis not in 'XY'}
            if set(indexers) != expected:
                raise ValueError('Selected plane indexers do not match source axes')
            for axis, value in indexers.items():
                if _index(value, axis) >= series.shape[axes.index(axis)]:
                    raise ValueError('Selected plane index is outside source dimensions')
            array = _plane(series, axes, indexers)
            if array.shape != (field['height'], field['width']):
                raise ValueError('Source dimensions differ from field dimensions')
            raw_bytes += array.nbytes
            if raw_bytes > MAX_RAW_BYTES:
                raise ValueError('Raw decode exceeds 256 MiB limit')
            if channel['id'] in output:
                raise ValueError('Duplicate channel ID')
            output[channel['id']] = array
    return output


def preview_field(field, channel_id=None, max_size=1200):
    if not isinstance(max_size, int) or not 1 <= max_size <= 4096:
        raise ValueError('Preview max_size must be between 1 and 4096')
    loaded = load_channels(field)
    if channel_id is not None and channel_id not in loaded:
        raise ValueError('Unknown preview channel')
    rgb = np.zeros((field['height'], field['width'], 3), dtype=np.float32)
    for channel in field['channels']:
        if channel_id is None and channel.get('visible', True) is False:
            continue
        if channel_id is not None and channel['id'] != channel_id:
            continue
        low, high = channel.get('display_min', 0), channel.get('display_max', 1)
        if not math.isfinite(low) or not math.isfinite(high) or high <= low:
            raise ValueError('Display range must be finite and increasing')
        scaled = np.clip((loaded[channel['id']].astype(np.float32) - low) / (high - low), 0, 1)
        rgb += scaled[..., None] * np.asarray(ImageColor.getrgb(channel['color']), dtype=np.float32)
    result = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))
    result.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    result.save(buffer, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii')
