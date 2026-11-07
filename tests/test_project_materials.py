import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from titan_wb.engine import dispatch


@pytest.fixture
def material_library(tmp_path):
    root = tmp_path / 'library'

    def call(command, **payload):
        return dispatch(dict(command=command, payload=payload, session={'library_root': str(root)}))

    return call, root


def test_materials_are_independent_copies_in_the_requested_order(tmp_path, material_library):
    call, root = material_library
    project = call('library_create_collection', name='课题')['id']
    original_folder = tmp_path / 'outside'
    original_folder.mkdir()
    first = original_folder / '原始图像.tiff'
    second = original_folder / 'data.csv'
    first.write_bytes(b'raw image')
    second.write_bytes(b'x,y\n1,2\n')

    materials = call('library_material_add', collection_id=project, paths=[str(first), str(second)])
    assert [row['name'] for row in materials] == [first.name, second.name]
    assert all(row.keys() == {'id', 'name', 'size', 'sha256', 'added_at'} for row in materials)
    assert materials[0]['size'] == 9
    assert materials[0]['sha256'] == hashlib.sha256(b'raw image').hexdigest()
    assert call('library_workspace')['projects'][0]['materials'] == materials
    assert str(original_folder) not in (root / 'index.json').read_text()
    first.unlink()
    second.unlink()

    paths = [Path(path) for path in call('library_material_paths', collection_id=project,
                                        material_ids=[materials[1]['id'], materials[0]['id']])]
    assert [path.name for path in paths] == ['data.csv', '原始图像.tiff']
    assert [path.read_bytes() for path in paths] == [b'x,y\n1,2\n', b'raw image']
    assert all(path.is_relative_to(root.resolve()) for path in paths)


def test_projects_cannot_access_each_others_materials(tmp_path, material_library):
    call, _ = material_library
    first = call('library_create_collection', name='甲')['id']
    second = call('library_create_collection', name='乙')['id']
    file = tmp_path / 'notes.txt'
    file.write_text('data')
    first_record, = call('library_material_add', collection_id=first, paths=[str(file)])
    second_record, = call('library_material_add', collection_id=second, paths=[str(file)])

    with pytest.raises(ValueError, match='资料'):
        call('library_material_paths', collection_id=second, material_ids=[first_record['id']])
    with pytest.raises(ValueError, match='资料'):
        call('library_material_remove', collection_id=first, material_id=second_record['id'])
    assert first_record['id'] != second_record['id']


def test_legacy_project_index_reads_without_rewriting_and_accepts_materials(tmp_path, material_library):
    call, root = material_library
    legacy_id = '../../old/project'
    root.mkdir()
    index = root / 'index.json'
    index.write_text(json.dumps({'version': 1, 'entries': [], 'projects': [
        {'id': legacy_id, 'name': 'old', 'created_at': '2024-01-01', 'pinned': True},
    ]}))
    before = index.read_bytes()

    assert call('library_workspace')['projects'][0].get('materials', []) == []
    assert call('library_material_paths', collection_id=legacy_id, material_ids=[]) == []
    assert index.read_bytes() == before

    original = tmp_path / 'legacy.txt'
    original.write_text('legacy material')
    material, = call('library_material_add', collection_id=legacy_id, paths=[str(original)])
    path, = call('library_material_paths', collection_id=legacy_id, material_ids=[material['id']])
    assert Path(path).is_relative_to(root.resolve())
    assert call('library_workspace')['projects'][0]['id'] == legacy_id


def test_material_add_rolls_back_a_failed_batch(tmp_path, material_library):
    call, root = material_library
    project = call('library_create_collection', name='课题')['id']
    index = root / 'index.json'
    before = index.read_bytes()
    original = tmp_path / 'sample.csv'
    original.write_text('data')

    with pytest.raises(ValueError, match='资料|文件'):
        call('library_material_add', collection_id=project, paths=[str(original), str(tmp_path / 'missing')])

    assert index.read_bytes() == before
    assert {path.name for path in root.rglob('*') if path.is_file()} == {'.index.lock', 'index.json'}
    assert original.read_text() == 'data'


