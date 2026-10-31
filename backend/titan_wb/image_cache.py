"""Bounded, process-local caches. Source verification belongs to the caller."""
from collections import OrderedDict

class ImageCache:
    def __init__(self,pixel_limit=256*1024*1024,value_limit=32*1024*1024):
        self.pixel_limit=pixel_limit;self.value_limit=value_limit
        self.pixels=OrderedDict();self.values=OrderedDict()
        self.pixel_bytes=0;self.value_bytes=0

    def get_pixels(self,key,load):
        if key in self.pixels:
            self.pixels.move_to_end(key);return self.pixels[key]
        value=load();value.setflags(write=False)
        if value.nbytes<=self.pixel_limit:
            while self.pixel_bytes+value.nbytes>self.pixel_limit:
                _,old=self.pixels.popitem(last=False);self.pixel_bytes-=old.nbytes
            self.pixels[key]=value;self.pixel_bytes+=value.nbytes
        return value

    def get_value(self,key,load):
        if key in self.values:
            self.values.move_to_end(key);return self.values[key][0]
        value=load();size=len(value.encode('utf-8'))
        if size<=self.value_limit:
            while self.value_bytes+size>self.value_limit:
                _,(_,old_size)=self.values.popitem(last=False);self.value_bytes-=old_size
            self.values[key]=(value,size);self.value_bytes+=size
        return value

CACHE=ImageCache()
