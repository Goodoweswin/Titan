import copy
import numpy as np
import pytest
from PIL import Image
from titan_wb.engine import dispatch
from titan_wb.images import import_image,read_pixels,file_hash
from titan_wb.models import new_project,validate_project
from titan_wb.analysis import measure_project
from titan_wb.projects import save_project,release_project,open_project


def source(tmp_path,a):
 path=tmp_path/'original.png';Image.fromarray(a).save(path)
 return import_image(new_project('rotation'),str(path)),path


def corrected(p,angle):
 return dispatch({'command':'rotate_image','payload':{'project':p,'image_id':p['images'][0]['id'],'degrees':angle}})


def test_right_angle_rotation_preserves_raw_values_and_source_file(tmp_path):
 p,path=source(tmp_path,np.array([[1,2,3],[4,5,6]],dtype=np.uint8));before=file_hash(path)
 a=corrected(p,90)
 assert (a['width'],a['height'])==(2,3)
 np.testing.assert_array_equal(read_pixels(a),[[4,1],[5,2],[6,3]])
 assert file_hash(path)==before and p['images'][0]['width']==3
 assert a['id']!=p['images'][0]['id'] and a['sha256']==before


def test_fine_rotation_quantifies_original_pixel_centers_not_interpolation(tmp_path):
 p,_=source(tmp_path,np.full((5,5),20,dtype=np.uint8));a=corrected(p,45)
 # For 45 degrees the central 3x3 view box contains 13 original centers.
 p['images'].append(a);p['samples']=[dict(id='S1',bio_id='B1',group='control')];p['lanes']=[dict(id='L1',sample_id='S1',membrane_id='M1')]
 p['rois']=[dict(id='r',image_id=a['id'],lane_id='L1',analyte='A',role='reference',rect=[2,2,5,5],backgrounds=[[0,0,7,2]],reference_id=None,reviewed_revision=p['revision'])]
 m=measure_project(p)[0]
 assert m['area_px']==13 and m['raw_sum']==260 and m['background_mean']==20 and m['corrected_sum']==0
 assert a['rotation_degrees']==45


def test_corrected_image_roundtrips_with_portable_originals_and_rejects_tampering(tmp_path):
 p,path=source(tmp_path,np.arange(20,dtype=np.uint8).reshape(4,5));a=corrected(p,-3.5);p['images'].append(a)
 session={'pid':0,'token':'rotation'};dest=tmp_path/'saved.titanwb'
 saved=save_project(p,str(dest),None,session);release_project(str(dest),session);path.unlink()
 reopened=open_project(str(dest),session)
 np.testing.assert_array_equal(read_pixels(reopened['images'][1]),read_pixels(saved['images'][1]))
 Image.fromarray(np.zeros((4,5),dtype=np.uint8)).save(saved['images'][1]['path'])
 with pytest.raises(ValueError,match='hash'):read_pixels(saved['images'][1])
 release_project(str(dest),session)


@pytest.mark.parametrize('degrees',[float('nan'),float('inf'),True,'2',361])
def test_invalid_rotation_is_rejected_without_mutation(tmp_path,degrees):
 p,_=source(tmp_path,np.ones((4,5),dtype=np.uint8));old=copy.deepcopy(p)
 with pytest.raises(ValueError):corrected(p,degrees)
 assert p==old
 p['images'][0]['rotation_degrees']=degrees
 with pytest.raises(ValueError):validate_project(p)
