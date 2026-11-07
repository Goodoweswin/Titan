"""Portable collection folders. Validate and stage a complete copy before publishing it."""
import hashlib
import json
import re
import shutil
import tempfile
import uuid
from contextlib import nullcontext
from pathlib import Path, PureWindowsPath

from titan_if.projects import open_project as open_if
from titan_if.projects import stream_hash
from titan_stats.models import signature, validate as validate_stats
from titan_stats.store import _portable_project

from . import figure_documents, library, project_materials, wb_figures
from .projects import atomic_json, open_project as open_wb, operation_lock


_SUFFIX = {'wb': '.titanwb', 'if': '.titanif', 'stats': '.titanstats'}
_ANALYSIS_FOLDERS = {'wb': {'originals', 'figures'}, 'if': {'originals', 'masks', 'results', 'history'}, 'stats': set()}
_MANIFEST = 'bundle.json'


def _relative(value):
    if not isinstance(value, str) or any(
        not part or part in ('.', '..') or part[-1] in ' .' or PureWindowsPath(part).is_reserved()
        or any(c in '\\:<>"|?*' or ord(c) < 32 for c in part)
        for part in value.split('/')
    ):
        raise ValueError('项目包包含不安全的相对路径')
    return Path(*value.split('/'))


def _folder(path):
    if path.resolve() != path or not path.is_dir():
        raise ValueError('项目包目录不存在或包含符号链接')
    return path


def _file(path):
    if path.resolve() != path or not path.is_file():
        raise ValueError(f'项目包文件缺失或路径不安全：{path.name}')
    return path


def _json(path):
    return json.loads(_file(path).read_text(encoding='utf-8'))


def _copy(source, target, expected=None):
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with _file(source).open('rb') as reader, target.open('xb') as writer:
        for block in iter(lambda: reader.read(1024 * 1024), b''):
            writer.write(block)
            digest.update(block)
    result = digest.hexdigest()
    if expected is not None and result != expected:
        raise ValueError(f'项目包文件校验不一致：{source.name}')
    return result


def _analysis_path(index, module):
    return Path('Analyses') / (str(index) + _SUFFIX[module])


def _analysis_member(relative, module):
    return relative == Path('project.json') or (
        len(relative.parts) > 1 and relative.parts[0] in _ANALYSIS_FOLDERS[module]
        and all(not part.startswith('.') and not part.endswith('.tmp') for part in relative.parts)
    )


def _analysis_lock(root, name):
    path = root / name
    if path.exists() or path.is_symlink():
        _file(path)
    return operation_lock(root, name)


def _copy_saved_analysis(source, target, module):
    _folder(source)
    folders = _ANALYSIS_FOLDERS[module]
    figures = source / 'figures'
    lock = nullcontext()
    if module in ('if', 'stats'):
        lock = _analysis_lock(source, '.save.lock')
    elif figures.exists() or figures.is_symlink():
        lock = _analysis_lock(_folder(figures), '.catalog.lock')
    else:
        folders = folders - {'figures'}
    with lock:
        # The WB manifest is published atomically and its saved originals are immutable.
        hashes = {'project.json': _copy(source / 'project.json', target / 'project.json')}
        for name in sorted(folders):
            folder = source / name
            if not folder.exists() and not folder.is_symlink():
                continue
            for item in _folder(folder).rglob('*'):
                relative = item.relative_to(source)
                if not _analysis_member(relative, module):
                    continue
                _relative(relative.as_posix())
                if not item.is_dir() or item.is_symlink():
                    hashes[relative.as_posix()] = _copy(item, target / relative)
        return hashes


def _reference(root, value, folder):
    # Older Windows manifests may store backslashes; all references stay within their own folder.
    relative = _relative(value.replace('\\', '/'))
    if len(relative.parts) < 2 or relative.parts[0] != folder:
        raise ValueError(f'项目包分析路径越过 {folder} 目录')
    return _file(root / relative)


