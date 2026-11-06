import numpy as np
import pytest
import tifffile

from titan_if.volume import inspect_volume, prepare_volume


def make_stack(tmp_path, *, positions=None, calibrated=True, axes="TZCYX"):
    data = np.arange(2 * 4 * 3 * 5 * 7, dtype=np.uint16).reshape(2, 4, 3, 5, 7)
    path = tmp_path / "volume.ome.tif"
    metadata = {"axes": axes, "Channel": {"Name": ["DNA", "Actin", "Membrane"]}}
    if calibrated:
        metadata.update(PhysicalSizeX=200, PhysicalSizeXUnit="nm", PhysicalSizeY=.3, PhysicalSizeZ=1.5)
    if positions is not None:
        metadata["Plane"] = {"PositionZ": positions}
    tifffile.imwrite(path, data, photometric="minisblack", compression="deflate", metadata=metadata)
    return path, data


def test_stage_uses_requested_t_c_and_preserves_z_order(tmp_path):
    source, raw = make_stack(tmp_path)
    info = inspect_volume(source)
    series = info["series"][0]
    assert series["spacing"] == [.2, .3, 1.5]
    assert series["channels"] == ["DNA", "Actin", "Membrane"]
    assert series["timepoints"] == 2
    target = tmp_path / "volume.raw"
    progress = []
    result = prepare_volume({"path": str(source), "series": 0, "time": 1, "channels": [2, 0]},
                            target, lambda done, total: progress.append((done, total)), lambda: False)
    staged = np.fromfile(target, dtype="<u2").reshape(4, 5, 7, 2)
    np.testing.assert_array_equal(staged, raw[1][:, [2, 0]].transpose(0, 2, 3, 1))
    assert result["dimensions"] == [7, 5, 4]
    assert progress[-1] == (4, 4)


def test_missing_spacing_and_cancel_do_not_publish(tmp_path):
    source, _ = make_stack(tmp_path, calibrated=False)
    target = tmp_path / "volume.raw"
    options = {"path": str(source), "series": 0, "time": 0, "channels": [0, 1]}
    with pytest.raises(ValueError, match="标定"):
        prepare_volume(options, target, lambda *_: None, lambda: False)
    options["spacing"] = [.2, .3, 1]
    cancelled = []
    assert prepare_volume(options, target, lambda *_: cancelled.append(True), lambda: bool(cancelled)) is None
    assert not target.exists()


def test_rejects_irregular_z_positions(tmp_path):
    source, _ = make_stack(tmp_path, positions=np.repeat([0., 1., 3., 4.] * 2, 3).tolist())
    assert "不等距" in inspect_volume(source)["series"][0]["error"]


def test_downsample_only_xy_and_keep_calibrated_spacing(tmp_path, monkeypatch):
    from titan_if import volume
    monkeypatch.setattr(volume, "MAX_DISPLAY_SIDE", 4)
    source, raw = make_stack(tmp_path)
    target = tmp_path / "volume.raw"
    options = {"path": str(source), "series": 0, "time": 0, "channels": [1]}
    result = prepare_volume(options, target, lambda *_: None, lambda: False)
    assert result["dimensions"] == [4, 3, 4]
    assert result["spacing"] == [.4, .6, 1.5]
    np.testing.assert_array_equal(np.fromfile(target, dtype="<u2").reshape(4, 3, 4),
                                  raw[0, :, 1, ::2, ::2])


def test_rejects_z_positions_that_conflict_with_the_shared_calibration(tmp_path):
    positions = np.repeat([0., 2., 4., 6.] * 2, 3)
    source, _ = make_stack(tmp_path, positions=positions.tolist())
    assert "Z 标定" in inspect_volume(source)["series"][0]["error"]


def test_rejects_single_plane_and_oversized_source(tmp_path, monkeypatch):
    from titan_if import volume
    path = tmp_path / "flat.ome.tif"
    tifffile.imwrite(path, np.zeros((3, 8, 8), np.uint8), photometric="minisblack",
                     metadata={"axes": "CYX"})
    assert "一个 Z 层" in inspect_volume(path)["series"][0]["error"]
    source, _ = make_stack(tmp_path)
    monkeypatch.setattr(volume, "MAX_SOURCE_BYTES", 8)
    with pytest.raises(ValueError, match="超过"):
        prepare_volume({"path": str(source), "series": 0, "time": 0, "channels": [0, 1]},
                       tmp_path / "volume.raw", lambda *_: None, lambda: False)
