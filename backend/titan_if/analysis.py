"""Original-pixel IF measurement, reviewed nuclear masks, and biological pooling.

Positive nuclei use raw channel mean >= the frozen threshold. Positive area uses
raw pixels >= the same threshold. Neither uses display or segmentation pixels.
"""
from __future__ import annotations

from collections import defaultdict
import math
import json

import numpy as np
from scipy import ndimage as ndi
import tifffile

from .images import file_sha256, load_channels, MAX_WORK_BYTES


def _finite(value, name, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)) or not math.isfinite(value):
        raise ValueError(f'{name} must be finite')
    if minimum is not None and value < minimum:
        raise ValueError(f'{name} must be at least {minimum}')
    return float(value)


def roi_mask(roi, shape):
    """Rasterize original-coordinate geometry at (x + .5, y + .5).

    Boundaries are included for all shapes. Overlapping background ROIs are
    unioned by the consumer; separate signal regions must be disjoint.
    """
    if len(shape) != 2 or min(shape) < 1 or max(shape) > 4096:
        raise ValueError('ROI image shape must be two-dimensional and <=4096 per side')
    try:
        points = np.asarray(roi['points'], dtype=np.float64)
    except (TypeError, ValueError, KeyError) as exc:
        raise ValueError('ROI points must be finite pairs') from exc
    kind = roi.get('shape')
    minimum = 3 if kind == 'polygon' else 2
    if points.ndim != 2 or points.shape[1] != 2 or len(points) < minimum or not np.isfinite(points).all():
        raise ValueError('ROI points must be finite pairs with enough vertices')
    yy, xx = np.ogrid[:shape[0], :shape[1]]
    xx, yy = xx + .5, yy + .5
    if kind in ('rectangle', 'ellipse'):
        if len(points) != 2:
            raise ValueError('Rectangle/ellipse require exactly two points')
        lo, hi = points.min(axis=0), points.max(axis=0)
        if np.any(hi <= lo):
            raise ValueError('ROI area is empty')
        if kind == 'rectangle':
            return (xx >= lo[0]) & (xx <= hi[0]) & (yy >= lo[1]) & (yy <= hi[1])
        center, radius = (lo + hi) / 2, (hi - lo) / 2
        return ((xx - center[0]) / radius[0])**2 + ((yy - center[1]) / radius[1])**2 <= 1 + 1e-12
    if kind != 'polygon':
        raise ValueError('Unknown ROI shape')
    area = np.dot(points[:, 0], np.roll(points[:, 1], -1)) - np.dot(points[:, 1], np.roll(points[:, 0], -1))
    if abs(area) < 1e-12:
        raise ValueError('Polygon ROI area is empty or self-cancelling')
    inside = np.zeros(shape, dtype=bool)
    boundary = np.zeros(shape, dtype=bool)
    for (x0, y0), (x1, y1) in zip(points, np.roll(points, -1, axis=0)):
        dx, dy = x1 - x0, y1 - y0
        if dx == 0 and dy == 0:
            continue
        if dy:
            inside ^= ((y0 > yy) != (y1 > yy)) & (xx < (dx * (yy - y0) / dy + x0))
        cross = (xx - x0) * dy - (yy - y0) * dx
        boundary |= (np.abs(cross) <= 1e-10 * max(1, abs(dx), abs(dy))) & (xx >= min(x0, x1)) & (xx <= max(x0, x1)) & (yy >= min(y0, y1)) & (yy <= max(y0, y1))
    return inside | boundary


def _regions(field):
    shape = field['height'], field['width']
    background = np.zeros(shape, dtype=bool)
    signals = []
    for roi in field.get('rois', []):
        if roi.get('role') == 'background':
            mask = roi_mask(roi, shape)
            if not mask.any():
                raise ValueError('ROI contains no pixel centers')
            background |= mask
        elif roi.get('role') == 'signal':
            signals.append(roi)
        else:
            raise ValueError('ROI role must be signal or background')
    regions = np.zeros(shape, dtype=np.uint32)
    ids = {}
    for ordinal, roi in enumerate(signals, 1):
        mask = roi_mask(roi, shape)
        if not mask.any():
            raise ValueError('ROI contains no pixel centers')
        if np.any(regions[mask]) or np.any(background & mask):
            raise ValueError('Signal regions must not overlap signal or background ROIs')
        regions[mask] = ordinal
        ids[ordinal] = roi.get('id', str(ordinal))
    warnings = []
    if not signals:
        regions[~background] = 1
        ids[1] = 'whole_field'
        warnings.append('No signal ROI: measuring the whole field excluding background ROIs.')
        if not np.any(regions):
            raise ValueError('No signal pixels remain outside background ROIs')
    if not background.any():
        warnings.append('No background ROI: background_mean and corrected_sum are unavailable.')
    return regions, ids, background, warnings


