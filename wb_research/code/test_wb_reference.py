"""Hand-calculated scientific fixtures; no network or model required."""
import unittest
import json
import tempfile
from pathlib import Path
from PIL import Image
import numpy as np
from wb_reference import (measure, propose_rectangles, normalize_records,
                          biological_summary, run, load_gray)


def record(rid, role, value, *, group="control", bio="B1", sample="S1",
           lane="L1", blot="M1", ref_id=None, reviewed=True, flags=None):
    return dict(id=rid, role=role, analyte="AKT" if role == "target" else "TP",
                corrected_sum=value, flags=flags or [], reviewed=reviewed,
                linear_range_validated=False, group=group, bio_id=bio,
                sample_id=sample, lane_id=lane, blot_id=blot, ref_id=ref_id)


class MeasurementTests(unittest.TestCase):
    def setUp(self):
        self.im = np.full((8, 8), 10, dtype=np.uint16)
        self.im[2:4, 2:4] = 30
        self.roi = [2, 2, 4, 4]
        self.bg = [[0, 0, 2, 2]]

    def test_integrates_above_background_instead_of_mean_or_area(self):
        m = measure(self.im, self.roi, self.bg, ceiling=4095)
        self.assertEqual(m["corrected_sum"], 80)
        self.assertEqual(m["raw_sum"], 120)
        self.assertEqual(m["area_px"], 4)

    def test_dark_16bit_and_bright_have_identical_signal(self):
        m = measure(4095 - self.im, self.roi, self.bg,
                    polarity="dark", ceiling=4095)
        self.assertEqual(m["corrected_sum"], 80)

    def test_negative_values_are_preserved(self):
        self.im[2:4, 2:4] = 5
        m = measure(self.im, self.roi, self.bg, ceiling=4095)
        self.assertEqual(m["corrected_sum"], -20)
        self.assertIn("nonpositive_signal", m["flags"])

    def test_offset_does_not_change_background_corrected_signal(self):
        m = measure(self.im.astype(float) + 500, self.roi, self.bg)
        self.assertEqual(m["corrected_sum"], 80)
        self.assertIn("clipping_unknown", m["flags"])

    def test_adc_ceiling_is_not_assumed_to_equal_dtype_maximum(self):
        self.im[2, 2] = 4095
        m = measure(self.im, self.roi, self.bg, ceiling=4095)
        self.assertEqual(m["clipped_fraction"], 0.25)
        self.assertIn("signal_clipped", m["flags"])

    def test_dark_zero_is_signal_clipping(self):
        im = 4095 - self.im
        im[2, 2] = 0
        m = measure(im, self.roi, self.bg, polarity="dark", ceiling=4095)
        self.assertIn("signal_clipped", m["flags"])

    def test_background_regions_may_not_contain_signal_roi(self):
        with self.assertRaises(ValueError):
            measure(self.im, self.roi, [[3, 3, 5, 5]], ceiling=4095)

    def test_out_of_bounds_roi_is_not_silently_truncated(self):
        with self.assertRaises(ValueError):
            measure(self.im, [7, 7, 10, 10], self.bg, ceiling=4095)

    def test_rgb_is_not_silently_converted_to_gray(self):
        with self.assertRaises(ValueError):
            measure(np.zeros((8, 8, 3)), self.roi, self.bg)

    def test_dark_requires_explicit_intensity_ceiling(self):
        with self.assertRaises(ValueError):
            measure(self.im, self.roi, self.bg, polarity="dark")


class ProposalTests(unittest.TestCase):
    def test_horizontal_background_gradient_is_not_mistaken_for_lane(self):
        yy, xx = np.mgrid[:40, :100]
        im = (1000 + 3 * xx + yy).astype(float)
        im[10:15, 10:20] += 80
        im[10:15, 70:80] += 40
        boxes = propose_rectangles(im, [0, 8, 100, 18])
        self.assertEqual(len(boxes), 2)
        self.assertTrue(boxes[0][0] <= 15 < boxes[0][2])
        self.assertTrue(boxes[1][0] <= 75 < boxes[1][2])

    def test_finds_two_separate_bands_in_user_selected_mw_window(self):
        im = np.full((30, 80), 10, dtype=float)
        im[10:15, 10:20] += 80
        im[10:15, 50:60] += 40
        boxes = propose_rectangles(im, [0, 8, 80, 18])
        self.assertEqual(len(boxes), 2)
        self.assertTrue(boxes[0][0] <= 15 < boxes[0][2])
        self.assertTrue(boxes[1][0] <= 55 < boxes[1][2])

    def test_empty_window_does_not_invent_bands(self):
        self.assertEqual(propose_rectangles(np.ones((20, 40)),
                                           [0, 0, 40, 20]), [])


