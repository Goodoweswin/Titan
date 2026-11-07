import copy
import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

from titan_stats.models import signature
from titan_wb import library
from titan_wb.analysis import analyze
from titan_wb.engine import dispatch
from titan_wb.projects import save_project
from test_lane_results import fixture as wb_fixture
from test_stats_sources import if_project, read


def library_session(root):
    return dict(pid=os.getpid(), token=root.name, library_root=str(root))


def call(session, command, **payload):
    return dispatch(dict(command=command, payload=payload, session=session))


def export_bundle(session, collection, path):
    assert call(session, 'library_export_bundle', collection_id=collection['id'], destination=str(path)) == str(path)
    return path


def import_bundle(session, path):
    return call(session, 'library_import_bundle', path=str(path))


def attach(session, collection, project):
    entry = library.library_register(project['project_path'], session)
    library.library_assign(entry['entry_id'], collection['id'], session)
    return entry


def test_bundle_restores_saved_analyses_figures_materials_and_registered_outputs(tmp_path):
    source = library_session(tmp_path / 'old-library')
    target = library_session(tmp_path / 'new-library')
    collection = library.library_create_collection('衰老课题', source)
    material = tmp_path / '设计.csv'
    material.write_text('group,value\ncontrol,10\n', encoding='utf-8')
    call(source, 'library_material_add', collection_id=collection['id'], paths=[str(material)])
    material.unlink()

    wb = save_project(wb_fixture(tmp_path), str(tmp_path / 'source.titanwb'), None, source)
    wb_entry = attach(source, collection, wb)
    results = analyze(wb)
    output = tmp_path / 'exported'
    publication = call(source, 'export', project=wb, result=results, destination=str(output))
    figure = call(source, 'save_figure', project=wb, result=results, name='WB 冻结图',
                  export_origin=dict(path=str(output), png_sha256=publication['outputs']['plot.png']))
    strip = call(source, 'wb_new', project=wb)
    for row in strip['rows']:
        row.update(crop=[1, 1, 12, 15], confirmed=True)
    strip = call(source, 'wb_save', project=wb, document=strip)
    library.library_set_resume(wb_entry['entry_id'], dict(view='figure', artifact_id=figure['id'],
                                                         version_id=figure['current_version']), source)
    original_export = (output / 'results.xlsx').read_bytes()
    wb['name'] = '未保存的修改'

    fluorescence = if_project(tmp_path, source, nuclear=True)
    fluorescence['figure'].update(crop=[1, 1, 8, 8], field_ids=['f0'])
    fluorescence['revision'] += 1
    fluorescence = call(source, 'if_save', project=fluorescence)
    attach(source, collection, fluorescence)
    stats = read(fluorescence, source)
    d = stats['datasets'][0]
    run = call(source, 'stats_analyze', dataset=d)
    d['runs'].append(run)
    stats['figures'].append(dict(id='if-snapshot', name='IF 冻结图', dataset=run['dataset'],
                                 run=run, style=d['style'], source_revision=0))
    stats['revision'] += 1
    call(source, 'stats_save', project=stats)

    bundle = export_bundle(source, collection, tmp_path / 'shared.titanproject')
    for folder in (source['library_root'], wb['project_path'], fluorescence['project_path'], output):
        shutil.rmtree(folder)
    moved_bundle = bundle.rename(tmp_path / 'moved.titanproject')
    restored = import_bundle(target, moved_bundle)
    assert restored['id'] != collection['id'] and restored['name'] == '衰老课题'
    material_path, = call(target, 'library_material_paths', collection_id=restored['id'],
                          material_ids=[restored['materials'][0]['id']])
    assert Path(material_path).read_text(encoding='utf-8') == 'group,value\ncontrol,10\n'

    entries = {entry['module']: entry for entry in library.library_list(target)}
    assert set(entries) == {'wb', 'if', 'stats'}
    assert {entry['collection_id'] for entry in entries.values()} == {restored['id']}
    assert entries['wb']['entry_id'] != wb_entry['entry_id']
    assert entries['wb']['resume']['version_id'] == figure['current_version']
    assert entries['wb']['name'] != wb['name']
    wb_path = entries['wb']['path']
    restored_wb = call(target, 'open_project', path=wb_path)
    assert restored_wb['id'] == wb['id'] and analyze(restored_wb)['lane_results'][0]['normalized'] == 4
    assert call(target, 'wb_load', project=restored_wb, document_id=strip['id'])['rows'][0]['crop'] == [1, 1, 12, 15]
    saved_figure = call(target, 'load_figure', path=wb_path, figure_id=figure['id'])
    assert saved_figure['result']['lane_results'][0]['normalized'] == 4
    artifact = next(a for a in entries['wb']['artifacts'] if a['kind'] == 'result_export')
    assert artifact['version_id'] == figure['current_version']
    assert Path(library.library_target(entries['wb']['entry_id'], artifact['id'], target)).read_bytes() == original_export

    restored_if = call(target, 'if_open', path=entries['if']['path'], entry_id=entries['if']['entry_id'])
    assert restored_if['id'] == fluorescence['id']
    assert restored_if['figure']['crop'] == [1, 1, 8, 8]
    assert Path(restored_if['fields'][0]['mask']['path']).is_file()
    restored_stats = call(target, 'stats_open', path=entries['stats']['path'], entry_id=entries['stats']['entry_id'])
    assert restored_stats['id'] == stats['id']
    table = restored_stats['datasets'][0]
    assert table['rows'] == d['rows']
    assert table['source']['entry_id'] == entries['if']['entry_id']
    assert table['source']['path'] == entries['if']['path']
    assert call(target, 'stats_source_status', source=table['source'])['state'] == 'current'
    assert table['runs'][0]['signature'] == signature(table)
    frozen = restored_stats['figures'][0]
    assert frozen['run']['signature'] == signature(frozen['dataset'])


