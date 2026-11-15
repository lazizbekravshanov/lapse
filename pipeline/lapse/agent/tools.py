"""The only things the agent can do.

Every tool reads the published files in web/data (the same files the website
reads) and nothing else: no network, no file writes, no code execution. The
numbers in those files come from NASA's AIRS and MERRA-2 records.

Each tool returns plain data plus:
  summary  one or two sentences in everyday words, built here, not by a model
  source   the NASA product and the file the numbers came from

To add a tool: write a function, add one entry to TOOLS. The harness, the
command line and the MCP server all pick it up from there.
"""

from __future__ import annotations

import json
import os
import re
from functools import cached_property
from pathlib import Path

import numpy as np

from .. import config
from ..hub import router

CLEAR, LIKELY, NOT_PROVEN, DISPUTED = 2, 1, 0, 3


class Site:
    """A read-only view of the published files."""

    def __init__(self, data_dir: Path | None = None, content_dir: Path | None = None):
        self.data_dir = Path(data_dir or os.environ.get("LAPSE_DATA_DIR") or config.WEB_DATA_DIR)
        content = self.data_dir.parent / "content"
        self.content_dir = Path(content_dir or (content if content.exists() else config.ROOT / "web" / "content"))
        self._files: dict = {}

    def load(self, name: str) -> dict:
        if name not in self._files:
            self._files[name] = json.loads((self.data_dir / name).read_text())
        return self._files[name]

    @cached_property
    def manifest(self) -> dict:
        return self.load("manifest.json")

    @cached_property
    def catalog(self) -> dict:
        return self.load("catalog.json")

    @cached_property
    def glossary(self) -> dict:
        path = self.content_dir / "glossary.json"
        return json.loads(path.read_text()) if path.exists() else {"terms": [], "layers": [], "landmarks": []}

    def dataset(self, ds_id: str) -> dict:
        return next(d for d in self.manifest["datasets"] if d["id"] == ds_id)

    def variable(self, ds_id: str, var_id: str) -> dict:
        return next(v for v in self.dataset(ds_id)["variables"] if v["id"] == var_id)

    def label(self, code) -> str:
        return next(v["label"] for v in self.manifest["verdicts"] if v["code"] == int(code))

    def reason(self, code) -> str:
        return next(r["text"] for r in self.manifest["reasons"] if r["code"] == int(code))


# --- shared pieces --------------------------------------------------------------

def _request(args: dict) -> dict:
    """Tool arguments use everyday names; the hub router uses its own."""
    return {"what": args.get("what"), "where": args.get("where"), "km": args.get("km"), "hpa": args.get("hpa"),
            "dataset": args.get("data"), "method": args.get("method"), "period": args.get("years"),
            "mask": args.get("months")}


def _open(site: Site, args: dict, **override) -> dict:
    """Resolve the request (filling in Auto choices) and open the file that answers it."""
    res = router.resolve({**_request(args), **override}, site.manifest, site.catalog)
    path = router.route(res, site.catalog)
    trend = site.load(path)
    ds = site.dataset(res["dataset"])
    return {"res": res, "path": path, "trend": trend, "ds": ds, "var": site.variable(res["dataset"], res["variable"]),
            "col": router.column(trend, res["place"]), "levels": ds["levels_hpa"],
            "where": router.place_phrase(res["place"], site.manifest)}


def _km(hpa: float) -> int:
    return round(float(config.approx_altitude_km(hpa)))


def _layer(site: Site, km: float) -> str:
    for layer in site.glossary["layers"]:
        if layer["from_km"] <= km < layer["to_km"]:
            return f"{layer['plain'].lower()} ({layer['science']}, {layer['from_km']} to {layer['to_km']} km)"
    return ""


def _words(var: dict) -> dict:
    if var["id"] == "t":
        return {"subject": "the air", "up": "warming", "down": "cooling"}
    return {"subject": var["label"].lower(), "up": "rising", "down": "falling"}


def _direction(var: dict, rate) -> str:
    return "" if rate is None else _words(var)["up" if rate > 0 else "down"]


def _tools_used(site: Site, o: dict) -> dict:
    res = o["res"]
    method = next(m for m in site.catalog["methods"] if m["id"] == res["method"])
    months = next(m for m in site.manifest["masks"] if m["id"] == res["mask"])
    return {"data": o["ds"]["label"], "method": method["label"], "months": months["label"],
            "years": f"{o['trend']['span']['start']} to {o['trend']['span']['end']}",
            "chosen_by_auto": res["chosen_by_auto"]}


