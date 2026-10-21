import numpy as np

def _oriented(image, polarity, ceiling):
    a = np.asarray(image)
    if a.ndim != 2 or a.size == 0 or a.dtype.kind not in "uif":
        raise ValueError("Use a nonempty, single-channel, numeric 2D image")
    a = a.astype(np.float64)
    if not np.isfinite(a).all():
        raise ValueError("Image has NaN/Inf")
    if polarity not in {"bright", "dark"}:
        raise ValueError("polarity must be bright or dark")
    if ceiling is not None:
        if not np.isfinite(ceiling) or ceiling <= 0:
            raise ValueError("ceiling must be a positive finite acquisition limit")
        if a.min() < 0 or a.max() > ceiling:
            raise ValueError("Pixels outside declared [0, ceiling] range")
    if polarity == "dark" and ceiling is None:
        raise ValueError("Dark bands require an explicit ceiling")
    return a if polarity == "bright" else ceiling - a


def _slice(roi, shape):
    if len(roi) != 4 or any(isinstance(v, bool) or int(v) != v for v in roi):
        raise ValueError("ROI must contain four integer coordinates")
    x0, y0, x1, y1 = map(int, roi)
    h, w = shape
    if not (0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h):
        raise ValueError(f"ROI {roi} is empty or outside image {shape}")
    return np.s_[y0:y1, x0:x1]


def measure(image, roi, backgrounds, *, polarity="bright", ceiling=None):
    """Sum signal minus ROI area times mean of the union of local BG pixels.

    No truncation at zero. The background must be manually verified to contain
    neither neighboring bands nor artifacts. Clipping checks do not establish
    assay linearity, and cannot reconstruct clipping in a processed export.
    """
    raw = np.asarray(image)
    signal = _oriented(raw, polarity, ceiling)
    selection = _slice(roi, signal.shape)
    if not backgrounds:
        raise ValueError("Provide at least one explicit background ROI")
    bg_mask = np.zeros(signal.shape, dtype=bool)
    for box in backgrounds:
        bg_mask[_slice(box, signal.shape)] = True
    if bg_mask[selection].any():
        raise ValueError("Background overlaps the signal ROI")
    band = signal[selection]
    bg = signal[bg_mask]
    corrected = float(band.sum() - band.size * bg.mean())
    flags = []
    fraction = None
    # For dark exports the signal endpoint is zero, but the transform ceiling
    # must still be known. A dtype maximum is deliberately never guessed.
    if ceiling is None:
        flags.append("clipping_unknown")
    else:
        clipped = raw >= ceiling if polarity == "bright" else raw <= 0
        fraction = float(clipped[selection].mean())
        if fraction > 0:
            flags.append("signal_clipped")
        if clipped[bg_mask].any():
            flags.append("background_clipped")
    if corrected <= 0:
        flags.append("nonpositive_signal")
    bg_sd = float(bg.std(ddof=1)) if bg.size > 1 else None
    contrast = (float((band.mean() - bg.mean()) / bg_sd)
                if bg_sd is not None and bg_sd > 0 else None)
    return dict(area_px=int(band.size), raw_sum=float(raw[selection].sum()),
                oriented_sum=float(band.sum()), background_mean=float(bg.mean()),
                background_sd=bg_sd, background_n=int(bg.size),
                corrected_sum=corrected, contrast_over_bg_sd=contrast,
                clipped_fraction=fraction, flags=flags)


