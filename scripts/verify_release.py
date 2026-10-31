"""Exercise the bundled engine away from the source tree with a clean PATH.

This does NOT claim to automate the native macOS window.
"""
import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def verify(app,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='titan-release-') as tmp:
        root=Path(tmp);copied=root/'Titan WB.app';shutil.copytree(app,copied)
        binary=copied/'Contents/MacOS/wb-engine'
        session=dict(pid=os.getpid(),token='release-verification')
        def call(command,payload=None):
            print('Checking bundled command:', command, flush=True)
            p=subprocess.run([str(binary)],input=json.dumps(dict(command=command,payload=payload or {},session=session)),
                text=True,capture_output=True,cwd=root,timeout=60,
                env={'PATH':'/usr/bin:/bin','HOME':os.environ['HOME'],'TMPDIR':tmp})
            assert p.returncode==0,p.stderr
            response=json.loads(p.stdout);assert response['ok'],response.get('error')
            return response['data']
        health=call('health');assert health['protocol']==1
        assert call('probe')['corrected_sum']==80
        project=call('demo');result=call('analyze',dict(project=project))
        assert len(result['measurements'])==24
        assert len(result['normalized'])==12
        assert sum(r['normalized'] is None for r in result['normalized'])==1
        assert len(result['biological'])==6
        profile=call('profile',dict(project=project,roi_id=project['rois'][0]['id']))
        assert profile['measurement']['corrected_sum']==result['measurements'][0]['corrected_sum']
        preview=call('export_preview',dict(project=project,result=result))
        assert preview['width']>0 and preview['height']>0
        project=call('save_project',dict(project=project,path=str(root/'实验.titanwb'),expected_revision=None))
        reopened=call('open_project',dict(path=project['project_path']))
        assert reopened['id']==project['id']
        exported=call('export',dict(project=project,result=result,destination=str(root/'导出结果')))
        assert (root/'导出结果/plot.svg').is_file()
        assert hashlib.sha256(base64.b64decode(preview['png'].split(',')[1])).hexdigest()==exported['outputs']['plot.png']
        for name, digest in exported['outputs'].items():
            assert hashlib.sha256((root/'导出结果'/name).read_bytes()).hexdigest()==digest
        call('release_project',dict(path=project['project_path']))
        sig=subprocess.run(['codesign','--verify','--deep','--strict',str(copied)],capture_output=True,text=True)
        assert sig.returncode==0,sig.stderr
        report=dict(engine_protocol=health['protocol'],clean_path=True,source_independent_copy=True,
             measurements=24,targets=12,blocked=1,biological_units=6,save_reopen=True,export_files=len(exported['outputs']),
             signature_verify_exit=sig.returncode,signature_verify_message=sig.stderr,
             profile_matches_measurement=True,preview_matches_export=True,
             native_window_verified=False,real_wb_verified=False)
        (output/'release-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
        print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--app',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();verify(Path(a.app),a.output)
