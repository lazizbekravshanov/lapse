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

import warnings
from functools import lru_cache

import numpy as np
from scipy.stats import norm
from scipy.stats import t as student_t

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
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)      # cells with no data at all
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


def jump_check(anom: np.ndarray, starts, ends, window: int = 24, min_valid: int = 12):
    """Does the series jump at a known data-source change?

    anom[time, ...] is monthly and contiguous (gaps are NaN). starts/ends are index
    ranges of the documented changes. For every month k the "shift" is the mean of
    the next `window` months minus the mean of the previous `window` months.

    Returns (step, usual): the largest shift inside any change window (signed), and
    the 97.5th percentile of |shift| at all other times, i.e. how big a two-year
    shift normally gets in this series. Shapes follow anom[0].
    """
    y = np.asarray(anom, dtype=float)
    n = y.shape[0]
    ok = np.isfinite(y)
    zero = np.zeros((1,) + y.shape[1:])
    csum = np.concatenate([zero, np.cumsum(np.where(ok, y, 0.0), axis=0)])
    ccnt = np.concatenate([zero, np.cumsum(ok, axis=0)])
    shift = np.full(y.shape, np.nan)
    for k in range(1, n):
        a0, b1 = max(0, k - window), min(n, k + window)
        nb, na = ccnt[k] - ccnt[a0], ccnt[b1] - ccnt[k]
        with np.errstate(invalid="ignore", divide="ignore"):
            d = (csum[b1] - csum[k]) / na - (csum[k] - csum[a0]) / nb
        shift[k] = np.where((nb >= min_valid) & (na >= min_valid), d, np.nan)

    near = np.zeros(n, dtype=bool)
    step = np.zeros(y.shape[1:])
    for s0, e0 in zip(starts, ends):
        lo, hi = max(1, s0), min(n - 1, e0 + 1)
        if lo > hi:
            continue
        near[max(0, lo - window):min(n, hi + window + 1)] = True
        seg = shift[lo:hi + 1]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            idx = np.nanargmax(np.where(np.isfinite(seg), np.abs(seg), -1.0), axis=0)
        cand = np.take_along_axis(seg, idx[None], axis=0)[0]
        step = np.where(np.abs(np.nan_to_num(cand)) > np.abs(step), np.nan_to_num(cand), step)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        usual = np.nanpercentile(np.abs(shift[~near]), 97.5, axis=0) if (~near).sum() > window else np.full(y.shape[1:], np.inf)
    return step, usual


# --- many series at once ------------------------------------------------------
# Every method below takes y[time, cells] and month indices t[time], and returns
# a dict of arrays with one value per cell: slope, lo, hi (per decade), p, r1, n.
# That shared shape is what lets the hub offer them as interchangeable tools.

def sen_mk_many(y: np.ndarray, t: np.ndarray, alpha: float = 0.05, min_n: int = 24) -> dict:
    """Theil-Sen slope with the memory-corrected Mann-Kendall test, cell by cell."""
    y = np.asarray(y, dtype=float)
    keys = ("slope", "lo", "hi", "p", "r1", "n")
    out = {k: np.full(y.shape[1], np.nan) for k in keys}
    for c in range(y.shape[1]):
        res = trend(y[:, c], t, alpha=alpha, min_n=min_n)
        for k in keys:
            out[k][c] = res[k]
    return out


def _lag1_many(resid: np.ndarray, t: np.ndarray, step: int = 1) -> np.ndarray:
    """Lag-1 autocorrelation per cell, from pairs of consecutive time steps."""
    consecutive = np.diff(t) == step
    a, b = resid[:-1][consecutive], resid[1:][consecutive]
    ok = np.isfinite(a) & np.isfinite(b)
    cnt = ok.sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        am = np.where(ok, a, 0.0).sum(axis=0) / cnt
        bm = np.where(ok, b, 0.0).sum(axis=0) / cnt
        da, db = np.where(ok, a - am, 0.0), np.where(ok, b - bm, 0.0)
        r = (da * db).sum(axis=0) / np.sqrt((da * da).sum(axis=0) * (db * db).sum(axis=0))
    return np.where((cnt >= 10) & np.isfinite(r), r, 0.0)