class NormalizationTests(unittest.TestCase):
    def test_explicit_loading_control_ratio(self):
        rows = normalize_records([record("T", "target", 200, ref_id="R"),
                                  record("R", "reference", 100)])
        self.assertEqual(rows[0]["normalized"], 2)
        self.assertIn("linearity_not_validated", rows[0]["flags"])

    def test_zero_denominator_is_blocked_without_epsilon(self):
        rows = normalize_records([record("T", "target", 200, ref_id="R"),
                                  record("R", "reference", 0)])
        self.assertIsNone(rows[0]["normalized"])

    def test_mismatched_sample_reference_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_records([record("T", "target", 200, ref_id="R"),
                               record("R", "reference", 100, sample="S2")])

    def test_unreviewed_roi_cannot_become_accepted_ratio(self):
        rows = normalize_records([record("T", "target", 200, ref_id="R",
                                         reviewed=False),
                                  record("R", "reference", 100)])
        self.assertIsNone(rows[0]["normalized"])
        self.assertIn("review_required", rows[0]["flags"])

    def test_saturated_reference_blocks_ratio(self):
        rows = normalize_records([record("T", "target", 200, ref_id="R"),
                                  record("R", "reference", 100,
                                         flags=["signal_clipped"])])
        self.assertIsNone(rows[0]["normalized"])

    def test_technical_repeats_do_not_overweight_control_mean(self):
        rows = [dict(blot_id="M1", analyte="AKT", group=g, bio_id=b,
                     normalized=n, flags=[]) for g, b, n in
                [("control", "B1", 1), ("control", "B1", 3),
                 ("control", "B2", 4), ("treated", "B3", 6)]]
        summary = biological_summary(rows, "control")
        self.assertEqual(len(summary), 3)
        treated = next(r for r in summary if r["group"] == "treated")
        self.assertEqual(treated["control_mean"], 3)
        self.assertEqual(treated["fold_vs_control"], 2)


class FileTests(unittest.TestCase):
    def test_uint16_tiff_preserves_values_above_8bit(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "raw.tif"
            Image.fromarray(np.full((8, 8), 12345, dtype=np.uint16)).save(p)
            self.assertEqual(int(load_gray(p)[0, 0]), 12345)

    def test_full_pipeline_exports_hand_calculated_ratio_and_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            im = np.full((8, 12), 10, dtype=np.uint16)
            im[2:4, 2:4] = 30
            im[2:4, 6:8] = 20
            Image.fromarray(im).save(p / "raw.tif")
            t = record("T", "target", 0, ref_id="R")
            r = record("R", "reference", 0)
            for row, roi in [(t, [2, 2, 4, 4]), (r, [6, 2, 8, 4])]:
                row.update(image_id="img", roi=roi, backgrounds=[[0, 0, 2, 2]])
            cfg = dict(images={"img": dict(path="raw.tif", polarity="bright", ceiling=65535)},
                       records=[t, r], control_group="control")
            (p / "config.json").write_text(json.dumps(cfg))
            result = run(p / "config.json", p / "result")
            self.assertEqual(result["blocked"], 0)
            import csv
            with (p / "result/normalized.csv").open(encoding="utf-8-sig") as f:
                self.assertEqual(float(next(csv.DictReader(f))["normalized"]), 2)
            audit = json.loads((p / "result/audit.json").read_text())
            self.assertEqual(len(audit["images"]["img"]["sha256"]), 64)
            self.assertEqual(len(audit["outputs"]), 3)
            with self.assertRaises(ValueError):
                run(p / "config.json", p / "result")


if __name__ == "__main__":
    unittest.main()
