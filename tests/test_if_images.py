"""Real TIFF regression fixtures for IF import; expectations are hand-derived."""
import base64
import hashlib
from io import BytesIO

import numpy as np
import pytest
import tifffile
from PIL import Image


def api():
    from titan_if import images
    return images


def test_ome_metadata_calibration_and_selected_zt_channels(tmp_path):
    path = tmp_path / 'stack.ome.tif'
    raw = np.arange(2 * 3 * 2 * 4 * 5, dtype=np.uint16).reshape(2, 3, 2, 4, 5)
    tifffile.imwrite(path, raw, ome=True, metadata={
        'axes': 'TZCYX', 'PhysicalSizeX': 0.2, 'PhysicalSizeXUnit': 'µm',
        'PhysicalSizeY': 300, 'PhysicalSizeYUnit': 'nm', 'Channel': {'Name': ['DAPI', 'Target']}}, photometric='minisblack')
    info = api().inspect_image(str(path))
    series = info['series'][0]
    assert series['axes'] == 'TZCYX'
    assert series['channel_names'] == ['DAPI', 'Target']
    assert series['pixel_size_um'] == pytest.approx([0.2, 0.3])
    assert series['width'] == 5 and series['height'] == 4
    with pytest.raises(ValueError, match='T|plane'):
        api().import_field([{'path': str(path)}])
    field = api().import_field([{'path': str(path), 'indexers': {'T': 1, 'Z': 2}, 'channel_indices': [1]}], {'bio_id': 'mouse1'})
    assert field['bio_id'] == 'mouse1'
    assert field['channels'][0]['name'] == 'Target'
    assert field['channels'][0]['source']['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    loaded = api().load_channels(field)
    np.testing.assert_array_equal(next(iter(loaded.values())), raw[1, 2, 1])
    assert next(iter(loaded.values())).dtype == np.uint16


def test_ambiguous_pages_need_mapping_and_mapping_is_not_a_guess(tmp_path):
    path = tmp_path / 'pages.tif'
    raw = np.arange(3 * 4 * 5, dtype=np.uint16).reshape(3, 4, 5)
    tifffile.imwrite(path, raw, metadata={'axes': 'QYX'}, photometric='minisblack')
    assert api().inspect_image(str(path))['series'][0]['requires_axes_mapping']
    with pytest.raises(ValueError, match='axes|ambiguous'):
        api().import_field([{'path': str(path)}])
    field = api().import_field([{'path': str(path), 'axes_override': 'ZYX', 'indexers': {'Z': 1}}])
    np.testing.assert_array_equal(next(iter(api().load_channels(field).values())), raw[1])
    assert len(field['channels']) == 1
    with pytest.raises(ValueError, match='axes|length'):
        api().import_field([{'path': str(path), 'axes_override': 'YX'}])


def test_split_channels_require_same_geometry_and_calibration(tmp_path):
    paths = [tmp_path / 'a.ome.tif', tmp_path / 'b.ome.tif']
    for path, size in zip(paths, [0.5, 0.6]):
        tifffile.imwrite(path, np.ones((3, 5), np.uint16), ome=True,
                          metadata={'axes': 'YX', 'PhysicalSizeX': size, 'PhysicalSizeY': size})
    with pytest.raises(ValueError, match='calibration|pixel_size'):
        api().import_field([{'path': str(p)} for p in paths])
    field = api().import_field([{'path': str(p)} for p in paths], {'pixel_size_um': [1, 2]})
    assert field['pixel_size_um'] == [1, 2]
    tifffile.imwrite(paths[1], np.ones((4, 5), np.uint16))
    with pytest.raises(ValueError, match='dimensions|shape|geometry'):
        api().import_field([{'path': str(p)} for p in paths])


def test_rgb_is_figure_only_and_preview_never_modifies_raw(tmp_path):
    path = tmp_path / 'rgb.tif'
    raw = np.zeros((5, 6, 3), np.uint8)
    raw[..., 0] = 255
    tifffile.imwrite(path, raw, photometric='rgb')
    field = api().import_field([{'path': str(path)}])
    assert field['quantitative'] is False
    assert len(field['channels']) == 3
    before = {key: value.copy() for key, value in api().load_channels(field).items()}
    png = api().preview_field(field, max_size=3)
    image = Image.open(BytesIO(base64.b64decode(png.split(',', 1)[1])))
    assert image.size == (3, 3)  # 6x5 reduced by two, nearest integer height
    assert image.getpixel((1, 1)) == (255, 0, 0)  # RGB figure retains original RGB colors.
    for key, value in api().load_channels(field).items():
        np.testing.assert_array_equal(value, before[key])


def test_source_tampering_is_detected_and_bad_selection_is_rejected(tmp_path):
    path = tmp_path / 'mono.tif'
    tifffile.imwrite(path, np.ones((4, 5), np.uint8))
    field = api().import_field([{'path': str(path)}])
    with pytest.raises(ValueError, match='channel'):
        api().import_field([{'path': str(path), 'channel_indices': [1]}])
    with pytest.raises(ValueError, match='index|axis'):
        api().import_field([{'path': str(path), 'indexers': {'Z': 1}}])
    tifffile.imwrite(path, np.full((4, 5), 2, np.uint8))
    with pytest.raises(ValueError, match='hash|changed|sha256'):
        api().load_channels(field)


def test_import_limits_and_nonfinite_pixels(tmp_path):
    wide = tmp_path / 'wide.tif'
    tifffile.imwrite(wide, np.zeros((2, 4097), np.uint8))
    with pytest.raises(ValueError, match='4096|dimensions|limit'):
        api().import_field([{'path': str(wide)}])
    many = tmp_path / 'many.ome.tif'
    tifffile.imwrite(many, np.zeros((5, 3, 4), np.uint8), ome=True, metadata={'axes': 'CYX'}, photometric='minisblack')
    with pytest.raises(ValueError, match='four|4|channel'):
        api().import_field([{'path': str(many)}])
    invalid = tmp_path / 'nan.tif'
    tifffile.imwrite(invalid, np.array([[np.nan, 1]], np.float32))
    with pytest.raises(ValueError, match='finite|NaN'):
        api().import_field([{'path': str(invalid)}])


def test_compressed_pages_and_planar_rgb(tmp_path):
    path = tmp_path / 'compressed.ome.tif'
    raw = np.arange(2 * 6 * 7, dtype=np.uint16).reshape(2, 6, 7)
    tifffile.imwrite(path, raw, compression='deflate', ome=True, metadata={'axes': 'CYX'}, photometric='minisblack')
    field = api().import_field([{'path': str(path)}])
    loaded = list(api().load_channels(field).values())
    np.testing.assert_array_equal(loaded[0], raw[0])
    np.testing.assert_array_equal(loaded[1], raw[1])
    planar = tmp_path / 'planar.tif'
    tifffile.imwrite(planar, np.full((3, 6, 7), 23, np.uint8), photometric='rgb', planarconfig='separate')
    field = api().import_field([{'path': str(planar)}])
    assert not field['quantitative']
    assert all(np.all(value == 23) for value in api().load_channels(field).values())


def test_rgb_cannot_be_relabelled_quantitative_and_wide_integer_is_rejected(tmp_path):
    path = tmp_path / 'rgb_forced.tif'
    tifffile.imwrite(path, np.zeros((3, 4, 3), np.uint8), photometric='rgb')
    field = api().import_field([{'path': str(path)}])
    field['quantitative'] = True
    with pytest.raises(ValueError, match='RGB|quantitative|figure'):
        api().load_channels(field)
    path = tmp_path / 'uint64.tif'
    tifffile.imwrite(path, np.ones((3, 4), np.uint64))
    with pytest.raises(ValueError, match='dtype|64'):
        api().import_field([{'path': str(path)}])


def test_merge_visibility_is_display_only_and_explicit_channel_stays_visible(tmp_path):
    from titan_if.models import analysis_signature
    path = tmp_path / 'visibility.ome.tif'
    tifffile.imwrite(path, np.full((2, 3, 4), 100, np.uint8), ome=True,
                      metadata={'axes': 'CYX'}, photometric='minisblack')
    field = api().import_field([{'path': str(path)}])
    first, second = field['channels']
    first.update(color='#ff0000', display_max=100)
    second.update(color='#00ff00', display_max=100)
    signature = analysis_signature(field)
    first['visible'] = False
    merged = Image.open(BytesIO(base64.b64decode(api().preview_field(field).split(',', 1)[1])))
    assert merged.getpixel((0, 0)) == (0, 255, 0)
    single = Image.open(BytesIO(base64.b64decode(api().preview_field(field, first['id']).split(',', 1)[1])))
    assert single.getpixel((0, 0)) == (255, 0, 0)
    assert analysis_signature(field) == signature


def test_multifile_ome_requires_explicit_channel_files_for_complete_provenance(tmp_path):
    # A manifest with one plane in another TIFF cannot be verified by hashing
    # only the manifest. Reject it before tifffile opens the referenced file.
    path = tmp_path / 'manifest.ome.tif'
    xml = '''<?xml version="1.0" encoding="UTF-8"?>
    <OME xmlns="http://www.openmicroscopy.org/Schemas/OME/2016-06" UUID="urn:uuid:12345678-1234-1234-1234-123456789abc">
    <Image ID="Image:0"><Pixels ID="Pixels:0" DimensionOrder="XYCZT" Type="uint8" SizeX="4" SizeY="3" SizeC="2" SizeZ="1" SizeT="1">
    <Channel ID="Channel:0:0" SamplesPerPixel="1"/><Channel ID="Channel:0:1" SamplesPerPixel="1"/>
    <TiffData IFD="0" FirstC="0" FirstZ="0" FirstT="0" PlaneCount="1"><UUID FileName="manifest.ome.tif">urn:uuid:12345678-1234-1234-1234-123456789abc</UUID></TiffData>
    <TiffData IFD="0" FirstC="1" FirstZ="0" FirstT="0" PlaneCount="1"><UUID FileName="other.tif">urn:uuid:22345678-1234-1234-1234-123456789abc</UUID></TiffData>
    </Pixels></Image></OME>'''
    tifffile.imwrite(path, np.ones((3, 4), np.uint8), description=xml, metadata=None)
    tifffile.imwrite(tmp_path / 'other.tif', np.full((3, 4), 99, np.uint8), metadata=None)
    with pytest.raises(ValueError, match='multi|external|channel files'):
        api().import_field([{'path': str(path), 'channel_indices': [0]}])
