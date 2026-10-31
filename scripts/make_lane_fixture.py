"""Known-value TIFF for independent ImageJ ROI/background verification."""
import sys
from pathlib import Path
import numpy as np
import tifffile
path=Path(sys.argv[1]);path.parent.mkdir(parents=True,exist_ok=True)
a=np.full((40,20),1000,dtype=np.uint16);a[10:12,2:4]=3000;a[25:29,2:6]=3000
tifffile.imwrite(path,a,photometric='minisblack')
print('Expected target raw=48000, net=32000; reference raw=12000, net=8000; ratio=4')
