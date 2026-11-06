import copy
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pytest
import tifffile

from titan_if.models import analysis_signature, segmentation_signature
from titan_if.projects import save_project as save_if
from titan_stats.analysis import analyze
from titan_stats.models import prepared, signature
from titan_stats.service import dispatch
from titan_stats.sources import if_tables
from test_if_projects import fixture as raw_fixture


@pytest.fixture
def session(tmp_path):
    return dict(pid=os.getpid(), token='source-tests', library_root=str(tmp_path/'library'))


def if_project(tmp_path, session, nuclear=False):
    p = raw_fixture(tmp_path); template = p['fields'][0]; p['fields'] = []
    # Unequal areas expose accidental averaging of field means/percentages.
    for i, (bio, group, area, total, positive, count, positive_nuclei) in enumerate([
        ('A1', 'control', 10, 100, 1, 1, 1), ('A1', 'control', 90, 1800, 45, 9, 0),
        ('A2', 'control', 20, 400, 2, 2, 1), ('B1', 'treated', 20, 600, 15, 3, 2),
        ('B2', 'treated', 20, 800, 16, 4, 3),
    ]):
        f = copy.deepcopy(template); f.update(id=f'f{i}', name=f'视野{i}', bio_id=bio, group=group, sample_id=bio)
        f['recipe'].update(mode='nuclei' if nuclear else 'region', thresholds={'c1': 10}, thresholds_frozen=True, threshold_source='negative control')
        if nuclear:
            mask = tmp_path/f'mask{i}.tif'; labels = np.zeros((10,12), np.uint32); labels.flat[:count] = np.arange(1,count+1)
            tifffile.imwrite(mask, labels)
            f['mask'] = dict(path=str(mask), sha256=hashlib.sha256(mask.read_bytes()).hexdigest(), version=1,
                             segmentation_signature=segmentation_signature(f), confirmed=True)
        row = dict(channel_id='c1', field_id=f['id'], measurement_mode=f['recipe']['mode'], object_count=count,
                   area_px=area, area_um2=area*.25, raw_sum=total, mean=total/area, background_mean=1,
                   corrected_sum=total-area, positive_pixels=positive, positive_count=positive_nuclei if nuclear else None)
        f['result'] = dict(field_id=f['id'], input_signature=analysis_signature(f), summary=[row], objects=[], warnings=[])
        p['fields'].append(f)
    return save_if(p, str(tmp_path/'source.titanif'), None, session)


def choose(catalog, metric):
    return next(c for c in catalog['choices'] if json.loads(c['key']).get('metric') == metric)


def read(p, session, metric='mean', target=None):
    c = dispatch('stats_source_catalog', {'path': p['project_path']}, session)
    key = choose(c, metric)['key']
    return dispatch('stats_from_source', dict(path=c['path'], keys=[key], expected_signature=c['signature'], confirmed=True, project=target), session)


def test_if_weights_fields_and_exposes_sample_counts_and_percent_units(tmp_path, session):
    p = if_project(tmp_path, session)
    c = dispatch('stats_source_catalog', {'path': p['project_path']}, session)
    mean = choose(c, 'mean'); percent = choose(c, 'positive_area_fraction')
    assert mean['n'] == 4 and mean['groups'] == [{'name':'control','n':2},{'name':'treated','n':2}]
    assert mean['preview'][0]['value'] == 19  # (100 + 1800) / (10 + 90), not 15.
    assert percent['preview'][0]['value'] == 46  # (1 + 45) / 100 * 100, not 30.
    assert percent['unit'] == '%' and choose(c, 'positive_fraction')['unavailable']
    stats = read(p, session); values, missing, _ = prepared(stats['datasets'][0])
    assert len(values) == 4 and missing == 0  # Sparse inter-group blanks aren't missing samples.
    assert stats['datasets'][0]['source']['records'][0]['field_count'] == 2


