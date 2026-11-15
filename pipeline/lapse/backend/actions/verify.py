"""Recompute every published number from the data cubes and compare.

    python -m lapse verify

Anyone with a clone can run this: the four cubes are in data/zonal, so no NASA
login is needed. It answers one question: are the files the website reads exactly
what this code produces from that data?
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ... import config
from . import export

TOLERANCE = 1e-3          # numbers are published to 4 decimals; this allows a last-digit wobble
LABELS = ("verdict", "reason", "sig", "agree")     # whole-number labels; these can flip on a knife edge
FLIP_BUDGET = 0.005       # share of labels allowed to differ between computers before we call it a failure
SKIP = ("generated_at",)


def _walk(a, b, path, key, out):
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            out["shape"].append(f"{path}: keys differ ({sorted(set(a) ^ set(b))})")
            return
        for k in a:
            if k not in SKIP:
                _walk(a[k], b[k], f"{path}/{k}", k, out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out["shape"].append(f"{path}: length {len(a)} vs {len(b)}")
            return
        for i, (x, y) in enumerate(zip(a, b)):
            _walk(x, y, f"{path}[{i}]", key, out)
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        label = key in LABELS
        out["labels" if label else "numbers"] += 1
        gap = abs(a - b)
        if gap > TOLERANCE * max(1.0, abs(a)):
            out["flips" if label else "off"].append((gap, path, a, b))
    elif a != b:
        if key in LABELS:                         # a label present on one side and missing on the other
            out["labels"] += 1
            out["flips"].append((float("inf"), path, a, b))
        else:
            out["shape"].append(f"{path}: {a!r} vs {b!r}")


def compare(published: Path, fresh: Path) -> dict:
    """Compare two web/data folders file by file."""
    out = {"files": 0, "numbers": 0, "labels": 0, "off": [], "flips": [], "shape": []}
    names = {str(p.relative_to(published)) for p in published.rglob("*.json") if p.name != "validation.json"}
    made = {str(p.relative_to(fresh)) for p in fresh.rglob("*.json")}
    for name in sorted(names ^ made):
        out["shape"].append(f"{name}: only in {'published' if name in names else 'recomputed'} files")
    for name in sorted(names & made):
        out["files"] += 1
        _walk(json.loads((published / name).read_text()), json.loads((fresh / name).read_text()), name, "", out)
    out["ok"] = (not out["off"] and not out["shape"]
                 and len(out["flips"]) <= FLIP_BUDGET * max(1, out["labels"]))
    return out


def run(zonal_dir: Path | None = None, data_dir: Path | None = None, verbose: bool = True) -> dict:
    data_dir = data_dir or config.WEB_DATA_DIR
    with tempfile.TemporaryDirectory() as tmp:
        export.run(zonal_dir, Path(tmp), verbose=False)
        out = compare(data_dir, Path(tmp))
    if verbose:
        print(f"Recomputed {out['files']} files from the data cubes: "
              f"{out['numbers']:,} numbers and {out['labels']:,} labels compared.")
        print(f"  numbers that differ by more than {TOLERANCE}: {len(out['off'])}")
        print(f"  labels that differ: {len(out['flips'])} (allowed between computers: "
              f"{FLIP_BUDGET:.1%} of {out['labels']:,})")
        for line in out["shape"][:10]:
            print("  structure:", line)
        for gap, path, a, b in sorted(out["off"], reverse=True)[:10]:
            print(f"  {path}: published {a}, recomputed {b}")
        for gap, path, a, b in out["flips"][:5]:
            print(f"  label {path}: published {a}, recomputed {b}")
        print("OK: the published files match the code and the data." if out["ok"]
              else "MISMATCH: the published files are not what this code produces. Run: python -m lapse export")
    return out