def _source(o: dict) -> dict:
    return {"product": o["ds"]["source"], "file": f"web/data/{o['path']}"}


def _reading(site: Site, o: dict, i: int, brief: bool = False) -> dict:
    """One height in one column: the rate, its range and its label."""
    col = o["col"]
    hpa = o["levels"][int(i)]
    out = {"height_km": _km(hpa), "pressure_hpa": hpa}
    if col["slope"][i] is None or col["verdict"][i] is None:
        out.update(rate=None, label="No measurements here")
        return out
    out.update(rate=col["slope"][i], range=[col["lo"][i], col["hi"][i]], label=site.label(col["verdict"][i]))
    if not brief:
        out.update(direction=_direction(o["var"], col["slope"][i]), why=site.reason(col["reason"][i]))
    return out


def _level(o: dict) -> int:
    return o["res"]["level"] if o["res"]["level"] is not None else router.strongest_level(o["col"], o["levels"])


def _span(o: dict) -> str:
    span = o["trend"]["span"]
    return f"{o['ds']['label']}, {span['start'][:4]} to {span['end'][:4]}"


def _rate(x: float) -> str:
    return f"{x:+.2f}"


def _near(km: int) -> str:
    return "near the ground" if km < 1 else f"near {km} km"


def _head(o: dict, i: int) -> str:
    """Place and height. The pressure is given too, because two nearby heights can round to the same km."""
    hpa = o["levels"][i]
    km = _km(hpa)
    return f"{o['where']}, " + ("near the ground" if km < 1 else f"about {km} km up") + f" ({hpa:g} hPa)"


# --- the tools ------------------------------------------------------------------

def list_options(site: Site, args: dict) -> dict:
    m, c = site.manifest, site.catalog
    measures = {}
    for d in m["datasets"]:
        for v in d["variables"]:
            measures.setdefault(v["id"], {"id": v["id"], "label": v["label"], "explain": v["explain"],
                                          "units": v["trend_units_plain"], "limit": v["limit_note"],
                                          "measured_by": []})["measured_by"].append(d["id"])
    return {
        "measures": list(measures.values()),
        "data": [{"id": d["id"], "label": d["label"], "kind": d["kind"], "note": d["note"], "product": d["source"],
                  "years": f"{d['time']['start']} to {d['time']['end']}",
                  "heights_km": f"{_km(max(d['levels_hpa']))} to {_km(min(d['levels_hpa']))}",
                  "number_of_heights": len(d["levels_hpa"])} for d in m["datasets"]],
        "places": {"regions": [{"id": r["id"], "label": r["label"]} for r in m["regions"]],
                   "latitude": "Or any latitude in degrees, north positive. Each one is a ring around the Earth "
                               f"{m['lat_step']:g} degrees wide."},
        "methods": [{"id": x["id"], "label": x["label"], "plain": x["plain"],
                     "role": "recommended" if x["recommended"] else "sound" if x["sound"] else "comparison only",
                     "caution": x["caution"]} for x in c["methods"]],
        "months": [{"id": x["id"], "label": x["label"]} for x in m["masks"]],
        "labels": [{"label": v["label"], "meaning": v["meaning"]} for v in m["verdicts"]],
        "checks_always_on": [{"label": x["label"], "plain": x["plain"]} for x in c["checks"]],
        "auto": c["auto"],
        "landmarks": site.glossary["landmarks"],
        "summary": "You can ask about " + ", ".join(v["label"].lower() for v in measures.values())
                   + ", for the whole globe, a region or a latitude, at any height from the ground to about "
                   + f"{max(_km(min(d['levels_hpa'])) for d in m['datasets'])} km. "
                   + "Anything you leave out is chosen for you and reported back.",
        "source": {"product": ", ".join(d["source"] for d in m["datasets"]), "file": "web/data/manifest.json"},
    }


