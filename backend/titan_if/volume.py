"""Read and stage bounded display volumes from single-file OME-TIFF stacks."""
import base64
import binascii
import math
import os
import uuid
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import numpy as np
import tifffile

from .images import _axes, _index, _path, _plane, _validate_manifest

MAX_SOURCE_SIDE = 2048
MAX_Z = 128
MAX_SOURCE_BYTES = 512 * 1024**2
MAX_DISPLAY_SIDE = 512
MAX_DISPLAY_BYTES = 64 * 1024**2
UNITS = {"µm": 1, "μm": 1, "um": 1, "nm": .001, "mm": 1000, "cm": 10000, "m": 1e6}


def _source(path):
    source = _path(path)
    if not source.name.lower().endswith((".ome.tif", ".ome.tiff")):
        raise ValueError("请选择单文件 OME-TIFF（.ome.tif 或 .ome.tiff）")
    return source


def _pixels(tiff):
    if not tiff.ome_metadata:
        raise ValueError("文件缺少 OME 元数据，无法确认 Z 层和通道")
    root = ET.fromstring(tiff.ome_metadata)
    return [node.find("{*}Pixels") for node in root.findall("{*}Image")]


def _physical(node, attr):
    try:
        value = float(node.get(attr)) * UNITS[node.get(attr + "Unit", "µm")]
        return value if math.isfinite(value) else None
    except (TypeError, ValueError, KeyError):
        return None


def _check_z_spacing(pixels, declared):
    positions = defaultdict(dict)
    for plane in pixels.findall("{*}Plane"):
        position = _physical(plane, "PositionZ")
        if position is not None:
            positions[(plane.get("TheT"), plane.get("TheC"))][int(plane.get("TheZ"))] = position
    lattices = {}
    for (time, channel), group in positions.items():
        if len(group) < 2:
            continue
        indices = sorted(group)
        steps = [(group[b] - group[a]) / (b - a) for a, b in zip(indices, indices[1:])]
        # Some readers repeat a single stage coordinate in every plane.
        if all(abs(step) < 1e-9 for step in steps):
            continue
        if not np.allclose(steps, steps[0], rtol=.01, atol=1e-6):
            raise ValueError("检测到不等距 Z 层，原型仅支持规则 Z-stack")
        step = steps[0]
        if declared is not None and not math.isclose(abs(step), declared, rel_tol=.01, abs_tol=1e-6):
            raise ValueError("OME 的 Z 标定和逐层位置不一致")
        origin = group[indices[0]] - step * indices[0]
        if time in lattices:
            reference_step, reference_origin = lattices[time]
            if (not math.isclose(step, reference_step, rel_tol=.01, abs_tol=1e-6)
                    or abs(origin - reference_origin) > .1 * abs(reference_step)):
                raise ValueError(f"通道 {int(channel) + 1} 的 Z 位置与同一时间点的其他通道不一致")
        else:
            lattices[time] = step, origin
    return lattices


def _series_info(series, pixels, index):
    axes = _axes(series)
    dimensions = dict(zip(axes, series.shape))
    if "S" in axes or int(series.pages[0].photometric) == 2:
        raise ValueError("仅支持独立灰度通道，RGB 合并图无法作为荧光 Z-stack")
    if series.dtype.kind != "u" or series.dtype.itemsize not in (1, 2):
        raise ValueError("仅支持 8 位或 16 位无符号灰度通道")
    if dimensions.get("Z", 1) < 2:
        raise ValueError("此序列只有一个 Z 层，无法体渲染")
    if max(dimensions["X"], dimensions["Y"]) > MAX_SOURCE_SIDE or dimensions["Z"] > MAX_Z:
        raise ValueError("体数据超限（单边 2048 像素、128 个 Z 层），请先在 Fiji 裁剪")
    if pixels is None or len(series.pages[0].shape) != 2:
        raise ValueError("无法确定 OME 层序，或 TIFF 页面无法独立解码")
    sizes = [_physical(pixels, "PhysicalSize" + axis) for axis in "XYZ"]
    _check_z_spacing(pixels, sizes[2] if sizes[2] and sizes[2] > 0 else None)
    names = [node.get("Name") for node in pixels.findall("{*}Channel")]
    return {
        "index": index, "axes": axes,
        "dimensions": [dimensions[axis] for axis in "XYZ"],
        "spacing": [v if v is not None and v > 0 else None for v in sizes],
        "timepoints": dimensions.get("T", 1),
        "channels": [(names[i] if i < len(names) else None) or f"通道 {i + 1}"
                     for i in range(dimensions.get("C", 1))],
    }