def test_nuclear_fraction_pools_denominator_instead_of_field_percentages(tmp_path, session):
    p = if_project(tmp_path, session, nuclear=True)
    c = dispatch('stats_source_catalog', {'path': p['project_path']}, session)
    assert choose(c, 'positive_fraction')['preview'][0]['value'] == 10  # 1 / (1+9), not 50%.


def test_partial_sample_is_missing_not_a_partial_mean_or_zero(tmp_path, session):
    p = if_project(tmp_path, session); p['fields'][1]['result'] = None
    d = next(d for d in if_tables(p) if d['source']['selector']['metric'] == 'mean')
    values, missing, _ = prepared(d)
    assert len(values) == 3 and missing == 1
    record = d['source']['records'][0]
    assert record['value'] is None and '部分视野' in record['missing_reason']


def test_missing_channel_summary_cannot_silently_reduce_a_sample(tmp_path, session):
    p = if_project(tmp_path, session); p['fields'][1]['result']['summary'] = []
    d = next(d for d in if_tables(p) if d['source']['selector']['metric'] == 'mean')
    assert d['source']['records'][0]['value'] is None
    assert '缺少对应通道结果' in d['source']['records'][0]['missing_reason']


@pytest.mark.parametrize('change', ['stale','threshold','identity','zero'])
def test_invalid_if_results_are_explicitly_unavailable(tmp_path, session, change):
    p = if_project(tmp_path, session)
    if change == 'stale': p['fields'][0]['recipe']['thresholds']['c1'] = 11
    elif change == 'threshold':
        p['fields'][0]['recipe']['thresholds']['c1'] = 11
        p['fields'][0]['result']['input_signature'] = analysis_signature(p['fields'][0])
    elif change == 'identity': p['fields'][0]['bio_id'] = ''
    else:
        for f in p['fields']:
            f['result']['summary'][0].update(area_px=0, positive_pixels=0)
    d = next(d for d in if_tables(p) if d['source']['selector']['metric'] == 'positive_area_fraction')
    assert all(r['value'] is None for r in d['source']['records'])
    assert any(r['missing_reason'] for r in d['source']['records'])


def test_if_batches_remain_separate_and_groups_share_biological_identity(tmp_path, session):
    p = if_project(tmp_path, session)
    p['fields'][-1]['batch_id'] = 'batch2'
    ds = [d for d in if_tables(p) if d['source']['selector']['metric'] == 'mean']
    assert len(ds) == 2 and sorted(len(prepared(d)[0]) for d in ds) == [1,3]
    p['fields'][-1]['batch_id'] = 'batch1'
    p['fields'][-2]['bio_id'] = 'A1'
    d = next(d for d in if_tables(p) if d['source']['selector'] == {'channel':'DAPI','batch':'batch1','metric':'mean'})
    d['confirmed'] = True; d['analysis']['method'] = 'welch'
    with pytest.raises(ValueError, match='共享'): analyze(d)


def test_preview_confirmation_checks_source_version(tmp_path, session):
    p = if_project(tmp_path, session); c = dispatch('stats_source_catalog', {'path':p['project_path']}, session)
    p['name'] = 'changed'; p['revision'] += 1; save_if(p, p['project_path'], p['saved_revision'], session)
    args = dict(path=c['path'],keys=[choose(c,'mean')['key']],expected_signature=c['signature'],confirmed=True)
    with pytest.raises(ValueError,match='来源已改变'): dispatch('stats_from_source', args, session)


