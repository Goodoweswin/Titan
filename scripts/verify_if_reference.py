"""Compare Titan raw measurements to the independent ImageJ core used by Fiji.

Supply an external ImageJ ij.jar and a local Java runtime; neither is bundled
with Titan. This uses identical raster masks to isolate measurement arithmetic.
It does not validate segmentation or real biological images.
"""
import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import tifffile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--reference-dir",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args();reference=args.reference_dir.resolve();args.output.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(reference/"python"))
    import jpype
    jvm=next(reference.glob("**/Contents/Home/lib/server/libjvm.dylib"))
    jar=reference/"ij.jar"
    jpype.startJVM(str(jvm),"-Djava.awt.headless=true",classpath=[str(jar)],convertStrings=True)
    IJ=jpype.JClass("ij.IJ")
    ThresholdToSelection=jpype.JClass("ij.plugin.filter.ThresholdToSelection")
    Measurements=jpype.JClass("ij.measure.Measurements")
    from titan_if.images import import_field
    from titan_if.analysis import roi_mask,measure_field
    rows=[]
    shapes=[("rectangle",[[1,2],[7,8]]),("ellipse",[[1,2],[7,8]]),
            ("polygon",[[1,2],[7,3],[6,8],[2,7]])]
    for dtype in [np.uint8,np.uint16,np.float32]:
        raw=(np.arange(120).reshape(10,12)+30).astype(dtype)
        if dtype==np.float32:raw=raw/7-30
        path=args.output/(np.dtype(dtype).name+".tif");tifffile.imwrite(path,raw,photometric="minisblack")
        field=import_field([dict(path=str(path),channel_indices=[0],indexers={})],dict(pixel_size_um=[.5,.7]))
        for shape,points in shapes:
            f=copy.deepcopy(field)
            region=dict(id="signal",name="signal",role="signal",shape=shape,points=points)
            bg=dict(id="background",name="background",role="background",shape="rectangle",points=[[9,0],[12,2]])
            f["rois"]=[region,bg];f["recipe"]["target_channel_ids"]=[f["channels"][0]["id"]]
            actual=measure_field(f)["summary"][0]
            image=IJ.openImage(str(path))
            calibration=image.getCalibration();calibration.pixelWidth=.5;calibration.pixelHeight=.7;calibration.setUnit("um")
            values={}
            for name,roi in [("signal",region),("background",bg)]:
                mask=(roi_mask(roi,raw.shape)*255).astype(np.uint8)
                mask_path=args.output/(np.dtype(dtype).name+"-"+shape+"-"+name+"-mask.tif")
                tifffile.imwrite(mask_path,mask)
                mask_image=IJ.openImage(str(mask_path));processor=mask_image.getProcessor()
                processor.setThreshold(255,255,0)
                selection=ThresholdToSelection().convert(processor);image.setRoi(selection)
                raw_stats=image.getRawStatistics()
                stats=image.getStatistics(Measurements.AREA|Measurements.MEAN|Measurements.INTEGRATED_DENSITY)
                values[name]=dict(area_px=int(raw_stats.pixelCount),mean=float(raw_stats.mean),
                    raw_sum=float(raw_stats.mean)*int(raw_stats.pixelCount),area_um2=float(stats.area))
                mask_image.close()
            image.close()
            expected=values["signal"]
            expected["corrected_sum"]=expected["raw_sum"]-expected["area_px"]*values["background"]["mean"]
            differences={}
            for key in ["area_px","mean","raw_sum","area_um2","corrected_sum"]:
                assert np.isclose(actual[key],expected[key],rtol=1e-6,atol=1e-7),(dtype,shape,key,actual[key],expected[key])
                differences[key]=actual[key]-expected[key]
            rows.append(dict(dtype=np.dtype(dtype).name,shape=shape,titan=actual,imagej=expected,differences=differences))
    record=dict(imagej_version=IJ.getVersion(),imagej_jar_sha256=hashlib.sha256(jar.read_bytes()).hexdigest(),
        cases=rows,passed=len(rows),scope="Synthetic identical-mask arithmetic against ImageJ core; not full Fiji segmentation or real-image validation")
    (args.output/"reference-verification.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(dict(passed=len(rows),imagej_version=IJ.getVersion(),scope=record["scope"])))
    jpype.shutdownJVM()


if __name__=="__main__":main()
