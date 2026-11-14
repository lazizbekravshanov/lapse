import json

import numpy as np

from lapse import config, export, reduce, synthetic


def test_demo_round_trip(tmp_path, monkeypatch):
    """Synthetic cubes -> export -> files that match the data contract."""
    zonal, out = tmp_path / "zonal", tmp_path / "web"
    synthetic.generate(zonal)
    for extra in ("merra2_qv.nc", "merra2_o3.nc"):          # keep the test fast
        (zonal / extra).unlink()
    (out / "trend" / "old").mkdir(parents=True)
    (out / "trend" / "old" / "stale.json").write_text("{}")

    manifest = export.run(zonal, out, verbose=False)
    assert manifest["schema"] == 2 and manifest["synthetic"] is True
    assert [d["id"] for d in manifest["datasets"]] == ["merra2", "airs"]
    assert not (out / "trend" / "old").exists()                 # stale output is removed

    merra, airs = manifest["datasets"]
    assert [p["id"] for p in merra["periods"]] == ["full", "airs_era"]
    assert [p["id"] for p in airs["periods"]] == ["full"]       # same years as airs_era: kept once
    pair = {(w["dataset"], w["period"]): (w["with_dataset"], w["with_period"]) for w in manifest["witness"]}
    assert pair[("airs", "full")] == ("merra2", "airs_era")
    assert pair[("merra2", "airs_era")] == ("airs", "full")
    assert ("merra2", "full") not in pair                       # no second dataset before 2002

    trend = json.loads((out / "trend/merra2/t/airs_era__none.json").read_text())
    levels = np.array(merra["levels_hpa"])
    glob = trend["regions"]["global"]
    slope = np.array(glob["slope"], dtype=float)
    assert slope.shape == levels.shape
    assert len(trend["slope"]) == len(levels) and len(trend["slope"][0]) == len(manifest["lat_centers"])
    assert set(trend["regions"]) == {r["id"] for r in config.REGIONS}

    # The planted signal: warming low down, cooling high up, and it is detected.
    assert slope[levels == 500][0] > 0.1 and slope[levels == 1][0] < -0.4
    assert 50 < glob["flip_hpa"] < 300
    assert glob["verdict"][list(levels).index(500)] == 2        # clear: both datasets agree
    codes = {v for row in trend["verdict"] for v in row if v is not None}
    assert codes <= {0, 1, 2, 3}

    # Before 2002 there is no witness, so nothing can be "clear".
    full = json.loads((out / "trend/merra2/t/full__none.json").read_text())
    assert 2 not in {v for row in full["verdict"] for v in row}

    series = json.loads((out / "series/airs/t/region_global.json").read_text())
    assert len(series["anom"][0]) == airs["time"]["n"]

    pairs = json.loads((out / "pairs/airs/t/full.json").read_text())
    top = pairs["vertical"][0]
    assert top["where"] == {"region": "global"}
    assert top["low"]["slope"] > 0 > top["high"]["slope"]


def test_region_series_needs_half_the_area():
    w = export.region_weights()
    assert w["global"].sum() > w["tropics"].sum() > w["arctic"].sum() > 0
    anom = np.ones((3, 2, len(config.LAT_CENTERS)))
    anom[:, 1, :] = np.nan
    anom[:, 1, 3:6] = 5.0                                   # only three Antarctic-edge bands have data
    out = export.region_series(anom, w["global"])
    assert np.allclose(out[:, 0], 1.0) and np.isnan(out[:, 1]).all()
    assert np.allclose(export.region_series(anom, w["antarctic"])[:, 1], 5.0)


def test_lat_bands_weights_and_fill():
    lat = np.arange(-89.75, 90, 0.5)
    field = np.ones((2, lat.size, 8))
    field[0, :, 0] = 1e15                                   # fill value must be ignored
    bands = reduce.zonal_bands(field, lat)
    assert bands.shape == (2, len(config.LAT_CENTERS))
    assert np.allclose(bands, 1.0)


def test_validation_table_from_synthetic_cubes(tmp_path):
    from lapse import validate

    zonal = tmp_path / "zonal"
    synthetic.generate(zonal)
    rows = validate.run(zonal, tmp_path / "docs", tmp_path / "web")
    assert {r["id"] for r in rows} == {c["id"] for c in validate.CHECKS}
    text = (tmp_path / "docs" / "validation.md").read_text()
    assert text.count("\n| ") >= len(rows) + 1
    by = {r["id"]: r for r in rows}
    assert by["jpl_low"]["match"].startswith("Yes") and by["jpl_high"]["match"].startswith("Yes")
