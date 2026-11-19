import numpy as np
import base64
import io
import tifffile
from PIL import Image
import pytest
from titan_wb.images import decode,import_image,inspect_image
from titan_wb.models import new_project
from titan_wb.engine import dispatch
from titan_wb.quantify import measure


@pytest.mark.parametrize('dtype,scale', [(np.uint8,1),(np.uint16,128)])
def test_adjusted_display_preserves_quantitative_pixels(tmp_path,dtype,scale):
 path=tmp_path/'display.tif'
 pixels=(np.tile(np.arange(20),(16,1))*5*scale).astype(dtype)
 tifffile.imwrite(path,pixels,photometric='miniswhite')
 asset=import_image(new_project('display'),str(path))['images'][0]
 from titan_wb.images import read_pixels
 before=measure(read_pixels(asset),[10,4,16,10],[[1,4,5,10]],ceiling=int(np.iinfo(dtype).max))
 def display(brightness,contrast):
  result=dispatch({'command':'wb_display_preview','payload':{'asset':asset,'brightness':brightness,'contrast':contrast}})
  return np.array(Image.open(io.BytesIO(base64.b64decode(result.split(',')[1]))))
 baseline=display(0,0)
 assert display(25,0).mean()<baseline.mean()
 assert not np.array_equal(display(0,50),baseline)
 np.testing.assert_array_equal(read_pixels(asset),pixels)
 assert measure(read_pixels(asset),[10,4,16,10],[[1,4,5,10]],ceiling=int(np.iinfo(dtype).max))==before

def test_inverted_gray_lzw_palette_preserves_indices_and_metadata(tmp_path):
 path=tmp_path/'gray.tif';a=np.array([[0,64,255]],dtype=np.uint8)
 im=Image.fromarray(a,mode='P');im.putpalette([v for i in range(256) for v in [255-i]*3]);im.save(path,compression='tiff_lzw')
 np.testing.assert_array_equal(decode(path),a)
 asset=import_image(new_project('gray'),str(path))['images'][0]
 assert asset['display_inverted'] is True and asset['polarity']=='bright'
 assert asset['photometric']=='palette' and asset['gray_lut'][0]>asset['gray_lut'][-1]
 assert inspect_image(path)['pages'][0]['display_inverted'] is True

def test_miniswhite_preserves_16bit_values(tmp_path):
 path=tmp_path/'white.tif';a=np.array([[0,4095,65535]],dtype=np.uint16)
 tifffile.imwrite(path,a,photometric='miniswhite')
 np.testing.assert_array_equal(decode(path),a)
 assert import_image(new_project('white'),str(path))['images'][0]['display_inverted']

def test_color_palette_is_not_silently_quantified(tmp_path):
 path=tmp_path/'color.tif';im=Image.fromarray(np.array([[0,64,255]],dtype=np.uint8),mode='P')
 im.putpalette([v for i in range(256) for v in [i,0,0]]);im.save(path,compression='tiff_lzw')
 assert inspect_image(path)['pages'][0]['error']
 with pytest.raises(ValueError):decode(path)

@pytest.mark.parametrize('dtype,values', [('uint8',[0,16,240,255]),('uint16',[0,1000,60000,65535])])
def test_lzw_miniswhite_preserves_encoded_pixels(tmp_path,dtype,values):
 # Write known MINISBLACK compressed bytes, then change only the display tag.
 import struct
 path=tmp_path/f'white-{dtype}.tif';a=np.array([values],dtype=dtype)
 Image.fromarray(a).save(path,compression='tiff_lzw')
 with tifffile.TiffFile(path) as t:
  offset=t.pages[0].tags['PhotometricInterpretation'].valueoffset;order=t.byteorder
 with path.open('r+b') as f:f.seek(offset);f.write(struct.pack(order+'H',0))
 np.testing.assert_array_equal(decode(path),a)
 assert import_image(new_project('compressed'),str(path))['images'][0]['display_inverted']