def _labels(labels, shape=None):
    value = np.asarray(labels)
    if value.ndim != 2 or (shape is not None and value.shape != shape) or max(value.shape) > 4096:
        raise ValueError('Label image dimensions must match the original image')
    if value.dtype.kind not in 'ui' or (value.size and (value.min() < 0 or value.max() > np.iinfo(np.uint32).max)):
        raise ValueError('Labels must be nonnegative uint32-compatible integer IDs')
    return value.astype(np.uint32, copy=False)


def segment_nuclei(field):
    """Segment DAPI nuclei using preprocessing + distance watershed, in pixels."""
    from skimage.feature import peak_local_max
    from skimage.filters import threshold_otsu
    from skimage.restoration import rolling_ball
    from skimage.segmentation import watershed

    if not field.get('quantitative', True):
        raise ValueError('RGB figure-only data cannot be segmented quantitatively')
    channels = load_channels(field)
    recipe = field.get('recipe', {})
    nuclear_id = recipe.get('nuclear_channel_id')
    if nuclear_id not in channels:
        raise ValueError('Nuclear channel is unavailable')
    source = channels[nuclear_id]
    if sum(channel.nbytes for channel in channels.values()) + source.size * 48 > MAX_WORK_BYTES:
        raise ValueError('Estimated segmentation working memory exceeds 1 GiB')
    config = recipe.get('segmentation', {})
    sigma = _finite(config.get('sigma', 1), 'sigma', 0)
    radius = _finite(config.get('rolling_ball_radius', 0), 'rolling_ball_radius', 0)
    min_area = _finite(config.get('min_area', 20), 'min_area', 1)
    max_area = _finite(config.get('max_area', 100000), 'max_area', min_area)
    distance = _finite(config.get('min_distance', 5), 'min_distance', 1)
    if sigma > 100 or radius > 256 or distance > 4096:
        raise ValueError('Segmentation parameter exceeds resource limit (sigma100/radius256/distance4096)')
    if not distance.is_integer():
        raise ValueError('min_distance must be an integer number of pixels')
    regions, _, background, _ = _regions(field)
    allowed = (regions > 0) & ~background
    work = source.astype(np.float32)
    if radius:
        work = work - rolling_ball(work, radius=radius)
    if sigma:
        work = ndi.gaussian_filter(work, sigma=sigma)
    method = config.get('threshold_method', 'otsu')
    if method == 'manual':
        cutoff = _finite(config.get('threshold'), 'Manual segmentation threshold')
    elif method == 'otsu':
        values = work[allowed]
        if not values.size or values.max() == values.min():
            return np.zeros(source.shape, dtype=np.uint32)
        cutoff = threshold_otsu(values)
    else:
        raise ValueError('Segmentation threshold_method must be manual or otsu')
    foreground = ndi.binary_fill_holes((work > cutoff) & allowed) & allowed
    if not foreground.any():
        return np.zeros(source.shape, dtype=np.uint32)
    distances = ndi.distance_transform_edt(foreground)
    coordinates = peak_local_max(distances, min_distance=int(distance), labels=foreground.astype(np.uint8), exclude_border=False)
    markers = np.zeros(source.shape, dtype=np.int32)
    for ordinal, coordinate in enumerate(coordinates, 1):
        markers[tuple(coordinate)] = ordinal
    # Every disconnected component needs a marker even if a nearby component's
    # maximum suppressed its only candidate.
    components, count = ndi.label(foreground)
    marked = set(np.unique(components[markers > 0]))
    next_marker = len(coordinates) + 1
    for component in range(1, count + 1):
        if component not in marked:
            region = components == component
            location = np.unravel_index(np.argmax(np.where(region, distances, -1)), source.shape)
            markers[location] = next_marker
            next_marker += 1
    labels = watershed(-distances, markers, mask=foreground)
    sizes = np.bincount(labels.ravel())
    keep = (sizes >= min_area) & (sizes <= max_area)
    keep[0] = False
    if config.get('exclude_border', True):
        edge_ids = np.unique(np.concatenate((labels[0], labels[-1], labels[:, 0], labels[:, -1])))
        keep[edge_ids] = False
    remap = np.zeros(len(sizes), dtype=np.uint32)
    remap[keep] = np.arange(1, np.count_nonzero(keep) + 1, dtype=np.uint32)
    return remap[labels]


