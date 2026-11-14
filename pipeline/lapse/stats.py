"""Trend statistics. The only place numbers shown on the site are computed.

Method, in plain words:
1. Remove the seasonal cycle (each month minus that month's long-term average).
2. Slope: Theil-Sen, the median of the slopes between every pair of months.
   One freak month cannot bend it.
3. Significance: Mann-Kendall test, with its variance widened for month-to-month
   memory (lag-1 autocorrelation). Without this, slow wiggles look like trends.
4. Many cells at once: Benjamini-Hochberg false discovery rate, so about 5% of
   the *flagged* cells are wrong, instead of 5% of all cells.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from scipy.stats import norm

MONTHS_PER_DECADE = 120.0
R1_MAX = 0.95


def deseasonalize(values: np.ndarray, month_of_year: np.ndarray, relative: bool = False) -> np.ndarray:
    """Subtract each calendar month's mean along axis 0. NaNs are ignored.

    relative=True returns percent of the monthly normal instead of a difference.
    """
    values = np.asarray(values, dtype=float)
    out = np.full_like(values, np.nan)
    for m in range(1, 13):
        sel = month_of_year == m
        if not sel.any():
            continue
        with np.errstate(invalid="ignore"):
            clim = np.nanmean(values[sel], axis=0)
        if relative:
            with np.errstate(divide="ignore", invalid="ignore"):
                out[sel] = 100.0 * (values[sel] - clim) / np.where(clim == 0, np.nan, clim)
        else:
            out[sel] = values[sel] - clim
    return out


@lru_cache(maxsize=64)
def _pairs(n: int):
    return np.triu_indices(n, k=1)


def lag1_autocorr(resid: np.ndarray, t: np.ndarray) -> float:
    """Lag-1 autocorrelation using only pairs of consecutive months."""
    consecutive = np.diff(t) == 1
    if consecutive.sum() < 10:
        return 0.0
    a = resid[:-1][consecutive]
    b = resid[1:][consecutive]
    a = a - a.mean()
    b = b - b.mean()
    denom = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / denom) if denom > 0 else 0.0


def trend(y: np.ndarray, t: np.ndarray, alpha: float = 0.05, min_n: int = 24) -> dict:
    """Trend of one series.

    y: anomalies. t: month index (integers, gaps allowed). NaNs in y are dropped.
    Returns slope per decade with a confidence interval, the p-value, lag-1
    autocorrelation and the number of months used.
    """
    y = np.asarray(y, dtype=float)
    t = np.asarray(t, dtype=float)
    ok = np.isfinite(y)
    y, t = y[ok], t[ok]
    n = y.size
    nan = float("nan")
    if n < min_n:
        return {"slope": nan, "lo": nan, "hi": nan, "p": nan, "r1": nan, "n": int(n)}

    i, j = _pairs(n)
    dy = y[j] - y[i]
    dt = t[j] - t[i]
    slopes = np.sort(dy / dt)
    slope = float(np.median(slopes))

    s = float(np.sign(dy).sum())
    var0 = n * (n - 1) * (2 * n + 5) / 18.0

    resid = y - slope * t
    r1 = lag1_autocorr(resid - np.median(resid), t)
    r1c = min(max(r1, 0.0), R1_MAX)          # never shrink the variance
    var = var0 * (1.0 + r1c) / (1.0 - r1c)

    z = 0.0 if s == 0 else (s - np.sign(s)) / np.sqrt(var)
    p = float(2.0 * norm.sf(abs(z)))

    # Confidence interval on the Sen slope (Sen 1968), with the widened variance.
    npairs = slopes.size
    c = norm.ppf(1.0 - alpha / 2.0) * np.sqrt(var)
    lo_idx = int(np.clip(np.floor((npairs - c) / 2.0) - 1, 0, npairs - 1))
    hi_idx = int(np.clip(np.ceil((npairs + c) / 2.0), 0, npairs - 1))

    k = MONTHS_PER_DECADE
    return {
        "slope": slope * k,
        "lo": float(slopes[lo_idx]) * k,
        "hi": float(slopes[hi_idx]) * k,
        "p": p,
        "r1": float(r1),
        "n": int(n),
    }


def bh_qvalues(p: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg q-values. NaN in, NaN out. Shape is preserved."""
    p = np.asarray(p, dtype=float)
    q = np.full(p.shape, np.nan)
    flat = p.ravel()
    ok = np.isfinite(flat)
    m = int(ok.sum())
    if m == 0:
        return q
    idx = np.flatnonzero(ok)
    order = idx[np.argsort(flat[idx])]
    ranked = flat[order] * m / np.arange(1, m + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    q.ravel()[order] = np.minimum(ranked, 1.0)
    return q


def flip_pressure(slope_by_level: np.ndarray, levels_hpa: np.ndarray) -> float:
    """Pressure where the trend changes from positive (below) to negative (above).

    Levels may be in any order. Interpolates in log-pressure. NaN if there is no
    such crossing. If there are several, the lowest one in the atmosphere wins.
    """
    levels_hpa = np.asarray(levels_hpa, dtype=float)
    order = np.argsort(-levels_hpa)                 # surface first
    s = np.asarray(slope_by_level, dtype=float)[order]
    lp = np.log(levels_hpa[order])
    for k in range(len(s) - 1):
        a, b = s[k], s[k + 1]
        if np.isfinite(a) and np.isfinite(b) and a > 0 and b < 0:
            frac = a / (a - b)
            return float(np.exp(lp[k] + frac * (lp[k + 1] - lp[k])))
    return float("nan")