def _verify_wb_images(root, images):
    for image in images:
        image_id = image['id']
        # WB uses the image ID as a filename during later saves and exports.
        if not isinstance(image_id, str) or not re.fullmatch('[A-Za-z0-9_-]{1,80}', image_id):
            raise ValueError('项目包图像标识不能作为安全文件名')
        _reference(root, image['path'], 'originals')


def _validate_analysis(root, entry, session):
    manifest = _json(root / 'project.json')
    module, project_id = entry['module'], entry['project_id']
    if manifest.get('module', 'wb') != module or manifest.get('id') != project_id or not project_id:
        raise ValueError('项目包中的分析身份不匹配')
    if module == 'stats':
        validate_stats(manifest)
    elif module == 'if':
        for field in manifest['fields']:
            for channel in field['channels']:
                _reference(root, channel['source']['path'], 'originals')
            if field.get('mask'):
                for mask in [field['mask'], *field['mask'].get('history', [])]:
                    _reference(root, mask['path'], 'masks')
            if (field.get('result') or {}).get('artifact'):
                _reference(root, field['result']['artifact']['path'], 'results')
        open_if(root, session, read_only=True)
    else:
        _verify_wb_images(root, manifest['images'])
        wb = open_wb(root, session, read_only=True)
        for document in figure_documents._catalog(root)['figures']:
            versions = [figure_documents._id(version['version_id']) for version in document['versions']]
            if len(set(versions)) != len(versions):
                raise ValueError('项目包图表版本身份重复')
            for version in versions:
                folder = root / 'figures' / document['id'] / version
                snapshot = _json(folder / 'source.json')['project']
                if snapshot['id'] != project_id:
                    raise ValueError('项目包图表的冻结分析身份不匹配')
                _verify_wb_images(root, snapshot['images'])
                figure_documents.load_figure(root, document['id'], session, version_id=version)
        for document in wb_figures.document_catalog_metadata(root):
            versions = [version['version'] for version in document['versions']]
            if len(set(versions)) != len(versions):
                raise ValueError('项目包组图版本身份重复')
            for version in versions:
                strip = _json(root / 'figures' / 'wb' / document['id'] / (version + '.json'))
                if strip['id'] != document['id'] or strip['version'] != version:
                    raise ValueError('项目包组图版本身份不匹配')
                for row in strip['rows']:
                    _reference(root, row['source']['path'], 'originals')
                wb_figures.load_document(wb, document['id'], version_id=version)
    return manifest


def _rewrite_stats(manifest, locate):
    _portable_project(manifest)

    def rewrite_table(table):
        source = table.get('source')
        if not source:
            return
        target = locate(source) if source.get('kind') in ('wb', 'if') else None
        source.pop('path', None)
        source.pop('entry_id', None)
        if target:
            source.update(target)

    def rewrite_run(run):
        if run is not None:
            snapshot = run['dataset']
            valid = run['signature'] == signature(snapshot)
            rewrite_table(snapshot)
            if valid:
                run['signature'] = signature(snapshot)

    for table in manifest['datasets']:
        rewrite_table(table)
        for run in table.get('runs', []):
            rewrite_run(run)
    for figure in manifest['figures']:
        rewrite_table(figure['dataset'])
        rewrite_run(figure['run'])


def _rewrite_wb_origins(root, destinations):
    catalog = figure_documents._catalog(root)
    changed = []
    for document in catalog['figures']:
        for version in document['versions']:
            origin = version.get('export_origin')
            if not origin:
                continue
            target = destinations.get((origin['path'], origin['png_sha256']))
            version['export_origin'] = {**origin, 'path': target} if target else None
            version_path = root / 'figures' / document['id'] / version['version_id'] / 'figure.json'
            atomic_json(version_path, version)
            changed.append(version_path)
    if changed:
        catalog_path = root / 'figures' / 'catalog.json'
        atomic_json(catalog_path, catalog)
        changed.append(catalog_path)
    return changed


def _artifact_path(entry_index, artifact_index):
    return Path('Outputs') / str(entry_index) / str(artifact_index)


