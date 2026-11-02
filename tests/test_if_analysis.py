"""Independent numerical and geometry fixtures; synthetic, not biological validation."""
import copy

import numpy as np
import pytest
import tifffile


def api():
    from titan_if import analysis
    return analysis


def field_from(tmp_path, raw, name='field'):
    from titan_if.images import import_field
    raw = np.asarray(raw, dtype=np.uint16)
    path = tmp_path / f'{name}.ome.tif'
    axes = 'YX' if raw.ndim == 2 else 'CYX'
    tifffile.imwrite(path, raw, ome=True, metadata={'axes': axes, 'Channel': {'Name': ['Target'] if raw.ndim == 2 else ['DAPI', 'Target']}}, photometric='minisblack')
    return import_field([{'path': str(path)}], {'bio_id': 'B1', 'group': 'control', 'batch_id': 'batch1', 'pixel_size_um': [.5, 2]})


def rect(x0, y0, x1, y1, role='signal', id='r1'):
    return {'id': id, 'name': id, 'role': role, 'shape': 'rectangle', 'points': [[x0, y0], [x1, y1]]}


def threshold(field, value):
    field['recipe'].update(thresholds={c['id']: value for c in field['channels']}, threshold_source='negative-control', thresholds_frozen=True)


def test_roi_pixel_centers_and_polygon_boundary_are_consistent():
    a = api()
    expected = np.array([[1, 1, 0], [1, 1, 0], [0, 0, 0]], bool)
    for shape in ['rectangle', 'polygon']:
        points = [[0, 0], [2, 2]] if shape == 'rectangle' else [[0, 0], [2, 0], [2, 2], [0, 2]]
        np.testing.assert_array_equal(a.roi_mask({'shape': shape, 'points': points}, (3, 3)), expected)
    ellipse = a.roi_mask({'shape': 'ellipse', 'points': [[0, 0], [3, 3]]}, (3, 3))
    assert ellipse.sum() == 9
    tiny = a.roi_mask(rect(.6, .6, 1.4, 1.4), (3, 3))
    assert not tiny.any()
    triangle = a.roi_mask({'shape': 'polygon', 'points': [[0, 0], [2, 0], [0, 2]]}, (3, 3))
    assert triangle.sum() == 3  # Includes pixel centers on the diagonal.
    with pytest.raises(ValueError, match='finite|points'):
        a.roi_mask({'shape': 'polygon', 'points': [[0, 0], [1, 0], [np.nan, 1]]}, (3, 3))


def test_hand_derived_raw_mean_and_negative_background_correction(tmp_path):
    field = field_from(tmp_path, [[1, 3, 10], [5, 7, 14]], 'negative')
    field['rois'] = [rect(0, 0, 2, 2), rect(2, 0, 3, 2, 'background', 'bg')]
    threshold(field, 5)
    result = api().measure_field(field)
    row = result['objects'][0]
    assert row['area_px'] == 4
    assert row['area_um2'] == 4
    assert row['raw_sum'] == 16
    assert row['mean'] == 4
    assert row['background_mean'] == 12
    assert row['corrected_sum'] == -32
    assert row['positive_pixels'] == 2
    assert row['positive'] is None
    summary = result['summary'][0]
    assert summary['positive_area_fraction'] == .5
    assert summary['positive_fraction'] is None
    original_signature = result['input_signature']
    field['channels'][0].update(display_min=3, display_max=4, color='#ffffff')
    assert api().measure_field(field) == result
    assert api().measure_field(field)['input_signature'] == original_signature


def test_background_union_not_double_counted_and_signal_overlap_rejected(tmp_path):
    field = field_from(tmp_path, [[2, 8, 12, 16]], 'bg')
    field['rois'] = [rect(0, 0, 1, 1), rect(1, 0, 3, 1, 'background', 'b1'), rect(2, 0, 4, 1, 'background', 'b2')]
    result = api().measure_field(field)
    assert result['objects'][0]['background_mean'] == 12
    field['rois'][0] = rect(0, 0, 2, 1)
    with pytest.raises(ValueError, match='overlap'):
        api().measure_field(field)
    field['rois'] = [rect(0, 0, 2, 1), rect(1, 0, 2, 1, id='r2')]
    with pytest.raises(ValueError, match='overlap'):
        api().measure_field(field)


