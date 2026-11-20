"""WB teaching data must retain its synthetic provenance."""
import copy
import json
from pathlib import Path

import pytest

from titan_wb.engine import dispatch
from titan_wb.images import file_hash, read_pixels
from titan_wb.models import validate_project

def launch(mode='annotated'):
    return dispatch({'command': 'reference_case', 'payload': {'mode': mode}})


def test_case_generates_synthetic_source_and_selects_16_bit_second_page():
    p = launch()
    a, = p['images']
    assert p['synthetic'] is True and not p.get('demo')
    assert p['example_case']['id'] == 'wb-synthetic-tutorial-v1'
    assert Path(a['path']).name == p['example_case']['source_name'] == 'SYNTHETIC_WB_TUTORIAL.tif'
    assert file_hash(Path(a['path'])) == p['example_case']['source_sha256'] == a['sha256']
    assert (a['width'], a['height'], a['dtype'], a['page_index'], a['page_count']) == (2688, 2200, 'uint16', 1, 2)
    assert a['ceiling'] is None
    assert a['linear_validated'] is False
    assert p['example_case']['page_index'] == 1
    assert p['example_case']['uint16_max_pixels'] == 0


def test_annotated_case_has_editable_unreviewed_target_only_suggestions():
    p = validate_project(launch())
    assert len(p['lanes']) == len(p['rois']) == 9
    assert {r['role'] for r in p['rois']} == {'target'}
    assert all(r['reference_id'] is None and r['reviewed_revision'] is None for r in p['rois'])
    assert all(r['backgrounds'] for r in p['rois'])
    assert {s['group'] for s in p['samples']} == {'未提供'}
    assert {s['bio_id'] for s in p['samples']} == {'未提供'}
    assert p['settings']['design_confirmed'] is False


def test_practice_is_blank_and_launches_use_independent_identity_and_source():
    a, b = launch('practice'), launch('practice')
    assert a['id'] != b['id']
    assert a['images'][0]['path'] != b['images'][0]['path']
    for key in ('samples', 'lanes', 'rois', 'lane_layouts', 'band_sets'):
        assert a[key] == []
    assert file_hash(Path(a['images'][0]['path'])) == file_hash(Path(b['images'][0]['path']))
    assert 255 < read_pixels(a['images'][0]).max() < 65535


def test_tutorial_starts_with_unconfirmed_lane_template_and_no_measurements():
    p = validate_project(launch('tutorial'))
    assert p['example_case']['mode'] == 'tutorial'
    assert file_hash(Path(p['images'][0]['path'])) == p['example_case']['source_sha256']
    assert p['images'][0]['page_index'] == 1
    assert len(p['lanes']) == len(p['band_sets'][0]['assignments']) == 9
    assert p['rois'] == []
    assert p['lane_layouts'][0]['confirmed_revision'] is None
    assert all(a == {'lane_id': f'L{n}', 'roi_id': None, 'status': 'pending'}
               for n, a in enumerate(p['band_sets'][0]['assignments'], 1))
    result = dispatch({'command': 'analyze', 'payload': {'project': p}})
    assert result['measurements'] == result['biological'] == result['statistics'] == []
    assert len(result['lane_results']) == 9
    assert all(row['status'] == 'pending' and row['normalized'] is None for row in result['lane_results'])


def test_case_rejects_invalid_mode():
    with pytest.raises(ValueError, match='模式'):
        launch('unknown')


def test_case_analysis_uses_normal_missing_reference_results():
    p = launch()
    ordinary = copy.deepcopy(p)
    ordinary.pop('example_case')
    example = dispatch({'command': 'analyze', 'payload': {'project': p}})
    normal = dispatch({'command': 'analyze', 'payload': {'project': ordinary}})
    assert len(example['measurements']) == len(example['lane_results']) == 9
    for key in ('measurements', 'normalized', 'biological', 'statistics', 'lane_results', 'multigroup_omnibus', 'multigroup_comparisons'):
        assert example[key] == normal[key]
    assert all(r['normalized'] is None and 'missing_reference' in r['flags'] for r in example['normalized'])
    assert all(r['status'] == 'blocked' for r in example['lane_results'])
    assert example['biological'] == example['statistics'] == []


def test_teaching_marker_does_not_bypass_normal_analysis_with_complete_fixture_data():
    from titan_wb.demo import make_demo
    p = make_demo()
    normal = dispatch({'command': 'analyze', 'payload': {'project': p}})
    p['example_case'] = {'id': 'synthetic-test-fixture'}
    example = dispatch({'command': 'analyze', 'payload': {'project': p}})
    for key in ('measurements', 'normalized', 'biological', 'statistics', 'lane_results'):
        assert example[key] == normal[key]
    assert len(example['biological']) == 6



def test_case_can_save_reopen_without_original_download(tmp_path):
    p = launch()
    source = Path(p['images'][0]['path'])
    saved = dispatch({'command': 'save_project', 'payload': {'project': p, 'path': str(tmp_path/'case.titanwb')}})
    source.unlink()
    reopened = dispatch({'command': 'open_project', 'payload': {'path': saved['project_path']}})
    assert reopened['example_case'] == p['example_case']
    assert file_hash(Path(reopened['images'][0]['path'])) == p['example_case']['source_sha256']


def test_case_assembly_exports_teaching_marker_provenance_and_physical_pdf(tmp_path):
    from titan_wb.wb_figures import new_document, export_document
    from PIL.PdfParser import PdfParser
    p = launch()
    d = new_document(p)
    d['rows'][0]['confirmed'] = True
    dest = tmp_path / 'figure'
    export_document(p, d, str(dest))
    assert {'figure.png', 'figure.svg', 'figure.pdf', 'source.json'} <= {f.name for f in dest.iterdir()}
    source = json.loads((dest/'source.json').read_text(encoding='utf-8'))
    assert source['document']['example_case'] == p['example_case']
    assert source['document']['synthetic'] is True
    assert source['document']['rows'][0]['source']['sha256'] == p['example_case']['source_sha256']
    assert '合成示例 · 非实验数据' in (dest/'figure.svg').read_text(encoding='utf-8')
    with PdfParser(filename=str(dest/'figure.pdf')) as pdf:
        assert len(pdf.pages) == 1
        box = pdf.read_indirect(pdf.pages[0])[b'MediaBox']
        assert box[2] == pytest.approx(85/25.4*72, abs=.3)
        assert box[3] == pytest.approx(source['height_mm']/25.4*72, abs=.3)


def test_teaching_caption_fits_minimum_width_at_maximum_label_font():
    from titan_wb.wb_figures import new_document
    from titan_wb.wb_render import render, font
    p = launch('practice')
    d = new_document(p)
    d['settings'].update(width_mm=40, font_pt=24)
    output = render(d)
    caption, = [t for t in output['layout']['texts'] if t['text'] == '合成示例 · 非实验数据']
    size = caption.get('font_pt', 24)
    right = caption['x'] + font(size*4).getlength(caption['text'])/4
    assert right <= 40/25.4*72 - 3/25.4*72
