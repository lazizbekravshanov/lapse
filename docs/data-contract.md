# Data contract

The pipeline writes these files into `web/data/`. The website reads nothing else.
If both sides respect this page, they can be built by different people at the same time.

All grids are `[level][lat]`: the outer list follows `levels_hpa`, the inner list
follows `lat_centers`. Missing values are `null`.

## manifest.json

| Key | Meaning |
|---|---|
| `schema` | Contract version. Now `1`. |
| `synthetic` | `true` if any cube was synthetic. The site must show a banner. |
| `method` | `alpha`, `fdr_q`, names of the slope and test, `trend_per`. |
| `lat_centers`, `lat_step` | Latitude band centres in degrees, and the band width. |
| `periods[]` | `id`, `label`, `start`, `end` (`YYYY-MM` or `null`). |
| `masks[]` | `id`, `label`, `exclude` (event ids whose months are dropped). |
| `events[]` | `id`, `label`, `start`, `end`, `kind` (`volcano` or `data_change`), `explain`. |
| `datasets[]` | `id`, `label`, `kind`, `note`, `source`, `levels_hpa`, `alt_km`, `time {start, end, n}`, `variables[]`. |
| `datasets[].variables[]` | `id`, `label`, `units`, `trend_units`, `explain`, `relative`. |
| `agreement[]` | `variable`, `a`, `b`, `period`, `mask`, `file`. |

## trend/{dataset}/{variable}/{period}__{mask}.json

| Key | Shape | Meaning |
|---|---|---|
| `slope` | grid | Trend per decade. |
| `lo`, `hi` | grid | 95% confidence interval of the slope. |
| `p` | grid | p-value after the autocorrelation correction. |
| `q` | grid | False discovery rate q-value across the whole grid. |
| `sig` | grid | `1` if `q <= fdr_q`, else `0`. |
| `r1` | grid | Lag-1 autocorrelation of the residuals. |
| `n` | grid | Months used. |
| `flip_hpa` | per lat | Pressure where the trend turns from positive below to negative above. |
| `global` | object | Same keys per level for the area-weighted global mean, plus one `flip_hpa`. |

## series/{dataset}/{variable}/lat_{NN}.json and global.json

`anom`: `[level][month]` anomalies. Months start at `datasets[].time.start` and run
for `time.n` months with no gaps. `NN` is the two-digit index into `lat_centers`.

## agreement/{variable}/{a}__{b}__{mask}.json

Compared over the `airs_era` period on the levels both datasets share.

| Key | Meaning |
|---|---|
| `levels_hpa` | The shared levels. |
| `status` | `0` neither significant, `1` both significant with the same sign, `2` only one significant, `3` both significant with opposite signs. |
| `ci_overlap` | `1` if the two confidence intervals overlap. |
| `diff` | Slope of `a` minus slope of `b`. |

## Intermediate format (not read by the site)

`data/zonal/{dataset}_{variable}.nc`: one variable `value(time, level, lat)`, monthly
time, level in hPa, lat as band centre. Attribute `synthetic` is `"true"` or `"false"`.
Both `fetch.py` and `synthetic.py` write this, so everything after it is identical.