def edit_labels(labels, action):
    """Copy a uint32 mask and perform a deterministic, explicit object edit."""
    output = _labels(labels).copy()
    kind = action.get('kind')
    if kind == 'add':
        mask = roi_mask(action.get('roi', {}), output.shape)
        if not mask.any():
            raise ValueError('Added label ROI contains no pixel centers')
        if np.any(output[mask]):
            raise ValueError('Added label ROI overlaps an existing label; delete or split it first')
        if output.max() == np.iinfo(np.uint32).max:
            raise ValueError('No uint32 label IDs remain')
        output[mask] = int(output.max()) + 1
        return output
    ids = action.get('ids', [])
    if not isinstance(ids, list) or not ids or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in ids) or len(set(ids)) != len(ids):
        raise ValueError('Edit ids must be a nonempty list of unique positive label IDs')
    available = set(np.unique(output))
    if any(value not in available for value in ids):
        raise ValueError('Selected label ID does not exist')
    if kind == 'delete':
        output[np.isin(output, ids)] = 0
    elif kind == 'merge':
        if len(ids) < 2:
            raise ValueError('Merge requires at least two label IDs')
        output[np.isin(output, ids)] = min(ids)
    elif kind == 'split':
        if len(ids) != 1:
            raise ValueError('Split requires exactly one label ID')
        points = np.asarray(action.get('points'), dtype=float)
        if points.shape != (2, 2) or not np.isfinite(points).all() or np.allclose(points[0], points[1]):
            raise ValueError('Split requires two distinct finite line points')
        (x0, y0), (x1, y1) = points
        yy, xx = np.ogrid[:output.shape[0], :output.shape[1]]
        side = (xx + .5 - x0) * (y1 - y0) - (yy + .5 - y0) * (x1 - x0)
        selected = output == ids[0]
        partition = selected & (side < 0)
        if not partition.any() or not np.any(selected & ~partition):
            raise ValueError('Split line must partition the selected label into two nonempty parts')
        if output.max() == np.iinfo(np.uint32).max:
            raise ValueError('No uint32 label IDs remain')
        output[partition] = int(output.max()) + 1
    else:
        raise ValueError('Unknown label edit kind')
    return output


def _thresholds(field, channel_ids):
    recipe = field.get('recipe', {})
    thresholds = recipe.get('thresholds', {})
    if not isinstance(thresholds, dict) or any(key not in {c['id'] for c in field['channels']} for key in thresholds):
        raise ValueError('Threshold refers to an unknown channel')
    if thresholds and (not recipe.get('thresholds_frozen') or not str(recipe.get('threshold_source', '')).strip()):
        raise ValueError('Positive thresholds must be frozen with explicit source provenance')
    validated = {key: _finite(value, 'Positive threshold') for key, value in thresholds.items()}
    return {key: value for key, value in validated.items() if key in channel_ids}


def _stored_labels(field):
    from .models import segmentation_signature
    mask = field.get('mask')
    if not mask or not mask.get('confirmed'):
        raise ValueError('Nuclear measurement requires a confirmed label mask')
    if mask.get('segmentation_signature') != segmentation_signature(field):
        raise ValueError('Nuclear mask is stale after segmentation inputs changed')
    if file_sha256(mask['path']) != mask['sha256']:
        raise ValueError('Label mask SHA256 hash changed')
    return tifffile.imread(mask['path'])


