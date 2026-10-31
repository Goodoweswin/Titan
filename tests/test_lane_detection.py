import numpy as np
from titan_wb.lanes import propose_lanes

def blot(missing=False):
 a=np.full((60,150),100.,dtype=float)
 for center,signal in zip([15,40,65,90,115],[400,25,0 if missing else 200,100,300]):a[25:35,center-5:center+5]+=signal
 a[20:40,135:145]=100000
 return a

def test_excluded_bright_marker_does_not_hide_weak_lanes():
 r=propose_lanes(blot(),[0,0,150,60],excluded_regions=[[130,0,150,60]],expected_count=5,polarity='bright',ceiling=None)
 assert len(r['columns'])==5
 centers=[(c['rect'][0]+c['rect'][2])/2 for c in r['columns']]
 np.testing.assert_allclose(centers,[15,40,65,90,115],atol=2)
 assert all(c['confidence']=='high' for c in r['columns'])

def test_missing_middle_lane_keeps_uncertain_slot_and_stable_later_position():
 r=propose_lanes(blot(True),[0,0,150,60],excluded_regions=[[130,0,150,60]],expected_count=5,polarity='bright',ceiling=None)
 assert len(r['columns'])==5 and r['requires_review']
 assert r['columns'][2]['confidence']=='low'
 assert abs(sum(r['columns'][3]['rect'][::2])/2-90)<=2
 assert len({c['proposal_id'] for c in r['columns']})==5

def test_flat_data_cannot_be_silently_accepted():
 r=propose_lanes(np.zeros((20,100)),[0,0,100,20],excluded_regions=[],expected_count=None,polarity='bright',ceiling=None)
 assert r['columns']==[] and r['requires_review']
