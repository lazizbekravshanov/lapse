"""Zonal cubes in, website JSON out. See docs/data-contract.md for the format.

Everything the site shows is decided here: trends, ranges, the four-label
verdict, regional averages and the list of opposite pairs.
"""

from __future__ import annotations

import json
import shutil
import time as _time
import warnings
from pathlib import Path

import numpy as np

from . import config, reduce, stats, verdict

SCHEMA = 2
GENERATED = ("trend", "series", "pairs", "agreement")     # folders this module owns
KEYS = ("slope", "lo", "hi", "p", "r1", "n")


# --- small helpers ------------------------------------------------------------

def _r(a, digits=4):
    """Round to JSON-friendly lists; NaN becomes null."""
    a = np.asarray(a, dtype=float)
    out = np.round(a, digits).astype(object)
    out[~np.isfinite(a)] = None
    return out.tolist()


def _num(x, digits=2):
    return None if x is None or not np.isfinite(x) else round(float(x), digits)


def _dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, separators=(",", ":")))


def _keep(time, period, mask) -> np.ndarray:
    """Boolean array: which months count for this period and mask."""
    t = np.asarray(time, dtype="datetime64[M]")
    keep = np.ones(t.shape, dtype=bool)
    if period["start"]:
        keep &= t >= np.datetime64(period["start"], "M")
    if period["end"]:
        keep &= t <= np.datetime64(period["end"], "M")
    events = {e["id"]: e for e in config.EVENTS}
    for eid in mask["exclude"]:
        e = events[eid]
        keep &= ~((t >= np.datetime64(e["start"], "M")) & (t <= np.datetime64(e["end"], "M")))
    return keep


def _span(time, period):
    """First and last month a period covers in this dataset, as month numbers."""
    t = np.asarray(time, dtype="datetime64[M]")[_keep(time, period, {"exclude": []})]
    return (int(t[0].astype(int)), int(t[-1].astype(int))) if t.size else None


def _same_span(a, b) -> bool:
    return a is not None and b is not None and abs(a[0] - b[0]) <= 1 and abs(a[1] - b[1]) <= 3


def _month(n: int) -> str:
    return str(np.datetime64(n, "M"))


# --- regions ------------------------------------------------------------------

def region_weights() -> dict:
    """{region id: weight per latitude band}. cos(latitude) inside, zero outside."""
    lat = config.LAT_CENTERS
    w = np.cos(np.deg2rad(lat))
    return {r["id"]: np.where((lat >= r["lat"][0]) & (lat <= r["lat"][1]), w, 0.0)
            for r in config.REGIONS}