def _artifact_metadata(record):
    metadata = {key: record[key] for key in ('id', 'kind', 'title', 'source_revision', 'primary_sha256')}
    metadata.update({key: record[key] for key in ('plot_sha256', 'version_id', 'document_id') if record.get(key) is not None})
    if (
        not isinstance(metadata['id'], str) or not metadata['id'] or metadata['kind'] not in library._EXPORT_KINDS
        or not isinstance(metadata['title'], str) or not metadata['title'].strip()
        or not re.fullmatch('[0-9a-f]{64}', metadata['primary_sha256'])
        or ('plot_sha256' in metadata and not re.fullmatch('[0-9a-f]{64}', metadata['plot_sha256']))
        or (metadata['source_revision'] is not None and (type(metadata['source_revision']) is not int or metadata['source_revision'] < 0))
        or (metadata['source_revision'] is None and 'version_id' not in metadata)
        or any(not isinstance(metadata[key], str) or not metadata[key] for key in ('version_id', 'document_id') if key in metadata)
    ):
        raise ValueError('项目包导出记录无效')
    return metadata


def _export_artifact(record, target):
    metadata = _artifact_metadata(record)
    destination = Path(record['destination'])
    primary = Path(record['primary_file'])
    files = [Path(file) for file in record['files']]
    try:
        base = destination if destination.is_dir() else destination.parent
        _folder(base)
        is_folder = destination == base
        if primary not in files or (not is_folder and destination not in files):
            return None
        relatives = {file: _relative(file.relative_to(base).as_posix()) for file in files}
        for file in files:
            _file(file)
            if file.suffix.lower() not in library._OUTPUT_SUFFIXES:
                return None
        if stream_hash(primary) != metadata['primary_sha256']:
            return None
        plot_hash = metadata.get('plot_sha256')
        plot = base / 'plot.png'
        if plot_hash and (plot not in files or stream_hash(plot) != plot_hash):
            return None
    except (OSError, ValueError):
        return None
    hashes = {}
    for file, relative in relatives.items():
        expected = metadata['primary_sha256'] if file == primary else plot_hash if file == plot else None
        hashes[relative.as_posix()] = _copy(file, target / relative, expected)
    return dict(metadata, destination=None if is_folder else relatives[destination].as_posix(),
                primary_file=relatives[primary].as_posix(), hashes=hashes)


def _restore_artifact(record, source, stage, final):
    metadata = _artifact_metadata(record)
    hashes = record['hashes']
    primary = record['primary_file']
    destination = record['destination']
    if not isinstance(hashes, dict) or not 0 < len(hashes) <= 500 or hashes.get(primary) != metadata['primary_sha256']:
        raise ValueError('项目包导出主文件缺失或校验无效')
    if destination is not None and destination not in hashes:
        raise ValueError('项目包导出位置无效')
    if metadata.get('plot_sha256') and hashes.get('plot.png') != metadata['plot_sha256']:
        raise ValueError('项目包图表导出校验无效')
    paths = []
    for name, digest in hashes.items():
        relative = _relative(name)
        if relative.suffix.lower() not in library._OUTPUT_SUFFIXES or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('项目包导出文件清单无效')
        _copy(source / relative, stage / relative, digest)
        paths.append(str(final / relative))
    return dict(metadata, destination=str(final / _relative(destination)) if destination is not None else str(final),
                primary_file=str(final / _relative(primary)), files=paths)


def _bundle_path(path):
    if not isinstance(path, str) or not path:
        raise ValueError('请选择 .titanproject 项目包文件夹')
    original = Path(path).expanduser()
    result = original.parent.resolve() / original.name
    if result.suffix.lower() != '.titanproject':
        raise ValueError('请选择 .titanproject 项目包文件夹')
    return result


