"""Fake but realistic-looking zonal cubes, so everything downstream can be built
and tested before any NASA data is downloaded.

THIS IS NOT DATA. The shapes are loosely modelled on the textbook picture
(warming below, cooling above, a volcanic cold patch in 2022-23, a fake jump in
the reanalysis high up) so the website has something meaningful to draw.
Every file written here is tagged synthetic, and the site shows a banner.
"""

from __future__ import annotations

import numpy as np

from ... import config
from . import cubes

END_MONTH = "2026-09"


def _months(start: str, end: str = END_MONTH) -> np.ndarray:
    return np.arange(np.datetime64(start, "M"), np.datetime64(end, "M") + np.timedelta64(1, "M"))


def _between(time, start, end):
    return (time >= np.datetime64(start, "M")) & (time <= np.datetime64(end, "M"))


def _ar1(rng, shape, phi):
    """AR(1) noise along axis 0 with unit variance."""
    e = rng.standard_normal(shape)
    out = np.empty(shape)
    out[0] = e[0]
    k = np.sqrt(1.0 - phi * phi)
    for i in range(1, shape[0]):
        out[i] = phi * out[i - 1] + k * e[i]
    return out


def true_t_trend(levels, lat):
    """The planted temperature trend, K per decade, shape [level, lat]."""
    p = np.asarray(levels, dtype=float)[:, None]
    la = np.asarray(lat, dtype=float)[None, :]
    lp = np.log(p)
    trop = 0.20 + 0.10 * np.exp(-((la / 25.0) ** 2)) * np.exp(-((lp - np.log(300)) ** 2) / 0.3)
    arctic = 0.45 * np.clip((la - 55.0) / 30.0, 0, 1) * np.clip((p - 600.0) / 400.0, 0, 1)
    low = trop + arctic
    # log-linear fall from +0.2 at 300 hPa to -0.8 at 1 hPa
    frac = np.clip((np.log(300.0) - lp) / (np.log(300.0) - np.log(1.0)), 0, 1)
    high = 0.20 - 1.0 * frac
    return np.where(p >= 300.0, low, high)


def _nature_t(rng, time, levels, lat):
    """Seasonal cycle + trend + weather noise + volcanoes, on the given levels."""
    nt, nl, nb = len(time), len(levels), len(lat)
    p = np.asarray(levels, dtype=float)[None, :, None]
    la = np.asarray(lat, dtype=float)[None, None, :]
    tt = (np.arange(nt) / 120.0)[:, None, None]                 # decades
    moy = cubes.month_of_year(time)[:, None, None]

    z = config.approx_altitude_km(p)
    base = np.where(z < 11, 288.0 - 6.5 * z, np.where(z < 20, 216.5, 216.5 + 2.2 * (z - 20)))
    base = base - 30.0 * np.sin(np.deg2rad(la)) ** 2 * np.clip(p / 1000.0, 0.1, 1)
    season = 8.0 * np.sin(np.deg2rad(la)) * np.cos(2 * np.pi * (moy - 7) / 12.0) * np.clip(p / 500.0, 0.3, 1)

    sd = np.where(p >= 150, 0.45, 0.6) + np.where((np.abs(la) > 60) & (p < 150), 2.4, 0.0)
    phi = 0.55
    noise = _ar1(rng, (nt, nl, nb), phi) * sd
    # smooth the noise a little in the vertical so neighbouring levels agree
    noise = (noise + np.roll(noise, 1, axis=1) + np.roll(noise, -1, axis=1)) / 3.0

    out = base + season + true_t_trend(levels, lat)[None] * tt + noise

    def bump(center_hpa, width):
        return np.exp(-((np.log(p) - np.log(center_hpa)) ** 2) / width)

    hunga = _between(time, "2022-02", "2023-08")[:, None, None]
    out = out - 2.5 * hunga * bump(15.0, 1.2) * np.exp(-(((la + 15.0) / 25.0) ** 2))
    pin = _between(time, "1991-07", "1993-06")[:, None, None]
    out = out + 2.0 * pin * bump(50.0, 0.8) * np.exp(-((la / 35.0) ** 2))
    return out


