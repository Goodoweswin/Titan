"""Verify lane-first numerics through a packaged worker (no backend imports).

The optional source is read only for pixel/page/hash checks, never annotated as
an experimental sample. Synthetic fixture identities carry no biological claim.
"""
import argparse, hashlib, json, os, struct, subprocess
from pathlib import Path
import numpy as np
import tifffile
from PIL import Image


def verify(binary, output, source=None):
    output.mkdir(parents=True, exist_ok=True)
    worker=subprocess.Popen([str(binary.resolve()),'--stdio-server'], stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,cwd=output,env={'PATH':'/usr/bin:/bin','HOME':os.environ['HOME']})
    sequence=0
    def call(command, **payload):
        nonlocal sequence
        sequence+=1
        worker.stdin.write(json.dumps(dict(request_id=sequence,command=command,payload=payload,session=dict(pid=os.getpid(),token='lane-release-verification')))+'\n');worker.stdin.flush()
        result=json.loads(worker.stdout.readline())
        assert result.get('request_id')==sequence and result['ok'],result
        return result['data']
    def pixel_check(path,index,expected):
        info=call('inspect_image',path=str(path));page=info['pages'][index]
        assert page['error'] is None
        p=call('new_project',name='原始像素检查')
        p=call('import_image',project=p,path=str(path),page_index=index,expected_sha256=info['sha256'])
        asset=p['images'][0];height,width=expected.shape;y1=min(10,height-1)
        p['rois']=[dict(id='pixel-check',image_id=asset['id'],lane_id='QA',analyte='pixel-check',role='reference',rect=[0,0,width,y1],backgrounds=[[0,y1,width,height]],reference_id=None,reviewed_revision=None)]
        measured=call('profile',project=p,roi_id='pixel-check')['measurement']
        assert measured['raw_sum']==float(expected[:y1,:].astype(np.float64).sum())
        assert measured['background_mean']==float(expected[y1:,:].astype(np.float64).mean())
        return dict(page_index=index,dtype=asset['dtype'],display_inverted=asset['display_inverted'],raw_sum_matches=True,background_matches=True)
    try:
        health=call('health');checks=[]
        for dtype,values in [('uint8',[0,16,240,255]),('uint16',[0,1000,60000,65535])]:
            path=output/f'compressed-white-{dtype}.tif';array=np.array([values,values],dtype=dtype)
            Image.fromarray(array).save(path,compression='tiff_lzw')
            with tifffile.TiffFile(path) as t:offset=t.pages[0].tags['PhotometricInterpretation'].valueoffset;order=t.byteorder
            with path.open('r+b') as f:f.seek(offset);f.write(struct.pack(order+'H',0))
            checks.append(pixel_check(path,0,array))
        real=[]
        if source:
            digest=hashlib.sha256(source.read_bytes()).hexdigest()
            with Image.open(source) as im:
                for index in range(im.n_frames):
                    im.seek(index);a=np.asarray(im).copy()
                    # Pillow transforms MINISWHITE L display; undo for raw comparison.
                    if im.tag_v2.get(262)==0 and im.mode=='L':a=np.uint8(255)-a
                    real.append(pixel_check(source,index,a))
            assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
        path=output/'golden.tif';a=np.full((40,20),1000,dtype=np.uint16);a[10:12,2:4]=3000;a[25:29,2:6]=3000;tifffile.imwrite(path,a,photometric='minisblack')
        p=call('import_image',project=call('new_project',name='定量验收 · 合成数据'),path=str(path));asset=p['images'][0];rev=p['revision']
        p['samples']=[dict(id=f'S{i}',bio_id=f'B{i}',group='control',pair_id='',kind='biological',pool_id='') for i in (1,2)]
        p['lanes']=[dict(id=f'L{i}',sample_id=f'S{i}',membrane_id='M1',technical_id='1') for i in (1,2)]
        p['lane_layouts']=[dict(id='layout',image_id=asset['id'],membrane_id='M1',window=[0,0,20,40],columns=[dict(lane_id='L1',rect=[2,0,6,40]),dict(lane_id='L2',rect=[12,0,16,40])],excluded_regions=[],source_layout_id=None,confirmed_revision=rev)]
        p['rois']=[dict(id=id,image_id=asset['id'],lane_id='L1',role=role,analyte=name,rect=rect,backgrounds=[bg],reference_id=ref,reviewed_revision=rev,lane_layout_id='layout',band_set_id=set_id) for id,role,name,rect,bg,ref,set_id in [('r','reference','ACTIN',[2,10,4,12],[2,2,4,4],None,'ref'),('t','target','AKT',[2,25,6,29],[2,35,6,38],'r','target')]]
        p['band_sets']=[dict(id=id,layout_id='layout',analyte=name,role=role,window=[0,0,20,40],reference_set_id=ref,assignments=[dict(lane_id='L1',roi_id=roi,status='accepted'),dict(lane_id='L2',roi_id=None,status='not_detected')]) for id,name,role,ref,roi in [('ref','ACTIN','reference',None,'r'),('target','AKT','target','ref','t')]]
        result=call('analyze',project=p);m={r['id']:r for r in result['measurements']}
        assert m['t']['raw_sum']==48000 and m['t']['corrected_sum']==32000 and m['r']['corrected_sum']==8000
        assert result['lane_results'][0]['normalized']==4 and result['lane_results'][1]['normalized'] is None
        p['images'][0]['display_inverted']=True
        assert call('analyze',project=p)['lane_results']==result['lane_results']
        p=call('save_project',project=p,path=str(output/'golden.titanwb'),expected_revision=None)
        p=call('open_project',path=p['project_path']);result=call('analyze',project=p)
        exported=call('export',project=p,result=result,destination=str(output/'export'))
        assert result['lane_results'][0]['normalized']==4
        for name,digest in exported['outputs'].items():assert hashlib.sha256((output/'export'/name).read_bytes()).hexdigest()==digest
        call('release_project',path=p['project_path'])
        assert call('health')['worker_pid']==health['worker_pid']
        report=dict(version=health,compressed_miniswhite=checks,source_pages=real,source_hash_unchanged=bool(source),target_raw=48000,target_net=32000,reference_net=8000,ratio=4,missing_lane=None,display_changes_numerics=False,save_reopen_export=True,worker_starts=1)
        (output/'lane-release-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
    finally:
        worker.stdin.close()
        try:worker.wait(timeout=5)
        except subprocess.TimeoutExpired:worker.kill();worker.wait()
        worker.stdout.close();worker.stderr.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--binary',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--source',type=Path)
    args=parser.parse_args();verify(args.binary,args.output.resolve(),args.source.resolve() if args.source else None)