def test_source_status_update_preserves_history_styles_and_source_readonly(tmp_path, session):
    p = if_project(tmp_path, session); stats = read(p, session); d = stats['datasets'][0]
    d['analysis']['method'] = 'welch'; d['runs'].append(analyze(d)); d['style']['colors'][d['groups'][0]['id']] = '#123456'
    stats['figures'].append(dict(id='frozen',name='冻结图',dataset=copy.deepcopy(d),run=d['runs'][0],style=copy.deepcopy(d['style'])))
    stats['revision'] += 1; stats = dispatch('stats_save', {'project':stats}, session)
    frozen = copy.deepcopy(stats['figures']); source_bytes = (Path(p['project_path'])/'project.json').read_bytes()
    assert dispatch('stats_source_status', {'source':d['source']}, session)['state'] == 'current'
    assert (Path(p['project_path'])/'project.json').read_bytes() == source_bytes
    p['fields'][0]['channels'][0]['display_max'] = 200; p['revision'] += 1
    p = save_if(p, p['project_path'], p['saved_revision'], session)
    assert dispatch('stats_source_status', {'source':d['source']}, session)['state'] == 'current'
    p['fields'][0]['result']['summary'][0]['raw_sum'] = 200; p['revision'] += 1
    p = save_if(p, p['project_path'], p['saved_revision'], session)
    assert dispatch('stats_source_status', {'source':d['source']}, session)['state'] == 'changed'
    updated = dispatch('stats_update_source', {'project':stats,'dataset_id':d['id']}, session); fresh=updated['datasets'][0]
    assert updated['figures'] == frozen and fresh['runs'] == d['runs']
    assert fresh['style']['colors'] == d['style']['colors'] and fresh['groups'] == d['groups']
    assert signature(fresh) != fresh['runs'][0]['signature']
    invalid = copy.deepcopy(updated); invalid['datasets'][0]['rows'][0]['values'][fresh['groups'][0]['id']] = '999'; invalid['revision'] += 1
    with pytest.raises(ValueError,match='来源表'):dispatch('stats_save', {'project':invalid}, session)
    appended = read(p, session, target=updated)
    assert len(appended['datasets']) == 1


def test_missing_or_replaced_source_preserves_stored_statistics(tmp_path, session):
    p = if_project(tmp_path, session); stats = read(p, session); source = stats['datasets'][0]['source']
    manifest=Path(p['project_path'])/'project.json'; data=json.loads(manifest.read_text()); data['id']='different';manifest.write_text(json.dumps(data))
    assert dispatch('stats_source_status', {'source':source}, session)['state'] == 'unavailable'
    with pytest.raises(ValueError,match='不同项目'):dispatch('stats_update_source', {'project':stats,'dataset_id':stats['datasets'][0]['id']}, session)
    manifest.unlink()
    assert dispatch('stats_open', {'path':stats['project_path']}, session)['datasets'][0]['rows'] == stats['datasets'][0]['rows']


def test_wb_saved_project_can_select_one_endpoint_and_keep_pair_ids(tmp_path, session):
    from titan_wb.demo import make_demo
    from titan_wb.projects import save_project
    p = save_project(make_demo(), str(tmp_path/'wb.titanwb'), None, session)
    c = dispatch('stats_source_catalog', {'path':p['project_path']}, session)
    assert c['kind'] == 'wb' and c['choices']
    choice = c['choices'][0]
    imported = dispatch('stats_from_source', dict(path=c['path'],keys=[choice['key']],expected_signature=c['signature'],confirmed=True), session)
    assert len(imported['datasets']) == 1
    d = imported['datasets'][0]
    assert d['source']['kind'] == 'wb' and d['source']['locked']
    assert len(prepared(d)[0]) == choice['n']
    assert all(r['label']==(r['origin'].get('pair_id') or r['origin']['bio_id']) for r in d['rows'])


def test_registered_if_snapshot_follows_relocated_entry_and_inherits_group(tmp_path, session):
    from titan_wb.library import library_create_collection, library_register, library_list

    source = if_project(tmp_path, session)
    group = library_create_collection('联合课题', session)
    entry = library_register(source['project_path'], session)
    from titan_wb.library import library_assign
    library_assign(entry['entry_id'], group['id'], session)
    stats = read(source, session)
    table = stats['datasets'][0]
    assert table['source']['entry_id'] == entry['entry_id']
    stats_entry = next(row for row in library_list(session) if row['module'] == 'stats')
    assert stats_entry['collection_id'] == group['id']

    old = Path(source['project_path'])
    moved = old.rename(tmp_path / 'relocated.titanif')
    library_register(str(moved), session, entry['entry_id'])
    old.mkdir()
    (old/'project.json').write_text(json.dumps(dict(id='replacement', name='另一分析', module='if')))
    assert dispatch('stats_source_status', {'source': table['source']}, session)['state'] == 'current'
    refreshed = dispatch('stats_update_source', {'project': stats, 'dataset_id': table['id']}, session)
    assert refreshed['datasets'][0]['source']['path'] == str(moved)


