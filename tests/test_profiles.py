import copy
import numpy as np
import pytest
from PIL import Image
from titan_wb.engine import dispatch
from titan_wb.images import import_image
from titan_wb.models import new_project


def fixture(tmp_path, dark=False, height=8):
    a=np.full((height,6),1000,dtype=np.uint16)
    a[2:4,2:4]=800 if dark else 3000
    path=tmp_path/'raw.png';Image.fromarray(a).save(path)
    p=import_image(new_project('profile'),str(path));asset=p['images'][0]
    asset.update(polarity='dark' if dark else 'bright',ceiling=65535)
    p['rois']=[dict(id='r',image_id=asset['id'],rect=[2,2,4,4],backgrounds=[[0,0,2,2],[1,0,2,2]])]
    return p


def profile(p):
    return dispatch(dict(command='profile',payload=dict(project=p,roi_id='r')))


@pytest.mark.parametrize('dark,signal',[(False,8000),(True,800)])
def test_native_depth_orientation_and_union_background(tmp_path,dark,signal):
    p=fixture(tmp_path,dark);r=profile(p)
    assert r['measurement']['corrected_sum']==signal
    assert r['measurement']['background_n']==4
    assert r['samples'][2]['mean']==(64735 if dark else 3000)
    assert r['input_revision']==p['revision']


def test_negative_signal_is_not_clamped(tmp_path):
    p=fixture(tmp_path,True);p['images'][0]['polarity']='bright'
    assert profile(p)['measurement']['corrected_sum']==-800


@pytest.mark.parametrize('backgrounds',[[],[[2,2,3,3]]])
def test_missing_or_overlapping_background_keeps_curve_but_no_correction(tmp_path,backgrounds):
    p=fixture(tmp_path);p['rois'][0]['backgrounds']=backgrounds
    r=profile(p)
    assert r['measurement'] is None and r['background_mean'] is None
    assert r['warning'] and len(r['samples'])==8


def test_dark_without_ceiling_and_changed_file_are_rejected(tmp_path):
    p=fixture(tmp_path,True);p['images'][0]['ceiling']=None
    with pytest.raises(ValueError,match='ceiling'):profile(p)
    p=fixture(tmp_path);Image.fromarray(np.zeros((8,6),dtype=np.uint16)).save(p['images'][0]['path'])
    with pytest.raises(ValueError,match='hash'):profile(p)


def test_large_profile_preserves_peaks_and_exact_integral(tmp_path):
    p=fixture(tmp_path,height=2501);r=profile(p)
    assert len(r['samples'])<=1200
    assert max(s['max'] for s in r['samples'])==3000
    assert r['measurement']['corrected_sum']==8000
