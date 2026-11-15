"""The tool catalog. To add a tool, add it here; the export, the router and the
website all pick it up from this file.

A method is a bundle of two choices: how to measure the rate of change, and how
to test whether it could be chance. Every method has the same input and output
(see backend/operations/stats.py), so they are interchangeable.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Callable

from .. import config
from ..backend.operations import stats


@dataclass(frozen=True)
class Method:
    id: str
    label: str            # short name on the site
    plain: str            # what it does, in everyday words
    science: str          # the names a scientist would use
    run: Callable         # run(y[time, cells], t[time], alpha=, min_n=) -> dict of arrays
    sound: bool = True    # counts toward "how many methods agree"
    recommended: bool = False
    caution: str = ""


METHODS = {m.id: m for m in [
    Method(
        id="robust", label="Robust", recommended=True,
        plain="Looks at every pair of months, takes the middle rate of change, then asks how steadily "
              "the record moves in one direction. One freak month cannot bend it.",
        science="Theil-Sen slope, Mann-Kendall test with lag-1 variance correction",
        run=stats.sen_mk_many,
    ),
    Method(
        id="classic", label="Classic straight line",
        plain="Fits the straight line closest to all the months and tests its slope, allowing for the "
              "fact that a warm month is often followed by another warm month.",
        science="Least squares, t-test with effective sample size",
        run=partial(stats.ols_many, memory=True),
    ),
    Method(
        id="yearly", label="Year by year",
        plain="Averages each year into one value first, which removes most of the month-to-month "
              "memory, then fits a straight line through the yearly values.",
        science="Least squares on annual means, t-test with effective sample size",
        run=stats.yearly_many,
    ),
    Method(
        id="textbook", label="Textbook, no memory", sound=False,
        plain="The straight-line fit and test exactly as in a first statistics course. It treats every "
              "month as independent of the last one.",
        science="Least squares, plain t-test",
        caution="The air is not independent from month to month, so this method claims certainty "
                "too easily. It is here for comparison and does not count toward agreement.",
        run=partial(stats.ols_many, memory=False),
    ),
]}

DEFAULT_METHOD = next(m.id for m in METHODS.values() if m.recommended)
SOUND = [m.id for m in METHODS.values() if m.sound]

# Checks run on every result, whatever method is chosen.
CHECKS = [
    {"id": "fdr", "label": "False-alarm control",
     "plain": "Hundreds of places are tested at once, so some would pass by luck. We limit how many "
              "of the flagged ones can be false alarms.",
     "science": f"Benjamini-Hochberg false discovery rate, q = {config.FDR_Q}"},
    {"id": "witness", "label": "Second dataset",
     "plain": "Where two independent datasets cover the same years and heights, a change is only "
              "\"Clear\" if both show it.",
     "science": "Sign, significance and range overlap between AIRS and MERRA-2"},
    {"id": "volcano", "label": "Volcano months",
     "plain": "Every trend is recomputed without the months after big eruptions. If it changes by "
              "more than half, the label becomes \"Disputed\".",
     "science": f"Recomputed with mask {config.EVENT_CHECK_MASK}; limit {config.EVENT_CHANGE_LIMIT:.0%}"},
    {"id": "jump", "label": "Data-source jumps",
     "plain": "If a record jumps at the moment its measuring instruments changed, and the jump explains "
              "much of the trend, the label becomes \"Disputed\".",
     "science": "Two-year shift at documented changes against the 97.5th percentile of all shifts"},
]

# Where each answer lives. The website and the router both build paths from these.
ROUTES = {
    "trend": "trend/{dataset}/{variable}/{period}__{mask}__{method}.json",
    "pairs": "pairs/{dataset}/{variable}/{period}__{method}.json",
    "series_region": "series/{dataset}/{variable}/region_{region}.json",
    "series_lat": "series/{dataset}/{variable}/lat_{lat:02d}.json",
}


def catalog() -> dict:
    """Everything a user can choose between, described in plain words."""
    return {
        "methods": [{"id": m.id, "label": m.label, "plain": m.plain, "science": m.science,
                     "sound": m.sound, "recommended": m.recommended, "caution": m.caution}
                    for m in METHODS.values()],
        "checks": CHECKS,
        "sound_methods": SOUND,
        "defaults": {"method": DEFAULT_METHOD, "mask": "none", "dataset": "auto", "period": "auto"},
        "routes": ROUTES,
        "auto": {
            "dataset": "The satellite record if it measures this, otherwise the reanalysis.",
            "period": "The years covered by two datasets if there are any, otherwise the full record.",
            "method": "The robust method.",
        },
    }
