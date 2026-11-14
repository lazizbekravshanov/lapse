"""Zonal cubes in, website JSON out. See docs/data-contract.md for the format."""

from __future__ import annotations

import json
import time as _time
from pathlib import Path

import numpy as np

from . import config, reduce, stats


def _r(a, digits=4):
    """Round to JSON-friendly lists; NaN becomes null."""
    a = np.asarray(a, dtype=float)
    out = np.round(a, digits).astype(object)
    out[~np.isfinite(a)] = None
    return out.tolist()


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


def trend_grid(anom, tidx, keep, levels) -> dict:
    """anom[time, level, lat] -> dict of [level][lat] arrays plus summaries."""
    _, nl, nb = anom.shape
    names = ("slope", "lo", "hi", "p", "r1", "n")
    grid = {k: np.full((nl, nb), np.nan) for k in names}
    a, t = anom[keep], tidx[keep]
    for i in range(nl):
        for j in range(nb):
            res = stats.trend(a[:, i, j], t, alpha=config.ALPHA, min_n=config.MIN_MONTHS)
            for k in names:
                grid[k][i, j] = res[k]
    grid["q"] = stats.bh_qvalues(grid["p"])
    grid["sig"] = (grid["q"] <= config.FDR_Q).astype(float)
    grid["flip_hpa"] = np.array(
        [stats.flip_pressure(grid["slope"][:, j], levels) for j in range(nb)]
    )

    # Whole-globe profile: cos(lat)-weighted mean of the bands, then the same test.
    w = np.cos(np.deg2rad(config.LAT_CENTERS))[None, None, :]
    ww = np.where(np.isfinite(a), w, 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        gmean = np.nansum(a * ww, axis=2) / ww.sum(axis=2)
    glob = {k: np.full(nl, np.nan) for k in names}
    for i in range(nl):
        res = stats.trend(gmean[:, i], t, alpha=config.ALPHA, min_n=config.MIN_MONTHS)
        for k in names:
            glob[k][i] = res[k]
    glob["q"] = stats.bh_qvalues(glob["p"])
    glob["sig"] = (glob["q"] <= config.FDR_Q).astype(float)
    glob["flip_hpa"] = stats.flip_pressure(glob["slope"], levels)
    grid["global"] = glob
    return grid


def _trend_json(grid) -> dict:
    def pack(g):
        return {
            "slope": _r(g["slope"]), "lo": _r(g["lo"]), "hi": _r(g["hi"]),
            "p": _r(g["p"], 5), "q": _r(g["q"], 5),
            "sig": _r(g["sig"], 0), "r1": _r(g["r1"], 2), "n": _r(g["n"], 0),
        }
    out = pack(grid)
    out["flip_hpa"] = _r(grid["flip_hpa"], 2)
    out["global"] = pack(grid["global"])
    fl = grid["global"]["flip_hpa"]
    out["global"]["flip_hpa"] = None if not np.isfinite(fl) else round(float(fl), 2)
    return out


def agreement(a: dict, b: dict, levels_a, levels_b) -> dict:
    """Compare two trend grids on the levels they share.

    status per cell: 0 neither significant, 1 both significant and same sign,
    2 only one significant, 3 both significant with opposite signs (conflict).
    """
    la = [float(x) for x in levels_a]
    lb = [float(x) for x in levels_b]
    common = [x for x in la if x in lb]
    ia = [la.index(x) for x in common]
    ib = [lb.index(x) for x in common]
    sa, sb = a["slope"][ia], b["slope"][ib]
    ga, gb = a["sig"][ia] > 0, b["sig"][ib] > 0
    same = np.sign(sa) == np.sign(sb)
    status = np.zeros(sa.shape)
    status[ga ^ gb] = 2
    status[ga & gb & same] = 1
    status[ga & gb & ~same] = 3
    status[~(np.isfinite(sa) & np.isfinite(sb))] = np.nan
    overlap = ((a["lo"][ia] <= b["hi"][ib]) & (b["lo"][ib] <= a["hi"][ia])).astype(float)
    return {"levels_hpa": common, "status": _r(status, 0), "ci_overlap": _r(overlap, 0),
            "diff": _r(sa - sb)}


def run(zonal_dir: Path | None = None, out_dir: Path | None = None, verbose: bool = True) -> dict:
    """Compute every trend variant and write the website data. Returns the manifest."""
    out_dir = out_dir or config.WEB_DATA_DIR
    t0 = _time.time()
    manifest = {
        "schema": 1,
        "generated_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
        "synthetic": False,
        "method": {"alpha": config.ALPHA, "fdr_q": config.FDR_Q,
                   "slope": "Theil-Sen", "test": "Mann-Kendall, lag-1 variance correction",
                   "trend_per": "decade"},
        "lat_centers": config.LAT_CENTERS.tolist(),
        "lat_step": config.LAT_STEP,
        "periods": [{"id": k, **v} for k, v in config.PERIODS.items()],
        "masks": [{"id": k, **v} for k, v in config.MASKS.items()],
        "events": config.EVENTS,
        "datasets": [],
        "agreement": [],
    }
    grids = {}   # (dataset, variable, period, mask) -> grid
    any_synth = False

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
            levels = cube["level"].values
            tidx = reduce.month_index(time)
            anom = stats.deseasonalize(cube["value"].values, reduce.month_of_year(time), var.relative)

            if entry is None:
                entry = {
                    "id": ds.id, "label": ds.label, "kind": ds.kind, "note": ds.note,
                    "source": f"{ds.short_name} v{ds.version}",
                    "levels_hpa": [float(x) for x in levels],
                    "alt_km": _r(config.approx_altitude_km(levels), 1),
                    "time": {"start": str(time[0]), "end": str(time[-1]), "n": int(time.size)},
                    "variables": [],
                }
            unit = var.units
            entry["variables"].append({
                "id": var.id, "label": var.label, "units": unit,
                "trend_units": f"{unit} per decade", "explain": var.explain,
                "relative": var.relative,
            })

            for pid, period in config.PERIODS.items():
                for mid, mask in config.MASKS.items():
                    keep = _keep(time, period, mask)
                    if keep.sum() < config.MIN_MONTHS:
                        continue
                    grid = trend_grid(anom, tidx, keep, levels)
                    grids[(ds.id, var.id, pid, mid)] = (grid, levels)
                    _dump(out_dir / "trend" / ds.id / var.id / f"{pid}__{mid}.json", _trend_json(grid))
                    if verbose:
                        print(f"  {ds.id}/{var.id} {pid}/{mid}: {int(np.nansum(grid['sig']))} "
                              f"significant cells  [{_time.time() - t0:.0f}s]")

            # Anomaly series for the click-through charts, one file per latitude band.
            digits = 2
            for j in range(anom.shape[2]):
                _dump(out_dir / "series" / ds.id / var.id / f"lat_{j:02d}.json",
                      {"anom": _r(anom[:, :, j].T, digits)})
            w = np.cos(np.deg2rad(config.LAT_CENTERS))[None, None, :]
            ww = np.where(np.isfinite(anom), w, 0.0)
            with np.errstate(invalid="ignore", divide="ignore"):
                gmean = np.nansum(anom * ww, axis=2) / ww.sum(axis=2)
            _dump(out_dir / "series" / ds.id / var.id / "global.json", {"anom": _r(gmean.T, digits)})

        if entry:
            manifest["datasets"].append(entry)

    # Two-witness check: same variable in two datasets, same period and mask.
    ids = [d["id"] for d in manifest["datasets"]]
    for x in range(len(ids)):
        for y in range(x + 1, len(ids)):
            a_id, b_id = ids[x], ids[y]
            for (d, v, pid, mid), (ga, la) in list(grids.items()):
                if d != a_id or pid != "airs_era" or (b_id, v, pid, mid) not in grids:
                    continue
                gb, lb = grids[(b_id, v, pid, mid)]
                rel = f"agreement/{v}/{a_id}__{b_id}__{mid}.json"
                _dump(out_dir / rel, agreement(ga, gb, la, lb))
                manifest["agreement"].append(
                    {"variable": v, "a": a_id, "b": b_id, "period": pid, "mask": mid, "file": rel})

    manifest["synthetic"] = bool(any_synth)
    _dump(out_dir / "manifest.json", manifest)
    if verbose:
        print(f"wrote {out_dir}  ({_time.time() - t0:.0f}s, synthetic={manifest['synthetic']})")
    return manifest
