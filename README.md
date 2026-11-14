# Lapse

**What is changing in the atmosphere, at which height, and is it real?**

Most trend tools look at the surface. Lapse looks at the whole column of air, from the
ground to about 65 km up, and tests the trend at every height.

The headline case: rising CO2 warms the lower atmosphere and cools the upper atmosphere.
One cause, opposite trends, in the same column of air.

Built for the 2026 NASA Space Apps Challenge, "Be An Earth System Trend Detective!".
Not affiliated with NASA.

> **Status:** the pipeline, statistics and website run end to end on **synthetic** data.
> The NASA catalog search and the download request format are tested. The logged-in
> download has not been run yet. The site shows a banner whenever the data on screen
> is synthetic.

## What you see

| View | Question it answers |
|---|---|
| **Curtain** | Where is it changing? Latitude left to right, height bottom to top, colour is the trend. Hatched cells did not pass the test. The dashed line is where warming turns into cooling. |
| **Profile** | How much, at each height? Trend with its uncertainty band for one latitude or the whole globe. |
| **History** | What happened month by month? The series behind any one point, with known events shaded. |
| **Verdict** | One plain sentence built only from the computed numbers. |

Extra checks: compare two independent datasets, and leave out volcano months to see
if a trend survives.

## Quick start

```bash
make setup     # install
make test      # 15 tests
make demo      # synthetic data -> web/data  (about a minute)
make serve     # http://localhost:8000
```

## Real NASA data

You need a free [Earthdata login](https://urs.earthdata.nasa.gov/).

1. In your Earthdata profile, open **Applications > Authorized Apps** and approve
   **NASA GESDISC DATA ARCHIVE**.
2. Open **Generate Token**, copy the token, and keep it out of git:

```bash
export EARTHDATA_TOKEN="paste-it-here"      # in your own terminal only
python -m lapse inspect airs                # prints the file's real structure
python -m lapse fetch airs --start 2024-01 --end 2024-03    # small test first
python -m lapse fetch airs                  # 289 months
python -m lapse fetch merra2                # 561 months, the long one
python -m lapse export
```

Downloads are resumable: every month is cached, so rerunning continues where it stopped.

| Dataset | NASA product | Record | Role |
|---|---|---|---|
| AIRS | AIRS3STM v7.0, monthly, 24 levels | Sept 2002 on | Satellite witness |
| MERRA-2 | M2IMNPASM v5.12.4, monthly, 42 levels | 1980 on | Long record, three variables |

## How the numbers are made

1. Remove the seasonal cycle: each month minus that calendar month's average.
2. **Slope:** Theil-Sen, the median slope over every pair of months.
3. **Significance:** Mann-Kendall, with the variance widened for month-to-month memory.
4. **Many cells at once:** Benjamini-Hochberg false discovery rate of 0.05 over the curtain.
5. "Not significant" is shown as **not proven**, never as "no change".

All statistics live in `pipeline/lapse/stats.py` and are tested in `pipeline/tests/`.
The website does no statistics of its own.

## Layout

```
pipeline/lapse/config.py     datasets, variables, periods, events (edit this first)
pipeline/lapse/fetch.py      NASA catalog + OPeNDAP download -> monthly cache -> zonal cubes
pipeline/lapse/synthetic.py  fake cubes for building and testing
pipeline/lapse/stats.py      trend, significance, false discovery rate
pipeline/lapse/export.py     cubes -> web/data JSON
web/                         static site, no build step
docs/                        data contract, weekend plan, prior art
```

## Limits

- Latitude bands are averages around the whole globe, so east-west differences are hidden.
- Reanalysis data can jump when its input satellites change, most of all above 10 hPa.
- Heights in km are approximate conversions from pressure.
- A trend line describes the record. It does not say the change is steady or will continue.