def trend_at(site: Site, args: dict) -> dict:
    o = _open(site, args)
    i = _level(o)
    r = _reading(site, o, i)
    km, var, span = r["height_km"], o["var"], o["trend"]["span"]
    out = {"measure": var["label"], "place": o["where"], "layer": _layer(site, km), **r,
           "units": var["trend_units_plain"], "tools_used": _tools_used(site, o), "source": _source(o)}
    if o["res"]["level"] is None:
        out["height_chosen_because"] = "No height was asked for, so this is the strongest change that earned a label."
    if r["rate"] is None:
        out["summary"] = f"{_head(o, i)}: no measurements here. " + (
            var["limit_note"] or "This height may be below the ground at this place.") + f" Data: {_span(o)}."
        return out
    agree, sound = int(o["col"]["agree"][i]), len(site.catalog["sound_methods"])
    total = round(r["rate"] * span["years"] / 10.0, 1)
    out.update(methods_agree=f"{agree} of {sound}",
               range_meaning="The true rate is very likely (95% confidence) inside the range.",
               total_change={"value": total, "units": var["units_plain"], "over_years": span["years"]})
    rng = f"very likely between {_rate(r['range'][0])} and {_rate(r['range'][1])}"
    if o["col"]["verdict"][i] == NOT_PROVEN:
        out["summary"] = (f"{_head(o, i)}: {r['label']}. The best estimate is {_rate(r['rate'])} {out['units']}, but the "
                          f"true value is {rng}, so a real change cannot be told apart from chance.")
    else:
        subject = _words(var)["subject"]
        out["summary"] = (f"{_head(o, i)}: {r['label']}. {subject[0].upper() + subject[1:]} is {r['direction']}: "
                          f"{_rate(r['rate'])} {out['units']}, {rng}. Over the {span['years']} years of data that adds up to about "
                          f"{total:+.1f} {var['units_plain']}. {agree} of {sound} sound methods find a change in this "
                          f"direction. {r['why']}")
    out["summary"] += f" Data: {_span(o)}."
    return out


def profile(site: Site, args: dict) -> dict:
    o = _open(site, {**args, "km": None, "hpa": None})
    col, levels, var, w = o["col"], o["levels"], o["var"], _words(o["var"])
    rows = [_reading(site, o, int(i), brief=True) for i in np.argsort(-np.array(levels))]      # ground first
    rows = [r for r in rows if r["rate"] is not None]
    idx = [i for i in range(len(levels)) if col["slope"][i] is not None and col["verdict"][i] is not None]
    count = {site.label(c): sum(1 for i in idx if col["verdict"][i] == c) for c in (CLEAR, LIKELY, NOT_PROVEN, DISPUTED)}
    good = [i for i in idx if col["verdict"][i] in (CLEAR, LIKELY)]
    up, down = [i for i in good if col["slope"][i] > 0], [i for i in good if col["slope"][i] < 0]

    def strongest(group):
        clear = [i for i in group if col["verdict"][i] == CLEAR]
        return max(clear or group, key=lambda i: abs(col["slope"][i]))

    out = {"measure": var["label"], "place": o["where"], "units": var["trend_units_plain"], "heights": rows,
           "heights_checked": len(idx), "labels_count": count,
           "tools_used": _tools_used(site, o), "source": _source(o)}
    tally = (f"Of {len(idx)} heights checked: " + ", ".join(f'{n} "{label}"' for label, n in count.items()) + ".")
    if not idx:
        out["summary"] = f"{o['where']}, there are no measurements for this."
        return out
    if not good:
        out["summary"] = (f"{o['where']}, no height shows a change that can be called likely or clear. "
                          f'"{site.label(NOT_PROVEN)}" does not mean nothing changed. {tally}')
        return out
    parts = []
    if up and down:
        mean = lambda g: float(np.mean([_km(levels[i]) for i in g]))            # noqa: E731
        low, high = (w["up"], w["down"]) if mean(up) < mean(down) else (w["down"], w["up"])
        parts.append(f"{o['where']}, {w['subject']} is {low} low down and {high} higher up.")
    else:
        parts.append(f"{o['where']}, {w['subject']} is {w['up'] if up else w['down']}, and no height shows a likely "
                     "change the other way.")
    for group, word, key in ((up, w["up"], "strongest_" + w["up"]), (down, w["down"], "strongest_" + w["down"])):
        if group:
            i = strongest(group)
            out[key] = _reading(site, o, i)
            parts.append(f"Strongest {word}: {_rate(col['slope'][i])} {out['units']} {_near(_km(levels[i]))} "
                         f'("{site.label(col["verdict"][i])}").')
    if up and down and col.get("flip_hpa") is not None:
        out["direction_flips_at_km"] = _km(col["flip_hpa"])
        parts.append(f"The direction flips at about {_km(col['flip_hpa'])} km.")
    if var["limit_note"]:
        parts.append(var["limit_note"])
    out["summary"] = " ".join(parts + [tally, f"Data: {_span(o)}."])
    return out


