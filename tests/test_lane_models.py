import copy,json
import numpy as np
import pytest
from PIL import Image
from titan_wb.models import new_project,validate_project
from titan_wb.images import import_image
from titan_wb.projects import save_project,open_project,recover_project

def project(tmp_path):
 path=tmp_path/'a.png';Image.fromarray(np.zeros((40,60),dtype=np.uint8)).save(path)
 p=import_image(new_project('lanes'),str(path))
 p['samples']=[dict(id=f'S{i}',bio_id=f'B{i}',group='control',pair_id='',kind='biological',pool_id='') for i in range(1,4)]
 p['lanes']=[dict(id=f'L{i}',sample_id=f'S{i}',membrane_id='M1',technical_id='1') for i in range(1,4)]
 p['lane_layouts']=[dict(id='layout',image_id=p['images'][0]['id'],membrane_id='M1',window=[0,0,60,40],columns=[dict(lane_id=f'L{i}',rect=[(i-1)*20,0,i*20,40]) for i in range(1,4)],excluded_regions=[],source_layout_id=None,confirmed_revision=p['revision'])]
 p['band_sets']=[dict(id='ref',layout_id='layout',analyte='ACTIN',role='reference',window=[0,5,60,20],reference_set_id=None,assignments=[dict(lane_id=f'L{i}',roi_id=None,status='not_detected') for i in range(1,4)])]
 return p

def test_new_schema_and_missing_assignment_preserve_lane_identity(tmp_path):
 p=project(tmp_path);assert p['schema_version']==2
 validate_project(p)
 p['lane_layouts'][0]['columns'][1]['rect']=[21,0,39,40]
 validate_project(p)
 assert p['band_sets'][0]['assignments'][2]['lane_id']=='L3'

@pytest.mark.parametrize('mutation',['overlap','duplicate','cross_membrane','bad_assignment'])
def test_invalid_layout_and_reference_links_are_rejected(tmp_path,mutation):
 p=project(tmp_path)
 if mutation=='overlap':p['lane_layouts'][0]['columns'][1]['rect']=[10,0,40,40]
 if mutation=='duplicate':p['lane_layouts'][0]['columns'][1]['lane_id']='L1'
 if mutation=='cross_membrane':p['lanes'][1]['membrane_id']='M2'
 if mutation=='bad_assignment':p['band_sets'][0]['assignments'][1]['lane_id']='L999'
 with pytest.raises(ValueError):validate_project(p)

def test_v1_migration_requires_new_copy_and_does_not_invent_geometry(tmp_path):
 p=project(tmp_path);p['schema_version']=1;p.pop('lane_layouts');p.pop('band_sets')
 root=tmp_path/'old.titanwb';root.mkdir();(root/'originals').mkdir()
 import shutil
 image=p['images'][0];dest=root/'originals/a.png';shutil.copy2(image['path'],dest);image['path']='originals/a.png'
 raw=json.dumps(p);(root/'project.json').write_text(raw)
 session=dict(pid=0,token='migration')
 migrated=open_project(str(root),session)
 assert migrated['schema_version']==2 and migrated['lane_layouts']==[]
 assert migrated['lanes']==p['lanes'] and migrated['upgrade_from']==str(root)
 assert recover_project(str(root),session)['schema_version']==2
 with pytest.raises(ValueError):save_project(migrated,str(root),p['revision'],session)
 saved=save_project(migrated,str(tmp_path/'new.titanwb'),None,session)
 assert saved['schema_version']==2 and (root/'project.json').read_text()==raw
