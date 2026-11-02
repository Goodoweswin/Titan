"""IF figure/export contracts use tiny hand-derived original-pixel fixtures."""
import base64
import copy
import hashlib
import importlib
import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest
import tifffile
from PIL import Image


NS = {'s': 'http://www.w3.org/2000/svg'}


def api():
    try:
        return importlib.import_module('titan_if.figures')
    except ModuleNotFoundError as error:
        if error.name == 'titan_if.figures':
            pytest.fail('IF figures are not yet implemented')
        raise


def fixture(tmp_path, calibrated=True):
    fields = []
    for i in range(2):
        path = tmp_path / f'original-{i}.tif'
        # Crop [1, 0, 3, 2] contains 20,40;60,80, with no display-dependent data.
        raw = np.array([[0, 20, 40, 60], [40, 60, 80, 100]], dtype=np.uint16)
        tifffile.imwrite(path, raw, metadata={'axes': 'YX'})
        source = dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                      series_index=0, axes='YX', indexers={})
        fields.append(dict(id=f'f{i}', name=f'Field {i}', sample_id='S1', bio_id='B1',
                           group='Ctrl', batch_id='batch1', width=4, height=2,
                           pixel_size_um=[.5, .75] if calibrated else None,
                           quantitative=True, channels=[dict(id=f'c{i}', name='Marker < A',
                           color='#ff0000', display_min=0, display_max=100, source=source)],
                           rois=[], recipe={}, mask=None, result=None))
    return dict(module='if', schema_version=1, id='p1', name='IF project', revision=0,
                fields=fields, figure=dict(field_ids=['f0', 'f1'], channel_ids=['c0'],
                include_merge=True, crop=[1, 0, 3, 2], inset=None, width_mm=80,
                dpi=100, font_pt=8, scale_bar_um=None, locked_ranges={}))


def decoded_panel(svg, panel=0):
    root = ET.fromstring(svg)
    node = root.findall('.//s:image', NS)[panel]
    return np.asarray(Image.open(io.BytesIO(base64.b64decode(node.attrib['href'].split(',')[1]))))


def test_source_linked_crop_same_marker_and_shared_preview_export_geometry(tmp_path):
    p = fixture(tmp_path)
    before = copy.deepcopy(p)
    preview = api().preview_figure(p)
    output = tmp_path / 'figure'
    files = api().export_figure(p, str(output))['files']
    assert set(Path(path).suffix for path in files) == {'.png', '.tiff', '.svg', '.json'}
    exported = Image.open(output / 'figure.png')
    assert exported.size == (preview['width'], preview['height'])
    assert exported.width == 315  # round(80 / 25.4 * 100)
    preview_image = Image.open(io.BytesIO(base64.b64decode(preview['png'].split(',')[1])))
    assert np.array_equal(np.asarray(exported), np.asarray(preview_image))
    assert (preview['export_width'], preview['export_height']) == exported.size
    svg = (output / 'figure.svg').read_text()
    assert decoded_panel(svg).tolist() == [[[51, 0, 0], [102, 0, 0]], [[153, 0, 0], [204, 0, 0]]]
    assert np.array_equal(decoded_panel(svg, 0), decoded_panel(svg, 2))
    provenance = json.loads((output / 'source.json').read_text())
    assert provenance['fields'][0]['channels'][0]['source']['sha256'] == p['fields'][0]['channels'][0]['source']['sha256']
    assert provenance['fields'][0]['channels'][0]['source']['axes'] == 'YX'
    assert provenance['fields'][0]['crop'] == [1, 0, 3, 2]
    assert p == before
    assert tifffile.imread(p['fields'][0]['channels'][0]['source']['path']).tolist() == [[0, 20, 40, 60], [40, 60, 80, 100]]


def test_locked_marker_range_applies_to_every_field_and_preserves_raw(tmp_path):
    p = fixture(tmp_path)
    p['fields'][1]['channels'][0].update(display_min=40, display_max=80)
    p['figure']['locked_ranges'] = {'Marker < A': [0, 200]}
    api().export_figure(p, str(tmp_path / 'locked.svg'))
    svg = (tmp_path / 'locked.svg').read_text()
    assert decoded_panel(svg).tolist() == [[[25, 0, 0], [51, 0, 0]], [[76, 0, 0], [102, 0, 0]]]
    assert np.array_equal(decoded_panel(svg, 0), decoded_panel(svg, 2))


