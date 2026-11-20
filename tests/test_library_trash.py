import os
from pathlib import Path

import pytest

from titan_wb.engine import dispatch
from titan_wb.projects import open_project


@pytest.fixture
def call(tmp_path):
    session = dict(pid=os.getpid(), token='trash-test', library_root=str(tmp_path / 'library'))

    def invoke(command, **payload):
        return dispatch(dict(command=command, payload=payload, session=session))
    return invoke


def test_delete_managed_analysis_and_restore_original_identity(call):
    project = call('library_create_collection', name='A')
    created = call('library_create', name='WB', collection_id=project['id'])
    entry = created['entry']
    path = Path(entry['path'])
    manifest = (path / 'project.json').read_bytes()
    assert entry['managed']
    call('library_trash_analysis', entry_id=entry['entry_id'], path=str(path))
    assert not path.exists()
    assert call('library_workspace')['entries'] == []
    [deleted] = call('library_trash')
    call('library_restore_deleted', id=deleted['id'])
    assert (path / 'project.json').read_bytes() == manifest
    [restored] = call('library_workspace')['entries']
    assert restored['entry_id'] == entry['entry_id']
    assert restored['collection_id'] == project['id']
    assert call('library_trash') == []


def test_delete_project_preserves_analyses_and_recovers_material_copy(tmp_path, call):
    source = tmp_path / 'source.csv'
    source.write_text('sample,value\n1,4\n')
    project = call('library_create_collection', name='A')
    [material] = call('library_material_add', collection_id=project['id'], paths=[str(source)])
    [copy] = call('library_material_paths', collection_id=project['id'], material_ids=[material['id']])
    created = call('library_create', name='WB', collection_id=project['id'])
    call('library_trash_collection', id=project['id'])
    assert not Path(copy).exists()
    assert source.is_file() and Path(created['entry']['path']).is_dir()
    workspace = call('library_workspace')
    assert workspace['projects'] == [] and workspace['entries'][0]['collection_id'] is None
    [deleted] = call('library_trash')
    call('library_restore_deleted', id=deleted['id'])
    assert Path(copy).read_bytes() == source.read_bytes()
    assert call('library_workspace')['entries'][0]['collection_id'] is None


def test_recoverable_deregistration_preserves_external_file(tmp_path, call):
    created = call('library_create', name='WB')
    path = str(tmp_path / 'external.titanwb')
    call('save_project', project=created['project'], path=path)
    entry = call('library_register', path=path)
    assert not entry['managed']
    call('library_trash_analysis', entry_id=entry['entry_id'], path=path)
    assert Path(path).is_dir()
    [deleted] = call('library_trash')
    call('library_restore_deleted', id=deleted['id'])
    assert any(item['entry_id']==entry['entry_id'] for item in call('library_workspace')['entries'])


def test_delete_rejects_stale_target_and_foreign_writer(tmp_path, call):
    created = call('library_create', name='WB')
    entry = created['entry']
    path = Path(entry['path'])
    with pytest.raises(ValueError, match='位置'):
        call('library_trash_analysis', entry_id=entry['entry_id'], path=str(tmp_path/'elsewhere.titanwb'))
    call('release_project', path=str(path))
    open_project(str(path), dict(pid=os.getpid(), token='foreign-writer'))
    with pytest.raises(ValueError, match='写入'):
        call('library_trash_analysis', entry_id=entry['entry_id'], path=str(path))
    assert path.is_dir() and call('library_trash') == []


def test_interrupted_move_recovers_the_directory_before_listing(monkeypatch, call):
    from titan_wb import library_trash

    created = call('library_create', name='WB')
    entry = created['entry']
    path = Path(entry['path'])
    manifest = (path / 'project.json').read_bytes()
    call('release_project', path=str(path))
    write = library_trash.atomic_json

    def interrupt_index_write(destination, value):
        if destination.name == 'index.json':
            raise KeyboardInterrupt
        return write(destination, value)

    with monkeypatch.context() as patch:
        patch.setattr(library_trash, 'atomic_json', interrupt_index_write)
        with pytest.raises(KeyboardInterrupt):
            call('library_trash_analysis', entry_id=entry['entry_id'], path=str(path))
        assert not path.exists()
    [recovered] = call('library_workspace')['entries']
    assert recovered['entry_id'] == entry['entry_id'] and recovered['available']
    assert (path / 'project.json').read_bytes() == manifest
    assert not (path / '.writer.lock').exists()
    assert call('library_trash') == []


def test_managed_analysis_from_imported_bundle_can_be_deleted_and_restored(tmp_path, call):
    project = call('library_create_collection', name='A')
    call('library_create', name='WB', collection_id=project['id'])
    bundle = str(tmp_path / 'project.titanproject')
    call('library_export_bundle', collection_id=project['id'], destination=bundle)
    imported = call('library_import_bundle', path=bundle)
    [entry] = [entry for entry in call('library_workspace')['entries'] if entry['collection_id'] == imported['id']]
    path = Path(entry['path'])
    assert entry['managed']
    call('library_trash_analysis', entry_id=entry['entry_id'], path=str(path))
    assert not path.exists()
    [deleted] = call('library_trash')
    call('library_restore_deleted', id=deleted['id'])
    assert (path / 'project.json').is_file()


@pytest.mark.parametrize('create,save', [('library_create','save_project'),('if_new','if_save'),('stats_new','stats_save')])
def test_stale_autosave_cannot_recreate_a_deleted_analysis(call, create, save):
    created=call(create, name='analysis')
    project=created['project'] if create=='library_create' else created
    [entry]=call('library_workspace')['entries']
    path=Path(entry['path'])
    call('library_trash_analysis', entry_id=entry['entry_id'], path=str(path))
    with pytest.raises(ValueError, match='已移除'):
        call(save, project=project, path=str(path), expected_revision=project['saved_revision'])
    assert not path.exists()
    [deleted]=call('library_trash')
    call('library_restore_deleted', id=deleted['id'])
    assert (path/'project.json').is_file()