def test_bundle_freezes_external_links_even_when_originals_are_available(tmp_path):
    source = library_session(tmp_path / 'library')
    collection = library.library_create_collection('统计课题', source)
    external = if_project(tmp_path, source)
    library.library_register(external['project_path'], source)
    stats = read(external, source)
    attach(source, collection, stats)
    table = stats['datasets'][0]
    table['runs'].append(call(source, 'stats_analyze', dataset=table))
    stale = copy.deepcopy(table['runs'][0]); stale['signature'] = 'historically-stale'
    table['runs'].append(stale)
    stats['revision'] += 1
    call(source, 'stats_save', project=stats)

    bundle = export_bundle(source, collection, tmp_path / 'snapshot.titanproject')
    restored = import_bundle(source, bundle)
    entry = next(row for row in library.library_list(source) if row['collection_id'] == restored['id'])
    opened = call(source, 'stats_open', path=entry['path'], entry_id=entry['entry_id'])
    d = opened['datasets'][0]
    assert not d['source'].get('entry_id') and not d['source'].get('path')
    assert d['source']['locked'] and d['source']['records'] == table['source']['records']
    assert call(source, 'stats_source_status', source=d['source'])['state'] == 'unavailable'
    assert d['runs'][0]['signature'] == signature(d)
    assert d['runs'][1]['signature'] == 'historically-stale'


@pytest.mark.parametrize('damage', ['missing', 'symlink', 'changed', 'wrong_identity'])
def test_bundle_rejects_invalid_saved_inputs_without_touching_target(tmp_path, damage):
    source = library_session(tmp_path / 'old-library')
    target = library_session(tmp_path / 'new-library')
    collection = library.library_create_collection('课题', source)
    wb = save_project(wb_fixture(tmp_path), str(tmp_path / 'source.titanwb'), None, source)
    attach(source, collection, wb)
    existing = library.library_create('已有分析', target)
    old_index = Path(target['library_root'], 'index.json').read_bytes()
    bundle = export_bundle(source, collection, tmp_path / 'bad.titanproject')
    manifest, = bundle.rglob('project.json')
    original, = (manifest.parent / 'originals').iterdir()
    if damage == 'wrong_identity':
        data = json.loads(manifest.read_bytes()); data['id'] = 'different'
        manifest.write_text(json.dumps(data), encoding='utf-8')
    elif damage == 'changed':
        original.write_bytes(b'changed')
    else:
        original.unlink()
        if damage == 'symlink':
            original.symlink_to(wb['images'][0]['path'])
    with pytest.raises(ValueError):
        import_bundle(target, bundle)
    assert Path(target['library_root'], 'index.json').read_bytes() == old_index
    assert list(Path(target['library_root'], 'Projects').iterdir()) == [Path(existing['entry']['path'])]