def test_scale_bar_only_calibrated_and_svg_annotations_are_editable(tmp_path):
    p = fixture(tmp_path, calibrated=False)
    p['figure']['scale_bar_um'] = .5
    preview = api().preview_figure(p)
    assert any('calibr' in warning.lower() or '标定' in warning for warning in preview['warnings'])
    api().export_figure(p, str(tmp_path / 'uncalibrated.svg'))
    root = ET.parse(tmp_path / 'uncalibrated.svg').getroot()
    assert not root.findall('.//s:line[@data-role="scale-bar"]', NS)
    p['fields'][0]['pixel_size_um'] = [.5, .75]
    p['fields'][1]['pixel_size_um'] = [.5, .75]
    p['figure']['inset'] = [1, 0, 2, 1]
    api().export_figure(p, str(tmp_path / 'calibrated.svg'))
    root = ET.parse(tmp_path / 'calibrated.svg').getroot()
    texts = [node.text for node in root.findall('.//s:text', NS)]
    assert 'Marker < A' in texts and 'Field 0' in texts and '0.5 µm' in texts
    assert len(root.findall('.//s:line[@data-role="scale-bar"]', NS)) == 4
    assert len(root.findall('.//s:rect[@data-role="inset-source"]', NS)) == 4
    assert len(root.findall('.//s:image[@data-role="inset"]', NS)) == 4
    assert decoded_panel((tmp_path / 'calibrated.svg').read_text()).shape == (2, 2, 3)


def test_missing_channel_panel_warns_and_other_channels_still_export(tmp_path):
    p = fixture(tmp_path)
    p['fields'][1]['channels'] = []
    preview = api().preview_figure(p)
    assert any('Field 1' in w and 'Marker < A' in w for w in preview['warnings'])
    assert preview['width'] > 0


@pytest.mark.parametrize('change', ['crop', 'dpi', 'size', 'ranges', 'scale', 'inset'])
def test_invalid_layout_rejected_before_any_export_created(tmp_path, change):
    p = fixture(tmp_path)
    if change == 'crop': p['figure']['crop'] = [-1, 0, 3, 2]
    if change == 'dpi': p['figure']['dpi'] = float('nan')
    if change == 'size': p['figure']['width_mm'] = 100000
    if change == 'ranges': p['figure']['locked_ranges'] = {'Marker < A': [2, 2]}
    if change == 'scale': p['figure']['scale_bar_um'] = -1
    if change == 'inset': p['figure']['inset'] = [0, 0, 2, 2]  # outside displayed crop
    with pytest.raises(ValueError):
        api().export_figure(p, str(tmp_path / 'invalid'))
    assert not (tmp_path / 'invalid').exists()


def test_changed_source_refused_without_export_files(tmp_path):
    p = fixture(tmp_path)
    Path(p['fields'][0]['channels'][0]['source']['path']).write_bytes(b'changed')
    with pytest.raises(ValueError, match='hash|原图|source|源'):
        api().export_figure(p, str(tmp_path / 'changed'))
    assert not (tmp_path / 'changed').exists()


def measured_project(tmp_path):
    from titan_if.models import analysis_signature
    p = fixture(tmp_path)
    for index, field in enumerate(p['fields']):
        cid = field['channels'][0]['id']
        field['recipe'] = dict(mode='region', nuclear_channel_id=cid, target_channel_ids=[cid],
                               thresholds={cid: 50}, threshold_source='negative control', thresholds_frozen=True)
        field['rois'] = [dict(id=f'r{index}', name='signal', role='signal', shape='rectangle', points=[[0, 0], [4, 2]])]
        obj = dict(object_id=1, channel_id=cid, area_px=8, area_um2=3,
                   raw_sum=400, mean=50, background_mean=None, corrected_sum=None,
                   positive_pixels=4, positive=None)
        summary = dict(field_id=field['id'], channel_id=cid, object_count=1,
                       area_px=8, area_um2=3, raw_sum=400, mean=50, background_mean=None,
                       corrected_sum=None, positive_pixels=4, positive_area_fraction=.5,
                       positive_count=None, positive_fraction=None)
        field['result'] = dict(field_id=field['id'], input_signature=analysis_signature(field),
                               objects=[obj], summary=[summary], warnings=[])
    return p