def compare_methods(site: Site, args: dict) -> dict:
    base = _open(site, {**args, "method": None})
    i = _level(base)
    rows, sound_total = [], len(site.catalog["sound_methods"])
    for m in site.catalog["methods"]:
        o = _open(site, args, method=m["id"])
        r = _reading(site, o, i)
        rows.append({"method": m["label"], "role": "recommended" if m["recommended"] else "sound" if m["sound"]
                     else "comparison only", "science": m["science"], **{k: r.get(k) for k in ("rate", "range", "label")},
                     "passes_test": None if r["rate"] is None else bool(o["col"]["sig"][i])})
    out = {"measure": base["var"]["label"], "place": base["where"], "height_km": _km(base["levels"][i]),
           "pressure_hpa": base["levels"][i], "units": base["var"]["trend_units_plain"], "methods": rows,
           "tools_used": {k: v for k, v in _tools_used(site, base).items() if k != "method"},
           "source": {"product": base["ds"]["source"],
                      "file": "web/data/" + site.catalog["routes"]["trend"].format(**{**base["res"], "method": "*"})}}
    if rows[0]["rate"] is None:
        out["summary"] = f"{_head(base, i)}: no measurements here."
        return out
    agree = int(base["col"]["agree"][i])
    out["sound_methods_that_agree"] = f"{agree} of {sound_total}"
    each = "; ".join(f"{r['method']}: {_rate(r['rate'])} ({'passes' if r['passes_test'] else 'does not pass'} its test)"
                     for r in rows)
    cautions = " ".join(f"{m['label']}: {m['caution']}" for m in site.catalog["methods"] if m["caution"])
    out["summary"] = (f"{_head(base, i)}: {agree} of {sound_total} sound methods find a change in this direction. "
                      f"In {out['units']}: {each}. {cautions}").strip()
    return out


def compare_datasets(site: Site, args: dict) -> dict:
    o = _open(site, args)
    res, i = o["res"], _level(o)
    pair = next((w for w in site.manifest["witness"] if w["dataset"] == res["dataset"]
                 and w["variable"] == res["variable"] and w["period"] == res["period"]), None)
    first = {"data": o["ds"]["label"], **_reading(site, o, i)}
    out = {"measure": o["var"]["label"], "place": o["where"], "height_km": first["height_km"],
           "units": o["var"]["trend_units_plain"], "first": first, "tools_used": _tools_used(site, o),
           "source": _source(o)}
    if pair is None:
        out["second"] = None
        out["summary"] = (f"Only one dataset here covers {o['var']['label'].lower()} for these years, so no result for it can "
                          f'be labelled "{site.label(CLEAR)}". {first["data"]} alone: '
                          + (f"{_rate(first['rate'])} {out['units']} ({first['label']})." if first["rate"] is not None
                             else "no measurements at this height."))
        return out
    other = _open(site, args, dataset=pair["with_dataset"], period=pair["with_period"], km=None, hpa=o["levels"][i])
    j = other["res"]["level"]
    same_height = abs(other["levels"][j] - o["levels"][i]) < 1e-6
    second = {"data": other["ds"]["label"], **_reading(site, other, j)}
    out["second"] = second
    out["other_sources"] = [_source(other)]
    if first["rate"] is None or second["rate"] is None or not same_height:
        out["summary"] = f"{_head(o, i)}: the two datasets do not both have measurements at this height."
        return out
    out["same_direction"] = (first["rate"] > 0) == (second["rate"] > 0)
    out["summary"] = (f"{_head(o, i)}, {o['trend']['span']['start']} to {o['trend']['span']['end']}: {first['data']} shows "
                      f"{_rate(first['rate'])} {out['units']} (range {_rate(first['range'][0])} to {_rate(first['range'][1])}). "
                      f"{second['data']} shows {_rate(second['rate'])} (range {_rate(second['range'][0])} to "
                      f"{_rate(second['range'][1])}). Label: {first['label']}. {first['why']}")
    return out


