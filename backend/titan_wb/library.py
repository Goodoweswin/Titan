"""A local index of explicitly created/opened portable projects. No disk scan."""
import json
import shutil
import uuid
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
from .models import new_project
from .images import file_hash
from .projects import atomic_json,save_project,operation_lock,release_project,writer_identity
from .figure_documents import save_figure,load_figure,source_signature,figure_catalog_metadata


def _now():return datetime.now(timezone.utc).isoformat()

def library_root(session):
    value=session.get('library_root')
    if not isinstance(value,str) or not value:raise ValueError('本地项目库路径未配置')
    root=Path(value).expanduser().resolve();root.mkdir(parents=True,exist_ok=True);return root


def _index(root):
    path=root/'index.json'
    if not path.exists():return dict(version=1,entries=[],projects=[])
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
        if data.get('version')!=1 or not isinstance(data.get('entries'),list):raise ValueError()
        ids=[r['entry_id'] for r in data['entries']]
        if len(ids)!=len(set(ids)) or any(not all(isinstance(r.get(k),str) and r[k] for k in ['entry_id','project_id','name','path','last_opened']) for r in data['entries']):raise ValueError()
        projects = data.setdefault('projects', [])
        if not isinstance(projects, list):
            raise ValueError()
        project_ids = [p['id'] for p in projects]
        if len(set(project_ids)) != len(project_ids) or any(
            not isinstance(p['id'], str) or not p['id'] or
            not isinstance(p['name'], str) or not p['name'].strip() or
            type(p['pinned']) is not bool or not isinstance(p['created_at'], str)
            for p in projects
        ):
            raise ValueError()
        return data
    except (ValueError,KeyError,TypeError,AttributeError):raise ValueError('项目列表索引损坏；原项目保持不变，可通过“打开项目”继续访问')


