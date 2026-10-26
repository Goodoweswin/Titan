import json
import tempfile
import unittest
from pathlib import Path
from titan_wb.demo import make_demo
from titan_wb.analysis import analyze
from titan_wb.export import export_analysis,plot_groups
from titan_wb.images import file_hash


class ExportTests(unittest.TestCase):
 def test_export_chart_does_not_pool_membranes(self):
  groups=plot_groups([dict(analyte='X',analysis_block='M1'),dict(analyte='X',analysis_block='M2')])
  self.assertEqual(len(groups),2)
 def test_complete_export_hashes_and_no_overwrite(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=make_demo();r=analyze(p);out=Path(tmp)/'结果'
   m=export_analysis(p,r,str(out))
   self.assertTrue((out/'plot.png').is_file());self.assertTrue((out/'plot.svg').is_file())
   self.assertTrue((out/'measurements.csv').is_file());self.assertTrue((out/'project.json').is_file())
   for name,digest in m['outputs'].items():self.assertEqual(file_hash(out/name),digest)
   with self.assertRaises(ValueError):export_analysis(p,r,str(out))
 def test_old_revision_cannot_be_exported_as_current(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=make_demo();r=analyze(p);p['revision']+=1
   with self.assertRaises(ValueError):export_analysis(p,r,str(Path(tmp)/'result'))

class PreviewTests(unittest.TestCase):
 def test_preview_matches_export_dimensions_pixels_and_audit(self):
  import base64,io
  from PIL import Image
  from titan_wb.engine import dispatch
  p=make_demo();r=analyze(p)
  settings=dict(panel_width=3,height=3,font_size=14,dpi=100)
  preview=dispatch(dict(command='export_preview',payload=dict(project=p,result=r,settings=settings)))
  image=Image.open(io.BytesIO(base64.b64decode(preview['png'].split(',')[1])))
  self.assertEqual(image.size,(preview['width'],preview['height']))
  self.assertEqual(preview['height'],300)
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'export'
   manifest=export_analysis(p,r,str(out),settings=settings)
   self.assertEqual(manifest['plot_settings'],settings)
   exported=Image.open(out/'plot.png')
   self.assertEqual(image.tobytes(),exported.tobytes())
 def test_preview_rejects_stale_results_and_invalid_settings(self):
  from titan_wb.engine import dispatch
  p=make_demo();r=analyze(p)
  for settings in [dict(dpi=10000),dict(height=float('nan')),dict(font_size=0),dict(panel_width=True)]:
   with self.assertRaises(ValueError):
    dispatch(dict(command='export_preview',payload=dict(project=p,result=r,settings=settings)))
  p['revision']+=1
  with self.assertRaisesRegex(ValueError,'过期'):
   dispatch(dict(command='export_preview',payload=dict(project=p,result=r)))