def compare_places(site: Site, args: dict) -> dict:
    base = _open(site, {**args, "where": "global"})
    i = _level(base)
    rows = []
    for r in site.manifest["regions"]:
        o = _open(site, {**args, "where": r["id"]}, km=None, hpa=base["levels"][i])
        rows.append({"place": r["label"], **{k: v for k, v in _reading(site, o, i).items()
                                             if k not in ("height_km", "pressure_hpa")}})
    out = {"measure": base["var"]["label"], "height_km": _km(base["levels"][i]), "pressure_hpa": base["levels"][i],
           "units": base["var"]["trend_units_plain"], "places": rows, "tools_used": _tools_used(site, base),
           "source": _source(base)}
    proven = [r for r in rows if r["rate"] is not None and r["label"] in (site.label(CLEAR), site.label(LIKELY))]
    each = "; ".join(f"{r['place']}: {_rate(r['rate'])} ({r['label']})" if r["rate"] is not None
                     else f"{r['place']}: no measurements" for r in rows)
    lead = ""
    if proven:
        top = max(proven, key=lambda r: abs(r["rate"]))
        out["fastest_labelled_change"] = top
        lead = (f"The fastest change that earned a label is in: {top['place']} ({top['direction']}, "
                f"{_rate(top['rate'])} {out['units']}). ")
    height = "Near the ground" if out["height_km"] < 1 else f"About {out['height_km']} km up"
    out["summary"] = (f"{height} ({out['pressure_hpa']:g} hPa). {lead}All places, in {out['units']}: {each}. "
                      f"Data: {_span(base)}.")
    return out


def opposite_pairs(site: Site, args: dict) -> dict:
    o = _open(site, {**args, "km": None, "hpa": None, "months": "none"})
    path = site.catalog["routes"]["pairs"].format(**o["res"])
    pairs, levels, units = site.load(path), o["levels"], o["var"]["trend_units_plain"]
    lat = site.manifest["lat_centers"]

    def side(s):
        return {"height_km": _km(s["hpa"]), "rate": s["slope"], "label": site.label(s["verdict"])}

    vertical = [{"place": router.place_phrase(p["where"], site.manifest), "low": side(p["low"]), "high": side(p["high"])}
                for p in pairs["vertical"]]
    horizontal = [{"height_km": _km(p["hpa"]),
                   "a": {"latitude": lat[p["a"]["lat"]], "rate": p["a"]["slope"], "label": site.label(p["a"]["verdict"])},
                   "b": {"latitude": lat[p["b"]["lat"]], "rate": p["b"]["slope"], "label": site.label(p["b"]["verdict"])}}
                  for p in pairs["horizontal"]]
    out = {"measure": o["var"]["label"], "units": units, "same_place_two_heights": vertical,
           "same_height_two_latitudes": horizontal, "tools_used": _tools_used(site, o),
           "rule": "Only changes labelled Likely or Clear count. A pair is ranked by the smaller of its two rates.",
           "source": {"product": o["ds"]["source"], "file": f"web/data/{path}"}}
    if not vertical and not horizontal:
        out["summary"] = f"No two proven changes in {o['var']['label'].lower()} point in opposite directions."
        return out
    w = _words(o["var"])
    lines = [f"{p['place']}: {w['up'] if p['low']['rate'] > 0 else w['down']} {_rate(p['low']['rate'])} "
             f"{_near(p['low']['height_km'])}, {w['up'] if p['high']['rate'] > 0 else w['down']} {_rate(p['high']['rate'])} "
             f"{_near(p['high']['height_km'])}" for p in vertical[:len(site.manifest["regions"])]]
    out["summary"] = (f"Same place, opposite directions at two heights ({units}). " + ". ".join(lines) + "."
                      if lines else "Opposite directions were found only between latitudes at the same height.")
    return out