def test_results_export_rows_match_biological_pooling_and_keep_null_correction(tmp_path):
    import csv
    from openpyxl import load_workbook
    p = measured_project(tmp_path)
    output = tmp_path / 'results'
    result = api().export_results(p, str(output))
    assert {Path(path).name for path in result['files']} == {
        'objects.csv', 'fields.csv', 'samples.csv', 'results.xlsx', 'sample_scatter.png', 'source.json'}
    def rows(name):
        with (output / name).open(encoding='utf-8-sig', newline='') as handle:
            return list(csv.DictReader(handle))
    assert len(rows('objects.csv')) == 2
    assert len(rows('fields.csv')) == 2
    samples = rows('samples.csv')
    assert len(samples) == 1  # two fields belong to one biological sample and marker
    assert samples[0]['bio_id'] == 'B1'
    assert float(samples[0]['raw_sum']) == 800
    assert float(samples[0]['area_px']) == 16
    assert float(samples[0]['positive_area_fraction']) == .5
    assert samples[0]['corrected_sum'] == ''
    book = load_workbook(output / 'results.xlsx', data_only=True)
    assert book.sheetnames == ['objects', 'fields', 'samples']
    assert [book[name].max_row for name in book.sheetnames] == [3, 3, 2]
    scatter = Image.open(output / 'sample_scatter.png')
    assert scatter.width >= 400 and scatter.height >= 300
    manifest = json.loads((output / 'source.json').read_text())
    assert manifest['scatter']['unit'] == 'biological_sample'
    assert manifest['scatter']['point_count'] == 1
    assert manifest['fields'][0]['result_signature'] == p['fields'][0]['result']['input_signature']
    assert manifest['fields'][0]['recipe']['threshold_source'] == 'negative control'


def test_stale_results_rejected_without_writing_any_output(tmp_path):
    p = measured_project(tmp_path)
    p['fields'][0]['recipe']['thresholds']['c0'] = 70
    with pytest.raises(ValueError, match='stale|签名|过期|重新'):
        api().export_results(p, str(tmp_path / 'stale'))
    assert not (tmp_path / 'stale').exists()


def test_export_existing_files_kept_and_xlsx_strings_are_literal(tmp_path):
    from openpyxl import load_workbook
    p = measured_project(tmp_path)
    for field in p['fields']:
        field['bio_id'] = '=1+2'
    output = tmp_path / 'literal.xlsx'
    api().export_results(p, str(output))
    sheet = load_workbook(output, data_only=False)['samples']
    header = [cell.value for cell in sheet[1]]
    cell = sheet.cell(row=2, column=header.index('bio_id')+1)
    assert cell.value == '=1+2' and cell.data_type == 's'
    previous = output.read_bytes()
    with pytest.raises(ValueError, match='exists|存在'):
        api().export_results(p, str(output))
    assert output.read_bytes() == previous