def inspect_volume(path):
    source = _source(path)
    with tifffile.TiffFile(source) as tiff:
        _validate_manifest(tiff, source)
        pixels = _pixels(tiff)
        result = []
        for index, series in enumerate(tiff.series):
            try:
                result.append(_series_info(series, pixels[index], index))
            except (ValueError, IndexError) as error:
                result.append({"index": index, "error": str(error) or "无法确认 OME 层序"})
        return {"name": source.name, "series": result}


def prepare_volume(options, destination, progress, cancelled):
    """Stage interleaved little-endian uint16 Z/Y/X/C samples."""
    source = _source(options["path"])
    before = source.stat()
    index = _index(options["series"], "Series")
    time = _index(options["time"], "Time")
    channels = [_index(channel, "Channel") for channel in options["channels"]]
    if not 1 <= len(channels) <= 3 or len(set(channels)) != len(channels):
        raise ValueError("请选择一至三个不同通道")
    partial = destination.with_suffix(".part")
    try:
        with tifffile.TiffFile(source) as tiff:
            _validate_manifest(tiff, source)
            pixels = _pixels(tiff)
            if index >= min(len(tiff.series), len(pixels)):
                raise ValueError("OME 序列不存在")
            series = tiff.series[index]
            info = _series_info(series, pixels[index], index)
            if time >= info["timepoints"] or max(channels) >= len(info["channels"]):
                raise ValueError("所选时间点或通道超出范围")
            spacing = info["spacing"]
            supplied = options.get("spacing", [None] * 3)
            if len(supplied) != 3:
                raise ValueError("请确认 XYZ 标定")
            for axis, actual in enumerate(spacing):
                if actual is None:
                    value = supplied[axis]
                    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                        raise ValueError("请补齐缺失的 XYZ 标定（µm）")
                    spacing[axis] = float(value)
            _check_z_spacing(pixels[index], spacing[2])

            width, height, depth = info["dimensions"]
            count = len(channels)
            if width * height * depth * count * series.dtype.itemsize > MAX_SOURCE_BYTES:
                raise ValueError("所选通道解码后超过 512 MiB，请减少通道或先裁剪")
            stride = 1
            while True:
                dw, dh = (width + stride - 1) // stride, (height + stride - 1) // stride
                if max(dw, dh) <= MAX_DISPLAY_SIDE and dw * dh * depth * count * 2 <= MAX_DISPLAY_BYTES:
                    break
                stride *= 2
            histograms = np.zeros((count, 65536), dtype=np.int64)
            axes = info["axes"]
            with partial.open("wb") as stream:
                for z in range(depth):
                    if cancelled():
                        return None
                    plane = np.empty((dh, dw, count), dtype="<u2")
                    for i, channel in enumerate(channels):
                        indexers = {axis: value for axis, value in (("Z", z), ("T", time), ("C", channel))
                                    if axis in axes}
                        plane[..., i] = _plane(series, axes, indexers)[::stride, ::stride]
                        histograms[i] += np.bincount(plane[..., i].ravel(), minlength=65536)
                    stream.write(plane.tobytes())
                    progress(z + 1, depth)
        if cancelled():
            return None
        after = source.stat()
        if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
            raise ValueError("读取期间原始文件发生变化，请重新打开")
        ranges = []
        for histogram in histograms:
            cumulative = np.cumsum(histogram)
            low = int(np.searchsorted(cumulative, max(1, math.ceil(cumulative[-1] * .85))))
            top = max(1, int(np.searchsorted(cumulative, max(1, math.ceil(cumulative[-1] * .997)))))
            if top == 1 and cumulative[0] == cumulative[-1]:
                top = 255 if series.dtype.itemsize == 1 else 65535
            elif top <= low:
                top = int(np.flatnonzero(histogram)[-1])
            ranges.append([low if top > low else 0, max(1, top)])
        os.replace(partial, destination)
        return {"name": source.name, "dimensions": [dw, dh, depth], "original_dimensions": info["dimensions"],
                "spacing": [spacing[0] * stride, spacing[1] * stride, spacing[2]],
                "channels": [info["channels"][i] for i in channels], "ranges": ranges,
                "bytes": dw * dh * depth * count * 2}
    finally:
        partial.unlink(missing_ok=True)


def save_png(destination, encoded):
    target = Path(destination).expanduser()
    if target.suffix.lower() != ".png" or not isinstance(encoded, str) or len(encoded) > 12 * 1024**2:
        raise ValueError("截图需保存为 PNG，且不能超过大小限制")
    try:
        data = base64.b64decode(encoded, validate=True)
    except binascii.Error as error:
        raise ValueError("无法读取截图") from error
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("截图数据不是 PNG")
    partial = target.with_name("." + target.name + "." + uuid.uuid4().hex)
    try:
        partial.write_bytes(data)
        os.replace(partial, target)
    finally:
        partial.unlink(missing_ok=True)
    return str(target)
