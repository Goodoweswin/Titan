import copy
import unittest
import numpy as np
from titan_wb.demo import make_demo
from titan_wb.models import validate_project
from titan_wb.analysis import analyze
from titan_wb.detection import detect


class AnalysisTests(unittest.TestCase):
 def test_demo_golden_counts_and_fold(self):
  p=make_demo();r=analyze(p)
  self.assertEqual(len(r['measurements']),24)
  self.assertEqual(len(r['normalized']),12)
  self.assertEqual(sum(x['normalized'] is None for x in r['normalized']),1)
  self.assertEqual(len(r['biological']),6)
  treated=[x['fold'] for x in r['biological'] if x['group']=='treated']
  self.assertAlmostEqual(float(np.mean(treated)),1.9939785492096116,places=7)
 def test_unreviewed_rows_are_retained_but_not_normalized(self):
  p=make_demo();p['rois'][0]['reviewed_revision']=None
  r=analyze(p);self.assertIsNone(r['normalized'][0]['normalized'])
  self.assertIn('review_required',r['normalized'][0]['flags'])
 def test_reference_lane_mismatch_is_blocked(self):
  p=make_demo();p['rois'][0]['reference_id']='reference_1'
  self.assertIsNone(analyze(p)['normalized'][0]['normalized'])
 def test_detection_returns_unaccepted_geometry_only(self):
  p=make_demo();boxes=detect(p,p['images'][0]['id'],[0,35,520,60],{})
  self.assertEqual(len(boxes),12)
 def test_duplicate_roi_identity_and_overlap_are_rejected(self):
  p=make_demo();p['rois'].append(copy.deepcopy(p['rois'][0]))
  with self.assertRaises(ValueError):validate_project(p)
  p=make_demo();p['rois'][0]['backgrounds']=[p['rois'][0]['rect']]
  with self.assertRaises(ValueError):validate_project(p)
 def test_negative_signal_is_not_replaced_with_zero(self):
  from titan_wb.quantify import measure
  a=np.full((8,8),10);a[2:4,2:4]=5
  self.assertEqual(measure(a,[2,2,4,4],[[0,0,2,2]])['corrected_sum'],-20)
