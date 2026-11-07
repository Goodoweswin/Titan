"""Restricted, one-request JSON engine. Diagnostics go to stderr only."""
import json
import sys
import os
from . import __version__


def dispatch(request):
    if not isinstance(request, dict):
        raise ValueError('请求必须是JSON对象')
    command = request.get('command')
    payload=request.get('payload') or {}
    session=request.get('session') or {'pid':0,'token':'cli'}
    if isinstance(command,str) and command.startswith('if_'):
        from titan_if.service import dispatch as dispatch_if
        return dispatch_if(command,payload,session)
    if isinstance(command,str) and command.startswith('stats_'):
        from titan_stats.service import dispatch as stats_dispatch
        return stats_dispatch(command,payload,session)
    if command in ('wb_new','wb_preview','wb_source_preview','wb_list','wb_save','wb_load','wb_export'):
        from . import wb_figures as wb
        project=payload['project']
        if command=='wb_new':return wb.new_document(project)
        if command=='wb_preview':return wb.preview_document(project,payload['document'])
        if command=='wb_source_preview':return wb.source_preview(project,payload['source'])
        if command=='wb_list':return wb.list_documents(project)
        if command=='wb_save':return wb.save_document(project,payload['document'],session,payload.get('expected_version'))
        if command=='wb_load':return wb.load_document(project,payload['document_id'],payload.get('version_id'))
        if command=='wb_export':
            from .library import register_published_export
            document = payload['document']
            destination = payload['destination']
            result = wb.export_document(project, document, destination)
            return register_published_export(project, result, destination, 'wb_figure_export',
                                             document['name'], project['revision'], session)
    if command == 'health':
        return {'protocol': 1, 'transport_version':2,'worker_pid':os.getpid(),'version': __version__, 'engine': 'Python / NumPy'}
    if command == 'probe':
        import numpy as np
        from .quantify import measure
        pixels = np.full((8, 8), 10, dtype=np.uint16)
        pixels[2:4, 2:4] = 30
        return measure(pixels, [2, 2, 4, 4], [[0, 0, 2, 2]], ceiling=4095)
    if command=='new_project':
        from .models import new_project
        return new_project(payload['name'])
    if command=='demo':
        from .demo import make_demo
        return make_demo()
    if command=='import_image':
        from .images import import_image
        return import_image(payload['project'],payload['path'],payload.get('page_index'),payload.get('expected_sha256'))
    if command=='rotate_image':
        from .image_rotation import rotate_image
        return rotate_image(payload['project'],payload['image_id'],payload['degrees'])
    if command=='inspect_image':
        from .images import inspect_image
        return inspect_image(payload['path'])
    if command=='preview_image_page':
        from .images import preview_image_page
        return preview_image_page(payload['path'],payload['page_index'],payload.get('expected_sha256'))
    if command=='library_list':
        from .library import library_list
        return library_list(session)
    if command=='library_create':
        from .library import library_create
        return library_create(payload['name'],session,collection_id=payload.get('collection_id'),new_collection_name=payload.get('new_collection_name'))
    if command=='library_create_from_wb':
        from .library import library_create_from_wb
        return library_create_from_wb(payload['project'], session, collection_id=payload.get('collection_id'))
    if command=='library_register':
        from .library import library_register
        return library_register(payload['path'],session,payload.get('entry_id'),source_entry_id=payload.get('source_entry_id'),touch_opened=payload.get('touch_opened',True))
    if command=='library_workspace':
        from .library import library_workspace
        return library_workspace(session)
    if command in ('library_create_collection','library_update_collection','library_remove_collection',
                   'library_assign','library_set_resume'):
        from . import library
        operations = {
            'library_create_collection': (library.library_create_collection, ('name',)),
            'library_update_collection': (library.library_update_collection, ('id','patch')),
            'library_remove_collection': (library.library_remove_collection, ('id',)),
            'library_assign': (library.library_assign, ('entry_id','collection_id')),
            'library_set_resume': (library.library_set_resume, ('entry_id','resume')),
        }
        operation, keys = operations[command]
        return operation(*(payload[key] for key in keys), session)
    if command in ('library_material_add', 'library_material_paths', 'library_material_remove'):
        from . import project_materials
        operations = {
            'library_material_add': (project_materials.library_material_add, 'paths'),
            'library_material_paths': (project_materials.library_material_paths, 'material_ids'),
            'library_material_remove': (project_materials.library_material_remove, 'material_id'),
        }
        operation, key = operations[command]
        return operation(payload['collection_id'], payload[key], session)
    if command=='library_export_bundle':
        from .project_bundle import library_export_bundle
        return library_export_bundle(payload['collection_id'], payload['destination'], session)
    if command=='library_import_bundle':
        from .project_bundle import library_import_bundle
        return library_import_bundle(payload['path'], session)
    if command=='library_record_export':
        from .library import library_record_export
        return library_record_export(payload['project_path'],payload['project_id'],payload['record'],session)
    if command=='library_check_path':
        from .library import library_check_path
        return library_check_path(payload['path'],payload.get('entry_id'),session)
    if command=='library_target':
        from .library import library_target
        return library_target(payload['entry_id'],payload.get('artifact_id'),session)
    if command=='library_remove':
        from .library import library_remove
        return library_remove(payload['entry_id'],session)
    if command=='save_figure':
        from .figure_documents import save_figure
        return save_figure(payload['project'],payload['result'],payload.get('figure_settings'),payload['name'],session,figure_id=payload.get('figure_id'),expected_version=payload.get('expected_version'),settings=payload.get('settings'),update_source=payload.get('update_source',False),default_key=payload.get('default_key'),export_origin=payload.get('export_origin'))
    if command=='load_figure':
        from .figure_documents import load_figure
        return load_figure(payload['path'],payload['figure_id'],session,payload.get('version_id'))
    if command=='save_project':
        from .projects import save_project
        return save_project(payload['project'],payload['path'],payload.get('expected_revision'),session)
    if command=='open_project':
        from .projects import open_project
        return open_project(payload['path'],session,payload.get('read_only',False))
    if command=='release_project':
        from .projects import release_project
        release_project(payload['path'],session);return True
    if command=='recover_project':
        from .projects import recover_project
        return recover_project(payload['path'],session)
    if command=='validate':
        from .models import validate_project
        return validate_project(payload['project'])
    if command=='detect':
        from .detection import detect
        return detect(payload['project'],payload['image_id'],payload['window'],payload.get('settings',{}))
    if command=='detect_lanes':
        from .lanes import detect_lanes
        return detect_lanes(payload['project'],payload['image_id'],payload['window'],payload.get('excluded_regions'),payload.get('expected_count'))
    if command=='profile':
        from .profiles import profile
        return profile(payload['project'],payload['roi_id'])
    if command=='lane_profile':
        from .bands import lane_profile
        return lane_profile(payload['project'],payload['layout_id'],payload['lane_id'],payload.get('window'))
    if command=='propose_bands':
        from .bands import propose_bands
        return propose_bands(payload['project'],payload['band_set_id'],payload.get('settings',{}))
    if command=='analyze':
        from .analysis import analyze
        return analyze(payload['project'])
    if command=='export_preview':
        from .export import export_preview
        return export_preview(payload['project'],payload['result'],payload.get('settings'),payload.get('figure_settings'))
    if command=='export':
        from .export import export_analysis
        from .library import register_published_export
        project, analysis, destination = payload['project'], payload['result'], payload['destination']
        result = export_analysis(project, analysis, destination, payload.get('settings'), payload.get('figure_settings'))
        return register_published_export(project, result, destination, 'result_export',
                                         project['name']+' · 定量结果', analysis['input_revision'], session)
    raise ValueError('不支持的引擎命令')


