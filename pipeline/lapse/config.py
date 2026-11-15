"""Everything that is a choice lives here: datasets, variables, bands, periods, events.

Change this file, not the code, when a dataset name or a variable turns out different.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

# Repo layout -----------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "data" / "cache"   # one small file per dataset/month (gitignored)
ZONAL_DIR = ROOT / "data" / "zonal"   # one cube per dataset/variable (gitignored)
WEB_DATA_DIR = ROOT / "web" / "data"  # what the website reads (committed)

# Latitude bands --------------------------------------------------------------
LAT_STEP = 5.0
LAT_EDGES = np.arange(-90.0, 90.0 + LAT_STEP, LAT_STEP)
LAT_CENTERS = (LAT_EDGES[:-1] + LAT_EDGES[1:]) / 2.0

# Pressure levels (hPa). Real data brings its own levels; these are used by the
# synthetic generator and match the documented level sets of each product.
MERRA2_LEVELS = [
    1000, 975, 950, 925, 900, 875, 850, 825, 800, 775, 750, 725, 700, 650, 600,
    550, 500, 450, 400, 350, 300, 250, 200, 150, 100, 70, 50, 40, 30, 20, 10,
    7, 5, 4, 3, 2, 1, 0.7, 0.5, 0.4, 0.3, 0.1,
]
AIRS_LEVELS = [
    1000, 925, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 70, 50, 30,
    20, 15, 10, 7, 5, 3, 2, 1.5, 1,
]


def approx_altitude_km(p_hpa):
    """Rough height for a pressure level, for labels only (7 km scale height)."""
    return 7.0 * np.log(1000.0 / np.asarray(p_hpa, dtype=float))


@dataclass(frozen=True)
class Variable:
    id: str                      # short id used in file names
    label: str                   # plain-language name shown to users
    units: str                   # units of the anomaly series
    source_names: tuple          # DAP4 path(s) in the NASA file, e.g. "/T"; averaged if several
    scale: float = 1.0           # multiply raw values by this
    relative: bool = False       # True: anomalies in % of the monthly normal
    units_plain: str = ""        # units in everyday words, e.g. "°C"
    min_hpa: float = 0.0         # levels above this height (lower pressure) are not assessed
    limit_note: str = ""         # why, in plain words
    explain: str = ""            # one-sentence definition for non-experts


@dataclass(frozen=True)
class Dataset:
    id: str
    label: str
    kind: str                    # "reanalysis" or "satellite"
    short_name: str              # NASA collection short name
    version: str
    start: str                   # first month, "YYYY-MM"
    levels: tuple                # documented pressure levels, hPa
    variables: tuple
    shape: tuple                 # source grid: (levels, lats, lons)
    has_time: bool               # True if arrays carry a leading time axis of size 1
    lat_path: str                # DAP4 path of the latitude variable
    lat_is_2d: bool = False      # True if latitude is stored as a [lat, lon] grid
    lev_path: str | None = None  # DAP4 path of the level variable; None = use `levels`
    stride: int = 1              # keep every Nth latitude and longitude
    month_regex: str = r"(\d{4})(\d{2})\.nc4"   # finds YYYY and MM in a file name
    note: str = ""


T = Variable(
    id="t", label="Air temperature", units="K", units_plain="°C", source_names=("/T",),
    explain="How warm the air is at that height.",
)
QV = Variable(
    id="qv", label="Water vapor", units="%", units_plain="%", source_names=("/QV",), relative=True,
    explain="How much water vapor the air holds, compared with normal for that month.",
    # MERRA-2 takes in humidity measurements only up to 300 hPa. Above the weather layer
    # it pulls water vapor toward a fixed yearly pattern (3-day relaxation to a zonal-mean
    # monthly climatology), so change there is not a measurement.
    # Source: Davis et al., Atmos. Chem. Phys. 17, 12743-12778, 2017, Table 2.
    min_hpa=300.0,
    limit_note="Only shown up to about 8 km. This dataset takes in humidity measurements up to that "
               "height. Higher up its water vapor comes from the model, and in the stratosphere it is "
               "held close to a fixed yearly pattern, so it cannot show real change there.",
)
O3 = Variable(
    id="o3", label="Ozone", units="%", units_plain="%", source_names=("/O3",), relative=True,
    explain="How much ozone the air holds, compared with normal for that month.",
)

DATASETS = {
    "merra2": Dataset(
        id="merra2",
        label="MERRA-2 (NASA reanalysis)",
        kind="reanalysis",
        short_name="M2IMNPASM",
        version="5.12.4",
        start="1980-01",
        levels=tuple(MERRA2_LEVELS),
        variables=(T, QV, O3),
        # Names and sizes confirmed in NASA's catalog (CMR) on 13 Nov 2026.
        shape=(42, 361, 576),
        has_time=True,
        lat_path="/lat",
        lev_path="/lev",
        stride=4,
        note="A model blended with observations. Long record, but the satellites "
             "feeding it changed over time, which can create fake jumps high up.",
    ),
    "airs": Dataset(
        id="airs",
        label="AIRS (NASA Aqua satellite)",
        kind="satellite",
        short_name="AIRS3STM",
        version="7.0",
        start="2002-09",
        levels=tuple(AIRS_LEVELS),
        # Day (ascending) and night (descending) passes are averaged.
        variables=(
            Variable(
                id="t", label="Air temperature", units="K", units_plain="°C",
                source_names=("/ascending/Data_Fields/Temperature_A",
                              "/descending/Data_Fields/Temperature_D"),
                explain=T.explain,
            ),
        ),
        # Paths and sizes confirmed in NASA's catalog (CMR) on 13 Nov 2026.
        # Level order (1000 hPa first) is from the product guide; `lapse inspect airs`
        # prints the file's own structure if anything looks off.
        shape=(24, 180, 360),
        has_time=False,
        lat_path="/location/Data_Fields/Latitude",
        lat_is_2d=True,
        lev_path=None,
        stride=2,
        month_regex=r"AIRS\.(\d{4})\.(\d{2})\.",
        note="One instrument measuring from orbit since 2002. Shorter record, "
             "independent of the reanalysis model.",
    ),
}

# Periods to compute trends over. None means "as far as the data goes".
PERIODS = {
    "full": {"label": "Full record", "start": None, "end": None},
    "airs_era": {"label": "Since 2002 (both datasets)", "start": "2002-09", "end": None},
}

# Events that can fake or hide a trend. "exclude" events can be masked out.
EVENTS = [
    {
        "id": "pinatubo", "label": "Pinatubo eruption", "start": "1991-06", "end": "1993-12",
        "kind": "volcano",
        "explain": "Volcanic dust warmed the stratosphere for about two years.",
    },
    {
        "id": "obs1998", "label": "New satellite sounders enter MERRA-2", "start": "1998-07",
        "end": "1998-12", "kind": "data_change", "datasets": ["merra2"],
        "explain": "The reanalysis started using a new satellite type. Jumps here "
                   "can be the data source, not the atmosphere.",
    },
    {
        "id": "obs2004", "label": "Aura satellite data enter MERRA-2", "start": "2004-08",
        "end": "2004-12", "kind": "data_change", "datasets": ["merra2"],
        "explain": "Ozone and upper-level temperature inputs changed.",
    },
    {
        "id": "hunga", "label": "Hunga eruption water vapor", "start": "2022-01",
        "end": "2023-12", "kind": "volcano",
        "explain": "An undersea volcano put a record amount of water vapor into the "
                   "stratosphere, which cooled it for about two years.",
    },
]

# Masks: named sets of events whose months are dropped before the trend test.
MASKS = {
    "none": {"label": "All months", "exclude": []},
    "no_hunga": {"label": "Without Hunga (2022-2023)", "exclude": ["hunga"]},
    "no_volcano": {"label": "Without volcanoes", "exclude": ["pinatubo", "hunga"]},
}

ALPHA = 0.05          # significance level
FDR_Q = 0.05          # false discovery rate across the whole curtain
MIN_MONTHS = 60       # skip cells with fewer valid months than this

# Regions: area-weighted averages of latitude bands. "global" must stay first.
REGIONS = [
    {"id": "global", "label": "Whole globe", "lat": [-90, 90], "phrase": "Averaged over the whole globe"},
    {"id": "arctic", "label": "Arctic", "lat": [60, 90], "phrase": "In the Arctic (60°N to the North Pole)"},
    {"id": "north_mid", "label": "Northern middle latitudes", "lat": [30, 60], "phrase": "In the northern middle latitudes (30°N to 60°N)"},
    {"id": "tropics", "label": "Tropics", "lat": [-30, 30], "phrase": "In the tropics (30°S to 30°N)"},
    {"id": "south_mid", "label": "Southern middle latitudes", "lat": [-60, -30], "phrase": "In the southern middle latitudes (30°S to 60°S)"},
    {"id": "antarctic", "label": "Antarctic", "lat": [-90, -60], "phrase": "In the Antarctic (60°S to the South Pole)"},
]

# The mask used to ask "does this trend depend on volcano months?"
EVENT_CHECK_MASK = "no_volcano"
EVENT_CHANGE_LIMIT = 0.5      # a trend that changes by more than half is event-sensitive

# The four labels. Words here are the words on the site.
VERDICTS = [
    {"code": 0, "id": "not_proven", "label": "Not proven yet",
     "meaning": "The change is too small or too irregular to tell apart from chance. "
                "This does not mean nothing changed."},
    {"code": 1, "id": "likely", "label": "Likely change",
     "meaning": "This dataset shows a change too consistent to be chance, and nothing contradicts it, "
                "but a second dataset has not fully confirmed it."},
    {"code": 2, "id": "clear", "label": "Clear change",
     "meaning": "Two independent datasets both show a change too consistent to be chance, "
                "in the same direction and of similar size."},
    {"code": 3, "id": "disputed", "label": "Disputed",
     "meaning": "The evidence conflicts: the second dataset shows the opposite, the result depends "
                "on a few volcano months, or the record jumps when its data source changed."},
]

REASONS = [
    {"code": 0, "id": "fails_test", "text": "The change does not pass the test."},
    {"code": 1, "id": "both_agree", "text": "Both datasets pass the test, in the same direction, with overlapping ranges."},
    {"code": 2, "id": "witness_agrees_weakly", "text": "The second dataset points the same way but does not pass the test."},
    {"code": 3, "id": "witness_unsure", "text": "The second dataset cannot confirm it."},
    {"code": 4, "id": "no_witness", "text": "There is no second dataset at this height or for these years."},
    {"code": 5, "id": "size_differs", "text": "Both datasets agree on the direction but not on the size."},
    {"code": 6, "id": "opposite_sign", "text": "The second dataset shows a proven change in the opposite direction."},
    {"code": 7, "id": "event_sensitive", "text": "The result changes a lot when volcano months are left out."},
    {"code": 8, "id": "data_change", "text": "The record jumps at a moment when the data source changed, and the jump explains much of the trend."},
    {"code": 9, "id": "witness_jumps", "text": "The second dataset jumps at a data-source change here, so it cannot confirm."},
]

# A jump at a documented data-source change makes a trend "Disputed" when it is
# both unusual for the series and at least this share of the total change.
JUMP_SHARE = 0.5
