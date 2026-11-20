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

def test_png_with_equal_rgb_channels_preserves_encoded_values(tmp_path):
 path=tmp_path/'gray-rgb.png'
 expected=np.array([[0,27,255]],dtype=np.uint8)
 Image.fromarray(np.repeat(expected[...,None],3,axis=2)).save(path)
 np.testing.assert_array_equal(decode(path),expected)
 assert inspect_image(path)['pages'][0]['dtype']=='uint8'

def test_png_with_equal_16bit_rgb_channels_preserves_encoded_values(tmp_path):
 import imagecodecs
 path=tmp_path/'gray-rgba16.png'
 expected=np.array([[1234,54321]],dtype=np.uint16)
 rgba=np.full((1,2,4),65535,dtype=np.uint16)
 rgba[...,:3]=expected[...,None]
 path.write_bytes(imagecodecs.png_encode(rgba))
 result=decode(path)
 assert result.dtype==np.uint16
 np.testing.assert_array_equal(result,expected)


def test_single_channel_png_keeps_original_values_with_transparency_hint(tmp_path):
 path=tmp_path/'gray-transparency.png'
 expected=np.array([[1234,54321]],dtype=np.uint16)
 Image.fromarray(expected).save(path,transparency=1234)
 with Image.open(path) as image:
  assert image.info['transparency']==1234
 np.testing.assert_array_equal(decode(path),expected)
 assert inspect_image(path)['pages'][0]['dtype']=='uint16'

def test_changing_file_during_decode_cannot_cache_pixels_for_old_hash(tmp_path,monkeypatch):
 from titan_wb import images
 path=tmp_path/'changing.tif'
 tifffile.imwrite(path,np.array([[11101,11102]],np.uint16))
 original=images.decode
 digest=images.file_hash(path)
 def replace_then_decode(path,page_index):
  tifffile.imwrite(path,np.array([[22201,22202]],np.uint16))
  return original(path,page_index)
 monkeypatch.setattr(images,'decode',replace_then_decode)
 with pytest.raises(ValueError,match='读取期间已改变'):
  images.verified_pixels(path,0,digest)

def test_tiff_over_old_file_cap_imports_without_rescaling(tmp_path):
 path=tmp_path/'large.tif'
 # One uncompressed 24 MP float32 page exceeds the old 50 MiB file limit.
 pixels=np.zeros((4000,6000),dtype=np.float32)
 pixels[3,5]=123.25
 tifffile.imwrite(path,pixels,photometric='minisblack')
 assert path.stat().st_size>50*1024**2
 result=import_image(new_project('large'),str(path))
 assert (result['images'][0]['width'],result['images'][0]['height'])==(6000,4000)
 assert decode(path)[3,5]==123.25

@pytest.mark.parametrize('pixel', [(40,41,40,255),(40,40,40,200)])
def test_png_does_not_silently_drop_color_or_transparency(tmp_path,pixel):
 path=tmp_path/'ambiguous.png'
 Image.new('RGBA',(2,2),pixel).save(path)
 with pytest.raises(ValueError):
  decode(path)
