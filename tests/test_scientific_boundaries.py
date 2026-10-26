"""Hand-calculated boundary fixtures exercised against the shipped app modules."""
import numpy as np
import pytest
from titan_wb.quantify import measure
from titan_wb.detection import propose_rectangles
from titan_wb.statistics import compare


def image():
    a=np.full((8,8),10,dtype=np.uint16);a[2:4,2:4]=30
    return a


def test_dark_and_bright_integrate_to_same_hand_calculated_signal():
    for a,polarity in [(image(),'bright'),(4095-image(),'dark')]:
        m=measure(a,[2,2,4,4],[[0,0,2,2]],polarity=polarity,ceiling=4095)
        assert m['corrected_sum']==80
        assert m['area_px']==4


def test_adc_clipping_uses_declared_limit_and_unknown_is_preserved():
    a=image();a[2,2]=4095
    assert measure(a,[2,2,4,4],[[0,0,2,2]],ceiling=4095)['clipped_fraction']==.25
    assert 'clipping_unknown' in measure(a,[2,2,4,4],[[0,0,2,2]])['flags']


def test_overlapping_background_boxes_are_counted_once():
    a=image();a[0,0]=20
    m=measure(a,[2,2,4,4],[[0,0,2,1],[1,0,3,1]],ceiling=4095)
    assert m['background_n']==3
    assert m['corrected_sum']==pytest.approx(120-4*40/3)


@pytest.mark.parametrize('roi,bgs,kwargs',[
    ([7,7,10,10],[[0,0,2,2]],{}),
    ([2,2,4,4],[[3,3,5,5]],{}),
    ([2,2,4,4],[],{}),
    ([2,2,4,4],[[0,0,2,2]],{'polarity':'dark'}),
])
def test_invalid_measurement_geometry_and_unknown_dark_limit_are_rejected(roi,bgs,kwargs):
    with pytest.raises(ValueError):measure(image(),roi,bgs,**kwargs)


def test_candidate_detection_rejects_blank_and_cancels_background_gradient():
    assert propose_rectangles(np.ones((20,40)),[0,0,40,20])==[]
    yy,xx=np.mgrid[:40,:100];a=(1000+3*xx+yy).astype(float)
    a[10:15,10:20]+=80;a[10:15,70:80]+=40
    boxes=propose_rectangles(a,[0,8,100,18])
    assert len(boxes)==2
    assert boxes[0][0]<=15<boxes[0][2] and boxes[1][0]<=75<boxes[1][2]


@pytest.mark.parametrize('vals,scale', [([1,1,2,2],'raw'),([0,1,2,3],'log2')])
def test_invalid_statistical_inputs_do_not_produce_p_values(vals,scale):
    rows=[dict(value=v,bio_id=str(i),group='a' if i<2 else 'b',membrane_id='M1') for i,v in enumerate(vals)]
    with pytest.raises(ValueError):compare(rows,dict(id='c',group_a='a',group_b='b',test='welch',scale=scale))