def measure_field(field, labels=None):
    from .models import analysis_signature, segmentation_signature
    if not field.get('quantitative', True):
        raise ValueError('RGB figure-only data is not quantitative')
    channels = load_channels(field)
    recipe = field.get('recipe', {})
    selected_ids = recipe.get('target_channel_ids', list(channels))
    if not selected_ids or len(selected_ids) != len(set(selected_ids)) or any(key not in channels for key in selected_ids):
        raise ValueError('Target channel selection is empty, duplicated, or unavailable')
    thresholds = _thresholds(field, selected_ids)
    regions, object_ids, background, warnings = _regions(field)
    mode = recipe.get('mode', 'region')
    if mode == 'nuclei':
        mask_descriptor = field.get('mask')
        if mask_descriptor and (not mask_descriptor.get('confirmed') or mask_descriptor.get('segmentation_signature') != segmentation_signature(field)):
            raise ValueError('Nuclear measurement requires a confirmed, non-stale label mask')
        if mask_descriptor:
            stored = _stored_labels(field)
            if labels is not None and not np.array_equal(labels, stored):
                raise ValueError('Explicit labels do not match the confirmed mask artifact')
            labels = stored
        elif labels is None:
            raise ValueError('Nuclear measurement requires a confirmed label mask')
        regions = _labels(labels, regions.shape)
        if np.any((regions > 0) & background):
            raise ValueError('Nuclear labels overlap a background ROI')
        signal, _, _, _ = _regions(field)
        regions = np.where(signal > 0, regions, 0).astype(np.uint32)
        object_ids = {int(value): int(value) for value in np.unique(regions) if value}
    elif mode != 'region':
        raise ValueError('Unknown measurement mode')
    unique, compact = np.unique(regions, return_inverse=True)
    compact = compact.reshape(regions.shape)
    areas = np.bincount(compact.ravel(), minlength=len(unique))
    foreground_indices = [index for index, value in enumerate(unique) if value]
    calibration = field.get('pixel_size_um')
    pixel_area = math.prod(calibration) if calibration is not None else None
    if pixel_area is not None and (not math.isfinite(pixel_area) or pixel_area <= 0):
        raise ValueError('Physical pixel calibration must be finite and positive')
    objects, summary = [], []
    for channel_id in selected_ids:
        raw = channels[channel_id]
        bg_count = int(np.count_nonzero(background))
        bg_sum = None
        if bg_count:
            dtype = np.uint64 if raw.dtype.kind == 'u' else np.int64 if raw.dtype.kind == 'i' else np.float64
            bg_sum = raw[background].sum(dtype=dtype).item()
        bg_mean = bg_sum / bg_count if bg_count else None

        def corrected(raw_sum, area):
            if not bg_count:
                return None
            if raw.dtype.kind in 'ui':
                # Cancel large integer terms before converting to float. This
                # retains a one-count signal above a near-uint32-max background.
                return (raw_sum * bg_count - area * bg_sum) / bg_count
            return raw_sum - area * bg_mean

        cutoff = thresholds.get(channel_id)
        # Integer reductions stay exact (uint32*4096² fits in uint64).
        if raw.dtype.kind in 'ui':
            totals = np.zeros(len(unique), dtype=np.uint64 if raw.dtype.kind == 'u' else np.int64)
            np.add.at(totals, compact.ravel(), raw.ravel())
        else:
            totals = np.bincount(compact.ravel(), weights=raw.ravel(), minlength=len(unique))
        sums = totals[foreground_indices]
        positive_counts = np.bincount(compact.ravel(), weights=(raw >= cutoff).ravel(), minlength=len(unique)) if cutoff is not None else None
        rows = []
        for position, index in enumerate(foreground_indices):
            area = int(areas[index])
            raw_sum = int(sums[position]) if raw.dtype.kind in 'ui' else float(sums[position])
            mean = raw_sum / area
            row = {'object_id': object_ids[int(unique[index])], 'channel_id': channel_id, 'measurement_mode': mode,
                   'area_px': area, 'area_um2': area * pixel_area if pixel_area is not None else None,
                   'raw_sum': raw_sum, 'mean': mean, 'background_mean': bg_mean,
                   'corrected_sum': corrected(raw_sum, area),
                   'positive_pixels': int(positive_counts[index]) if cutoff is not None else None,
                   'positive': bool(mean >= cutoff) if cutoff is not None and mode == 'nuclei' else None}
            rows.append(row)
            objects.append(row)
        area = sum(row['area_px'] for row in rows)
        raw_sum = sum(row['raw_sum'] for row in rows)
        positive_pixels = sum(row['positive_pixels'] for row in rows) if cutoff is not None else None
        positive_count = sum(row['positive'] for row in rows) if cutoff is not None and mode == 'nuclei' else None
        summary.append({'field_id': field['id'], 'channel_id': channel_id, 'measurement_mode': mode, 'object_count': len(rows),
                        'area_px': area, 'area_um2': area * pixel_area if pixel_area is not None else None,
                        'raw_sum': raw_sum, 'mean': raw_sum / area if area else None,
                        'background_mean': bg_mean, 'corrected_sum': corrected(raw_sum, area),
                        'positive_pixels': positive_pixels, 'positive_area_fraction': positive_pixels / area if cutoff is not None and area else None,
                        'positive_count': positive_count, 'positive_fraction': positive_count / len(rows) if positive_count is not None and rows else None})
    if not foreground_indices:
        warnings.append('No nuclei remain in the confirmed measurement mask.')
    return {'field_id': field['id'], 'input_signature': analysis_signature(field), 'objects': objects, 'summary': summary, 'warnings': warnings}