def effect_of_events(site: Site, args: dict) -> dict:
    base = _open(site, {**args, "months": "none"})
    i = _level(base)
    rows = []
    for mask in site.manifest["masks"]:
        o = _open(site, args, mask=mask["id"])
        r = _reading(site, o, i)
        rows.append({"months": mask["label"], **{k: r.get(k) for k in ("rate", "range", "label")}})
    events = [{"label": e["label"], "from": e["start"], "to": e["end"], "kind": e["kind"], "explain": e["explain"]}
              for e in site.manifest["events"] if e["kind"] == "volcano" or base["res"]["dataset"] in e.get("datasets", [])]
    out = {"measure": base["var"]["label"], "place": base["where"], "height_km": _km(base["levels"][i]),
           "units": base["var"]["trend_units_plain"], "with_and_without": rows, "events": events,
           "tools_used": {k: v for k, v in _tools_used(site, base).items() if k != "months"},
           "source": {"product": base["ds"]["source"],
                      "file": "web/data/" + site.catalog["routes"]["trend"].format(**{**base["res"], "mask": "*"})}}
    if rows[0]["rate"] is None:
        out["summary"] = f"{_head(base, i)}: no measurements here."
        return out
    each = "; ".join(f"{r['months']}: {_rate(r['rate'])} ({r['label']})" for r in rows if r["rate"] is not None)
    text = f"{_head(base, i)}, in {out['units']}. {each}."
    check = site.manifest["method"]
    without = next((r for m, r in zip(site.manifest["masks"], rows) if m["id"] == check["event_check_mask"]), None)
    if without and without["rate"] is not None and rows[0]["rate"]:
        moved = abs(without["rate"] - rows[0]["rate"]) / abs(rows[0]["rate"])
        out["depends_on_volcano_months"] = bool(moved > check["event_change_limit"])
        text += (" Leaving out the months after big eruptions changes the rate by more than half, so this result "
                 "depends on them." if moved > check["event_change_limit"] else
                 " Leaving out the months after big eruptions changes the rate by less than half, so this result "
                 "does not depend on them.")
    step = (base["col"].get("step") or [None] * len(base["levels"]))[i]
    if step is not None:
        out["jump_at_data_source_change"] = {"size": step, "units": base["var"]["units_plain"]}
        out["jump_at_data_source_change"]["meaning"] = ("The biggest shift at a moment this dataset changed its data "
                                                        "source: the two years after, minus the two years before.")
        text += (f" Biggest shift at a data-source change: the two years after were {step:+.1f} "
                 f"{base['var']['units_plain']} from the two years before.")
    out["summary"] = text + f" Data: {_span(base)}."
    return out


def yearly_history(site: Site, args: dict) -> dict:
    o = _open(site, args)
    i, res, var = _level(o), o["res"], o["var"]
    route = "series_region" if "region" in res["place"] else "series_lat"
    path = site.catalog["routes"][route].format(dataset=res["dataset"], variable=res["variable"], **res["place"])
    series = np.array([np.nan if x is None else x for x in site.load(path)["anom"][i]], dtype=float)
    y0, m0 = (int(x) for x in o["ds"]["time"]["start"].split("-"))
    year = (y0 * 12 + (m0 - 1) + np.arange(series.size)) // 12
    rows = []
    for y in np.unique(year):
        vals = series[(year == y) & np.isfinite(series)]
        if vals.size >= 6:                                    # a year needs at least half its months
            rows.append({"year": int(y), "value": round(float(vals.mean()), 2)})
            if vals.size < 12:
                rows[-1]["months_with_data"] = int(vals.size)
    units = var["units_plain"]
    out = {"measure": var["label"], "place": o["where"], "height_km": _km(o["levels"][i]),
           "units": units, "meaning": "Each value is that year's average compared with normal for the same calendar "
                                      "months over the whole record. Above zero means higher than normal. "
                                      "A year is listed if at least 6 of its months have data.",
           "years": rows, "source": {"product": o["ds"]["source"], "file": f"web/data/{path}"}}
    if len(rows) < 10:
        out["summary"] = f"{_head(o, i)}: not enough years of measurements to describe."
        return out
    hi, lo = max(rows, key=lambda r: r["value"]), min(rows, key=lambda r: r["value"])
    first, last = round(float(np.mean([r["value"] for r in rows[:5]])), 2), round(float(np.mean([r["value"] for r in rows[-5:]])), 2)
    out.update(highest_year=hi, lowest_year=lo,
               first_five_years_average={"years": f"{rows[0]['year']} to {rows[4]['year']}", "value": first},
               last_five_years_average={"years": f"{rows[-5]['year']} to {rows[-1]['year']}", "value": last})
    out["summary"] = (f"{_head(o, i)}, {o['ds']['label']}. Compared with normal, the first five years "
                      f"({rows[0]['year']} to {rows[4]['year']}) averaged {first:+.2f} {units} and the last five "
                      f"({rows[-5]['year']} to {rows[-1]['year']}) averaged {last:+.2f} {units}. Highest year: "
                      f"{hi['year']} ({hi['value']:+.2f}). Lowest year: {lo['year']} ({lo['value']:+.2f}).")
    return out


