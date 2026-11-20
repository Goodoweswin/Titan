"""Generate an independent, synthetic WB exercise for the formal editor."""
import shutil
import tempfile
from pathlib import Path

import numpy as np
import tifffile

from .images import file_hash, import_image, read_pixels
from .models import new_project

SOURCE_NAME = 'SYNTHETIC_WB_TUTORIAL.tif'
WINDOW = [800, 1200, 2040, 1380]
COLUMNS = [(810 + i * 136, 924 + i * 136) for i in range(9)]


def _write_training_image(path):
    pixels = np.full((2200, 2688), 520, dtype=np.uint16)

    def add_band(x0, x1, center, amplitude):
        x = np.linspace(-1.0, 1.0, x1 - x0)
        y = np.arange(-28, 29)
        band = amplitude * np.exp(-(x[None, :] ** 6 * 2 + (y[:, None] / 8) ** 2))
        pixels[center - 28:center + 29, x0:x1] += band.astype(np.uint16)

    for i, (x0, x1) in enumerate(COLUMNS):
        add_band(x0 + 5, x1 - 5, 1289 + (i % 4) * 3, 8400 + (i % 5) * 1900)
    for x in (704, 2090):
        for y in (1219, 1285, 1352):
            add_band(x, x + 52, y, 17000)

    with tifffile.TiffWriter(path) as tiff:
        tiff.write((pixels >> 8).astype(np.uint8), photometric='minisblack',
                   compression='deflate', metadata=None)
        tiff.write(pixels, photometric='minisblack', compression='deflate', metadata=None)


def make_reference_case(mode='annotated'):
    if mode not in ('annotated', 'practice', 'tutorial'):
        raise ValueError('示范模式无效')
    root = Path(tempfile.mkdtemp(prefix='titan-wb-reference-'))
    try:
        source = root / SOURCE_NAME
        _write_training_image(source)
        digest = file_hash(source)
        name = {'tutorial': 'WB 操作教程', 'annotated': 'WB 操作示范', 'practice': 'WB 操作练习'}[mode]
        p = import_image(new_project(name), str(source), page_index=1, expected_sha256=digest)
        p['synthetic'] = True
        p['example_case'] = dict(id='wb-synthetic-tutorial-v1', mode=mode, source_name=SOURCE_NAME,
                                 source_sha256=digest, page_index=1, uint16_max_pixels=0,
                                 source_note='程序生成的合成图像，仅供操作练习',
                                 suggested_window=WINDOW[:], suggested_lane_count=9)
        p['settings'].update(control_group='未提供', design_confirmed=False)
        if mode in ('annotated', 'tutorial'):
            _annotate(p, include_measurements=mode == 'annotated')
        return p
    except Exception:
        shutil.rmtree(root)
        raise


def _annotate(p, include_measurements=True):
    from .bands import propose_bands
    image = p['images'][0]
    layout_id, set_id = 'example-layout', 'example-bands'
    columns, assignments = [], []
    for n, (x0, x1) in enumerate(COLUMNS, 1):
        sid, lid = f'S{n}', f'L{n}'
        p['samples'].append(dict(id=sid, name=f'示范泳道 {n}', bio_id='未提供', group='未提供',
                                 pair_id='', kind='biological', pool_id=''))
        p['lanes'].append(dict(id=lid, membrane_id='示范图像', sample_id=sid, technical_id=''))
        columns.append(dict(lane_id=lid, rect=[x0, WINDOW[1], x1, WINDOW[3]]))
        assignments.append(dict(lane_id=lid, roi_id=None, status='pending'))
    p['lane_layouts'].append(dict(id=layout_id, image_id=image['id'], membrane_id='示范图像',
                                  window=WINDOW[:], columns=columns, excluded_regions=[],
                                  source_layout_id=None, confirmed_revision=p['revision']))
    p['band_sets'].append(dict(id=set_id, layout_id=layout_id, analyte='示范条带', role='target',
                               window=WINDOW[:], reference_set_id=None, assignments=assignments))
    if not include_measurements:
        p['lane_layouts'][0]['confirmed_revision'] = None
        return
    pixels = read_pixels(image)
    proposals = propose_bands(p, set_id, {})
    p['lane_layouts'][0]['confirmed_revision'] = None
    for proposal, assignment in zip(proposals, assignments):
        if not proposal['candidates']:
            assignment['status'] = 'not_detected'
            continue
        def signal(candidate):
            x0, y0, x1, y1 = candidate['rect']
            return float(pixels[y0:y1, x0:x1].sum())
        candidate = max(proposal['candidates'], key=signal)
        rid = 'example-' + proposal['lane_id']
        p['rois'].append(dict(id=rid, image_id=image['id'], lane_id=proposal['lane_id'], analyte='示范条带',
                              role='target', rect=candidate['rect'], backgrounds=candidate['backgrounds'],
                              reference_id=None, reviewed_revision=None, lane_layout_id=layout_id, band_set_id=set_id))
        assignment.update(roi_id=rid, status='accepted')