def _export_snapshot(root, collection, entries, stage, session):
    materials = project_materials.validate_materials(collection.get('materials', []))
    for material in materials:
        source = project_materials.verified_material_path(root, collection['id'], material)
        _copy(source, project_materials.material_path(stage, 'bundle', material), material['sha256'])
    by_id = {entry['entry_id']: entry for entry in entries}
    by_path = {entry['path']: entry for entry in entries}

    def portable_source(source):
        candidate = by_id.get(source['entry_id']) if source.get('entry_id') else by_path.get(source.get('path'))
        if candidate and (candidate['project_id'], candidate.get('module', 'wb')) == (source.get('project_id'), source['kind']):
            return dict(entry_id=candidate['entry_id'])
        return None

    records = []
    for index, entry in enumerate(entries):
        module = entry.get('module', 'wb')
        analysis = stage / _analysis_path(index, module)
        hashes = _copy_saved_analysis(Path(entry['path']), analysis, module)
        record = {key: entry[key] for key in ('entry_id', 'project_id', 'resume') if key in entry}
        record.update(module=module, exports=[])
        manifest = _validate_analysis(analysis, record, session)
        origins = {}
        for artifact in entry.get('exports', []):
            if artifact['source_revision'] is not None and artifact['source_revision'] > manifest['revision']:
                continue
            relative = _artifact_path(index, len(record['exports']))
            exported = _export_artifact(artifact, stage / relative)
            if exported:
                record['exports'].append(exported)
                if exported.get('plot_sha256'):
                    origins[artifact['destination'], exported['plot_sha256']] = (relative / (exported['destination'] or '')).as_posix()
        if module == 'stats':
            _rewrite_stats(manifest, portable_source)
            manifest_path = analysis / 'project.json'
            atomic_json(manifest_path, manifest)
            hashes['project.json'] = stream_hash(manifest_path)
        elif module == 'wb':
            for file in _rewrite_wb_origins(analysis, origins):
                hashes[file.relative_to(analysis).as_posix()] = stream_hash(file)
        record['hashes'] = hashes
        records.append(record)
    atomic_json(stage / _MANIFEST, dict(version=1, name=collection['name'], pinned=collection['pinned'],
                                       materials=materials, entries=records))


def library_export_bundle(collection_id, destination, session):
    root = library.library_root(session)
    destination = _bundle_path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError('项目包位置已存在，请选择新目录')
    with operation_lock(root, '.index.lock'):
        data = library._index(root)
        collection = library._collection(data, collection_id)
        entries = [entry for entry in data['entries'] if entry.get('collection_id') == collection_id]
        if any(destination.is_relative_to(path) for path in [root, *(Path(entry['path']) for entry in entries)]):
            raise ValueError('项目包不能保存在项目库或原分析内部')
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.titan-project-', dir=destination.parent) as temp:
            stage = Path(temp)
            _export_snapshot(root, collection, entries, stage, session)
            try:
                destination.mkdir()
            except FileExistsError as error:
                raise ValueError('项目包位置已存在，请选择新目录') from error
            try:
                for child in stage.iterdir():
                    if child.name != _MANIFEST:
                        child.rename(destination / child.name)
                # An importer only accepts a published manifest, after the data is in place.
                (stage / _MANIFEST).rename(destination / _MANIFEST)
            except Exception:
                shutil.rmtree(destination)
                raise
    return str(destination)


def _restore_analysis_files(source, stage, record):
    hashes = record['hashes']
    if not isinstance(hashes, dict) or 'project.json' not in hashes:
        raise ValueError('项目包缺少分析清单')
    for name, digest in hashes.items():
        relative = _relative(name)
        if not _analysis_member(relative, record['module']) or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('项目包分析文件清单无效')
        _copy(source / relative, stage / relative, digest)