def test_bundle_preserves_existing_destination(tmp_path):
    session = library_session(tmp_path / 'library')
    collection = library.library_create_collection('课题', session)
    destination = tmp_path / 'existing.titanproject'
    destination.mkdir()
    with pytest.raises(ValueError):
        call(session, 'library_export_bundle', collection_id=collection['id'], destination=str(destination))
    assert destination.is_dir() and not list(destination.iterdir())
    bundle = export_bundle(session, collection, tmp_path / 'empty.TITANPROJECT')
    assert import_bundle(session, bundle)['name'] == '课题'


@pytest.mark.parametrize('field', ['path', 'image_id'])
def test_bundle_rejects_unsafe_analysis_paths_even_with_matching_hash(tmp_path, field):
    source = library_session(tmp_path / 'source-library')
    target = library_session(tmp_path / 'target-library')
    collection = library.library_create_collection('课题', source)
    wb = save_project(wb_fixture(tmp_path), str(tmp_path / 'source.titanwb'), None, source)
    attach(source, collection, wb)
    bundle = export_bundle(source, collection, tmp_path / 'bad.titanproject')
    manifest, = bundle.rglob('project.json')
    data = json.loads(manifest.read_bytes())
    if field == 'path':
        original, = (manifest.parent / 'originals').iterdir()
        data['images'][0]['path'] = 'originals/../originals/' + original.name
    else:
        data['images'][0]['id'] = '../../../escaped'
        for row in data['rois'] + data['lane_layouts']:
            row['image_id'] = '../../../escaped'
    manifest.write_text(json.dumps(data), encoding='utf-8')
    envelope = bundle / 'bundle.json'
    header = json.loads(envelope.read_bytes())
    header['entries'][0]['hashes']['project.json'] = hashlib.sha256(manifest.read_bytes()).hexdigest()
    envelope.write_text(json.dumps(header), encoding='utf-8')
    with pytest.raises(ValueError, match='路径|图像标识'):
        import_bundle(target, bundle)
    assert library.library_workspace(target) == {'projects': [], 'entries': []}


def test_bundle_index_failure_rolls_back_all_managed_copies(tmp_path, monkeypatch):
    source = library_session(tmp_path / 'source-library')
    target = library_session(tmp_path / 'target-library')
    collection = library.library_create_collection('课题', source)
    material = tmp_path / 'plan.csv'
    material.write_text('A\n1\n')
    call(source, 'library_material_add', collection_id=collection['id'], paths=[str(material)])
    library.library_create('原分析', source, collection_id=collection['id'])
    existing = library.library_create('已有分析', target)
    index = Path(target['library_root'], 'index.json')
    before = index.read_bytes()
    bundle = export_bundle(source, collection, tmp_path / 'saved.titanproject')

    with monkeypatch.context() as patch:
        def fail_index(path, data):
            raise OSError('index write failed')

        patch.setattr(library, 'atomic_json', fail_index)
        with pytest.raises(OSError, match='index write failed'):
            import_bundle(target, bundle)
    assert index.read_bytes() == before
    assert list(Path(target['library_root'], 'Projects').iterdir()) == [Path(existing['entry']['path'])]
    assert not list(Path(target['library_root'], 'Materials').iterdir())
    import_bundle(target, bundle)
    assert len(library.library_list(target)) == 2


def test_bundle_export_refuses_symlinked_analysis_lock(tmp_path):
    session = library_session(tmp_path / 'library')
    collection = library.library_create_collection('课题', session)
    stats = call(session, 'stats_new', name='统计', collection_id=collection['id'])
    unrelated = tmp_path / 'unrelated.txt'
    unrelated.touch()
    lock = Path(stats['project_path'], '.save.lock')
    lock.unlink()
    lock.symlink_to(unrelated)
    destination = tmp_path / 'unsafe.titanproject'
    with pytest.raises(ValueError):
        export_bundle(session, collection, destination)
    assert unrelated.read_bytes() == b''
    assert not destination.exists()
