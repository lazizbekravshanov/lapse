"""Download real NASA data and shrink it to zonal cubes.

STATUS: written from NASA's documented access pattern but NOT yet run against
the live servers (it needs your Earthdata login). First thing Saturday:

    pip install -e "pipeline[nasa]"
    lapse inspect merra2        # prints the real variable and dimension names
    lapse fetch merra2 --start 2024-01 --end 2024-03    # small smoke test

If a name is wrong, fix it in config.py, not here.

How it stays small: the server (OPeNDAP) sends only the variables asked for,
and only every Nth grid point. A full MERRA-2 pressure-level field is about
361 x 576 x 42 values per month; with stride 4 that is 16 times less. Each
month is reduced to [level, latitude band] and cached, so a crash loses nothing.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from . import config, reduce


def _session():
    import earthaccess
    from pydap.net import create_session

    auth = earthaccess.login(persist=True)   # asks once, then reuses ~/.netrc
    return create_session(session=auth.get_session())


def _urls(ds: config.Dataset, start: str, end: str) -> list:
    import datetime as dt

    import earthaccess
    from pydap.client import get_cmr_urls

    hits = earthaccess.search_datasets(short_name=ds.short_name, version=ds.version)
    if not hits:
        raise SystemExit(f"No NASA collection found for {ds.short_name} v{ds.version}")
    ccid = hits[0].concept_id()
    y0, m0 = map(int, start.split("-"))
    y1, m1 = map(int, end.split("-"))
    time_range = [dt.datetime(y0, m0, 1), dt.datetime(y1, m1, 28)]
    return sorted(set(get_cmr_urls(ccid=ccid, time_range=time_range, limit=2000)))


def _open(url: str, session):
    import xarray as xr

    return xr.open_dataset(url.replace("https", "dap4", 1), engine="pydap", session=session)


def inspect(dataset_id: str) -> None:
    """Print one file's structure so names in config.py can be checked."""
    ds = config.DATASETS[dataset_id]
    urls = _urls(ds, "2020-01", "2020-01")
    print(f"{len(urls)} file(s) for 2020-01. First: {urls[0]}")
    print(_open(urls[0], _session()))


def _month_from_url(ds: config.Dataset, url: str):
    m = re.search(ds.month_regex, url)
    return f"{m.group(1)}-{m.group(2)}" if m else None


def _reduce_month(remote, ds: config.Dataset, var: config.Variable, stride: int):
    """One month, one variable -> ([level, band], levels)."""
    fields = []
    for name in var.source_names:
        da = remote[name]
        da = da.isel({ds.lat_dim: slice(None, None, stride), ds.lon_dim: slice(None, None, stride)})
        if "time" in da.dims:
            da = da.isel(time=0)
        da = da.transpose(ds.lev_dim, ds.lat_dim, ds.lon_dim).load()
        fields.append(reduce.clean(da.values) * var.scale)
        lat = da[ds.lat_dim].values
        levels = da[ds.lev_dim].values
    with np.errstate(invalid="ignore"):
        field = np.nanmean(np.stack(fields), axis=0)
    return reduce.zonal_bands(field, lat), np.asarray(levels, dtype=float)


def fetch(dataset_id: str, start: str | None = None, end: str | None = None,
          stride: int = 4, cache_dir: Path | None = None, zonal_dir: Path | None = None) -> list:
    """Download [start, end] (YYYY-MM), cache each month, then build the cubes."""
    ds = config.DATASETS[dataset_id]
    start = start or ds.start
    end = end or str(np.datetime64("today", "M") - np.timedelta64(2, "M"))
    cache = (cache_dir or config.CACHE_DIR) / ds.id
    cache.mkdir(parents=True, exist_ok=True)

    session = _session()
    urls = _urls(ds, start, end)
    print(f"{ds.id}: {len(urls)} monthly files, stride {stride}")
    for n, url in enumerate(urls, 1):
        month = _month_from_url(ds, url)
        if month is None:
            print(f"  ? cannot read the month from {url}")
            continue
        todo = [v for v in ds.variables if not (cache / f"{v.id}_{month}.npz").exists()]
        if not todo:
            continue
        try:
            remote = _open(url, session)
            for var in todo:
                bands, levels = _reduce_month(remote, ds, var, stride)
                np.savez_compressed(cache / f"{var.id}_{month}.npz", bands=bands, levels=levels)
            print(f"  [{n}/{len(urls)}] {month} ok")
        except Exception as exc:                      # keep going; rerun fills the gaps
            print(f"  [{n}/{len(urls)}] {month} FAILED: {exc}")
    return assemble(dataset_id, cache_dir, zonal_dir)


def assemble(dataset_id: str, cache_dir: Path | None = None, zonal_dir: Path | None = None) -> list:
    """Stack the cached months into one cube per variable. Missing months become NaN."""
    ds = config.DATASETS[dataset_id]
    cache = (cache_dir or config.CACHE_DIR) / ds.id
    written = []
    for var in ds.variables:
        files = sorted(cache.glob(f"{var.id}_*.npz"))
        if not files:
            continue
        months = np.array([np.datetime64(f.stem.split("_", 1)[1], "M") for f in files])
        time = np.arange(months.min(), months.max() + np.timedelta64(1, "M"))
        first = np.load(files[0])
        levels = first["levels"]
        cube = np.full((time.size, levels.size, len(config.LAT_CENTERS)), np.nan)
        for f, m in zip(files, months):
            cube[int((m - time[0]).astype(int))] = np.load(f)["bands"]
        path = reduce.cube_path(ds.id, var.id, zonal_dir)
        reduce.write_cube(path, cube, time, levels,
                          {"synthetic": "false", "source": f"{ds.short_name} v{ds.version}"})
        print(f"  wrote {path.name}: {time.size} months, {levels.size} levels")
        written.append(path)
    return written