def test_missing_background_and_calibration_remain_null(tmp_path):
    field = field_from(tmp_path, [[1, 2], [3, 4]], 'raw')
    field['pixel_size_um'] = None
    result = api().measure_field(field)
    row = result['summary'][0]
    assert row['mean'] == 2.5
    assert row['corrected_sum'] is None and row['background_mean'] is None
    assert row['area_um2'] is None
    assert row['positive_pixels'] is None and row['positive_fraction'] is None
    assert result['warnings']
    field['rois'] = [rect(1, 0, 2, 2, 'background')]
    result = api().measure_field(field)
    assert result['summary'][0]['area_px'] == 2
    assert result['summary'][0]['corrected_sum'] == -2


def test_threshold_provenance_and_figure_only_guard(tmp_path):
    field = field_from(tmp_path, [[1, 2], [3, 4]], 'guards')
    field['recipe']['thresholds'] = {field['channels'][0]['id']: 2}
    with pytest.raises(ValueError, match='frozen|provenance|source'):
        api().measure_field(field)
    threshold(field, float('nan'))
    with pytest.raises(ValueError, match='finite|threshold'):
        api().measure_field(field)
    field['quantitative'] = False
    with pytest.raises(ValueError, match='RGB|quantitative|figure'):
        api().measure_field(field)


def test_nuclei_measure_original_intensities_and_mean_based_positivity(tmp_path):
    raw = np.array([[[0, 0, 0], [100, 100, 100]], [[2, 6, 10], [20, 30, 40]]], np.uint16)
    field = field_from(tmp_path, raw, 'nuclei')
    field['recipe']['mode'] = 'nuclei'
    field['recipe']['target_channel_ids'] = [field['channels'][1]['id']]
    field['rois'] = [rect(0, 0, 3, 1)]
    threshold(field, 5)
    labels = np.array([[1, 1, 2], [0, 0, 0]], np.uint32)
    result = api().measure_field(field, labels)
    assert [row['mean'] for row in result['objects']] == [4, 10]
    assert [row['positive'] for row in result['objects']] == [False, True]
    summary = result['summary'][0]
    assert summary['object_count'] == 2 and summary['positive_count'] == 1
    assert summary['positive_fraction'] == .5
    assert summary['raw_sum'] == 18 and summary['mean'] == 6
    assert summary['positive_pixels'] == 2
    assert summary['positive_area_fraction'] == pytest.approx(2 / 3)


def test_segment_touching_nuclei_holes_border_and_empty(tmp_path):
    y, x = np.mgrid[:64, :64]
    disks = ((x - 25)**2 + (y - 32)**2 <= 9**2) | ((x - 40)**2 + (y - 32)**2 <= 9**2)
    raw = (disks * 1000).astype(np.uint16)
    raw[30:33, 23:26] = 0
    raw[0:5, 2:7] = 1000
    field = field_from(tmp_path, raw, 'touching')
    field['recipe']['segmentation'].update(sigma=0, threshold_method='manual', threshold=100,
                                         min_area=20, max_area=500, min_distance=8, exclude_border=True)
    labels = api().segment_nuclei(field)
    assert labels.dtype == np.uint32
    assert set(np.unique(labels)) == {0, 1, 2}
    assert labels[31, 24] > 0  # Filled nucleus hole.
    assert not labels[:5, :8].any()
    field['recipe']['segmentation'].update(threshold_method='otsu', rolling_ball_radius=10)
    assert api().segment_nuclei(field).max() >= 2
    empty = field_from(tmp_path, np.zeros((8, 8), np.uint16), 'empty')
    assert not api().segment_nuclei(empty).any()