def region_series(anom: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """anom[time, level, lat] -> [time, level]. Needs data for half the region's area."""
    ww = np.where(np.isfinite(anom), weights[None, None, :], 0.0)
    tot = ww.sum(axis=2)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = np.nansum(anom * ww, axis=2) / tot
    return np.where(tot >= 0.5 * weights.sum(), mean, np.nan)


# --- trends -------------------------------------------------------------------

def _trend_many(series: np.ndarray, tidx: np.ndarray) -> dict:
    """series[time, ...] -> dict of arrays shaped like series[0], plus q and sig."""
    shape = series.shape[1:]
    flat = series.reshape(series.shape[0], -1)
    out = {k: np.full(flat.shape[1], np.nan) for k in KEYS}
    for c in range(flat.shape[1]):
        res = stats.trend(flat[:, c], tidx, alpha=config.ALPHA, min_n=config.MIN_MONTHS)
        for k in KEYS:
            out[k][c] = res[k]
    out = {k: v.reshape(shape) for k, v in out.items()}
    out["q"] = stats.bh_qvalues(out["p"])
    out["sig"] = (out["q"] <= config.FDR_Q).astype(float)
    out["sig"][~np.isfinite(out["slope"])] = np.nan
    return out


def _pack(g: dict) -> dict:
    out = {
        "slope": _r(g["slope"]), "lo": _r(g["lo"]), "hi": _r(g["hi"]),
        "p": _r(g["p"], 5), "q": _r(g["q"], 5), "sig": _r(g["sig"], 0),
        "r1": _r(g["r1"], 2), "n": _r(g["n"], 0),
    }
    if "verdict" in g:
        out["verdict"] = _r(g["verdict"], 0)
        out["reason"] = _r(g["reason"], 0)
    if "step" in g:
        out["step"] = _r(g["step"], 2)
    return out


# --- opposite pairs -----------------------------------------------------------

def find_pairs(res: dict, levels, top_bands: int = 3, top_levels: int = 3) -> dict:
    """Places where two proven trends point in opposite directions.

    vertical:   same place, two heights.   horizontal: same height, two latitude bands.
    Only "Likely" and "Clear" trends count. Score = the smaller of the two sizes.
    """
    levels = np.asarray(levels, dtype=float)
    order = np.argsort(-levels)                         # ground first

    def good(v):
        return np.isin(v, (verdict.LIKELY, verdict.CLEAR))

    def best_vertical(slope, verd):
        best = None
        ok = good(verd)
        for a in range(len(order)):
            i = order[a]
            if not ok[i]:
                continue
            for b in range(a + 1, len(order)):
                j = order[b]
                if ok[j] and slope[i] * slope[j] < 0:
                    score = min(abs(slope[i]), abs(slope[j]))
                    if best is None or score > best[0]:
                        best = (score, int(i), int(j))
        return best

    def side(level, slope, verd):
        return {"level": int(level), "hpa": float(levels[level]), "slope": _num(slope, 4), "verdict": int(verd)}

    vertical = []
    for r in config.REGIONS:
        g = res["regions"][r["id"]]
        hit = best_vertical(g["slope"], g["verdict"])
        if hit:
            vertical.append({"where": {"region": r["id"]}, "score": _num(hit[0], 4),
                             "low": side(hit[1], g["slope"][hit[1]], g["verdict"][hit[1]]),
                             "high": side(hit[2], g["slope"][hit[2]], g["verdict"][hit[2]])})
    bands = []
    grid = res["grid"]
    for j in range(grid["slope"].shape[1]):
        hit = best_vertical(grid["slope"][:, j], grid["verdict"][:, j])
        if hit:
            bands.append({"where": {"lat": j}, "score": _num(hit[0], 4),
                          "low": side(hit[1], grid["slope"][hit[1], j], grid["verdict"][hit[1], j]),
                          "high": side(hit[2], grid["slope"][hit[2], j], grid["verdict"][hit[2], j])})
    vertical += sorted(bands, key=lambda p: -p["score"])[:top_bands]

    horizontal = []
    for i in range(grid["slope"].shape[0]):
        s, ok = grid["slope"][i], good(grid["verdict"][i])
        best = None
        for a in np.flatnonzero(ok):
            for b in np.flatnonzero(ok):
                if a < b and s[a] * s[b] < 0:
                    score = min(abs(s[a]), abs(s[b]))
                    if best is None or score > best[0]:
                        best = (score, int(a), int(b))
        if best:
            horizontal.append({
                "level": int(i), "hpa": float(levels[i]), "score": _num(best[0], 4),
                "a": {"lat": best[1], "slope": _num(s[best[1]], 4), "verdict": int(grid["verdict"][i, best[1]])},
                "b": {"lat": best[2], "slope": _num(s[best[2]], 4), "verdict": int(grid["verdict"][i, best[2]])},
            })
    horizontal = sorted(horizontal, key=lambda p: -p["score"])[:top_levels]
    return {"vertical": vertical, "horizontal": horizontal}


# --- main ---------------------------------------------------------------------

def run(zonal_dir: Path | None = None, out_dir: Path | None = None, verbose: bool = True) -> dict:
    """Compute every trend variant and write the website data. Returns the manifest."""
    out_dir = out_dir or config.WEB_DATA_DIR
    t0 = _time.time()
    for name in GENERATED:                       # never leave stale files from an older run
        shutil.rmtree(out_dir / name, ignore_errors=True)

    weights = region_weights()
    results = {}        # (dataset, variable, period, mask) -> result
    entries, any_synth = [], False

    # Pass 1: anomalies, series files and raw trends.
    for ds in config.DATASETS.values():
        entry = None
        for var in ds.variables:
            path = reduce.cube_path(ds.id, var.id, zonal_dir)
            if not path.exists():
                if verbose:
                    print(f"  skip {ds.id}/{var.id}: {path.name} not found")
                continue
            cube = reduce.read_cube(path)
            any_synth |= cube.attrs.get("synthetic") == "true"
            time = cube["time"].values.astype("datetime64[M]")
            levels = np.round(cube["level"].values.astype(float), 4)    # 0.30000001 -> 0.3
            tidx = reduce.month_index(time)
            anom = stats.deseasonalize(cube["value"].values, reduce.month_of_year(time), var.relative)
            anom[:, levels < var.min_hpa, :] = np.nan          # heights this variable cannot be trusted at
            regional = {rid: region_series(anom, w) for rid, w in weights.items()}

            if entry is None:
                entry = {
                    "id": ds.id, "label": ds.label, "kind": ds.kind, "note": ds.note,
                    "source": f"{ds.short_name} v{ds.version}",
                    "levels_hpa": [float(x) for x in levels],
                    "alt_km": _r(config.approx_altitude_km(levels), 1),
                    "time": {"start": str(time[0]), "end": str(time[-1]), "n": int(time.size)},
                    "periods": [], "variables": [],
                }
            plain = var.units_plain or var.units
            entry["variables"].append({
                "id": var.id, "label": var.label, "explain": var.explain, "relative": var.relative,
                "units": var.units, "trend_units": f"{var.units} per decade",
                "units_plain": plain, "trend_units_plain": f"{plain} per ten years",
                "limit_note": var.limit_note,
            })

            digits = 2
            for j in range(anom.shape[2]):
                _dump(out_dir / "series" / ds.id / var.id / f"lat_{j:02d}.json",
                      {"anom": _r(anom[:, :, j].T, digits)})
            for rid, series in regional.items():
                _dump(out_dir / "series" / ds.id / var.id / f"region_{rid}.json",
                      {"anom": _r(series.T, digits)})

            seen = []
            for pid, period in config.PERIODS.items():
                span = _span(time, period)
                if span is None or any(_same_span(span, s) for s in seen):
                    continue                      # same years as a period already kept
                seen.append(span)
                # Jumps at documented data-source changes, judged on every month of the period.
                inside = _keep(time, period, {"exclude": []})
                first = int(np.flatnonzero(inside)[0])
                changes = [e for e in config.EVENTS if e["kind"] == "data_change" and ds.id in e.get("datasets", [])]
                starts = [int((np.datetime64(e["start"], "M") - time[0]).astype(int)) - first for e in changes]
                ends = [int((np.datetime64(e["end"], "M") - time[0]).astype(int)) - first for e in changes]
                live = [(a, b) for a, b in zip(starts, ends) if 0 < a < inside.sum()]
                steps = {}
                if live:
                    a_, b_ = zip(*live)
                    steps["grid"] = stats.jump_check(anom[inside], a_, b_)
                    for rid, series in regional.items():
                        steps[rid] = stats.jump_check(series[inside], a_, b_)
                decades = (span[1] - span[0] + 1) / 120.0
                if not any(p["id"] == pid for p in entry["periods"]):
                    entry["periods"].append({
                        "id": pid, "label": period["label"], "start": _month(span[0]), "end": _month(span[1]),
                        "years": round((span[1] - span[0] + 1) / 12.0, 1)})
                for mid, mask in config.MASKS.items():
                    keep = _keep(time, period, mask)
                    if keep.sum() < config.MIN_MONTHS:
                        continue
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", RuntimeWarning)
                        grid = _trend_many(anom[keep], tidx[keep])
                        regs = {rid: _trend_many(s[keep], tidx[keep]) for rid, s in regional.items()}
                    for key, g in [("grid", grid)] + list(regs.items()):
                        if key in steps:
                            g["step"] = steps[key][0]
                            g["jump"] = verdict.jumps(g["slope"], decades, *steps[key])
                    results[(ds.id, var.id, pid, mid)] = {
                        "grid": grid, "regions": regs, "levels": levels, "span": span}
                    if verbose:
                        print(f"  {ds.id}/{var.id} {pid}/{mid}: trends done  [{_time.time() - t0:.0f}s]")
        if entry:
            entries.append(entry)

    # Pass 2: verdicts. Needs every trend first, because it compares them.
    witness = {}        # (dataset, variable, period) -> (other dataset, its period)
    for (d, v, pid, mid), res in results.items():
        for (d2, v2, pid2, mid2), other in results.items():
            if d2 != d and v2 == v and mid2 == mid and _same_span(res["span"], other["span"]):
                witness[(d, v, pid)] = (d2, pid2)

    for (d, v, pid, mid), res in results.items():
        alt_mask = "none" if mid == config.EVENT_CHECK_MASK else config.EVENT_CHECK_MASK
        alt = results.get((d, v, pid, alt_mask))
        w = witness.get((d, v, pid))
        other = results.get((w[0], v, w[1], mid)) if w else None

        b = verdict.align_levels(other["grid"], other["levels"], res["levels"]) if other else None
        res["grid"]["verdict"], res["grid"]["reason"] = verdict.classify(
            res["grid"], alt["grid"] if alt else None, b)
        for rid, g in res["regions"].items():
            b = verdict.align_levels(other["regions"][rid], other["levels"], res["levels"]) if other else None
            g["verdict"], g["reason"] = verdict.classify(g, alt["regions"][rid] if alt else None, b)

    for (d, v, pid, mid), res in results.items():
        levels, grid = res["levels"], res["grid"]
        obj = _pack(grid)
        obj["span"] = {"start": _month(res["span"][0]), "end": _month(res["span"][1]),
                       "years": round((res["span"][1] - res["span"][0] + 1) / 12.0, 1)}
        obj["flip_hpa"] = _r([stats.flip_pressure(grid["slope"][:, j], levels)
                              for j in range(grid["slope"].shape[1])], 2)
        obj["regions"] = {}
        for rid, g in res["regions"].items():
            obj["regions"][rid] = _pack(g)
            obj["regions"][rid]["flip_hpa"] = _num(stats.flip_pressure(g["slope"], levels))
        _dump(out_dir / "trend" / d / v / f"{pid}__{mid}.json", obj)
        if mid == "none":
            _dump(out_dir / "pairs" / d / v / f"{pid}.json", find_pairs(res, levels))

    manifest = {
        "schema": SCHEMA,
        "generated_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
        "synthetic": bool(any_synth),
        "method": {"alpha": config.ALPHA, "fdr_q": config.FDR_Q, "slope": "Theil-Sen",
                   "test": "Mann-Kendall, lag-1 variance correction", "trend_per": "decade",
                   "event_check_mask": config.EVENT_CHECK_MASK,
                   "event_change_limit": config.EVENT_CHANGE_LIMIT, "jump_share": config.JUMP_SHARE},
        "lat_centers": config.LAT_CENTERS.tolist(),
        "lat_step": config.LAT_STEP,
        "regions": config.REGIONS,
        "verdicts": config.VERDICTS,
        "reasons": config.REASONS,
        "masks": [{"id": k, **m} for k, m in config.MASKS.items()],
        "events": config.EVENTS,
        "datasets": entries,
        "witness": [{"dataset": d, "variable": v, "period": p, "with_dataset": w[0], "with_period": w[1]}
                    for (d, v, p), w in sorted(witness.items())],
    }
    _dump(out_dir / "manifest.json", manifest)
    if verbose:
        print(f"wrote {out_dir}  ({_time.time() - t0:.0f}s, synthetic={manifest['synthetic']})")
    return manifest
