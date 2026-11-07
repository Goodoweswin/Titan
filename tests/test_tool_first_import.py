import hashlib
import os
from pathlib import Path

import numpy as np
import pytest
import tifffile

from titan_wb.engine import dispatch


@pytest.fixture
def engine(tmp_path):
    session = dict(pid=os.getpid(), token='first-import', library_root=str(tmp_path / 'library'))

    def run(command, **payload):
        return dispatch(dict(command=command, payload=payload, session=session))

    return run


@pytest.fixture
def wb_draft(engine, tmp_path):
    source = tmp_path / 'blot.tif'
    with tifffile.TiffWriter(source) as output:
        for value in (20, 240):
            output.write(np.full((10, 12), value, np.uint16))
    draft = engine('new_project', name='WB 原图')
    return source, engine('import_image', project=draft, path=str(source), page_index=1)


@pytest.fixture
def if_import(tmp_path):
    source = tmp_path / 'microscopy.ome.tif'
    tifffile.imwrite(source, np.full((2, 10, 12), 20, np.uint16),
                     photometric='minisblack', metadata={'axes': 'CYX'})
    selections = [dict(path=str(source), series_index=0, channel_indices=[1], indexers={})]
    metadata = dict(name='视野', sample_id='S1', bio_id='B1', group='control', batch_id='batch1')
    return source, dict(selections=selections, metadata=metadata)


def assert_empty_library(engine, tmp_path):
    assert engine('library_list') == []
    assert list((tmp_path / 'library' / 'Projects').glob('*')) == []


def test_wb_first_import_persists_selected_page_in_chosen_project(engine, wb_draft):
    source, draft = wb_draft
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    collection = engine('library_create_collection', name='WB 课题')
    saved = engine('library_create_from_wb', project=draft, collection_id=collection['id'])
    project = engine('open_project', path=saved['project']['project_path'])
    source.unlink()

    entry, = engine('library_list')
    assert entry['entry_id'] == saved['entry']['entry_id']
    assert entry['collection_id'] == collection['id']
    assert project['id'] == draft['id']
    assert project['saved_revision'] == project['revision'] == 1
    image, = project['images']
    assert (image['page_index'], image['page_count'], image['sha256']) == (1, 2, digest)
    assert Path(image['path']).is_relative_to(Path(project['project_path']) / 'originals')
    from titan_wb.images import read_source_pixels
    assert np.all(read_source_pixels(image) == 240)


def test_wb_empty_draft_cannot_create_managed_analysis(engine, tmp_path):
    with pytest.raises(ValueError, match='导入'):
        engine('library_create_from_wb', project=engine('new_project', name='空白'))
    assert_empty_library(engine, tmp_path)


def test_wb_changed_source_cannot_create_managed_analysis(engine, wb_draft, tmp_path):
    source, draft = wb_draft
    source.write_bytes(b'changed')
    with pytest.raises(ValueError, match='原图|原始文件'):
        engine('library_create_from_wb', project=draft)
    assert_empty_library(engine, tmp_path)


def test_wb_first_import_requires_a_selected_page_for_multipage_tiff(engine, wb_draft, tmp_path):
    _, draft = wb_draft
    draft['images'][0].pop('page_index')
    with pytest.raises(ValueError, match='多页'):
        engine('library_create_from_wb', project=draft)
    assert_empty_library(engine, tmp_path)


def test_wb_saved_project_cannot_be_registered_as_a_first_import(engine, wb_draft, tmp_path):
    _, draft = wb_draft
    saved = engine('save_project', project=draft, path=str(tmp_path / 'outside.titanwb'))
    with pytest.raises(ValueError, match='未保存'):
        engine('library_create_from_wb', project=saved)
    assert_empty_library(engine, tmp_path)


def test_wb_first_import_cannot_write_outside_managed_projects(engine, wb_draft, tmp_path):
    _, draft = wb_draft
    draft['id'] = '../../outside'
    with pytest.raises(ValueError, match='身份'):
        engine('library_create_from_wb', project=draft)
    assert_empty_library(engine, tmp_path)
    assert not (tmp_path / 'outside.titanwb').exists()


def test_if_first_import_is_saved_with_selected_channel_and_sample(engine, if_import):
    source, imported = if_import
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    collection = engine('library_create_collection', name='IF 课题')
    saved = engine('if_new_from_import', name='IF 原图', collection_id=collection['id'], **imported)
    source.unlink()

    entry, = engine('library_list')
    assert (entry['module'], entry['collection_id']) == ('if', collection['id'])
    project = engine('if_open', path=saved['project_path'], entry_id=entry['entry_id'])
    assert project['saved_revision'] == project['revision']
    field, = project['fields']
    assert field['sample_id'] == 'S1'
    assert field['bio_id'] == 'B1'
    channel, = field['channels']
    assert channel['source']['indexers'] == {'C': 1}
    assert channel['source']['sha256'] == digest
    assert Path(channel['source']['path']).is_relative_to(Path(project['project_path']) / 'originals')


def test_if_rejects_changed_project_material_after_inspection(engine, if_import, tmp_path):
    source, imported = if_import
    imported['selections'][0]['expected_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    tifffile.imwrite(source, np.full((2, 10, 12), 50, np.uint16),
                     photometric='minisblack', metadata={'axes': 'CYX'})
    with pytest.raises(ValueError, match='项目资料副本已变化'):
        engine('if_new_from_import', name='被替换的资料', **imported)
    assert_empty_library(engine, tmp_path)


def test_if_invalid_channel_does_not_create_managed_analysis(engine, if_import, tmp_path):
    _, imported = if_import
    imported['selections'][0]['channel_indices'] = [2]
    with pytest.raises(ValueError, match='channel index'):
        engine('if_new_from_import', name='IF 无效', **imported)
    assert_empty_library(engine, tmp_path)


def test_if_first_import_requires_sample_metadata(engine, if_import, tmp_path):
    _, imported = if_import
    imported['metadata']['batch_id'] = ''
    with pytest.raises(ValueError, match='样本|批次'):
        engine('if_new_from_import', name='IF 缺样本信息', **imported)
    assert_empty_library(engine, tmp_path)


def test_stats_first_import_persists_inspected_table_and_provenance(engine, tmp_path):
    source = tmp_path / 'values.csv'
    source.write_text('id,A,B\nS1,3,7\n', encoding='utf-8')
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    imported = engine('stats_import', path=str(source))['dataset']
    source.unlink()
    saved = engine('stats_new_from_import', name='统计数据', dataset=imported)

    entry, = engine('library_list')
    assert (entry['module'], entry['collection_id']) == ('stats', None)
    project = engine('stats_open', path=saved['project_path'], entry_id=entry['entry_id'])
    dataset, = project['datasets']
    assert dataset == imported
    assert dataset['source'] == dict(kind='file', path=str(source), sha256=digest)


@pytest.mark.parametrize(('text', 'value', 'error'), [
    ('id,A,B\nS1,,', None, '数值'),
    ('id,A,B\nS1,3,7', 'not a number', '数值'),
])
def test_stats_invalid_observations_do_not_create_managed_analysis(engine, tmp_path, text, value, error):
    imported = engine('stats_import', text=text)['dataset']
    if value is not None:
        imported['rows'][0]['values'][imported['groups'][0]['id']] = value
    with pytest.raises(ValueError, match=error):
        engine('stats_new_from_import', name='统计数据', dataset=imported)
    assert_empty_library(engine, tmp_path)
