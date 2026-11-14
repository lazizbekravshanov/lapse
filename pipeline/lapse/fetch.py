"""Download real NASA data and shrink it to zonal cubes.

How it works
1. Ask NASA's catalog (CMR, no login) for the monthly files and their OPeNDAP links.
2. For each month, ask the OPeNDAP server for only the variables we need, and only
   every Nth grid point. The answer is a small netCDF file held in memory.
3. Reduce it to [level, latitude band] and cache it. A crash loses nothing; rerun
   the same command and it continues where it stopped.

Login: needs a free Earthdata account. Either set EARTHDATA_TOKEN to a token from
https://urs.earthdata.nasa.gov (Generate Token), or have `earthaccess` installed
and it will ask once and remember.

STATUS: catalog search and the request format are tested. The authenticated
download itself has not been run yet; start with a three-month test.
"""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
import warnings
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from . import config, reduce

CMR = "https://cmr.earthdata.nasa.gov/search"


# --- catalog (no login) -------------------------------------------------------

def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def collection_id(ds: config.Dataset) -> str:
    q = urllib.parse.urlencode({"short_name": ds.short_name, "version": ds.version})
    items = _get_json(f"{CMR}/collections.umm_json?{q}")["items"]
    if not items:
        raise SystemExit(f"No NASA collection found for {ds.short_name} v{ds.version}")
    return items[0]["meta"]["concept-id"]


def parse_granule(ds: config.Dataset, item: dict):
    """One catalog entry -> (month "YYYY-MM", OPeNDAP URL), or None."""
    umm = item["umm"]
    m = re.search(ds.month_regex, umm.get("GranuleUR", ""))
    if not m:
        return None
    urls = umm.get("RelatedUrls", [])
    dap = [u["URL"] for u in urls if u.get("Subtype") == "OPENDAP DATA"] or \
          [u["URL"] for u in urls if "opendap" in u.get("URL", "")]
    return (f"{m.group(1)}-{m.group(2)}", dap[0]) if dap else None


def granules(ds: config.Dataset, start: str, end: str) -> dict:
    """{month: OPeNDAP URL} for start..end inclusive ("YYYY-MM")."""
    cid = collection_id(ds)
    y1, m1 = map(int, end.split("-"))
    temporal = f"{start}-01T00:00:00Z,{y1:04d}-{m1:02d}-28T23:59:59Z"
    out, page = {}, 1
    while True:
        q = urllib.parse.urlencode({"collection_concept_id": cid, "temporal": temporal,
                                    "page_size": 2000, "page_num": page, "sort_key": "start_date"})
        items = _get_json(f"{CMR}/granules.umm_json?{q}")["items"]
        for it in items:
            hit = parse_granule(ds, it)
            if hit and start <= hit[0] <= end:
                out[hit[0]] = hit[1]
        if len(items) < 2000:
            return dict(sorted(out.items()))
        page += 1


# --- login --------------------------------------------------------------------

def session():
    import requests

    token = os.environ.get("EARTHDATA_TOKEN")
    if token:
        s = requests.Session()
        s.headers["Authorization"] = f"Bearer {token}"
        return s
    try:
        import earthaccess
    except ImportError:
        raise SystemExit("Set EARTHDATA_TOKEN, or run: pip install -e 'pipeline[nasa]'")
    earthaccess.login(persist=True)
    return earthaccess.get_requests_https_session()


# --- requests -----------------------------------------------------------------

def _rng(n: int, step: int = 1) -> str:
    return f"[0:{step}:{n - 1}]"


def constraint(ds: config.Dataset, variables, stride: int) -> str:
    """DAP4 constraint: the chosen variables on a thinned grid, plus coordinates."""
    nlev, nlat, nlon = ds.shape
    lead = "[0:1:0]" if ds.has_time else ""
    parts = []
    for var in variables:
        for path in var.source_names:
            parts.append(f"{path}{lead}{_rng(nlev)}{_rng(nlat, stride)}{_rng(nlon, stride)}")
    parts.append(ds.lat_path + _rng(nlat, stride) + ("[0:1:0]" if ds.lat_is_2d else ""))
    if ds.lev_path:
        parts.append(ds.lev_path)
    return ";".join(parts)


def _find(nc, path: str):
    """Variable at a group path like /a/b/NAME; falls back to a search by NAME."""
    parts = [p for p in path.split("/") if p]
    node = nc
    try:
        for g in parts[:-1]:
            node = node.groups[g]
        return node.variables[parts[-1]]
    except KeyError:
        stack = [nc]
        while stack:
            g = stack.pop()
            if parts[-1] in g.variables:
                return g.variables[parts[-1]]
            stack.extend(g.groups.values())
    raise KeyError(f"{path} not in the server's answer")


def _array(var) -> np.ndarray:
    return reduce.clean(np.ma.filled(np.ma.masked_invalid(var[:]).astype(float), np.nan))


