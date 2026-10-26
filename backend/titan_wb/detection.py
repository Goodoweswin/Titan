import numpy as np
from .quantify import _oriented, _slice
from .images import read_pixels
from .models import validate_project

def propose_rectangles(image, window, *, polarity="bright", ceiling=None,
                       smooth=3, threshold_fraction=0.25, min_width=3):
    """Heuristic proposals ONLY within an operator-selected protein/MW window.

    Does not identify proteins, guarantee lane count, choose exposures or decide
    which band is specific. Missing/merged/weak bands require review. Background
    ROIs and sample identities must be supplied separately.
    """
    s = _oriented(image, polarity, ceiling)
    sub = s[_slice(window, s.shape)]
    if smooth < 1 or int(smooth) != smooth or min_width < 1:
        raise ValueError("Invalid smoothing or minimum width")
    if not 0 < threshold_fraction < 1:
        raise ValueError("threshold_fraction must be between zero and one")
    smooth = int(smooth)
    x0, y0, x1, y1 = map(int, window)
    height = y1 - y0
    top, bottom = s[max(0, y0 - height):y0, x0:x1], s[y1:y1 + height, x0:x1]
    # Detection-only local baseline: per-column flanks cancel a horizontal
    # illumination gradient. These automatic flanks may contain other bands;
    # quantitative measurement still requires separately reviewed BG boxes.
    if top.size and bottom.size:
        yt = (max(0, y0 - height) + y0 - 1) / 2
        yb = (y1 + min(s.shape[0], y1 + height) - 1) / 2
        alpha = ((y0 + y1 - 1) / 2 - yt) / (yb - yt)
        baseline = (1 - alpha) * top.mean(axis=0) + alpha * bottom.mean(axis=0)
        profile = sub.mean(axis=0) - baseline
    elif top.size or bottom.size:
        flank = top if top.size else bottom
        profile = sub.mean(axis=0) - flank.mean(axis=0)
    else:
        profile = sub.mean(axis=0)
    profile = np.convolve(np.pad(profile, (smooth // 2, (smooth - 1) // 2),
                                  mode="edge"), np.ones(smooth) / smooth,
                          mode="valid")
    profile = profile - np.median(profile)
    if profile.max() <= 0:
        return []
    mask = profile > threshold_fraction * profile.max()
    transitions = np.diff(np.r_[False, mask, False].astype(int))
    starts, ends = np.where(transitions == 1)[0], np.where(transitions == -1)[0]
    return [[int(x0 + lo), y0, int(x0 + hi), y1]
            for lo, hi in zip(starts, ends) if hi - lo >= min_width]



def detect(project,image_id,window,settings):
    validate_project(project)
    asset=next(a for a in project['images'] if a['id']==image_id)
    return propose_rectangles(read_pixels(asset),window,polarity=asset['polarity'],ceiling=asset.get('ceiling'),
        smooth=int(settings.get('smooth',3)),threshold_fraction=float(settings.get('threshold_fraction',.25)),
        min_width=int(settings.get('min_width',3)))
