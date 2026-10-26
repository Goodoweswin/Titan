import unittest
from titan_wb.statistics import compare,holm


def units(a,b,paired=False):
 return [dict(value=v,bio_id=f'B{i}' if paired else f'{g}{i}',pair_id=f'P{i}' if paired else '',group=g,analyte='X',analysis_block='M1',membrane_id='M1') for g,vals in [('a',a),('b',b)] for i,v in enumerate(vals)]


class StatisticsTests(unittest.TestCase):
 def test_paired_log_contrast_hand_calculation(self):
  r=compare(units([1,1,1],[2,4,8],True),dict(id='C',group_a='a',group_b='b',test='paired',scale='log2'))
  self.assertAlmostEqual(r['statistic'],3.464101615,places=8);self.assertEqual(r['df'],2)
  self.assertEqual(r['effect'],2)
 def test_holm_golden(self):self.assertEqual(holm([.01,.03,.04]),[.03,.06,.06])
 def test_independent_test_rejects_shared_bio(self):
  with self.assertRaises(ValueError):compare(units([1,2],[3,4],True),dict(id='C',group_a='a',group_b='b',test='welch',scale='raw'))
 def test_incomplete_pairs_are_not_silently_dropped(self):
  v=units([1,2,3],[2,4],True)
  with self.assertRaises(ValueError):compare(v,dict(id='C',group_a='a',group_b='b',test='paired',scale='raw'))
 def test_multiple_membranes_do_not_enter_plain_t_test(self):
  v=units([1,2,3],[2,4,6]);v[0]['membrane_id']='M2'
  with self.assertRaises(ValueError):compare(v,dict(id='C',group_a='a',group_b='b',test='welch',scale='raw'))