def _project(path):
    root=Path(path).expanduser().resolve()
    if root.suffix not in ('.titanwb','.titanif','.titanstats'):raise ValueError('请选择 .titanwb、.titanif 或 .titanstats 项目文件夹')
    try:p=json.loads((root/'project.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):raise ValueError('项目文件夹不存在、已移动或清单损坏，请重新定位')
    if not isinstance(p,dict) or not isinstance(p.get('id'),str) or not isinstance(p.get('name'),str):raise ValueError('项目清单身份无效')
    return root,p


def _public(entry):
    row=dict(entry,module=entry.get('module','wb'),available=True,figures=[],collection_id=entry.get('collection_id'))
    row['artifacts'] = [_output_state(artifact) for artifact in entry.get('exports', [])]
    try:
        root,p=_project(entry['path'])
        if p['id'] != entry['project_id'] or p.get('module','wb') != row['module']:
            raise ValueError('此位置的分析身份已变化，请重新定位原分析')
        row.update(name=p['name'],revision=p.get('revision'))
        if row['module']=='wb':
            try:row['figures']=figure_catalog_metadata(root,source_signature(p))
            except (ValueError, OSError, KeyError, TypeError) as e:row['figure_error']=str(e)
            from .wb_figures import document_catalog_metadata
            try:
                for document in document_catalog_metadata(root):
                    row['artifacts'].append(dict(
                        id='strip:'+document['id'], title=document['name'], kind='wb_figure',
                        document_id=document['id'], version_id=document['version'], source_revision=None,
                        available=True,
                    ))
            except (ValueError, OSError, KeyError) as e:
                row['figure_error'] = ' · '.join(filter(None, [row.get('figure_error'), str(e)]))
            _include_archived_exports(row, root)
        if row['module'] == 'stats':
            figures = p.get('figures', [])
            if not isinstance(figures, list):
                row['figure_error'] = '统计图形记录损坏'
                figures = []
            for figure in figures:
                if not isinstance(figure, dict) or not all(isinstance(figure.get(key), str) for key in ('id', 'name')):
                    row['figure_error'] = '统计图形记录损坏'
                    continue
                row['artifacts'].append(dict(
                    id='stats:'+figure['id'], kind='stats_plot', title=figure['name'],
                    document_id=figure['id'], version_id=figure['id'],
                    source_revision=figure.get('source_revision'), available=True,
                ))
    except ValueError as e:row.update(available=False,error=str(e))
    for artifact in row['artifacts']:
        artifact['entry_id'] = entry['entry_id']
    return row


def _rows(data):
    rows = [_public(row) for row in sorted(data['entries'], key=lambda row: row['last_opened'], reverse=True)]
    owners = {}
    for row in rows:
        for artifact in row['artifacts']:
            if 'destination' not in artifact:
                continue
            key = (row['project_id'], artifact['destination'])
            explicit, inferred = owners.setdefault(key, (set(), set()))
            (inferred if artifact.get('legacy_origin') else explicit).add(row['entry_id'])
    for row in rows:
        artifacts = []
        for artifact in row['artifacts']:
            if artifact.get('legacy_origin'):
                explicit, inferred = owners[(row['project_id'], artifact['destination'])]
                if explicit or len(inferred) != 1:
                    continue
            artifacts.append(artifact)
        row['artifacts'] = artifacts
    return rows


def library_list(session):
    return _rows(_index(library_root(session)))


def library_workspace(session):
    data = _index(library_root(session))
    return dict(projects=data['projects'], entries=_rows(data))


@contextmanager
def _edit_index(session):
    root = library_root(session)
    with operation_lock(root, '.index.lock'):
        data = _index(root)
        yield data
        atomic_json(root / 'index.json', data)


def _find(rows, key, value, error):
    for row in rows:
        if row[key] == value:
            return row
    raise ValueError(error)


def _entry(data, entry_id):
    return _find(data['entries'], 'entry_id', entry_id, '找不到该分析记录')


def _collection(data, collection_id):
    return _find(data['projects'], 'id', collection_id, '找不到该课题项目')


def _name(name):
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
        raise ValueError('请输入 1–120 个字符的名称')
    return name.strip()


def _new_collection(data, name):
    project = dict(id=uuid.uuid4().hex, name=_name(name), pinned=False, created_at=_now())
    data['projects'].append(project)
    return project


def library_create_collection(name, session):
    with _edit_index(session) as data:
        return _new_collection(data, name)


def library_update_collection(collection_id, patch, session):
    if not isinstance(patch, dict) or not patch.keys() <= {'name', 'pinned'}:
        raise ValueError('课题项目设置无效')
    patch = dict(patch)
    if 'name' in patch:
        patch['name'] = _name(patch['name'])
    if 'pinned' in patch and type(patch['pinned']) is not bool:
        raise ValueError('置顶设置无效')
    with _edit_index(session) as data:
        project = _collection(data, collection_id)
        project.update(patch)
        return project


def library_remove_collection(collection_id, session):
    with _edit_index(session) as data:
        data['projects'].remove(_collection(data, collection_id))
        for entry in data['entries']:
            if entry.get('collection_id') == collection_id:
                entry['collection_id'] = None
    return True


def library_assign(entry_id, collection_id, session):
    with _edit_index(session) as data:
        if collection_id is not None:
            _collection(data, collection_id)
        _entry(data, entry_id)['collection_id'] = collection_id
    return True


def library_set_resume(entry_id, resume, session):
    if not isinstance(resume, dict) or resume.get('view') not in ('workspace', 'results', 'figure'):
        raise ValueError('续做位置无效')
    value = dict(view=resume['view'])
    if 'artifact_id' in resume:
        identifier = resume['artifact_id']
        if value['view'] != 'figure' or not isinstance(identifier, str) or not 0 < len(identifier) <= 200:
            raise ValueError('图表续做位置无效')
        value['artifact_id'] = identifier
    if 'version_id' in resume:
        version = resume['version_id']
        if 'artifact_id' not in value or not isinstance(version, str) or not 0 < len(version) <= 120:
            raise ValueError('图表版本无效')
        value['version_id'] = version
    if 'dataset_id' in resume:
        dataset_id = resume['dataset_id']
        if not isinstance(dataset_id, str) or not 0 < len(dataset_id) <= 120:
            raise ValueError('数据表续做位置无效')
        value['dataset_id'] = dataset_id
    with _edit_index(session) as data:
        _entry(data, entry_id)['resume'] = value
    return True


def _registered_entry(data, folder, manifest, entry_id):
    path = str(folder)
    project_id = manifest['id']
    module = manifest.get('module', 'wb')
    existing = next((entry for entry in data['entries'] if entry['path'] == path), None)
    entry = existing
    if entry_id is not None:
        entry = _entry(data, entry_id)
        if entry['project_id'] != project_id or entry.get('module', 'wb') != module:
            raise ValueError('重新定位的项目身份不匹配')
        if existing is not None and existing is not entry:
            raise ValueError('此位置已登记为另一条项目记录')
    if entry is not None and (entry['project_id'] != project_id or entry.get('module', 'wb') != module):
        raise ValueError('此路径已登记给其他分析，请先重新定位旧分析')
    return entry


def library_check_path(path, entry_id, session):
    folder, manifest = _project(path)
    _registered_entry(_index(library_root(session)), folder, manifest, entry_id)
    return str(folder)


def open_registered_analysis(path, load, session, entry_id=None):
    path = library_check_path(path, entry_id, session)
    try:
        owned = json.loads((Path(path) / '.writer.lock').read_text()) == writer_identity(session)
    except FileNotFoundError:
        owned = False
    project = load(path, session)
    try:
        library_register(project['project_path'], session, entry_id)
    except (ValueError, OSError):
        if not owned and not project.get('read_only'):
            release_project(project['project_path'], session)
        raise
    return project


def entry_for_path(path, session):
    if not path:
        return None
    canonical = str(Path(path).resolve())
    data = _index(library_root(session))
    return next((entry for entry in data['entries'] if entry['path'] == canonical), None)


def resolve_analysis_source(path, entry_id, project_id, module, session):
    if not isinstance(project_id, str) or not project_id or (not path and not entry_id):
        raise ValueError('找不到已保存的来源分析')
    data = _index(library_root(session))
    if entry_id:
        entry = _entry(data, entry_id)
        path = entry['path']
    try:
        folder, manifest = _project(path)
    except ValueError as e:
        raise ValueError('找不到来源分析，请先在左栏重新定位原分析') from e
    if manifest['id'] != project_id or manifest.get('module', 'wb') != module:
        raise ValueError('来源分析身份不匹配，路径指向不同项目，请重新定位原分析')
    entry = _registered_entry(data, folder, manifest, entry_id)
    return dict(path=str(folder), entry_id=entry and entry['entry_id'], project_id=project_id)


def _register(data, folder, manifest, *, entry_id=None, source_entry_id=None, touch_opened=True):
    path = str(folder)
    project_id = manifest['id']
    module = manifest.get('module', 'wb')
    entry = _registered_entry(data, folder, manifest, entry_id)
    if entry is None:
        stamp = _now()
        entry = dict(entry_id=uuid.uuid4().hex, created_at=stamp, last_opened=stamp)
        if source_entry_id is not None:
            source = _entry(data, source_entry_id)
            if source['project_id'] != project_id or source.get('module', 'wb') != module:
                raise ValueError('分析副本与来源身份不一致')
            entry['collection_id'] = source.get('collection_id')
        data['entries'].append(entry)
    entry.update(project_id=project_id, name=manifest['name'], path=path, module=module)
    if touch_opened:
        entry['last_opened'] = _now()
    return entry


def library_register(path, session, entry_id=None, *, source_entry_id=None, touch_opened=True):
    folder, manifest = _project(path)
    with _edit_index(session) as data:
        entry = _register(data, folder, manifest, entry_id=entry_id,
                          source_entry_id=source_entry_id, touch_opened=touch_opened)
    return _public(entry)


def create_managed_analysis(project, suffix, save, session, *, collection_id=None, new_collection_name=None):
    if collection_id is not None and new_collection_name is not None:
        raise ValueError('请选择已有课题或新建课题')
    root = library_root(session)
    path = root / 'Projects' / (project['id'] + suffix)
    created = False
    try:
        with _edit_index(session) as data:
            if new_collection_name is not None:
                collection_id = _new_collection(data, new_collection_name)['id']
            elif collection_id is not None:
                _collection(data, collection_id)
            path.mkdir(parents=True)
            created = True
            saved = save(project, str(path), None, session)
            entry = _register(data, path, saved)
            entry['collection_id'] = collection_id
    except Exception:
        if created:
            shutil.rmtree(path)
        raise
    return dict(project=saved, entry=_public(entry))


def copy_registered_analysis(project, destination, suffix, save, session):
    path = Path(destination).expanduser().resolve()
    if path.suffix != suffix:
        raise ValueError(f'项目目录名需以 {suffix} 结尾')
    created = False
    try:
        with _edit_index(session) as data:
            source_path = project.get('project_path')
            source_path = str(Path(source_path).resolve()) if source_path else None
            source = next((entry for entry in data['entries'] if entry['path'] == source_path), None)
            try:
                path.mkdir(parents=True)
            except FileExistsError as e:
                raise ValueError('请选择尚不存在的另存位置') from e
            created = True
            saved = save(project, str(path), None, session)
            _register(data, path, saved, source_entry_id=source and source['entry_id'])
    except Exception:
        if created:
            shutil.rmtree(path)
        raise
    return saved


def library_create(name, session, *, collection_id=None, new_collection_name=None):
    return create_managed_analysis(new_project(_name(name)), '.titanwb', save_project, session,
                                   collection_id=collection_id, new_collection_name=new_collection_name)


def library_remove(entry_id, session):
    with _edit_index(session) as data:
        data['entries'] = [entry for entry in data['entries'] if entry['entry_id'] != entry_id]
    return True


_EXPORT_KINDS = {'result_export', 'if_figure_export', 'wb_figure_export'}
_OUTPUT_SUFFIXES = {'.png', '.tif', '.tiff', '.svg', '.pdf', '.xlsx', '.csv', '.json', '.txt'}


def _primary_file(files):
    candidates = [Path(file) for file in files]
    for suffix in ('.xlsx', '.png', '.svg', '.tiff', '.tif', '.pdf'):
        matching = [path for path in candidates if path.suffix.lower() == suffix]
        if matching:
            return min(matching, key=lambda path: len(path.parts))
    return None


def _output_state(artifact):
    primary = artifact.get('primary_file') or _primary_file(artifact['files'])
    return dict(artifact, available=bool(primary and Path(primary).is_file()))


def _include_archived_exports(row, root):
    from .figure_documents import figure_export_metadata

    try:
        exports = figure_export_metadata(root)
    except (ValueError, OSError, KeyError, TypeError):
        return
    by_path = {artifact['destination']: artifact for artifact in row['artifacts'] if 'destination' in artifact}
    for version in exports:
        origin = version['export_origin']
        if not isinstance(origin, dict) or not isinstance(origin.get('path'), str):
            continue
        path = str(Path(origin['path']).resolve())
        artifact = by_path.get(path)
        if artifact is None:
            artifact = _output_state(dict(
                id='export:'+version['version_id'], title=version['name'], kind='result_export',
                destination=path, files=[str(Path(path) / 'plot.png')],
                source_revision=version['source_revision'], legacy_origin=True,
                primary_sha256=origin.get('png_sha256'),
            ))
            row['artifacts'].append(artifact)
            by_path[path] = artifact
        if artifact.get('legacy_origin') or artifact.get('plot_sha256') == origin.get('png_sha256'):
            artifact.update(document_id=version['document_id'], version_id=version['version_id'])


def library_record_export(project_path, project_id, record, session):
    if not isinstance(record, dict) or record.get('kind') not in _EXPORT_KINDS:
        raise ValueError('导出记录类型无效')
    destination = Path(record['destination']).expanduser().resolve()
    files = record['files']
    if not isinstance(files, list) or not 0 < len(files) <= 500:
        raise ValueError('导出文件清单无效')
    base = destination if destination.is_dir() else destination.parent
    checked = list(dict.fromkeys(Path(file).resolve() for file in files))
    if any(not f.is_file() or not f.is_relative_to(base) or f.suffix.lower() not in _OUTPUT_SUFFIXES for f in checked):
        raise ValueError('导出文件缺失或路径无效')
    if not destination.is_dir() and destination not in checked:
        raise ValueError('找不到已导出的主文件')
    primary = _primary_file(checked)
    expected_sha256 = record.get('primary_sha256')
    if primary is None or not expected_sha256 or file_hash(primary) != expected_sha256:
        raise ValueError('导出主文件已变化，无法登记到原版本')
    revision = record['source_revision']
    version_id = record.get('version_id')
    if version_id is not None and (not isinstance(version_id, str) or not 0 < len(version_id) <= 120):
        raise ValueError('导出文档版本无效')
    if not (type(revision) is int and revision >= 0) and not (revision is None and version_id):
        raise ValueError('导出来源版本无效')
    canonical = str(Path(project_path).resolve())
    with _edit_index(session) as data:
        entry = _find(data['entries'], 'path', canonical, '分析尚未登记到项目库')
        if entry['project_id'] != project_id:
            raise ValueError('导出来源分析身份不一致')
        exports = entry.setdefault('exports', [])
        previous = next((item for item in exports if item['kind'] == record['kind'] and item['destination'] == str(destination)), None)
        if previous is not None:
            if previous['source_revision'] == revision and previous.get('version_id') == version_id and previous.get('primary_sha256') == expected_sha256:
                return _output_state(previous)
            exports.remove(previous)
        artifact = dict(id='export:'+uuid.uuid4().hex, title=_name(record['title']),
                        kind=record['kind'], source_revision=revision,
                        destination=str(destination), files=[str(f) for f in checked],
                        primary_file=str(primary), primary_sha256=expected_sha256,
                        plot_sha256=record.get('plot_sha256'), version_id=version_id)
        exports.append(artifact)
        return _output_state(artifact)


def register_published_export(project, result, destination, kind, title, revision, session, *, version_id=None):
    """Record only successful publications, without making a catalog failure an export failure."""
    if not project.get('project_path') or not session.get('library_root'):
        return result
    path = Path(destination).expanduser().resolve()
    files = result.get('files')
    if files is None:
        files = [str(path / name) for name in result['outputs']]
    files = [str(path / file) if not Path(file).is_absolute() else file for file in files]
    primary = _primary_file(files)
    hashes = result.get('outputs', {})
    primary_sha256 = None
    if primary is not None:
        primary_sha256 = hashes.get(primary.relative_to(path).as_posix()) if path.is_dir() else None
        try:
            primary_sha256 = primary_sha256 or file_hash(primary)
        except OSError:
            pass
    record = dict(destination=str(path), files=files, kind=kind,
                  title=title.strip()[:120] or path.name[:120], source_revision=revision,
                  primary_sha256=primary_sha256, plot_sha256=hashes.get('plot.png'), version_id=version_id)
    request = dict(project_path=project['project_path'], project_id=project['id'], record=record)
    try:
        library_record_export(**request, session=session)
    except (ValueError, OSError) as error:
        return dict(result, library_export_retry=request, library_export_error=str(error))
    return result


def library_target(entry_id, artifact_id, session):
    rows = library_workspace(session)['entries']
    entry = _find(rows, 'entry_id', entry_id, '找不到该分析记录')
    if artifact_id is None:
        if not entry['available']:
            raise ValueError('分析文件夹不可用，请重新定位')
        return entry['path']
    artifact = _find(entry['artifacts'], 'id', artifact_id, '找不到导出记录')
    if 'destination' not in artifact:
        raise ValueError('请选择一个导出记录')
    selected = artifact.get('primary_file') or _primary_file(artifact['files'])
    if selected is not None:
        path = Path(selected)
        if path.is_file() and path.resolve() == path:
            digest = artifact.get('primary_sha256')
            if digest and file_hash(path) != digest:
                raise ValueError('导出文件已变化，请核对文件或重新导出')
            return str(path)
    raise ValueError('找不到导出文件')