def test_failed_file_publication_removes_partial_new_exports(tmp_path, monkeypatch):
    p = fixture(tmp_path)
    destination = tmp_path / 'interrupted.png'
    original_open = Path.open
    def disk_failure(path, mode='r', *args, **kwargs):
        if path == tmp_path / 'interrupted.source.json' and mode == 'xb':
            raise OSError('simulated storage failure')
        return original_open(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', disk_failure)
    with pytest.raises(OSError, match='storage failure'):
        api().export_figure(p, str(destination))
    assert not destination.exists()
    assert not (tmp_path / 'interrupted.source.json').exists()


def test_synthetic_sample_scatter_has_visible_header_label(tmp_path):
    p = measured_project(tmp_path)
    api().export_results(p, str(tmp_path / 'regular'))
    p['synthetic'] = True
    api().export_results(p, str(tmp_path / 'synthetic'))
    regular = np.asarray(Image.open(tmp_path / 'regular/sample_scatter.png'))
    synthetic = np.asarray(Image.open(tmp_path / 'synthetic/sample_scatter.png'))
    assert not np.array_equal(regular[:85], synthetic[:85])
    assert np.array_equal(regular[85:], synthetic[85:])
    assert json.loads((tmp_path / 'synthetic/source.json').read_text())['synthetic'] is True


def test_large_noisy_figure_preview_fits_transport_and_retains_export_geometry(tmp_path):
    from titan_if.images import import_field
    raw = np.random.default_rng(20261103).integers(0, 256, (2048, 2048, 3), dtype=np.uint8)
    source = tmp_path / 'noisy-rgb.tif'
    tifffile.imwrite(source, raw, photometric='rgb', metadata={'axes': 'YXS'})
    field = import_field([dict(path=str(source), series_index=0, indexers={})], metadata={'name': 'F'})
    project = dict(module='if', id='large-preview', name='Large preview', fields=[field],
                   figure=dict(field_ids=[], channel_ids=[], include_merge=True,
                               width_mm=500, dpi=400, font_pt=9, crop=None, inset=None,
                               scale_bar_um=None, locked_ranges={}))
    preview = api().preview_figure(project)
    image = Image.open(io.BytesIO(base64.b64decode(preview['png'].split(',')[1])))
    assert max(image.size) <= 1600
    assert image.size == (preview['width'], preview['height'])
    assert len(json.dumps(preview).encode('utf-8')) < 4*1024**2 + 1024
    # Nominal export dimensions must survive preview scaling.
    assert preview['export_width'] == 7874
    assert preview['export_height'] > 1600
    assert image.width/image.height == pytest.approx(preview['export_width']/preview['export_height'], rel=.003)
    # The pseudocolor order and merge remain visible in the same four columns.
    pixels = np.asarray(image)
    y = image.height//2
    for fraction, channel in ((.14, 0), (.39, 1), (.64, 2)):
        color = pixels[y, round(image.width*fraction)]
        assert color[channel] > 25
        assert all(color[other] < 3 for other in range(3) if other != channel)
    assert np.all(pixels[y, round(image.width*.89)] > 25)
    api().export_figure(project, str(tmp_path / 'full.png'))
    full = Image.open(tmp_path / 'full.png')
    assert full.size == (preview['export_width'], preview['export_height'])
    assert full.width > image.width


def test_xlsx_preserves_large_exact_integer_sums_as_decimal_text(tmp_path):
    import csv
    from openpyxl import load_workbook
    from titan_if.analysis import measure_field
    from titan_if.images import import_field
    raw = np.full((2048, 2048), np.iinfo(np.uint32).max, dtype=np.uint32)
    raw[0, 0] -= 1
    source = tmp_path / 'uint32-source.tif'
    tifffile.imwrite(source, raw, metadata={'axes': 'YX'})
    field = import_field([dict(path=str(source), series_index=0, indexers={})],
                         metadata={'name': 'Exact sum', 'bio_id': '=literal', 'sample_id': 'S1', 'group': 'Control'})
    field['rois'] = [dict(id='r1', name='all', role='signal', shape='rectangle', points=[[0, 0], [2048, 2048]])]
    field['result'] = measure_field(field)
    p = dict(module='if', id='exact', name='Exact', fields=[field])
    api().export_results(p, str(tmp_path / 'exact'))
    book = load_workbook(tmp_path / 'exact/results.xlsx', data_only=False)
    for name in ('objects', 'fields', 'samples'):
        sheet = book[name]
        headers = [cell.value for cell in sheet[1]]
        total = sheet.cell(row=2, column=headers.index('raw_sum')+1)
        assert total.value == '18014398505287679'
        assert total.data_type == 's'
        biological_id = sheet.cell(row=2, column=headers.index('bio_id')+1)
        assert biological_id.value == '=literal' and biological_id.data_type == 's'
        with (tmp_path / f'exact/{name}.csv').open(encoding='utf-8-sig', newline='') as handle:
            assert next(csv.DictReader(handle))['raw_sum'] == '18014398505287679'
