"""Shrink a global field to latitude bands, and read/write the zonal cubes.

A zonal cube is the hand-off format between "getting data" (real or synthetic)
and "doing statistics". Dimensions: time (monthly), level (hPa), lat (band centre).
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import xarray as xr

from . import config


def clean(a: np.ndarray) -> np.ndarray:
    """Turn fill values into NaN (MERRA-2 uses 1e15, AIRS uses -9999)."""
    a = np.asarray(a, dtype=float)
    return np.where((np.abs(a) > 1e10) | (a < -9000), np.nan, a)


def zonal_bands(field: np.ndarray, lat: np.ndarray) -> np.ndarray:
    """field[level, lat, lon] -> [level, band]. Mean around the globe, then
    cos(latitude)-weighted mean inside each latitude band."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)       # e.g. levels below the ground
        zonal = np.nanmean(clean(field), axis=-1)             # [level, lat]
    return lat_bands(zonal, lat)


def lat_bands(zonal: np.ndarray, lat: np.ndarray) -> np.ndarray:
    """zonal[level, lat] -> [level, band] with cos(lat) weights."""
    lat = np.asarray(lat, dtype=float)
    edges = config.LAT_EDGES
    out = np.full((zonal.shape[0], len(edges) - 1), np.nan)
    w = np.cos(np.deg2rad(lat))
    for b in range(len(edges) - 1):
        last = b == len(edges) - 2
        sel = (lat >= edges[b]) & ((lat <= edges[b + 1]) if last else (lat < edges[b + 1]))
        if not sel.any():
            continue
        vals = zonal[:, sel]
        ww = np.where(np.isfinite(vals), w[sel], 0.0)
        tot = ww.sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            out[:, b] = np.where(tot > 0, np.nansum(vals * ww, axis=1) / tot, np.nan)
    return out


def cube_path(dataset_id: str, variable_id: str, zonal_dir: Path | None = None) -> Path:
    return (zonal_dir or config.ZONAL_DIR) / f"{dataset_id}_{variable_id}.nc"


def write_cube(path: Path, values: np.ndarray, time: np.ndarray, levels, attrs: dict | None = None) -> None:
    """values[time, level, band]. time is an array of numpy datetime64[M]."""
    path.parent.mkdir(parents=True, exist_ok=True)
    ds = xr.Dataset(
        {"value": (("time", "level", "lat"), values.astype("float32"))},
        coords={
            "time": np.asarray(time, dtype="datetime64[ns]"),
            "level": np.asarray(levels, dtype=float),
            "lat": config.LAT_CENTERS,
        },
        attrs={k: str(v) for k, v in (attrs or {}).items()},
    )
    ds.to_netcdf(path)


def read_cube(path: Path) -> xr.Dataset:
    with xr.open_dataset(path) as ds:
        return ds.load()


def month_index(time: np.ndarray) -> np.ndarray:
    """Months since year 0, so consecutive months differ by exactly 1."""
    t = np.asarray(time, dtype="datetime64[M]")
    return t.astype(int) + 1970 * 12


def month_of_year(time: np.ndarray) -> np.ndarray:
    t = np.asarray(time, dtype="datetime64[M]")
    return t.astype(int) % 12 + 1
