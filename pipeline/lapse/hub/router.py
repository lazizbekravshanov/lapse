"""The router: one request shape in, one answer shape out.

It works only from the published files in web/data, exactly as the website does,
so anything the site can show can also be asked from a script:

    from lapse.hub import router
    router.answer({"what": "t", "where": "arctic", "km": 32, "method": "classic"})

Every field may be left out or set to "auto". The router then picks the default
tool and says which one it picked.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .. import config


def _load(data_dir: Path, name: str) -> dict:
    return json.loads((data_dir / name).read_text())


def resolve(request: dict, manifest: dict, catalog: dict) -> dict:
    """Fill in every choice the request left open. Raises ValueError on a bad choice."""
    req = {k: v for k, v in request.items() if v not in (None, "", "auto")}
    datasets = manifest["datasets"]

    what = str(req.get("what", "t")).lower()
    variables = {v["id"]: v for d in datasets for v in d["variables"]}
    by_label = {v["label"].lower(): v["id"] for v in variables.values()}
    variable = what if what in variables else by_label.get(what)
    if variable is None:
        raise ValueError(f"Unknown measure {what!r}. Choose from: {', '.join(variables)}")

    auto = manifest["auto"][variable]                 # written by the export (registry.auto_choices)
    ds_id = req.get("dataset", auto["dataset"])
    if ds_id not in auto["periods"]:
        raise ValueError(f"{ds_id!r} does not measure {variable}. Choose from: {', '.join(auto['periods'])}")
    ds = next(d for d in datasets if d["id"] == ds_id)
    periods = [p["id"] for p in ds["periods"]]
    period = req.get("period", auto["periods"][ds_id])
    if period not in periods:
        raise ValueError(f"Unknown years {period!r}. Choose from: {', '.join(periods)}")

    methods = [m["id"] for m in catalog["methods"]]
    method = req.get("method", catalog["defaults"]["method"])
    if method not in methods:
        raise ValueError(f"Unknown method {method!r}. Choose from: {', '.join(methods)}")
    mask = req.get("mask", catalog["defaults"]["mask"])
    if mask not in [m["id"] for m in manifest["masks"]]:
        raise ValueError(f"Unknown months setting {mask!r}.")

    where = req.get("where", "global")
    regions = [r["id"] for r in manifest["regions"]]
    if where in regions:
        place = {"region": where}
    else:
        try:
            lat = float(str(where).replace("lat:", ""))
        except ValueError:
            raise ValueError(f"Unknown place {where!r}. Use a latitude or one of: {', '.join(regions)}") from None
        place = {"lat": int(np.argmin(np.abs(np.array(manifest["lat_centers"]) - lat)))}

    levels = np.array(ds["levels_hpa"])
    hpa = req.get("hpa")
    if hpa is None and "km" in req:
        hpa = 1000.0 * np.exp(-float(req["km"]) / 7.0)        # same rough conversion as the labels
    level = None if hpa is None else int(np.argmin(np.abs(np.log(levels / float(hpa)))))

    return {"dataset": ds["id"], "variable": variable, "period": period, "mask": mask, "method": method,
            "place": place, "level": level,
            "chosen_by_auto": sorted(k for k in ("dataset", "period", "method") if k not in req)}


def strongest_level(col: dict, levels: list) -> int:
    """The height to talk about when none was asked for: the strongest change that
    earned a "Likely" or "Clear" label, or the middle of the weather layer if none did."""
    ranked = [k for k in range(len(levels)) if col["verdict"][k] in (1, 2)]
    if ranked:
        return max(ranked, key=lambda k: abs(col["slope"][k]))
    return int(np.argmin(np.abs(np.array(levels) - 500)))


def column(trend: dict, place: dict) -> dict:
    """One column of air out of a trend file: a region, or one latitude ring."""
    if "region" in place:
        return trend["regions"][place["region"]]
    j = place["lat"]
    col = {k: [row[j] for row in trend[k]] for k in ("slope", "lo", "hi", "sig", "verdict", "reason", "agree")}
    if "step" in trend:
        col["step"] = [row[j] for row in trend["step"]]
    col["flip_hpa"] = trend["flip_hpa"][j]
    return col


def place_phrase(place: dict, manifest: dict) -> str:
    if "region" in place:
        return next(r["phrase"] for r in manifest["regions"] if r["id"] == place["region"])
    lat = manifest["lat_centers"][place["lat"]]
    return f"In the ring around the Earth at {abs(lat)}°{'N' if lat > 0 else 'S'}"


def route(resolved: dict, catalog: dict) -> str:
    """The file that holds the answer to a resolved request."""
    return catalog["routes"]["trend"].format(**resolved)


def answer(request: dict, data_dir: Path | None = None) -> dict:
    """Resolve, read the published result, and return it with a plain sentence."""
    data_dir = data_dir or config.WEB_DATA_DIR
    manifest, catalog = _load(data_dir, "manifest.json"), _load(data_dir, "catalog.json")
    res = resolve(request, manifest, catalog)
    path = route(res, catalog)
    trend = _load(data_dir, path)
    ds = next(d for d in manifest["datasets"] if d["id"] == res["dataset"])
    var = next(v for v in ds["variables"] if v["id"] == res["variable"])
    levels = ds["levels_hpa"]

    col = column(trend, res["place"])
    where = place_phrase(res["place"], manifest)
    i = res["level"]
    if i is None:                                   # no height asked: the strongest labelled change
        i = strongest_level(col, levels)
    label = {v["code"]: v["label"] for v in manifest["verdicts"]}
    reason = {r["code"]: r["text"] for r in manifest["reasons"]}
    km = round(float(config.approx_altitude_km(levels[i])))
    sound = len(catalog["sound_methods"])
    out = {
        "request": res, "route": path, "where": where,
        "height": {"hpa": levels[i], "km": km},
        "units": var["trend_units_plain"], "years": trend["span"],
    }
    if col["slope"][i] is None:
        out.update(rate=None, sentence=f"{where}, about {km} km up: no measurements here.")
        return out
    v = int(col["verdict"][i])
    out.update(
        rate=col["slope"][i], range=[col["lo"][i], col["hi"][i]],
        label=label[v], reason=reason[int(col["reason"][i])],
        methods_agree=f"{int(col['agree'][i])} of {sound}",
        sentence=(f"{where}, about {km} km up: {label[v]}. {col['slope'][i]:+.2f} {var['trend_units_plain']}, "
                  f"very likely between {col['lo'][i]:+.2f} and {col['hi'][i]:+.2f}. "
                  f"{int(col['agree'][i])} of {sound} sound methods find a change in this direction. "
                  f"{reason[int(col['reason'][i])]}"),
    )
    return out