def _restore_entries(bundle, stage, final, records, collection_id, session):
    remapped = {}
    for index, record in enumerate(records):
        old_id, project_id, module = record['entry_id'], record['project_id'], record['module']
        if any(not isinstance(value, str) or not value for value in (old_id, project_id, module)) or old_id in remapped:
            raise ValueError('项目包分析身份无效或重复')
        relative = _analysis_path(index, module)
        remapped[old_id] = dict(entry_id=uuid.uuid4().hex, path=str(final / relative), project_id=project_id, module=module)

    def local_source(source):
        if source.get('path') is not None:
            raise ValueError('项目包统计来源包含外部路径')
        if not source.get('entry_id'):
            return None
        candidate = remapped.get(source['entry_id'])
        if candidate is None or (candidate['project_id'], candidate['module']) != (source['project_id'], source['kind']):
            raise ValueError('项目包统计来源的分析身份不匹配')
        return {key: candidate[key] for key in ('entry_id', 'path')}

    restored = []
    for index, record in enumerate(records):
        entry = remapped[record['entry_id']]
        relative = _analysis_path(index, entry['module'])
        analysis = stage / relative
        _restore_analysis_files(bundle / relative, analysis, record)
        manifest = _validate_analysis(analysis, entry, session)
        exports = []
        origins = {}
        for artifact_index, artifact in enumerate(record['exports']):
            location = _artifact_path(index, artifact_index)
            output = _restore_artifact(artifact, bundle / location, stage / location, final / location)
            exports.append(output)
            if output.get('plot_sha256'):
                origins[(location / (artifact['destination'] or '')).as_posix(), output['plot_sha256']] = output['destination']
        if entry['module'] == 'stats':
            _rewrite_stats(manifest, local_source)
            atomic_json(analysis / 'project.json', manifest)
        elif entry['module'] == 'wb':
            _rewrite_wb_origins(analysis, origins)
        entry.update(name=manifest['name'], collection_id=collection_id, created_at=library._now(),
                     last_opened=library._now(), exports=exports)
        if 'resume' in record:
            resume = record['resume']
            if not isinstance(resume, dict) or resume.get('view') not in ('workspace', 'results', 'figure'):
                raise ValueError('项目包续做位置无效')
            entry['resume'] = resume
        restored.append(entry)
    return restored


def library_import_bundle(path, session):
    bundle = _folder(_bundle_path(path))
    root = library.library_root(session)
    published = []
    with tempfile.TemporaryDirectory(prefix='.titan-project-', dir=root) as temp:
        stage = Path(temp)
        try:
            manifest = _json(bundle / _MANIFEST)
            if type(manifest['version']) is not int or manifest['version'] != 1 or not isinstance(manifest['entries'], list):
                raise ValueError('不支持此项目包版本')
            if type(manifest['pinned']) is not bool:
                raise ValueError('项目包置顶记录无效')
            materials = project_materials.validate_materials(manifest['materials'])
            name = library._name(manifest['name'])
            collection = dict(id=uuid.uuid4().hex, name=name, created_at=library._now(),
                              pinned=manifest['pinned'], materials=materials)
            analysis_stage = stage / 'Analyses-and-outputs'
            analysis_final = root / 'Projects' / ('bundle-' + collection['id'])
            entries = _restore_entries(bundle, analysis_stage, analysis_final, manifest['entries'], collection['id'], session)
            for material in materials:
                original = project_materials.verified_material_path(bundle, 'bundle', material)
                managed = project_materials.material_path(stage, collection['id'], material)
                _copy(original, managed, material['sha256'])
            moves = []
            if entries:
                moves.append((analysis_stage, analysis_final))
            if materials:
                managed_stage = project_materials.material_path(stage, collection['id'], materials[0]).parents[1]
                managed_final = project_materials.material_path(root, collection['id'], materials[0]).parents[1]
                moves.append((managed_stage, managed_final))
        except (KeyError, TypeError, AttributeError, IndexError, StopIteration, OSError, RuntimeError) as error:
            raise ValueError('项目包不完整或清单无效') from error

        try:
            with library._edit_index(session) as data:
                for source, destination in moves:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    _folder(destination.parent)
                    destination.mkdir()
                    published.append(destination)
                    for child in source.iterdir():
                        child.rename(destination / child.name)
                data['projects'].append(collection)
                data['entries'].extend(entries)
        except Exception:
            for path in reversed(published):
                shutil.rmtree(path)
            raise
    return collection