def test_manual_label_edits_copy_preserve_ids_and_partition_by_line():
    original = np.zeros((5, 6), np.uint32)
    added = api().edit_labels(original, {'kind': 'add', 'roi': rect(0, 0, 4, 4)})
    assert not original.any() and np.count_nonzero(added == 1) == 16
    split = api().edit_labels(added, {'kind': 'split', 'ids': [1], 'points': [[2, 0], [2, 4]]})
    assert np.count_nonzero(split == 1) == 8 and np.count_nonzero(split == 2) == 8
    merged = api().edit_labels(split, {'kind': 'merge', 'ids': [2, 1]})
    np.testing.assert_array_equal(merged, added)
    deleted = api().edit_labels(split, {'kind': 'delete', 'ids': [2]})
    assert np.count_nonzero(deleted) == 8
    with pytest.raises(ValueError, match='split|intersect|partition'):
        api().edit_labels(added, {'kind': 'split', 'ids': [1], 'points': [[9, 0], [9, 4]]})
    with pytest.raises(ValueError, match='label|ID|ids'):
        api().edit_labels(added, {'kind': 'delete', 'ids': [99]})


def test_biological_aggregation_pools_numerators_not_field_percentages(tmp_path):
    first = field_from(tmp_path, [[1, 9]], 'a')
    second = field_from(tmp_path, [[9, 9, 9, 9, 9, 9]], 'b')
    for field in [first, second]:
        threshold(field, 5)
        field['result'] = api().measure_field(field)
    project = {'fields': [first, second]}
    result = api().aggregate_results(project)
    assert len(result['samples']) == 1
    row = result['samples'][0]
    assert row['field_count'] == 2
    assert row['area_px'] == 8 and row['positive_pixels'] == 7
    assert row['positive_area_fraction'] == .875
    assert row['raw_sum'] == 64 and row['mean'] == 8
    assert len(result['fields']) == 2 and len(result['objects']) == 2
    second['recipe']['thresholds'][second['channels'][0]['id']] = 7
    with pytest.raises(ValueError, match='stale'):
        api().aggregate_results(project)
    second['result'] = api().measure_field(second)
    with pytest.raises(ValueError, match='threshold|incompatible'):
        api().aggregate_results(project)


def test_aggregation_refuses_missing_biological_identity(tmp_path):
    field = field_from(tmp_path, [[4]], 'identity')
    field['bio_id'] = ''
    field['result'] = api().measure_field(field)
    result = api().aggregate_results({'fields': [field]})
    assert result['samples'] == []  # Still available in fields; never invent biological n.
    assert len(result['fields']) == 1


def test_integer_raw_sum_retains_low_bits_above_float_precision(tmp_path):
    # 8,390,655 identical pixels: odd integer > 2^53 cannot be carried by float64.
    path = tmp_path / 'large.tif'
    raw = np.full((2049, 4095), np.iinfo(np.uint32).max, np.uint32)
    from titan_if.images import import_field
    tifffile.imwrite(path, raw)
    field = import_field([{'path': str(path)}])
    result = api().measure_field(field)
    assert result['objects'][0]['raw_sum'] == 36037588808628225
    assert isinstance(result['objects'][0]['raw_sum'], int)


def test_incompatible_thresholds_rejected_across_biological_samples_in_batch(tmp_path):
    first = field_from(tmp_path, [[1, 9]], 'bioA')
    second = field_from(tmp_path, [[1, 9]], 'bioB')
    second['bio_id'] = 'B2'
    for field, cutoff in [(first, 5), (second, 7)]:
        threshold(field, cutoff)
        field['result'] = api().measure_field(field)
    with pytest.raises(ValueError, match='threshold|incompatible|Incompatible'):
        api().aggregate_results({'fields': [first, second]})


def test_stored_nuclear_mask_confirmation_hash_and_signature(tmp_path):
    from titan_if.images import file_sha256
    from titan_if.models import segmentation_signature
    field = field_from(tmp_path, [[1, 2], [3, 4]], 'stored')
    field['recipe']['mode'] = 'nuclei'
    path = tmp_path / 'mask.tif'
    labels = np.array([[1, 1], [0, 0]], np.uint32)
    tifffile.imwrite(path, labels)
    field['mask'] = {'path': str(path), 'sha256': file_sha256(path), 'version': 1,
                     'segmentation_signature': segmentation_signature(field), 'confirmed': False}
    with pytest.raises(ValueError, match='confirmed'):
        api().measure_field(field)
    field['mask']['confirmed'] = True
    assert api().measure_field(field)['objects'][0]['raw_sum'] == 3
    with pytest.raises(ValueError, match='mask|labels|match'):
        api().measure_field(field, np.ones((2, 2), np.uint32))
    tifffile.imwrite(path, np.ones((2, 2), np.uint32))
    with pytest.raises(ValueError, match='hash|SHA256'):
        api().measure_field(field)
    field['rois'] = [rect(0, 0, 1, 2)]
    with pytest.raises(ValueError, match='stale'):
        api().measure_field(field)


