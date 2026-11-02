"""Exercise WB assembly commands through a packaged engine using synthetic pixels."""
import argparse
import base64
import copy
import hashlib
import json
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image
from release_environment import packaged_environment


def verify(binary, output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    session = dict(pid=os.getpid(), token='wb-release', library_root=str(output/'library'))
    sequence = 0
    with (output/'engine-stderr.log').open('w+', encoding='utf-8') as diagnostic:
        worker = subprocess.Popen([str(binary.resolve()), '--stdio-server'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=diagnostic,
            text=True, encoding='utf-8', cwd=output, env=packaged_environment())

        def request(command, **payload):
            nonlocal sequence
            sequence += 1
            worker.stdin.write(json.dumps(dict(request_id=sequence, command=command,
                payload=payload, session=session))+'\n')
            worker.stdin.flush()
            response = json.loads(worker.stdout.readline())
            assert response.get('request_id') == sequence, response
            return response

        def call(command, **payload):
            response = request(command, **payload)
            assert response['ok'], response
            return response['data']

        try:
            health = call('health')
            expected = json.loads((Path(__file__).resolve().parents[1]/'package.json').read_text(encoding='utf-8'))['version']
            assert health['version'] == expected
            source = output/'SYNTHETIC_ONLY.png'
            pixels = np.tile(np.arange(120, dtype=np.uint8), (60, 1))
            pixels[20:30, 10:110] = 200
            Image.fromarray(pixels).save(source)
            project = call('new_project', name='WB 组图 · 合成验收')
            project = call('import_image', project=project, path=str(source))
            project['synthetic'] = True
            project = call('save_project', project=project, path=str(output/'original.titanwb'), expected_revision=None)
            unchanged = copy.deepcopy(project)
            document = call('wb_new', project=project)
            document['rows'][0].update(protein='AKT 蛋白', crop=[10, 20, 110, 30], confirmed=True, expected_mw='60')
            document['labels'] = [dict(text='Ctrl < &', x=.25)]
            preview = call('wb_preview', project=project, document=document)
            saved = call('wb_save', project=project, document=document)
            assert call('wb_list', project=project)[0]['version'] == saved['version']
            reopened = call('wb_load', project=project, document_id=saved['id'])
            assert reopened['rows'][0]['crop'] == [10, 20, 110, 30]
            reopened['name'] = '修订'
            updated = call('wb_save', project=project, document=reopened, expected_version=saved['version'])
            assert updated['version'] != saved['version']
            conflict = request('wb_save', project=project, document=reopened, expected_version=saved['version'])
            assert not conflict['ok'] and '版本' in str(conflict)
            historical = call('wb_load', project=project, document_id=saved['id'], version_id=saved['version'])
            assert historical['name'] == saved['name']
            assert call('open_project', path=project['project_path']) == unchanged
            exported = call('wb_export', project=project, document=saved, destination=str(output/'export'))
            assert (output/'export/figure.png').read_bytes() == base64.b64decode(preview['png'].split(',')[1])
            svg = ET.parse(output/'export/figure.svg').getroot()
            assert any(node.text == 'Ctrl < &' for node in svg.findall('.//{http://www.w3.org/2000/svg}text'))
            images = svg.findall('.//{http://www.w3.org/2000/svg}image')
            assert images and all(node.get('href', '').startswith('data:image/png') for node in images)
            for name, digest in exported['outputs'].items():
                assert hashlib.sha256((output/'export'/name).read_bytes()).hexdigest() == digest
            empty = copy.deepcopy(project)
            empty['images'] = []
            empty['revision'] += 1
            empty = call('save_project', project=empty, path=project['project_path'], expected_revision=project['saved_revision'])
            copied = call('save_project', project=empty, path=str(output/'portable.titanwb'), expected_revision=None)
            call('release_project', path=project['project_path'])
            shutil.rmtree(project['project_path'])
            portable = call('wb_load', project=copied, document_id=saved['id'])
            assert all(Path(row['source']['path']).is_relative_to(Path(copied['project_path'])) for row in portable['rows'])
            assert call('wb_preview', project=copied, document=portable)['png'] == preview['png']
            call('release_project', path=copied['project_path'])
            report = dict(version=health['version'], synthetic_only=True, clean_path=True,
                wb_document_without_analysis=True, project_unchanged=True, save_reopen=True,
                version_conflict_rejected=True, historical_version_preserved=True,
                portable_copy_after_original_removed=True, preview_equals_png_export=True,
                editable_svg_text=True, embedded_strip_images=len(images), outputs_sha256=exported['outputs'],
                real_wb_verified=False)
            (output/'wb-release-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
            print(json.dumps(report, ensure_ascii=False, indent=2))
        finally:
            worker.stdin.close()
            try:
                worker.wait(timeout=5)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait()
            worker.stdout.close()
            diagnostic.seek(0)
            assert 'Glyph ' not in diagnostic.read(), 'Bundled font has missing glyphs'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    verify(args.binary, args.output)
