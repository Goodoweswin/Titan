import numpy as np
import pytest
from titan_wb.image_cache import ImageCache
from titan_wb.images import import_image,read_pixels
from titan_wb.models import new_project
from PIL import Image

def test_lru_is_byte_bounded_and_arrays_are_immutable():
 cache=ImageCache(pixel_limit=8)
 a=cache.get_pixels(('hash',0),lambda:np.ones(4,dtype=np.uint8))
 cache.get_pixels(('hash',1),lambda:np.full(4,2,dtype=np.uint8))
 assert cache.get_pixels(('hash',0),lambda:None) is a
 cache.get_pixels(('other',0),lambda:np.zeros(4,dtype=np.uint8))
 assert cache.pixel_bytes==8 and ('hash',1) not in cache.pixels
 with pytest.raises(ValueError):a[0]=3

def test_changed_file_is_not_hidden_by_cache(tmp_path):
 path=tmp_path/'a.png';Image.fromarray(np.ones((5,5),dtype=np.uint8)).save(path)
 asset=import_image(new_project('cache'),str(path))['images'][0]
 assert read_pixels(asset)[0,0]==1
 Image.fromarray(np.full((5,5),9,dtype=np.uint8)).save(path)
 with pytest.raises(ValueError,match='hash'):read_pixels(asset)
