import numpy as np
from PIL import Image
from titan_wb.models import new_project
from titan_wb.images import import_image
from titan_wb.analysis import analyze

def fixture(tmp_path):
 a=np.full((40,20),1000,dtype=np.uint16);a[10:12,2:4]=3000;a[25:29,2:6]=3000
 path=tmp_path/'ratios.tif';Image.fromarray(a).save(path);p=import_image(new_project('ratios'),str(path));im=p['images'][0]
 p['samples']=[dict(id=f'S{i}',bio_id=f'B{i}',group='control',pair_id='',kind='biological',pool_id='') for i in (1,2)]
 p['lanes']=[dict(id=f'L{i}',sample_id=f'S{i}',membrane_id='M1',technical_id='1') for i in (1,2)]
 p['lane_layouts']=[dict(id='layout',image_id=im['id'],membrane_id='M1',window=[0,0,20,40],columns=[dict(lane_id='L1',rect=[2,0,6,40]),dict(lane_id='L2',rect=[12,0,16,40])],excluded_regions=[],source_layout_id=None,confirmed_revision=p['revision'])]
 p['rois']=[dict(id='r',image_id=im['id'],lane_id='L1',role='reference',analyte='ACTIN',rect=[2,10,4,12],backgrounds=[[2,2,4,4]],reference_id=None,reviewed_revision=p['revision'],lane_layout_id='layout',band_set_id='ref'),dict(id='t',image_id=im['id'],lane_id='L1',role='target',analyte='AKT',rect=[2,25,6,29],backgrounds=[[2,35,6,38]],reference_id='r',reviewed_revision=p['revision'],lane_layout_id='layout',band_set_id='target')]
 p['band_sets']=[dict(id=id,layout_id='layout',analyte=analyte,role=role,window=[0,0,20,40],reference_set_id=ref,assignments=[dict(lane_id='L1',roi_id=roi,status='accepted'),dict(lane_id='L2',roi_id=None,status='not_detected')]) for id,analyte,role,ref,roi in [('ref','ACTIN','reference',None,'r'),('target','AKT','target','ref','t')]]
 return p

def test_lane_ratios_include_missing_slots_without_inventing_biological_n(tmp_path):
 result=analyze(fixture(tmp_path))
 assert len(result['lane_results'])==2
 assert result['lane_results'][0]['normalized']==4
 assert result['lane_results'][0]['reference_net']==8000
 assert result['lane_results'][1]['lane_id']=='L2' and result['lane_results'][1]['normalized'] is None
 assert result['lane_results'][1]['status']=='not_detected'
 assert result['biological']==[] and result['statistics']==[]

def test_nonpositive_reference_does_not_produce_valid_ratio(tmp_path):
 p=fixture(tmp_path);p['rois'][0]['rect']=[2,4,4,6]
 assert analyze(p)['lane_results'][0]['normalized'] is None

def test_unconfirmed_replicate_mapping_does_not_block_lane_ratios(tmp_path):
 from titan_wb.images import file_hash
 p=fixture(tmp_path);a=np.asarray(Image.open(p['images'][0]['path'])).copy();a[10:12,12:14]=3000;a[25:29,12:16]=3000
 Image.fromarray(a).save(p['images'][0]['path']);p['images'][0]['sha256']=file_hash(p['images'][0]['path'])
 p['samples'][1]['bio_id']='B1'
 import copy
 for original,id in [(p['rois'][0],'r2'),(p['rois'][1],'t2')]:
  roi=copy.deepcopy(original);roi.update(id=id,lane_id='L2',rect=[v+10 if i%2==0 else v for i,v in enumerate(roi['rect'])],backgrounds=[[v+10 if i%2==0 else v for i,v in enumerate(b)] for b in roi['backgrounds']],reference_id='r2' if roi['role']=='target' else None);p['rois'].append(roi)
 for g,id in zip(p['band_sets'],['r2','t2']):g['assignments'][1].update(roi_id=id,status='accepted')
 result=analyze(p)
 assert [r['normalized'] for r in result['lane_results']]==[4,4]
 assert result['biological']==[]
