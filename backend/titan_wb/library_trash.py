"""Recoverable removal of library records and Titan-owned directories."""

from contextlib import contextmanager
import json
import os
import re
import uuid

from .library import _collection, _entry, _index, _now, _project, library_root, managed_analysis_path
from .project_materials import material_collection_path
from .projects import atomic_json, check_lock, operation_lock, release_project, writer_identity

MOVE_JOURNAL = '.trash-move.json'

def _records(data):
    records = data.setdefault('trash', [])
    if not isinstance(records, list):
        raise ValueError('最近删除记录无效')
    return records


def _safe_path(path):
    if path.resolve() != path:
        raise ValueError('文件位置已变化，无法安全移动')
    return path


def _reserve_writer(source, scratch, session):
    marker = source / '.writer.lock'
    if marker.exists():
        check_lock(source, session, acquire=False)
        return
    # Publish complete lock contents in one step. A crash cannot leave an
    # empty marker at the active writer-lock path.
    pending = scratch / '.pending-writer'
    atomic_json(pending, writer_identity(session))
    try:
        try:
            os.link(pending, marker)
        except FileExistsError:
            raise ValueError('另一窗口刚刚取得项目写入权')
    finally:
        pending.unlink(missing_ok=True)


def recover_pending_move(root, data):
    """Called under the index lock. The committed index decides where the directory belongs."""
    journal = root / MOVE_JOURNAL
    if not journal.exists():
        return
    intent = json.loads(_safe_path(journal).read_text(encoding='utf-8'))
    record = intent['record']
    item = record['item']
    folder = _trash_path(root, record)
    if record['kind'] == 'analysis':
        live = managed_analysis_path(root, item)
        if live is None:
            raise ValueError('分析恢复位置无效')
        stored = folder / live.name
    elif record['kind'] == 'project':
        live = material_collection_path(root, item['id'])
        stored = folder / 'materials'
    else:
        raise ValueError('最近删除记录无效')
    in_trash = any(entry['id'] == record['id'] for entry in _records(data))
    source, target = (live, stored) if in_trash else (stored, live)
    _safe_path(source)
    _safe_path(target)
    if source.is_dir() and not target.exists():
        source.rename(target)
    elif source.exists() or not target.is_dir():
        raise ValueError('最近删除中的文件位置冲突，请检查后重试')
    if not in_trash and intent.get('temporary_writer'):
        release_project(str(live), intent['temporary_writer'])
    journal.unlink()


def settled_index(root):
    if not (root / MOVE_JOURNAL).exists():
        return _index(root)
    with operation_lock(root, '.index.lock'):
        data = _index(root)
        recover_pending_move(root, data)
        return data


@contextmanager
def _transaction(root):
    with operation_lock(root, '.index.lock'):
        data = _index(root)
        recover_pending_move(root, data)

        def move(source, target, record, writer=None):
            _safe_path(source)
            _safe_path(target)
            if target.exists() or not source.is_dir():
                raise ValueError('文件位置已变化，无法安全移动')
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary_writer = writer_identity(writer) if writer and not (source / '.writer.lock').exists() else None
            atomic_json(root / MOVE_JOURNAL, dict(record=record, temporary_writer=temporary_writer))
            if writer:
                _reserve_writer(source, target.parent, writer)
            source.rename(target)

        try:
            yield data, move
            atomic_json(root / 'index.json', data)
        except Exception:
            recover_pending_move(root, _index(root))
            raise
        (root / MOVE_JOURNAL).unlink(missing_ok=True)


def _add_record(data, kind, item, moved):
    record = dict(id=uuid.uuid4().hex, kind=kind, item=item, deleted_at=_now(), moved=moved)
    _records(data).append(record)
    return record


def _trash_path(root, record):
    identifier = record['id']
    if not isinstance(identifier, str) or not re.fullmatch(r'[0-9a-f]{32}', identifier):
        raise ValueError('最近删除记录无效')
    return root / 'Trash' / identifier


def library_trash(session):
    records = _records(settled_index(library_root(session)))
    return [dict(id=row['id'], kind=row['kind'], name=row['item']['name'], deleted_at=row['deleted_at'])
            for row in reversed(records)]


def library_trash_analysis(entry_id, expected_path, session, *, move_files=True):
    root = library_root(session)
    with _transaction(root) as (data, move):
        entry = _entry(data, entry_id)
        if entry['path'] != expected_path:
            raise ValueError('分析位置已变化，请重新打开菜单')
        path = managed_analysis_path(root, entry) if move_files else None
        if path is not None:
            _safe_path(path)
        moved = path is not None and path.exists()
        record = _add_record(data, 'analysis', entry, moved)
        if moved:
            _, manifest = _project(path)
            if manifest['id'] != entry['project_id'] or manifest.get('module', 'wb') != entry.get('module', 'wb'):
                raise ValueError('此位置的分析身份已变化，无法删除')
            if any(other is not entry and other['path'] == entry['path'] for other in data['entries']):
                raise ValueError('其他分析仍使用此文件夹，无法删除')
            record['deletion_writer'] = writer_identity(session)
            move(path, _trash_path(root, record) / path.name, record, writer=session)
        data['entries'].remove(entry)
    return True


def library_trash_collection(collection_id, session):
    root = library_root(session)
    with _transaction(root) as (data, move):
        project = _collection(data, collection_id)
        path = _safe_path(material_collection_path(root, collection_id))
        moved = path.exists()
        record = _add_record(data, 'project', project, moved)
        if moved:
            move(path, _trash_path(root, record) / 'materials', record)
        data['projects'].remove(project)
        for entry in data['entries']:
            if entry.get('collection_id') == collection_id:
                entry['collection_id'] = None
    return True


def library_restore_deleted(identifier, session):
    root = library_root(session)
    with _transaction(root) as (data, move):
        records = _records(data)
        record = next((record for record in records if record['id'] == identifier), None)
        if record is None:
            raise ValueError('找不到该删除记录，请刷新列表')
        folder = _trash_path(root, record)
        item = record['item']
        if record['kind'] == 'project':
            if any(project['id'] == item['id'] for project in data['projects']):
                raise ValueError('项目已经存在')
            if record['moved']:
                move(folder / 'materials', material_collection_path(root, item['id']), record)
            data['projects'].append(item)
        elif record['kind'] == 'analysis':
            if any(entry['entry_id'] == item['entry_id'] or entry['path'] == item['path'] for entry in data['entries']):
                raise ValueError('此分析已经在项目库中')
            if record['moved']:
                path = managed_analysis_path(root, item)
                if path is None:
                    raise ValueError('分析恢复位置无效')
                stored = _safe_path(folder / path.name)
                _, manifest = _project(stored)
                if manifest['id'] != item['project_id'] or manifest.get('module', 'wb') != item.get('module', 'wb'):
                    raise ValueError('最近删除中的分析身份已变化')
                if (stored / '.writer.lock').exists():
                    if json.loads((stored / '.writer.lock').read_text(encoding='utf-8')) != record['deletion_writer']:
                        raise ValueError('分析已有其他写入者，请关闭后再恢复')
                    release_project(str(stored), record['deletion_writer'])
                move(stored, path, record)
            if not any(project['id'] == item.get('collection_id') for project in data['projects']):
                item['collection_id'] = None
            data['entries'].append(item)
        else:
            raise ValueError('最近删除记录无效')
        records.remove(record)
    try:
        folder.rmdir()
    except OSError:
        pass
    return True
