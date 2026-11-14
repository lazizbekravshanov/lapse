import json

import numpy as np

from lapse import config, export, reduce, synthetic


def test_demo_round_trip(tmp_path, monkeypatch):
    """Synthetic cubes -> export -> files that match the data contract."""
    small = {"none": config.MASKS["none"]}
    monkeypatch.setattr(config, "MASKS", small)
    monkeypatch.setattr(config, "PERIODS", {"airs_era": config.PERIODS["airs_era"]})
    zonal, out = tmp_path / "zonal", tmp_path / "web"
    synthetic.generate(zonal)
    for extra in ("merra2_qv.nc", "merra2_o3.nc"):          # keep the test fast
        (zonal / extra).unlink()

    manifest = export.run(zonal, out, verbose=False)
    assert manifest["synthetic"] is True
    assert [d["id"] for d in manifest["datasets"]] == ["merra2", "airs"]

    trend = json.loads((out / "trend/merra2/t/airs_era__none.json").read_text())
    levels = np.array(manifest["datasets"][0]["levels_hpa"])
    slope = np.array(trend["global"]["slope"], dtype=float)
    assert slope.shape == levels.shape
    assert len(trend["slope"]) == len(levels) and len(trend["slope"][0]) == len(manifest["lat_centers"])

    # The planted signal: warming low down, cooling high up, and it is detected.
    assert slope[levels == 500][0] > 0.1
    assert slope[levels == 1][0] < -0.4
    assert 50 < trend["global"]["flip_hpa"] < 300

    series = json.loads((out / "series/airs/t/global.json").read_text())
    n = manifest["datasets"][1]["time"]["n"]
    assert len(series["anom"][0]) == n

    agree = json.loads((out / manifest["agreement"][0]["file"]).read_text())
    assert set(agree["levels_hpa"]) <= set(levels.tolist())


def test_lat_bands_weights_and_fill():
    lat = np.arange(-89.75, 90, 0.5)
    field = np.ones((2, lat.size, 8))
    field[0, :, 0] = 1e15                                   # fill value must be ignored
    bands = reduce.zonal_bands(field, lat)
    assert bands.shape == (2, len(config.LAT_CENTERS))
    assert np.allclose(bands, 1.0)
