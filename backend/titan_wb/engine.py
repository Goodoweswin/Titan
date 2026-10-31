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
    if command=='inspect_image':
        from .images import inspect_image
        return inspect_image(payload['path'])
    if command=='preview_image_page':
        from .images import preview_image_page
        return preview_image_page(payload['path'],payload['page_index'],payload.get('expected_sha256'))
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
    if command=='profile':
        from .profiles import profile
        return profile(payload['project'],payload['roi_id'])
    if command=='analyze':
        from .analysis import analyze
        return analyze(payload['project'])
    if command=='export_preview':
        from .export import export_preview
        return export_preview(payload['project'],payload['result'],payload.get('settings'))
    if command=='export':
        from .export import export_analysis
        return export_analysis(payload['project'],payload['result'],payload['destination'],payload.get('settings'))
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
