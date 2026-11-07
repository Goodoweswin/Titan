"""Explicitly registered, project-owned copies of local files."""
import hashlib
import os
import re
import shutil
import stat
import uuid
from pathlib import Path, PureWindowsPath
from tempfile import TemporaryDirectory

from .library import _collection, _edit_index, _index, _now, library_root


def _validate_material(material):
    if not isinstance(material, dict) or material.keys() != {'id', 'name', 'size', 'sha256', 'added_at'}:
        raise ValueError('项目资料记录损坏')
    if not isinstance(material['id'], str) or not re.fullmatch(r'[0-9a-f]{32}', material['id']):
        raise ValueError('项目资料标识无效')
    name = material['name']
    if not isinstance(name, str) or not name or name in ('.', '..') or '/' in name or '\0' in name:
        raise ValueError('项目资料文件名无效')
    name.encode('utf-8')
    if type(material['size']) is not int or material['size'] < 0:
        raise ValueError('项目资料大小无效')
    if not isinstance(material['sha256'], str) or not re.fullmatch(r'[0-9a-f]{64}', material['sha256']):
        raise ValueError('项目资料校验值无效')
    if not isinstance(material['added_at'], str) or not material['added_at']:
        raise ValueError('项目资料登记时间无效')


def validate_materials(materials):
    if not isinstance(materials, list):
        raise ValueError('项目资料清单损坏')
    seen = set()
    for material in materials:
        _validate_material(material)
        if material['id'] in seen:
            raise ValueError('项目资料标识重复')
        seen.add(material['id'])
    return materials


def _portable_name(name):
    # Preserve the displayed name in the catalog, while making the stored
    # basename usable by importers on both macOS and Windows.
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).rstrip(' .') or 'material'
    if PureWindowsPath(name).is_reserved():
        name = '_' + name[1:]
    return name


def material_path(root, collection_id, material):
    """Find a material's deterministic storage location, even before it exists."""
    _validate_material(material)
    if not isinstance(collection_id, str) or not collection_id:
        raise ValueError('课题项目标识无效')
    # A hash keeps even legacy project IDs with path separators inside the library.
    collection_key = hashlib.sha256(collection_id.encode('utf-8')).hexdigest()
    path = Path(root).resolve() / 'Materials' / collection_key / material['id'] / _portable_name(material['name'])
    try:
        if path.resolve() != path:
            raise ValueError('项目资料目录或文件已变化')
    except (OSError, RuntimeError) as exc:
        raise ValueError('项目资料目录或文件已变化') from exc
    return path


def verified_material_path(root, collection_id, material):
    """Return the owned file after verifying its recorded bytes."""
    _validate_material(material)
    try:
        path = material_path(root, collection_id, material)
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size != material['size']:
            raise ValueError('项目资料大小或类型已变化')
        with path.open('rb') as file:
            if hashlib.file_digest(file, 'sha256').hexdigest() != material['sha256']:
                raise ValueError('项目资料内容已变化')
    except (OSError, ValueError) as exc:
        raise ValueError(f'项目资料「{material["name"]}」缺失或已变化，请重新添加') from exc
    return path


def _stage_copy(path, folder):
    source = Path(path).expanduser()
    material_id = uuid.uuid4().hex
    staged = folder / material_id
    digest = hashlib.sha256()
    size = 0
    try:
        if not source.is_file():
            raise ValueError(f'请选择可读取的普通文件：{source.name}')
        with source.open('rb') as original, staged.open('xb') as copy:
            for block in iter(lambda: original.read(1024 * 1024), b''):
                copy.write(block)
                digest.update(block)
                size += len(block)
            copy.flush()
            os.fsync(copy.fileno())
    except OSError as exc:
        raise ValueError(f'无法复制项目资料「{source.name}」') from exc
    return staged, dict(id=material_id, name=source.name, size=size, sha256=digest.hexdigest(), added_at=_now())


def library_material_add(collection_id, paths, session):
    if not isinstance(paths, list) or not paths or any(not isinstance(path, str) or not path for path in paths):
        raise ValueError('请选择要添加的资料文件')
    root = library_root(session)
    _collection(_index(root), collection_id)
    with TemporaryDirectory(prefix='.material-stage-', dir=root) as directory:
        staged = [_stage_copy(path, Path(directory)) for path in paths]
        materials = [material for _, material in staged]
        installed = []
        try:
            # Recheck the project and append to its latest list under the index lock.
            with _edit_index(session) as data:
                project = _collection(data, collection_id)
                for copy, material in staged:
                    target = material_path(root, collection_id, material)
                    target.parent.mkdir(parents=True)
                    installed.append(target.parent)
                    copy.replace(target)
                project.setdefault('materials', []).extend(materials)
        except Exception:
            for folder in installed:
                shutil.rmtree(folder)
            raise
    return materials


def library_material_paths(collection_id, material_ids, session):
    if not isinstance(material_ids, list) or any(not isinstance(item, str) for item in material_ids):
        raise ValueError('项目资料选择无效')
    root = library_root(session)
    project = _collection(_index(root), collection_id)
    by_id = {material['id']: material for material in project.get('materials', [])}
    try:
        materials = [by_id[material_id] for material_id in material_ids]
    except KeyError as exc:
        raise ValueError('找不到该项目资料，请刷新资料列表') from exc
    return [str(verified_material_path(root, collection_id, material)) for material in materials]


def library_material_remove(collection_id, material_id, session):
    with _edit_index(session) as data:
        project = _collection(data, collection_id)
        materials = project.get('materials', [])
        for index, material in enumerate(materials):
            if material['id'] == material_id:
                # A detached copy may still be an input to an unsaved analysis.
                materials.pop(index)
                return True
        raise ValueError('找不到该项目资料，请刷新资料列表')
