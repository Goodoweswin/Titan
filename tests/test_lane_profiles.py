import numpy as np
from PIL import Image
from titan_wb.models import new_project
from titan_wb.images import import_image
from titan_wb.bands import lane_profile,propose_bands
from titan_wb.quantify import measure

def fixture(tmp_path,second=False,empty=False,width=4):
 a=np.full((40,width+4),1000,dtype=np.uint16)
 if not empty:a[12:16,2:2+width]=3000
 if second:a[26:30,2:2+width]=4000
 path=tmp_path/f'curve-{second}-{empty}-{width}.tif';Image.fromarray(a).save(path)
 p=import_image(new_project('curve'),str(path));im=p['images'][0]
 p['samples']=[dict(id='S1',bio_id='B1',group='control',pair_id='',kind='biological',pool_id='')]
 p['lanes']=[dict(id='L1',sample_id='S1',membrane_id='M1',technical_id='1')]
 p['lane_layouts']=[dict(id='layout',image_id=im['id'],membrane_id='M1',window=[0,0,width+4,40],columns=[dict(lane_id='L1',rect=[2,0,2+width,40])],excluded_regions=[],source_layout_id=None,confirmed_revision=p['revision'])]
 p['band_sets']=[dict(id='ref',layout_id='layout',analyte='ACTIN',role='reference',window=[0,5,width+4,35],reference_set_id=None,assignments=[dict(lane_id='L1',roi_id=None,status='pending')])]
 return p,a

def test_curve_sum_preserves_lane_width_and_exact_background_integral(tmp_path):
 p,a=fixture(tmp_path);data=lane_profile(p,'layout','L1')
 assert data['samples'][12]['sum']==12000
 assert sum(s['sum']-4000 for s in data['samples'])==32000
 assert measure(a,[2,12,6,16],[[2,5,6,8]])['corrected_sum']==32000
 p,a=fixture(tmp_path,width=8)
 assert sum(s['sum']-8000 for s in lane_profile(p,'layout','L1')['samples'])==64000

def test_proposed_integral_uses_existing_union_background_contract(tmp_path):
 p,a=fixture(tmp_path);r=propose_bands(p,'ref',{})[0]
 assert r['status']=='proposed' and len(r['candidates'])==1
 band=r['candidates'][0]
 assert measure(a,band['rect'],band['backgrounds'])['corrected_sum']==32000

def test_missing_and_multiple_peaks_are_not_automatically_assigned(tmp_path):
 p,_=fixture(tmp_path,empty=True);r=propose_bands(p,'ref',{})[0]
 assert r['status']=='not_detected' and r['candidates']==[]
 p,_=fixture(tmp_path,second=True);r=propose_bands(p,'ref',{})[0]
 assert r['status']=='ambiguous' and len(r['candidates'])==2