def published_checks(site: Site, args: dict) -> dict:
    try:
        rows = site.load("validation.json")["rows"]
    except FileNotFoundError:
        raise ValueError("The comparison with published results has not been run for this data.") from None
    checks = [{"published_by": r["source"], "published_finding": r["finding"], "data": r["dataset"],
               "years": r["years"], "our_number": r["ours"], "match": r["match"]} for r in rows]
    yes = sum(1 for r in rows if r["match"].startswith("Yes"))
    return {"checks": checks, "matching": f"{yes} of {len(rows)}",
            "summary": f"{yes} of {len(rows)} published results are matched by our own numbers. "
                       + " ".join(f"{r['source']}: {r['finding']} Ours: {r['ours']}. Match: {r['match']}" for r in rows),
            "source": {"product": "AIRS3STM, M2IMNPASM", "file": "web/data/validation.json"}}


def find_terms(site: Site, word: str) -> list:
    word = word.lower().strip()
    return [t for t in site.glossary["terms"] if word and len(word) > 2 and (
        word in t["plain"].lower() or word in t["science"].lower() or word == t["id"].replace("_", " "))]


def glossary(site: Site, args: dict) -> dict:
    terms = site.glossary["terms"]
    word = str(args.get("term") or "").lower().strip()
    hits = find_terms(site, word) if word else terms
    if not hits:
        raise ValueError(f"{word!r} is not a word in the glossary. The words are: "
                         + ", ".join(t["plain"].lower() for t in terms) + ".")
    chosen = hits
    return {"terms": [{"plain": t["plain"], "science": t["science"], "explain": t["explain"]} for t in chosen],
            "summary": " ".join(f"{t['plain']} ({t['science']}): {t['explain']}" for t in chosen[:3]),
            "source": {"product": "Lapse glossary", "file": "web/content/glossary.json"}}


# --- the catalog of tools ---------------------------------------------------------

def _fields(site: Site) -> dict:
    """Argument descriptions, with the allowed values read from the published files."""
    m, c = site.manifest, site.catalog
    measures = sorted({v["id"] for d in m["datasets"] for v in d["variables"]})
    periods = sorted({p["id"] for d in m["datasets"] for p in d["periods"]})
    regions = [r["id"] for r in m["regions"]]
    return {
        "what": {"type": "string", "enum": measures,
                 "description": "The measure. " + "; ".join(sorted({f"{v['id']} = {v['label']}" for d in m["datasets"]
                                                                    for v in d["variables"]})) + ". Default: t."},
        "where": {"type": "string", "description": "A region id (" + ", ".join(regions) + ") or a latitude in degrees, "
                  "north positive, for example \"45\" or \"-60\". Default: global."},
        "km": {"type": "number", "description": "Height above the ground in km. Leave out to get the height with the "
               "strongest labelled change."},
        "hpa": {"type": "number", "description": "Height as air pressure in hPa, instead of km."},
        "data": {"type": "string", "enum": ["auto"] + [d["id"] for d in m["datasets"]],
                 "description": "Which NASA dataset. auto = " + c["auto"]["dataset"]},
        "method": {"type": "string", "enum": ["auto"] + [x["id"] for x in c["methods"]],
                   "description": "How the trend is measured and tested. auto = " + c["auto"]["method"]},
        "years": {"type": "string", "enum": ["auto"] + periods, "description": "Which years. auto = " + c["auto"]["period"]},
        "months": {"type": "string", "enum": [x["id"] for x in m["masks"]],
                   "description": "Leave out months after big volcanic eruptions. Default: none (all months)."},
        "term": {"type": "string", "description": "A word to look up. Leave out to get every term."},
    }