def main():
    try:
        raw = sys.stdin.read(20 * 1024 * 1024 + 1)
        if len(raw) > 20 * 1024 * 1024:
            raise ValueError('请求过大')
        data = dispatch(json.loads(raw))
        response = {'ok': True, 'data': data, 'error': None}
    except Exception as e:
        response = {'ok': False, 'data': None, 'error': str(e)}
    sys.stdout.write(json.dumps(response, ensure_ascii=False, allow_nan=False))


def serve(input_stream,output_stream):
    """Newline-delimited, bounded UTF-8 frames; keep legacy main() intact."""
    limit=20*1024*1024
    while True:
        raw=input_stream.readline(limit+1)
        if not raw:return
        request_id=None
        try:
            if len(raw)>limit:
                while not raw.endswith(b'\n'):
                    raw=input_stream.readline(limit+1)
                    if not raw:break
                raise ValueError('请求过大')
            request=json.loads(raw)
            if isinstance(request,dict):request_id=request.get('request_id')
            result=dispatch(request)
            response=dict(request_id=request_id,ok=True,data=result,error=None)
        except Exception as e:
            response=dict(request_id=request_id,ok=False,data=None,error=str(e))
        try:
            encoded=json.dumps(response,ensure_ascii=False,allow_nan=False).encode('utf-8')
            if len(encoded)>limit:raise ValueError('返回数据过大，请减少本次图像数量')
        except (ValueError,TypeError) as e:
            encoded=json.dumps(dict(request_id=request_id,ok=False,data=None,error=str(e)),ensure_ascii=False).encode('utf-8')
        output_stream.write(encoded+b'\n');output_stream.flush()
