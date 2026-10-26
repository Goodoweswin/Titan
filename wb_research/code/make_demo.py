"""Generate explicitly SYNTHETIC WB data, a review overlay, and example config.

Never use this as real experimental evidence. One ROI deliberately contains a
clipped pixel. Output is a new directory; nothing is overwritten.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from wb_reference import propose_rectangles


def make_demo(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(42)
    yy, xx = np.mgrid[:160, :520]
    im = 1000 + 2 * xx + yy + rng.normal(0, 3, xx.shape)
    records = []
    true_ratios = [0.8, 1.0, 1.2, 1.6, 2.0, 2.4]
    for sample, ratio in enumerate(true_ratios):
        group = "control" if sample < 3 else "treated"
        for tech in range(2):
            lane = sample * 2 + tech
            x0 = 20 + 40 * lane
            amplitude = 100 * ratio + (-2 if tech == 0 else 2)
            im[40:55, x0:x0 + 16] += amplitude
            im[100:115, x0:x0 + 16] += 100
            for role, y in [("target", 40), ("reference", 100)]:
                records.append(dict(
                    id=f"{role}_{lane}", role=role, image_id="synthetic",
                    sample_id=f"S{sample + 1}", bio_id=f"B{sample + 1}",
                    lane_id=f"L{lane + 1}", blot_id="SYNTHETIC_M1", group=group,
                    analyte="TARGET" if role == "target" else "GAPDH_DEMO",
                    ref_id=f"reference_{lane}" if role == "target" else None,
                    roi=[x0, y, x0 + 16, y + 15],
                    backgrounds=[[x0, y - 10, x0 + 16, y - 5],
                                 [x0, y + 20, x0 + 16, y + 25]],
                    reviewed=True, linear_range_validated=False))
    im[44, 463] = 4095  # last technical target: intentional clipping
    raw = np.round(im).astype(np.uint16)
    Image.fromarray(raw).save(output / "SYNTHETIC_ONLY.tif")
    config = dict(
        purpose="SYNTHETIC demonstration only; reviewed flags reflect known generated boxes",
        images={"synthetic": dict(path="SYNTHETIC_ONLY.tif", polarity="bright",
                                  ceiling=4095, exposure_seconds=None)},
        control_group="control", records=records)
    (output / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    proposals = propose_rectangles(raw, [0, 35, 520, 60], ceiling=4095)
    (output / "unreviewed_proposals.json").write_text(
        json.dumps(dict(reviewed=False, warning="NOT sample-matched; not used for measurement",
                        rectangles=proposals), indent=2), encoding="utf-8")
    # Display scaling changes only this preview, never the quantification TIFF.
    preview = np.uint8(np.clip((raw.astype(float) - 900) / 1600, 0, 1) * 255)
    canvas = Image.new("RGB", (520, 195), "white")
    canvas.paste(Image.fromarray(preview).convert("RGB"), (0, 35))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 7), "SYNTHETIC DEMO ONLY - NOT EXPERIMENTAL DATA", fill="black")
    draw.text((8, 20), "green: target | blue: reference | red: clipped ROI", fill="black")
    for r in records:
        x0, y0, x1, y1 = r["roi"]
        color = "lime" if r["role"] == "target" else "cyan"
        if r["id"] == "target_11":
            color = "red"
        draw.rectangle([x0, y0 + 35, x1 - 1, y1 + 34], outline=color, width=1)
    canvas.save(output / "SYNTHETIC_review_overlay.png")
    return dict(directory=str(output.resolve()), measurements=len(records),
                expected_blocked_targets=1, biological_units=6,
                proposed_unreviewed_boxes=len(proposals))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", help="New directory")
    print(json.dumps(make_demo(parser.parse_args().output)))
