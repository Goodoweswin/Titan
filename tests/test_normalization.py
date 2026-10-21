import unittest
from titan_wb.normalization import normalize


def fixture():
 p={'samples':[],'lanes':[],'settings':{'control_group':'control','normalization_mode':'within','ibc_by_membrane':{},'analysis_blocks':[]}}
 m=[]
 def add(lid,sid,bio,group,mem,value,kind='biological',pool=''):
  if not any(s['id']==sid for s in p['samples']):p['samples'].append(dict(id=sid,bio_id=bio,group=group,pair_id='',kind=kind,pool_id=pool))
  p['lanes'].append(dict(id=lid,sample_id=sid,membrane_id=mem))
  m.extend([dict(id=lid+'T',lane_id=lid,analyte='X',role='target',reference_id=lid+'R',corrected_sum=value,flags=[]),
            dict(id=lid+'R',lane_id=lid,analyte='LC',role='reference',corrected_sum=1,flags=[])])
 return p,m,add


class NormalizationTests(unittest.TestCase):
 def test_unequal_technical_counts_do_not_weight_biological_control(self):
  p,m,add=fixture();add('a','S1','B1','control','M1',1);add('b','S1','B1','control','M1',3)
  add('c','S2','B2','control','M1',4);add('d','S3','B3','treated','M1',6)
  rows,bio=normalize(p,m)
  self.assertEqual(len(bio),3);self.assertEqual(next(r for r in bio if r['group']=='treated')['fold'],2)
 def test_ibc_bridges_then_equal_weights_membranes(self):
  p,m,add=fixture();add('a','S1','B1','control','M1',1);add('b','S1','B1','control','M1',3)
  add('c','S1','B1','control','M2',60)
  add('ib1','P','POOL','IBC','M1',1,'ibc','pool1');add('ib2','P','POOL','IBC','M2',10,'ibc','pool1')
  p['settings'].update(normalization_mode='ibc',ibc_by_membrane={'M1':{'X':'ib1T'},'M2':{'X':'ib2T'}},analysis_blocks=[dict(id='block',membrane_ids=['M1','M2'],pooled_reference_id='pool1',merge_same_sample=True)])
  rows,bio=normalize(p,m)
  self.assertEqual(len(bio),1);self.assertEqual(bio[0]['value'],4)
  self.assertFalse(any(r['group']=='IBC' for r in bio))
 def test_missing_ibc_prevents_combination(self):
  p,m,add=fixture();add('a','S1','B1','control','M1',2)
  p['settings']['normalization_mode']='ibc'
  with self.assertRaises(ValueError):normalize(p,m)
 def test_ibc_exploratory_flags_propagate_to_rows_and_biological_units(self):
  p,m,add=fixture();add('a','S1','B1','control','M1',2);add('ib','P','POOL','IBC','M1',1,'ibc','pool1')
  m[2]['flags']=['clipping_unknown'];m[3]['flags']=['linearity_not_validated']
  p['settings'].update(normalization_mode='ibc',ibc_by_membrane={'M1':{'X':'ibT'}})
  rows,bio=normalize(p,m)
  self.assertIn('ibc:clipping_unknown',bio[0]['flags'])
  self.assertIn('ibc:reference:linearity_not_validated',bio[0]['flags'])
  self.assertIn('ibc:clipping_unknown',rows[0]['flags'])
