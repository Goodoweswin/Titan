"""Verify source-pixel rotation through the actual packaged executable."""
import argparse,hashlib,json,os,subprocess
from pathlib import Path
import numpy as np
import tifffile
from release_environment import packaged_environment


def verify(binary,output):
    output=output.resolve();output.mkdir(parents=True,exist_ok=False)
    diagnostic=(output/'engine-stderr.log').open('w',encoding='utf-8')
    worker=subprocess.Popen([str(binary.resolve()),'--stdio-server'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=diagnostic,text=True,encoding='utf-8',cwd=output,env=packaged_environment())
    sequence=0;session=dict(pid=os.getpid(),token='rotation-release')
    def call(command,**payload):
        nonlocal sequence
        sequence+=1
        worker.stdin.write(json.dumps(dict(request_id=sequence,command=command,payload=payload,session=session))+'\n');worker.stdin.flush()
        response=json.loads(worker.stdout.readline());assert response.get('request_id')==sequence and response['ok'],response
        return response['data']
    try:
        health=call('health');expected=json.loads((Path(__file__).resolve().parents[1]/'package.json').read_text(encoding='utf-8'))['version'];assert health['version']==expected
        path=output/'SYNTHETIC_ONLY.tif';tifffile.imwrite(path,np.full((5,5),20,dtype=np.uint16));digest=hashlib.sha256(path.read_bytes()).hexdigest()
        p=call('import_image',project=call('new_project',name='rotation synthetic check'),path=str(path));a=call('rotate_image',project=p,image_id=p['images'][0]['id'],degrees=45);p['images'].append(a)
        p['samples']=[dict(id='S1',bio_id='B1',group='control')];p['lanes']=[dict(id='L1',sample_id='S1',membrane_id='M1')]
        p['rois']=[dict(id='r',image_id=a['id'],lane_id='L1',analyte='A',role='reference',rect=[2,2,5,5],backgrounds=[[0,0,7,2]],reference_id=None,reviewed_revision=p['revision'])]
        m=call('analyze',project=p)['measurements'][0];assert m['area_px']==13 and m['raw_sum']==260 and m['background_mean']==20 and m['corrected_sum']==0,m
        assert call('profile',project=p,roi_id='r')['measurement']['raw_sum']==260
        p=call('save_project',project=p,path=str(output/'rotation.titanwb'),expected_revision=None);p=call('open_project',path=p['project_path']);assert call('analyze',project=p)['measurements'][0]['raw_sum']==260
        assert hashlib.sha256(path.read_bytes()).hexdigest()==digest;call('release_project',path=p['project_path'])
        report=dict(version=health['version'],original_hash_unchanged=True,original_area_px=13,raw_sum=260,profile_matches=True,save_reopen=True)
        (output/'rotation-release-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
    finally:
        worker.stdin.close()
        try:worker.wait(timeout=5)
        except subprocess.TimeoutExpired:worker.kill();worker.wait()
        worker.stdout.close();diagnostic.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--binary',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();verify(args.binary,args.output)
