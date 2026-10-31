import tempfile
import unittest
import json
from pathlib import Path

import numpy as np
import tifffile

from titan_wb.engine import dispatch
from titan_wb.images import import_image, read_pixels, file_hash
from titan_wb.models import new_project, validate_project
from titan_wb.projects import save_project, open_project


class ImagePagesTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  self.path=self.root/'多页.tif'
  with tifffile.TiffWriter(self.path) as t:
   t.write(np.full((8,10),12345,dtype=np.uint16),photometric='minisblack')
   t.write(np.full((6,9),54321,dtype=np.uint16),photometric='minisblack')
 def tearDown(self):self.tmp.cleanup()
 def test_inspection_and_preview_do_not_silently_choose_a_page(self):
  info=dispatch({'command':'inspect_image','payload':{'path':str(self.path)}})
  self.assertEqual(info['page_count'],2)
  self.assertEqual([(p['width'],p['height'],p['dtype']) for p in info['pages']],[(10,8,'uint16'),(9,6,'uint16')])
  self.assertTrue(all(p['error'] is None for p in info['pages']))
  with self.assertRaises(ValueError):import_image(new_project('t'),str(self.path))
  preview=dispatch({'command':'preview_image_page','payload':{'path':str(self.path),'page_index':1,'expected_sha256':info['sha256']}})
  self.assertTrue(preview.startswith('data:image/png;base64,'))
 def test_selected_page_retains_original_values_after_portable_save(self):
  p=import_image(new_project('t'),str(self.path),page_index=1)
  asset=p['images'][0]
  self.assertEqual((asset['page_index'],asset['page_count'],asset['width'],asset['height']),(1,2,9,6))
  self.assertIn('第 2 页',asset['name'])
  self.assertEqual(read_pixels(asset).dtype,np.uint16)
  self.assertEqual(int(read_pixels(asset)[0,0]),54321)
  session={'pid':0,'token':'page-test'}
  saved=save_project(p,str(self.root/'t.titanwb'),None,session)
  self.path.unlink()
  reopened=open_project(saved['project_path'],session)
  self.assertEqual(int(read_pixels(reopened['images'][0])[0,0]),54321)
 def test_separate_imports_of_the_same_file_read_their_own_pages(self):
  p=import_image(new_project('t'),str(self.path),page_index=0)
  p=import_image(p,str(self.path),page_index=1)
  self.assertNotEqual(p['images'][0]['id'],p['images'][1]['id'])
  self.assertEqual([int(read_pixels(a)[0,0]) for a in p['images']],[12345,54321])
 def test_invalid_page_indices_and_changed_sources_are_rejected(self):
  for index in [-1,2,True,0.5,'1']:
   with self.subTest(index=index),self.assertRaises(ValueError):
    import_image(new_project('t'),str(self.path),page_index=index)
  old_hash=file_hash(self.path)
  with tifffile.TiffWriter(self.path,append=True) as t:t.write(np.zeros((2,2),dtype=np.uint8))
  with self.assertRaises(ValueError):
   import_image(new_project('t'),str(self.path),page_index=0,expected_sha256=old_hash)
 def test_unsupported_page_does_not_prevent_selecting_valid_page(self):
  with tifffile.TiffWriter(self.path,append=True) as t:t.write(np.zeros((4,5,3),dtype=np.uint8),photometric='rgb')
  info=dispatch({'command':'inspect_image','payload':{'path':str(self.path)}})
  self.assertIsNotNone(info['pages'][2]['error'])
  self.assertEqual(int(read_pixels(import_image(new_project('t'),str(self.path),page_index=1)['images'][0])[0,0]),54321)
  with self.assertRaises(ValueError):import_image(new_project('t'),str(self.path),page_index=2)
 def test_invalid_saved_page_metadata_is_rejected(self):
  p=import_image(new_project('t'),str(self.path),page_index=1)
  p['images'][0]['page_index']=-1
  with self.assertRaises(ValueError):validate_project(p)
 def test_engine_quantification_and_export_use_selected_page(self):
  p=dispatch({'command':'import_image','payload':{'project':new_project('t'),'path':str(self.path),'page_index':1}})
  p['samples']=[dict(id='S1',bio_id='B1',group='control',kind='biological',pair_id='',pool_id='')]
  p['lanes']=[dict(id='L1',sample_id='S1',membrane_id='M1',technical_id='1')]
  p['rois']=[dict(id='R1',image_id=p['images'][0]['id'],lane_id='L1',analyte='TARGET',role='target',rect=[0,0,2,2],backgrounds=[[2,0,4,2]],reference_id=None,reviewed_revision=p['revision'])]
  result=dispatch({'command':'analyze','payload':{'project':p}})
  self.assertEqual(result['measurements'][0]['raw_sum'],217284)
  self.assertEqual(result['measurements'][0]['background_mean'],54321)
  dest=self.root/'export'
  dispatch({'command':'export','payload':{'project':p,'result':result,'destination':str(dest)}})
  exported=json.loads((dest/'project.json').read_text())
  asset=exported['images'][0];asset['path']=str(dest/asset['path'])
  self.assertEqual(asset['page_index'],1)
  self.assertEqual(file_hash(asset['path']),file_hash(self.path))
  self.assertEqual(int(read_pixels(asset)[0,0]),54321)
