import copy
import os
import tempfile
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
from titan_wb.models import new_project, validate_project
from titan_wb.images import import_image, read_pixels
from titan_wb.projects import save_project, open_project, release_project,recover_project

SESSION={'pid':os.getpid(),'token':'unit-session'}

class ProjectsTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  self.image=self.root/'原始 图.tif';Image.fromarray(np.full((10,12),12345,dtype=np.uint16)).save(self.image)
 def tearDown(self):self.tmp.cleanup()
 def test_preserves_16bit_and_source_bytes(self):
  p=import_image(new_project('测试'),str(self.image))
  a=p['images'][0];self.assertEqual(read_pixels(a)[0,0],12345)
  self.assertTrue(a['preview'].startswith('data:image/png;base64,'))
 def test_rgb_and_multipage_are_explicitly_rejected(self):
  rgb=self.root/'rgb.png';Image.new('RGB',(5,5)).save(rgb)
  with self.assertRaises(ValueError):import_image(new_project('t'),str(rgb))
  stack=self.root/'stack.tif';Image.new('L',(5,5)).save(stack,save_all=True,append_images=[Image.new('L',(5,5))])
  with self.assertRaises(ValueError):import_image(new_project('t'),str(stack))
 def test_save_reopen_owns_originals_and_checks_hash(self):
  p=import_image(new_project('测试'),str(self.image));path=self.root/'中文实验.titanwb'
  p=save_project(p,str(path),None,SESSION);self.image.unlink()
  p2=open_project(str(path),SESSION)
  self.assertEqual(p2['images'][0]['sha256'],p['images'][0]['sha256'])
  self.assertEqual(read_pixels(p2['images'][0])[0,0],12345)
  Path(p2['images'][0]['path']).write_bytes(b'changed')
  with self.assertRaises(ValueError):open_project(str(path),SESSION)
 def test_lock_and_revision_conflicts_do_not_overwrite(self):
  p=save_project(new_project('a'),str(self.root/'p.titanwb'),None,SESSION)
  with self.assertRaises(ValueError):open_project(p['project_path'],{'pid':os.getpid(),'token':'other'})
  p['revision']=2
  with self.assertRaises(ValueError):save_project(p,p['project_path'],99,SESSION)
  self.assertEqual(open_project(p['project_path'],SESSION)['revision'],0)
 def test_unknown_schema_and_duplicate_ids_are_rejected(self):
  p=new_project('a');p['schema_version']=99
  with self.assertRaises(ValueError):validate_project(p)
 def test_readonly_open_cannot_write_without_lock(self):
  p=save_project(new_project('a'),str(self.root/'p.titanwb'),None,SESSION)
  other={'pid':os.getpid(),'token':'other'}
  ro=open_project(p['project_path'],other,True)
  with self.assertRaises(ValueError):save_project(ro,ro['project_path'],0,other)
 def test_release_allows_next_session(self):
  p=save_project(new_project('a'),str(self.root/'p.titanwb'),None,SESSION)
  release_project(p['project_path'],SESSION)
  self.assertFalse(open_project(p['project_path'],{'pid':os.getpid(),'token':'other'})['read_only'])
 def test_valid_backup_recovers_to_new_copy_without_overwriting_damage(self):
  path=self.root/'recover.titanwb';p=save_project(new_project('first'),str(path),None,SESSION)
  p['name']='second';p['revision']=1;save_project(p,str(path),0,SESSION)
  (path/'project.json').write_text('damaged')
  r=recover_project(str(path),SESSION)
  self.assertEqual(r['name'],'first');self.assertNotEqual(r['project_path'],str(path))
  self.assertEqual((path/'project.json').read_text(),'damaged')
 def test_live_foreign_lock_cannot_be_recovered(self):
  p=save_project(new_project('a'),str(self.root/'live.titanwb'),None,SESSION)
  with self.assertRaises(ValueError):recover_project(p['project_path'],{'pid':os.getpid(),'token':'other'})
