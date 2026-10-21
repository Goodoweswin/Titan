"""Educational WB quantification, not a validated assay or a complete app.

Coordinates are zero-based [x0, y0, x1, y1], right/bottom exclusive.
NumPy + Pillow only. No normalization, gamma, threshold or clipping of raw
quantification pixels is performed. Candidate detection uses a separate view.
"""
import argparse
import csv
import hashlib
import json
import platform
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, __version__ as pillow_version

VERSION = "0.1.0-research"


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


def normalize_records(records):
    """Explicit target/reference matching, retaining excluded and review rows.

    Ratios without documented linear-range validation are marked exploratory.
    No small epsilon, pseudocount, or missing-reference substitution is used.
    """
    by_id = {r["id"]: r for r in records}
    if len(by_id) != len(records):
        raise ValueError("Duplicate record IDs")
    out = []
    blocks = {"signal_clipped", "background_clipped", "nonpositive_signal"}
    for t in records:
        if t["role"] != "target":
            continue
        ref = by_id.get(t.get("ref_id"))
        if ref is None or ref["role"] != "reference":
            raise ValueError(f"Missing explicit reference for {t['id']}")
        for key in ["sample_id", "bio_id", "lane_id", "blot_id", "group"]:
            if not t.get(key) or t[key] != ref.get(key):
                raise ValueError(f"Reference mismatch in {key} for {t['id']}")
        flags = list(t.get("flags", []))
        flags.extend("reference:" + x for x in ref.get("flags", []))
        good = not (blocks & set(t.get("flags", []) + ref.get("flags", [])))
        if not (t.get("reviewed") is True and ref.get("reviewed") is True):
            flags.append("review_required")
            good = False
        numerator, denominator = t["corrected_sum"], ref["corrected_sum"]
        if not (np.isfinite(numerator) and np.isfinite(denominator)
                and numerator > 0 and denominator > 0):
            good = False
            flags.append("nonpositive_or_invalid_ratio_input")
        if not (t.get("linear_range_validated") is True
                and ref.get("linear_range_validated") is True):
            flags.append("linearity_not_validated")
        value = float(numerator / denominator) if good else None
        status = "blocked" if not good else ("exploratory" if flags else "measured")
        out.append({**t, "flags": flags, "normalized": value, "status": status})
    return out


def biological_summary(rows, control_group):
    """Average technical ratios per biological unit within each blot/analyte.

    Control fold changes are descriptive within-blot results. This function
    deliberately does not pool blots, choose a statistical test or calculate p.
    """
    grouped = defaultdict(list)
    for r in rows:
        if r["normalized"] is not None:
            grouped[tuple(r[k] for k in ["blot_id", "analyte", "group", "bio_id"])].append(r)
    out = []
    for (blot, analyte, group, bio), units in grouped.items():
        out.append(dict(blot_id=blot, analyte=analyte, group=group, bio_id=bio,
                        normalized_mean=float(np.mean([u["normalized"] for u in units])),
                        n_technical=len(units),
                        flags=sorted({f for u in units for f in u.get("flags", [])})))
    controls = defaultdict(list)
    for r in out:
        if r["group"] == control_group:
            controls[(r["blot_id"], r["analyte"])].append(r["normalized_mean"])
    for r in out:
        base = controls[(r["blot_id"], r["analyte"])]
        r["control_mean"] = float(np.mean(base)) if base else None
        r["fold_vs_control"] = (r["normalized_mean"] / r["control_mean"]
                                 if base else None)
        if not base:
            r["flags"].append("missing_within_blot_control")
    return out


def load_gray(path):
    """Preserve grayscale numeric pixels; reject ambiguous formats/stacks."""
    with Image.open(path) as im:
        if getattr(im, "n_frames", 1) != 1:
            raise ValueError("Extract a named plane/channel from a stack first")
        if im.mode not in {"L", "I", "F", "I;16", "I;16L", "I;16B"}:
            raise ValueError(f"Explicit grayscale channel required: {im.mode}")
        # TIFF MINISWHITE may be decoded with different polarity by readers.
        tags = getattr(im, "tag_v2", {})
        if tags.get(262, 1) != 1:
            raise ValueError("TIFF photometric must be MINISBLACK; verify export")
        a = np.asarray(im).copy()
    _oriented(a, "bright", None)
    return a


def _write_csv(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v) if isinstance(v, (list, dict)) else v
                             for k, v in row.items()})


def run(config_path, output):
    config_path, output = Path(config_path).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("Use a new output directory to preserve previous results")
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    images, metadata = {}, {}
    for image_id, spec in cfg["images"].items():
        path = (config_path.parent / spec["path"]).resolve()
        images[image_id] = load_gray(path)
        metadata[image_id] = dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                  dtype=str(images[image_id].dtype),
                                  shape=list(images[image_id].shape))
    measurements = []
    for r in cfg["records"]:
        spec = cfg["images"][r["image_id"]]
        m = measure(images[r["image_id"]], r["roi"], r["backgrounds"],
                    polarity=spec["polarity"], ceiling=spec.get("ceiling"))
        measurements.append({**r, **m})
    normalized = normalize_records(measurements)
    summary = biological_summary(normalized, cfg["control_group"])
    output.mkdir(parents=True)
    _write_csv(output / "measurements.csv", measurements)
    _write_csv(output / "normalized.csv", normalized)
    _write_csv(output / "biological_summary.csv", summary)
    audit = dict(software=VERSION, python=platform.python_version(),
                 numpy=np.__version__, pillow=pillow_version,
                 config_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),
                 config=cfg, images=metadata,
                 outputs={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in output.glob("*.csv")},
                 limitations=["No assay linearity inferred from pixels",
                              "No cross-blot calibration or inferential statistics",
                              "Human-provided review/linearity fields are assertions, not verification"])
    (output / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    return dict(measurements=len(measurements), targets=len(normalized),
                blocked=sum(r["normalized"] is None for r in normalized))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", help="JSON with images and explicit ROI/sample/reference map")
    parser.add_argument("output", help="New output directory")
    args = parser.parse_args()
    print(json.dumps(run(args.config, args.output), ensure_ascii=False))