def test_many_roi_rasterization_does_not_retain_one_full_mask_per_region():
    import tracemalloc
    a = api()
    # At full supported size, retaining every signal mask would exceed 1 GiB.
    # This half-scale fixture enforces the same bounded, streaming behavior.
    field = {'height': 2048, 'width': 2048,
             'rois': [rect(i * 128, 0, (i + 1) * 128, 2048, id=str(i)) for i in range(16)]}
    tracemalloc.start()
    try:
        regions, ids, background, warnings = a._regions(field)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert len(ids) == 16
    assert np.count_nonzero(regions) == 4194304
    assert peak < 48 * 1024**2


def test_aggregation_uses_complete_verified_artifact_not_ui_preview(tmp_path):
    import json
    from titan_if.images import file_sha256
    from titan_if.images import import_field
    raw_path = tmp_path / 'artifact.tif'
    tifffile.imwrite(raw_path, np.full((2049, 4095), 4294967295, np.uint32))
    field = import_field([{'path': str(raw_path)}], {'bio_id': 'B1'})
    field['rois'] = [rect(0, 0, 2049, 2049), rect(2049, 0, 4095, 2049, id='r2')]
    threshold(field, 5)
    complete = api().measure_field(field)
    path = tmp_path / 'result.json'
    path.write_text(json.dumps(complete), encoding='utf-8')
    field['result'] = {**complete, 'objects': [], 'objects_truncated': True, 'total_objects': 2,
                       'artifact': {'path': str(path), 'sha256': file_sha256(path)}}
    aggregated = api().aggregate_results({'fields': [field]})
    assert len(aggregated['objects']) == 2
    assert aggregated['objects'][0]['raw_sum'] == 18031994986295295
    assert aggregated['samples'][0]['area_px'] == 8390655
    path.write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='hash|SHA256|artifact'):
        api().aggregate_results({'fields': [field]})


def test_integer_background_correction_avoids_catastrophic_cancellation(tmp_path):
    from titan_if.images import import_field
    path = tmp_path / 'cancellation.tif'
    raw = np.full((2048, 4096), 4294967294, np.uint32)
    raw[0, 0] = 4294967295
    tifffile.imwrite(path, raw)
    field = import_field([{'path': str(path)}])
    field['rois'] = [rect(0, 0, 2048, 2048), rect(2048, 0, 4096, 2048, 'background', 'bg')]
    result = api().measure_field(field)
    assert result['objects'][0]['corrected_sum'] == 1
    assert result['summary'][0]['corrected_sum'] == 1


def test_region_positivity_reports_area_without_inventing_positive_nuclei(tmp_path):
    field = field_from(tmp_path, [[0, 0, 10, 10]], 'region_positivity')
    threshold(field, 5)
    result = api().measure_field(field)
    row, summary = result['objects'][0], result['summary'][0]
    assert row['mean'] == 5
    assert row['positive_pixels'] == 2
    assert row['positive'] is None
    assert summary['positive_area_fraction'] == .5
    assert summary['object_count'] == 1
    assert summary['positive_count'] is None
    assert summary['positive_fraction'] is None
    field['result'] = result
    sample = api().aggregate_results({'fields': [field]})['samples'][0]
    assert sample['positive_area_fraction'] == .5
    assert sample['positive_count'] is None
    assert sample['positive_fraction'] is None
    assert sample['positive_nucleus_numerator'] is None
    assert sample['positive_nucleus_denominator'] is None
    from titan_if.figures import _scatter
    _, scatter = _scatter([sample])
    assert scatter['points'][0]['metric'] == 'positive_area_fraction'
    assert scatter['points'][0]['value'] == .5