TOOLS = [
    (list_options, [], "Lists everything that can be asked: measures, datasets, places, heights, methods, the four "
                       "labels and what they mean. Call this first if unsure what exists."),
    (trend_at, ["what", "where", "km", "hpa", "data", "method", "years", "months"],
     "How fast one measure is changing at one place and one height: the rate per ten years, the range it very likely "
     "lies in, the total change over the record, and one of four labels (Clear change, Likely change, Not proven "
     "yet, Disputed) with the reason."),
    (profile, ["what", "where", "data", "method", "years", "months"],
     "The whole column of air above one place: the rate and label at every height from the ground up, where the "
     "direction flips, and the strongest change each way. Use this for questions about a place with no height."),
    (compare_methods, ["what", "where", "km", "hpa", "data", "years", "months"],
     "The same place and height measured by every method in the hub, and how many sound methods agree."),
    (compare_datasets, ["what", "where", "km", "hpa", "method", "years", "months", "data"],
     "The same place, height and years in two independent NASA datasets (AIRS satellite and MERRA-2 reanalysis), "
     "and whether they agree."),
    (compare_places, ["what", "km", "hpa", "data", "method", "years", "months"],
     "One height compared across every region of the Earth, and where the labelled change is fastest."),
    (opposite_pairs, ["what", "data", "method", "years"],
     "Places where two proven changes point in opposite directions: the same place at two heights, or the same "
     "height at two latitudes."),
    (effect_of_events, ["what", "where", "km", "hpa", "data", "method", "years"],
     "Whether a trend depends on volcano months or on a change of data source: the rate with all months, without "
     "the 2022 Hunga eruption, and without all volcano months."),
    (yearly_history, ["what", "where", "km", "hpa", "data"],
     "The record year by year at one place and height, compared with normal: every year's average, the highest and "
     "lowest year, and the first and last five-year averages."),
    (published_checks, [], "How our numbers compare with results published by other scientists. Use for questions "
                           "about trust or accuracy."),
    (glossary, ["term"], "Plain-language meanings of the words used here (height, rate, range, significant, "
                         "troposphere, stratosphere, reanalysis and more)."),
]
NAMES = [fn.__name__ for fn, _, _ in TOOLS]


def _place(where) -> str:
    """Accept "45", "45N", "60 S", "-17.5" or a region id."""
    text = str(where).strip().lower().replace("°", "").replace("lat:", "")
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*(n|s|north|south)?", text)
    if not m:
        return text.replace(" ", "_").replace("-", "_")
    lat = float(m.group(1)) * (-1 if (m.group(2) or "").startswith("s") else 1)
    if abs(lat) > 90:
        raise ValueError("A latitude must be between -90 and 90.")
    return str(lat)


def specs(site: Site) -> list:
    """Tool definitions in the neutral shape every adapter converts from."""
    fields = _fields(site)
    return [{"name": fn.__name__, "description": text,
             "parameters": {"type": "object", "properties": {k: fields[k] for k in keys}, "additionalProperties": False}}
            for fn, keys, text in TOOLS]


def call(site: Site, name: str, args: dict | None) -> dict:
    """Run one tool. Never raises on bad input: the error text goes back to the caller."""
    entry = next((t for t in TOOLS if t[0].__name__ == name), None)
    if entry is None:
        return {"ok": False, "error": f"There is no tool called {name!r}. The tools are: {', '.join(NAMES)}."}
    fn, keys, _ = entry
    args = dict(args or {})
    extra = sorted(set(args) - set(keys))
    if extra:
        return {"ok": False, "error": f"{name} does not take {', '.join(extra)}. It takes: {', '.join(keys) or 'nothing'}."}
    try:
        for k in ("km", "hpa"):
            if args.get(k) is not None:
                try:
                    args[k] = float(args[k])
                except (TypeError, ValueError):
                    raise ValueError(f"{k} must be a number, not {args[k]!r}.") from None
                if args[k] < 0 or (k == "hpa" and args[k] == 0):
                    raise ValueError(f"{k} must be a positive number.")
        if args.get("where") is not None:
            args["where"] = _place(args["where"])
        return {"ok": True, "result": fn(site, args)}
    except (ValueError, TypeError) as exc:
        return {"ok": False, "error": str(exc)}
    except FileNotFoundError:
        return {"ok": False, "error": "That combination has not been computed. Try other years or months."}