def _ols_fit(y: np.ndarray, t: np.ndarray):
    """Least-squares line per cell, ignoring missing months. Returns the pieces."""
    y = np.asarray(y, dtype=float)
    tt = np.asarray(t, dtype=float)[:, None]
    ok = np.isfinite(y)
    n = ok.sum(axis=0).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        tbar = (ok * tt).sum(axis=0) / n
        ybar = np.where(ok, y, 0.0).sum(axis=0) / n
        dt = np.where(ok, tt - tbar, 0.0)
        sxx = (dt * dt).sum(axis=0)
        slope = (dt * np.where(ok, y - ybar, 0.0)).sum(axis=0) / sxx
        resid = np.where(ok, y - ybar - slope * (tt - tbar), np.nan)
    return slope, resid, dt, sxx, n


def ols_many(y: np.ndarray, t: np.ndarray, alpha: float = 0.05, min_n: int = 24, memory: bool = True,
             step: int = 1) -> dict:
    """Least-squares slope with a t-test.

    memory=True shrinks the number of independent months for month-to-month memory
    (effective sample size). memory=False is the plain textbook test.
    """
    slope, resid, dt, sxx, n = _ols_fit(y, t)
    r1 = _lag1_many(resid, np.asarray(t), step)
    r1c = np.clip(r1, 0.0, R1_MAX) if memory else np.zeros_like(r1)
    with np.errstate(invalid="ignore", divide="ignore"):
        se = np.sqrt(np.nansum(resid ** 2, axis=0) / (n - 2) / sxx)
        n_eff = n * (1.0 - r1c) / (1.0 + r1c)
        df = np.maximum(n_eff - 2.0, 1.0)
        se = se * np.sqrt((n - 2.0) / df)
        p = 2.0 * student_t.sf(np.abs(slope / se), df)
        half = student_t.ppf(1.0 - alpha / 2.0, df) * se
    out = {"slope": slope * MONTHS_PER_DECADE, "lo": (slope - half) * MONTHS_PER_DECADE,
           "hi": (slope + half) * MONTHS_PER_DECADE, "p": p, "r1": r1, "n": n}
    return _blank_short(out, min_n)


def yearly_many(y: np.ndarray, t: np.ndarray, alpha: float = 0.05, min_n: int = 24,
                min_months: int = 6, min_years: int = 10) -> dict:
    """Average each calendar year first, then fit a line through the yearly values.

    Yearly averages carry far less memory than months, so the ordinary t-test (with
    the same memory correction) is close to honest. A year needs `min_months` months
    of data to count.
    """
    y = np.asarray(y, dtype=float)
    t = np.asarray(t)
    years = t // 12
    labels = np.unique(years)
    annual = np.full((labels.size, y.shape[1]), np.nan)
    for k, yr in enumerate(labels):
        block = y[years == yr]
        have = np.isfinite(block).sum(axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            mean = np.where(np.isfinite(block), block, 0.0).sum(axis=0) / have
        annual[k] = np.where(have >= min_months, mean, np.nan)
    out = ols_many(annual, labels * 12 + 6, alpha=alpha, min_n=max(min_years, min_n // 12), step=12)
    out["n"] = np.isfinite(y).sum(axis=0).astype(float)          # months behind the yearly values
    return out


def _blank_short(out: dict, min_n: int) -> dict:
    """Cells with too few months get no result."""
    short = ~(out["n"] >= min_n) | ~np.isfinite(out["slope"])
    for k in ("slope", "lo", "hi", "p", "r1"):
        out[k] = np.where(short, np.nan, out[k])
    return out