def _interp_levels(values, src_levels, dst_levels):
    """Interpolate [time, level, lat] in log-pressure to another level set."""
    src = np.log(np.asarray(src_levels, dtype=float))
    dst = np.log(np.asarray(dst_levels, dtype=float))
    order = np.argsort(src)
    nt, _, nb = values.shape
    out = np.empty((nt, len(dst), nb))
    for b in range(nb):
        for t in range(nt):
            out[t, :, b] = np.interp(dst, src[order], values[t, order, b])
    return out


def _relative_field(rng, time, levels, lat, kind):
    """Positive fields for water vapor / ozone with a planted % trend."""
    nt, nl, nb = len(time), len(levels), len(lat)
    p = np.asarray(levels, dtype=float)[None, :, None]
    la = np.asarray(lat, dtype=float)[None, None, :]
    tt = (np.arange(nt) / 120.0)[:, None, None]
    moy = cubes.month_of_year(time)[:, None, None]
    if kind == "qv":
        base = 1e-2 * (p / 1000.0) ** 3 * np.cos(np.deg2rad(la)) ** 2 + 3e-6
        trend_pct = np.where(p >= 200, 1.5, 0.3)
        extra = 0.20 * _between(time, "2022-02", "2024-06")[:, None, None] * (p <= 50) * (p >= 1)
        sd = np.where(p >= 200, 0.04, 0.03)
    else:  # ozone
        base = 8e-6 * np.exp(-((np.log(p) - np.log(8.0)) ** 2) / 2.5) + 5e-8
        trend_pct = np.where(p <= 5, 1.0, np.where(p <= 100, -0.8, 0.5))
        extra = 0.0
        sd = 0.03
    season = 1.0 + 0.1 * np.sin(np.deg2rad(la)) * np.cos(2 * np.pi * (moy - 7) / 12.0)
    noise = _ar1(rng, (nt, nl, nb), 0.5) * sd
    return base * season * (1.0 + trend_pct / 100.0 * tt + extra + noise)


def generate(zonal_dir=None, seed: int = 7) -> list:
    """Write synthetic cubes for every dataset/variable in config. Returns paths."""
    lat = config.LAT_CENTERS
    written = []
    attrs = {"synthetic": "true", "note": "Synthetic demo data. Not NASA measurements."}

    # One "nature" run on MERRA-2 levels from 1980, shared by both datasets.
    m2 = config.DATASETS["merra2"]
    time_all = _months(m2.start)
    nature = _nature_t(np.random.default_rng(seed), time_all, m2.levels, lat)

    for ds in config.DATASETS.values():
        time = _months(ds.start)
        sel = time_all >= time[0]
        rng = np.random.default_rng(seed + sum(map(ord, ds.id)))
        for var in ds.variables:
            if var.id == "t":
                vals = nature[sel]
                if tuple(ds.levels) != tuple(m2.levels):
                    vals = _interp_levels(vals, m2.levels, ds.levels)
                vals = vals + 0.15 * rng.standard_normal(vals.shape)   # instrument noise
                if ds.kind == "reanalysis":
                    # planted fake jumps high up, where the input satellites changed
                    p = np.asarray(ds.levels, dtype=float)[None, :, None]
                    vals = vals + 1.0 * (time >= np.datetime64("1998-07"))[:, None, None] * (p <= 5)
                    vals = vals + 0.7 * (time >= np.datetime64("2004-08"))[:, None, None] * (p <= 3)
            else:
                vals = _relative_field(rng, time, ds.levels, lat, var.id)
            path = cubes.cube_path(ds.id, var.id, zonal_dir)
            cubes.write_cube(path, vals, time, ds.levels, attrs)
            written.append(path)
    return written