@pytest.mark.parametrize('keep_channel', [True, False])
def test_missing_marker_in_sibling_view_prevents_partial_sample(tmp_path, session, keep_channel):
    p = if_project(tmp_path, session)
    field = p['fields'][1]
    field['recipe']['target_channel_ids'] = []
    if not keep_channel:
        field['channels'][0]['name'] = 'different marker'
    field['result'] = None
    d = next(d for d in if_tables(p) if d['source']['selector'] ==
             {'channel': 'DAPI', 'batch': 'batch1', 'metric': 'mean'})
    sample = next(row for row in d['source']['records'] if row['bio_id'] == 'A1')
    assert sample['value'] is None and sample['field_count'] == 2


def test_relocation_keeps_signature_of_authoritative_if_result(tmp_path, session):
    from titan_if.jobs import stage_result
    from titan_wb.library import library_register

    p = if_project(tmp_path, session)
    staging = tmp_path / 'staged'
    staging.mkdir()
    for field in p['fields']:
        field['result'] = stage_result(field['result'], staging)
    p['revision'] += 1
    p = save_if(p, p['project_path'], p['saved_revision'], session)
    entry = library_register(p['project_path'], session)
    source = read(p, session)['datasets'][0]['source']
    moved = Path(p['project_path']).rename(tmp_path / 'moved.titanif')
    library_register(str(moved), session, entry['entry_id'])
    assert dispatch('stats_source_status', {'source': source}, session)['state'] == 'current'


def test_pooled_if_integer_keeps_precision_in_statistical_snapshot(tmp_path, session):
    p = if_project(tmp_path, session)
    p['fields'][0]['result']['summary'][0]['raw_sum'] = 2**52 + 1
    p['fields'][1]['result']['summary'][0]['raw_sum'] = 2**52
    record = next(d for d in if_tables(p) if d['source']['selector']['metric'] == 'mean')['source']['records'][0]
    assert record['pooled']['raw_sum'] == '9007199254740993'


def test_legacy_large_if_provenance_remains_saveable_and_exportable(tmp_path, session):
    source = if_project(tmp_path, session)
    project = read(source, session)
    manifest = Path(project['project_path']) / 'project.json'
    legacy = json.loads(manifest.read_text(encoding='utf-8'))
    dataset = legacy['datasets'][0]
    dataset['source'].pop('signature_version', None)
    dataset['source']['records'][0]['pooled']['raw_sum'] = 9007199254740993
    dataset['analysis']['method'] = 'welch'
    run = analyze(dataset)
    dataset['runs'].append(run)
    legacy['figures'].append(dict(id='old-figure', name='旧图', dataset=copy.deepcopy(run['dataset']),
                                  style=dataset['style'], run=copy.deepcopy(run)))
    manifest.write_text(json.dumps(legacy), encoding='utf-8')
    before = manifest.read_bytes()
    opened = dispatch('stats_open', {'path': project['project_path']}, session)
    assert manifest.read_bytes() == before
    active = opened['datasets'][0]
    assert active['source']['records'][0]['pooled']['raw_sum'] == '9007199254740993'
    assert signature(active) == active['runs'][0]['signature']
    opened['name'] = '保留精度后另命名'
    opened['revision'] += 1
    saved = dispatch('stats_save', {'project': opened}, session)
    dest = tmp_path/'legacy-export'
    dispatch('stats_export', dict(project=saved, dataset=active, style=active['style'],
             figure_id='old-figure', destination=str(dest)), session)
    assert (dest/'results.xlsx').is_file()