def _pool(rows):
    """Pool sums and numerators; unavailable values propagate, never become zero."""
    output = {key: sum(row[key] for row in rows) if all(row.get(key) is not None for row in rows) else None
              for key in ('object_count', 'area_px', 'area_um2', 'raw_sum', 'corrected_sum', 'positive_pixels', 'positive_count')}
    area, count = output['area_px'], output['object_count']
    output['mean'] = output['raw_sum'] / area if area else None
    output['background_mean'] = sum(row['background_mean'] * row['area_px'] for row in rows) / area if area and all(row.get('background_mean') is not None for row in rows) else None
    output['positive_area_fraction'] = output['positive_pixels'] / area if area and output['positive_pixels'] is not None else None
    output['positive_fraction'] = output['positive_count'] / count if count and output['positive_count'] is not None else None
    output['positive_area_numerator'] = output['positive_pixels']
    output['positive_area_denominator'] = area
    output['positive_nucleus_numerator'] = output['positive_count']
    output['measurement_mode'] = rows[0].get('measurement_mode')
    output['positive_nucleus_denominator'] = count if output['measurement_mode'] == 'nuclei' else None
    return output


def aggregate_results(project, channel_name=None):
    """Export current field rows and pool fields at biological-sample level."""
    from .models import analysis_signature
    objects, fields, samples = [], [], []
    groups = defaultdict(list)
    conventions = {}
    canonical = {}
    for field in project.get('fields', []):
        result = field.get('result')
        if result is None:
            continue  # Unmeasured/failed fields remain absent; never fabricate zeros.
        artifact = result.get('artifact')
        if artifact:
            if file_sha256(artifact['path']) != artifact['sha256']:
                raise ValueError('Result artifact SHA256 hash changed')
            with open(artifact['path'], encoding='utf-8') as handle:
                result = json.load(handle)
            if not isinstance(result, dict):
                raise ValueError('Result artifact must contain a measurement result')
        if result.get('field_id') != field['id'] or result.get('input_signature') != analysis_signature(field):
            raise ValueError(f"Field {field.get('name', field['id'])} has stale results")
        channels = {channel['id']: channel for channel in field['channels']}
        names = [channel['name'] for channel in field['channels']]
        if len(set(names)) != len(names):
            raise ValueError('Duplicate channel names cannot be pooled as biological markers')
        metadata = {key: field.get(key, '') for key in ('sample_id', 'bio_id', 'group', 'batch_id')}
        for row in result.get('objects', []):
            if channel_name is not None and channels[row['channel_id']]['name'] != channel_name:continue
            objects.append({**row, **metadata, 'field_id': field['id'], 'field_name': field.get('name', ''),
                            'channel_name': channels[row['channel_id']]['name']})
        for row in result.get('summary', []):
            marker = channels[row['channel_id']]['name']
            if channel_name is not None and marker != channel_name:continue
            canonical.setdefault(marker, row['channel_id'])
            enriched = {**row, **metadata, 'field_name': field.get('name', ''), 'channel_name': marker}
            fields.append(enriched)
            if not str(metadata['bio_id']).strip():
                continue
            key = metadata['bio_id'], metadata['group'], metadata['batch_id'], marker
            recipe = field.get('recipe', {})
            convention = (recipe.get('mode'), recipe.get('thresholds', {}).get(row['channel_id']),
                          recipe.get('threshold_source', '') if row.get('positive_pixels') is not None else '', bool(recipe.get('thresholds_frozen')))
            comparison_key = metadata['batch_id'], marker
            if comparison_key in conventions and conventions[comparison_key] != convention:
                raise ValueError('Incompatible threshold, provenance, or measurement mode within a comparable marker/batch')
            conventions[comparison_key] = convention
            groups[key].append(enriched)
    for (bio_id, group, batch_id, marker), rows in groups.items():
        samples.append({'bio_id': bio_id, 'group': group, 'batch_id': batch_id,
                        'channel_id': canonical[marker], 'channel_name': marker,
                        'sample_ids': sorted({row['sample_id'] for row in rows if row['sample_id']}),
                        'field_count': len(rows), **_pool(rows)})
    return {'objects': objects, 'fields': fields, 'samples': samples}
