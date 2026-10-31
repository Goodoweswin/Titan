"""Read-only lane profiles using original pixels and the quantification contract."""
import numpy as np
from .images import read_pixels
from .quantify import _oriented, _slice, measure


def profile(project, roi_id):
    roi = next((r for r in project['rois'] if r['id'] == roi_id), None)
    if roi is None:
        raise ValueError('条带不存在，请重新选择')
    asset = next(a for a in project['images'] if a['id'] == roi['image_id'])
    pixels = read_pixels(asset)
    signal = _oriented(pixels, asset['polarity'], asset.get('ceiling'))
    _slice(roi['rect'], signal.shape)
    x0, _, x1, _ = roi['rect']
    rows = signal[:, x0:x1].mean(axis=1)
    # Bucket extrema preserve narrow peaks in the display; measurement never downsamples.
    step = max(1, int(np.ceil(len(rows) / 1200)))
    samples = [dict(y=(i + min(i + step, len(rows)) - 1) / 2,
                    mean=float(rows[i:i+step].mean()),
                    min=float(rows[i:i+step].min()), max=float(rows[i:i+step].max()))
               for i in range(0, len(rows), step)]
    measurement, warning = None, None
    try:
        measurement = measure(pixels, roi['rect'], roi['backgrounds'],
                              polarity=asset['polarity'], ceiling=asset.get('ceiling'))
    except ValueError as exc:
        warning = '背景尚不可用于扣除，请检查背景框：' + str(exc)
    return dict(project_id=project['id'], input_revision=project['revision'], roi_id=roi_id,
                rect=roi['rect'], height=int(signal.shape[0]), samples=samples,
                background_mean=measurement['background_mean'] if measurement else None,
                measurement=measurement, warning=warning)
