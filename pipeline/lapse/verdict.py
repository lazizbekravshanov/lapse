"""The verdict ladder: one of four labels for every trend, chosen by rule.

Pure functions over arrays. No files, no network. See config.VERDICTS for the words.

A   = the dataset on screen.
ALT = the same dataset with volcano months left out.
B   = the second dataset over the same years (NaN where it has no data).
"""

from __future__ import annotations

import numpy as np

from . import config

NOT_PROVEN, LIKELY, CLEAR, DISPUTED = 0, 1, 2, 3
R = {r["id"]: r["code"] for r in config.REASONS}


def jumps(slope, span_decades: float, step, usual) -> np.ndarray:
    """True where a data-source jump is unusual for the series and explains at
    least config.JUMP_SHARE of the total change the trend implies."""
    total = np.abs(np.asarray(slope, dtype=float)) * span_decades
    step = np.abs(np.asarray(step, dtype=float))
    with np.errstate(invalid="ignore"):
        return (step >= np.asarray(usual, dtype=float)) & (step >= config.JUMP_SHARE * total) & (step > 0)


def classify(a: dict, alt: dict | None = None, b: dict | None = None):
    """Return (verdict, reason) arrays shaped like a["slope"]. NaN where A has no trend.

    a, alt, b are dicts with "slope", "lo", "hi", "sig" arrays of the same shape.
    """
    s = np.asarray(a["slope"], dtype=float)
    a_sig = np.asarray(a["sig"], dtype=float) > 0
    shape = s.shape
    nan = np.full(shape, np.nan)

    if alt is not None:
        alt_s = np.asarray(alt["slope"], dtype=float)
        have_alt = np.isfinite(alt_s)
        flips = np.sign(alt_s) != np.sign(s)
        with np.errstate(invalid="ignore"):
            big_change = np.abs(alt_s - s) > config.EVENT_CHANGE_LIMIT * np.abs(s)
        event = have_alt & (flips | big_change)
    else:
        event = np.zeros(shape, dtype=bool)

    if b is not None:
        b_s = np.asarray(b["slope"], dtype=float)
        b_sig = np.asarray(b["sig"], dtype=float) > 0
        b_lo, b_hi = np.asarray(b["lo"], dtype=float), np.asarray(b["hi"], dtype=float)
    else:
        b_s, b_sig, b_lo, b_hi = nan, np.zeros(shape, dtype=bool), nan, nan
    have_b = np.isfinite(b_s)
    same = np.sign(b_s) == np.sign(s)
    with np.errstate(invalid="ignore"):
        overlap = (np.asarray(a["lo"], float) <= b_hi) & (b_lo <= np.asarray(a["hi"], float))

    verdict = np.full(shape, float(LIKELY))
    reason = np.full(shape, float(R["no_witness"]))

    # Later rules override earlier ones, so the list runs from weakest to strongest claim.
    def put(where, v, r):
        verdict[where] = v
        reason[where] = R[r]

    put(have_b & ~b_sig & ~same, LIKELY, "witness_unsure")
    put(have_b & ~b_sig & same, LIKELY, "witness_agrees_weakly")
    put(have_b & b_sig & same & ~overlap, LIKELY, "size_differs")
    put(have_b & b_sig & same & overlap, CLEAR, "both_agree")
    put(have_b & b_sig & ~same, DISPUTED, "opposite_sign")
    if b is not None and "jump" in b:
        put(have_b & np.asarray(b["jump"], dtype=bool), LIKELY, "witness_jumps")
    put(event, DISPUTED, "event_sensitive")
    if "jump" in a:
        put(np.asarray(a["jump"], dtype=bool), DISPUTED, "data_change")
    put(~a_sig, NOT_PROVEN, "fails_test")

    missing = ~np.isfinite(s)
    verdict[missing] = np.nan
    reason[missing] = np.nan
    return verdict, reason


def align_levels(b: dict, b_levels, a_levels) -> dict:
    """Put B's arrays (level first) on A's levels. Exact pressure matches only."""
    b_levels = [float(x) for x in b_levels]
    out = {}
    for key in ("slope", "lo", "hi", "sig", "jump"):
        if key not in b:
            continue
        src = np.asarray(b[key], dtype=float)
        dst = np.full((len(a_levels),) + src.shape[1:], np.nan)
        for i, p in enumerate(a_levels):
            if float(p) in b_levels:
                dst[i] = src[b_levels.index(float(p))]
        out[key] = np.nan_to_num(dst) > 0 if key == "jump" else dst
    return out