def download(sess, url: str, ce: str) -> bytes:
    r = sess.get(url + ".dap.nc4", params={"dap4.ce": ce}, timeout=600)
    if r.status_code in (401, 403):
        raise PermissionError("Earthdata login was refused. Check your token, and approve the "
                              "'NASA GESDISC DATA ARCHIVE' application in your Earthdata profile.")
    r.raise_for_status()
    if r.content[:1] == b"<":
        raise PermissionError("Got a web page instead of data. This usually means the login did not go through.")
    return r.content


def reduce_month(blob: bytes, ds: config.Dataset, variables) -> dict:
    """Server answer -> {variable id: [level, band]} plus "levels"."""
    import netCDF4

    out = {}
    with netCDF4.Dataset("inmemory.nc", memory=blob) as nc:
        nc.set_auto_maskandscale(True)
        lat = np.squeeze(_array(_find(nc, ds.lat_path)))
        levels = np.squeeze(_array(_find(nc, ds.lev_path))) if ds.lev_path else np.array(ds.levels, float)
        if levels.size != ds.shape[0]:
            raise ValueError(f"expected {ds.shape[0]} levels, got {levels.size}")
        for var in variables:
            fields = [np.squeeze(_array(_find(nc, p))) * var.scale for p in var.source_names]
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)      # all-missing cells are fine
                field = np.nanmean(np.stack(fields), axis=0)        # [level, lat, lon]
            out[var.id] = reduce.zonal_bands(field, lat)
    out["levels"] = levels
    return out


def _one(sess, ds, month, url, cache, stride):
    todo = [v for v in ds.variables if not (cache / f"{v.id}_{month}.npz").exists()]
    if not todo:
        return month, "cached"
    try:
        res = reduce_month(download(sess, url, constraint(ds, todo, stride)), ds, todo)
        for var in todo:
            np.savez_compressed(cache / f"{var.id}_{month}.npz", bands=res[var.id], levels=res["levels"])
        return month, "ok"
    except Exception as exc:                       # keep going; a rerun fills the gaps
        return month, f"FAILED: {exc}"


def fetch(dataset_id: str, start: str | None = None, end: str | None = None,
          stride: int | None = None, workers: int = 4,
          cache_dir: Path | None = None, zonal_dir: Path | None = None) -> list:
    """Download start..end (YYYY-MM), cache each month, then build the cubes."""
    ds = config.DATASETS[dataset_id]
    start = start or ds.start
    end = end or str(np.datetime64("today", "M") - np.timedelta64(2, "M"))
    stride = stride or ds.stride
    cache = (cache_dir or config.CACHE_DIR) / ds.id
    cache.mkdir(parents=True, exist_ok=True)

    found = granules(ds, start, end)
    print(f"{ds.id}: {len(found)} monthly files from {start} to {end}, stride {stride}, {workers} at a time")
    sess = session()
    failed = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = [pool.submit(_one, sess, ds, m, u, cache, stride) for m, u in found.items()]
        for n, job in enumerate(jobs, 1):
            month, status = job.result()
            failed += status.startswith("FAILED")
            if status != "cached":
                print(f"  [{n}/{len(jobs)}] {month} {status}")
            if failed == 3 and n == 3:
                print("  The first three months all failed. Stopping; fix the cause and rerun.")
                pool.shutdown(cancel_futures=True)
                break
    if failed:
        print(f"  {failed} month(s) failed. Run the same command again to retry them.")
    return assemble(dataset_id, cache_dir, zonal_dir)


def inspect(dataset_id: str) -> None:
    """Print one real file's groups, variables and sizes, to check config.py."""
    ds = config.DATASETS[dataset_id]
    month, url = next(iter(granules(ds, "2024-01", "2024-01").items()))
    print(f"{ds.short_name} {month}\n{url}\n")
    r = session().get(url + ".dmr", timeout=120)
    r.raise_for_status()
    wanted = {p for v in ds.variables for p in v.source_names} | {ds.lat_path, ds.lev_path}

    def walk(node, prefix):
        for child in node:
            tag = child.tag.split("}")[-1]
            name = child.get("name")
            if tag == "Group":
                walk(child, f"{prefix}/{name}")
            elif tag in ("Float32", "Float64", "Int16", "Int32", "Int8", "UInt8", "UInt16") and name:
                dims = [d.get("name") or d.get("size") for d in child if d.tag.endswith("Dim")]
                path = f"{prefix}/{name}"
                print(("* " if path in wanted else "  ") + path, dims)
            elif tag == "Dimension":
                print(f"  dim {prefix}/{name} = {child.get('size')}")

    walk(ET.fromstring(r.content), "")
    print("\n* = used by config.py. If a starred line is missing above, the path in config.py is wrong.")


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
        levels = np.load(files[0])["levels"]
        cube = np.full((time.size, levels.size, len(config.LAT_CENTERS)), np.nan)
        for f, m in zip(files, months):
            cube[int((m - time[0]).astype(int))] = np.load(f)["bands"]
        path = reduce.cube_path(ds.id, var.id, zonal_dir)
        reduce.write_cube(path, cube, time, levels,
                          {"synthetic": "false", "source": f"{ds.short_name} v{ds.version}"})
        print(f"  wrote {path.name}: {time.size} months, {levels.size} levels")
        written.append(path)
    return written
