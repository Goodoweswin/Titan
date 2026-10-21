import json
import tempfile
import unittest
from pathlib import Path
from titan_wb.demo import make_demo
from titan_wb.analysis import analyze
from titan_wb.export import export_analysis
from titan_wb.images import file_hash


class ExportTests(unittest.TestCase):
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