def test_material_add_rolls_back_copies_when_index_commit_fails(tmp_path, material_library, monkeypatch):
    from titan_wb import library

    call, root = material_library
    project = call('library_create_collection', name='课题')['id']
    index = root / 'index.json'
    before = index.read_bytes()
    original = tmp_path / 'sample.csv'
    original.write_text('data')

    def fail_index(*args):
        raise OSError('index commit failed')

    with monkeypatch.context() as patch:
        patch.setattr(library, 'atomic_json', fail_index)
        with pytest.raises(OSError, match='index commit failed'):
            call('library_material_add', collection_id=project, paths=[str(original)])

    assert index.read_bytes() == before
    assert {path.name for path in root.rglob('*') if path.is_file()} == {'.index.lock', 'index.json'}
    record, = call('library_material_add', collection_id=project, paths=[str(original)])
    assert call('library_workspace')['projects'][0]['materials'] == [record]


@pytest.mark.parametrize('problem', ['changed', 'missing', 'symlink'])
def test_unusable_material_copies_remain_listed(tmp_path, material_library, problem):
    call, _ = material_library
    project = call('library_create_collection', name='课题')['id']
    original = tmp_path / 'image.tiff'
    original.write_bytes(b'1234')
    material, = call('library_material_add', collection_id=project, paths=[str(original)])
    path, = call('library_material_paths', collection_id=project, material_ids=[material['id']])
    managed = Path(path)
    if problem == 'changed':
        managed.write_bytes(b'4321')
    else:
        managed.unlink()
        if problem == 'symlink':
            try:
                managed.symlink_to(original)
            except OSError:
                pytest.skip('symbolic links unavailable')

    with pytest.raises(ValueError, match='重新添加'):
        call('library_material_paths', collection_id=project, material_ids=[material['id']])
    assert call('library_workspace')['projects'][0]['materials'] == [material]


@pytest.mark.parametrize('remove_collection', [False, True])
def test_removing_a_material_or_project_detaches_its_copy(tmp_path, material_library, remove_collection):
    call, _ = material_library
    project = call('library_create_collection', name='课题')['id']
    original = tmp_path / 'table.csv'
    original.write_bytes(b'source')
    material, = call('library_material_add', collection_id=project, paths=[str(original)])
    path, = call('library_material_paths', collection_id=project, material_ids=[material['id']])

    if remove_collection:
        assert call('library_remove_collection', id=project) is True
        assert call('library_workspace')['projects'] == []
    else:
        assert call('library_material_remove', collection_id=project, material_id=material['id']) is True
        assert call('library_workspace')['projects'][0].get('materials', []) == []
    with pytest.raises(ValueError):
        call('library_material_paths', collection_id=project, material_ids=[material['id']])
    assert original.read_bytes() == Path(path).read_bytes() == b'source'


def test_concurrent_adds_keep_both_same_named_files(tmp_path, material_library):
    call, _ = material_library
    project = call('library_create_collection', name='课题')['id']
    sources = [tmp_path / 'first' / 'same.csv', tmp_path / 'second' / 'same.csv']
    for source in sources:
        source.parent.mkdir()
        source.write_text(source.parent.name)

    def add(source):
        record, = call('library_material_add', collection_id=project, paths=[str(source)])
        return record

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.map(add, sources)

    assert {row['id'] for row in call('library_workspace')['projects'][0]['materials']} == {first['id'], second['id']}
    paths = call('library_material_paths', collection_id=project, material_ids=[first['id'], second['id']])
    assert [Path(path).read_text() for path in paths] == ['first', 'second']


def test_corrupt_material_metadata_does_not_get_exposed_or_overwritten(tmp_path, material_library):
    call, root = material_library
    project = call('library_create_collection', name='课题')['id']
    original = tmp_path / 'table.csv'
    original.write_text('data')
    material, = call('library_material_add', collection_id=project, paths=[str(original)])
    index = root / 'index.json'
    data = json.loads(index.read_text())
    data['projects'][0]['materials'] = [dict(material, path=str(original))]
    index.write_text(json.dumps(data))
    before = index.read_bytes()

    with pytest.raises(ValueError, match='索引'):
        call('library_workspace')
    with pytest.raises(ValueError, match='索引'):
        call('library_material_remove', collection_id=project, material_id=material['id'])
    assert index.read_bytes() == before
