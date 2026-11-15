# Data contract (schema 4)

The backend writes these files into `web/data/`. The hub's router and the website
both read them, plus `web/content/glossary.json`, and nothing else. The website never computes a trend,
a range or a label.

All grids are `[level][lat]`: the outer list follows `levels_hpa` of the dataset,
the inner list follows `lat_centers`. Missing values are `null`.

`python -m lapse export` deletes and rewrites `trend/`, `series/` and `pairs/`
on every run, so no stale file survives.

## catalog.json (the hub's tool catalog)

| Key | Meaning |
|---|---|
| `methods[]` | `id`, `label`, `plain`, `science`, `sound`, `recommended`, `caution`. Every method answers in the same form. |
| `checks[]` | `id`, `label`, `plain`, `science`. Checks that run whatever method is chosen. |
| `sound_methods` | Ids of the methods that count toward agreement. |
| `defaults` | The choices Auto makes: `method`, `mask`, and `auto` for `dataset` and `period`. |
| `auto` | Plain-language rule for each automatic choice. |
| `routes` | Path templates: `trend`, `pairs`, `series_region`, `series_lat`. Clients build paths from these. |

A request is `{dataset, variable, period, mask, method, place, height}`. Its answer is at
`routes.trend` filled with the first five. "Auto" is decided once, by
`lapse.hub.registry.auto_choices`, and published as `manifest.auto`. The router, the website
and the agent tools all read that and never work it out again.

## manifest.json

| Key | Meaning |
|---|---|
| `schema` | Contract version. Now `4` (added `auto`). |
| `synthetic` | `true` if any cube was synthetic. The site must show a banner. |
| `method` | `alpha`, `fdr_q`, slope and test names, `event_check_mask`, `event_change_limit`, `jump_share`. |
| `lat_centers`, `lat_step` | Latitude band centres in degrees, and the band width. |
| `regions[]` | `id`, `label`, `lat` (south and north edge), `phrase` (how a sentence starts). `global` is first. |
| `verdicts[]` | `code`, `id`, `label`, `meaning`. The label words shown on the site. |
| `reasons[]` | `code`, `id`, `text`. Why a cell got its label. |
| `masks[]` | `id`, `label`, `exclude` (event ids whose months are dropped). |
| `events[]` | `id`, `label`, `start`, `end`, `kind` (`volcano` or `data_change`), `explain`, optional `datasets` (only these datasets are affected). |
| `datasets[]` | `id`, `label`, `kind`, `note`, `source`, `levels_hpa`, `alt_km`, `time {start, end, n}`, `periods[]`, `variables[]`. |
| `datasets[].periods[]` | `id`, `label`, `start`, `end`, `years`. Only periods that cover different years are listed. |
| `datasets[].variables[]` | `id`, `label`, `explain`, `relative`, `units`, `trend_units`, `units_plain`, `trend_units_plain`, `limit_note`. |
| `witness[]` | `dataset`, `variable`, `period`, `with_dataset`, `with_period`: the second dataset that covers the same years. |
| `auto` | For each variable id: `dataset` (the one Auto picks) and `periods` (for each dataset that measures it, the years Auto picks). |

## Verdict codes

| Code | Label | Rule |
|---|---|---|
| 2 | Clear change | This dataset passes the test. The second dataset passes with the same sign and overlapping ranges. |
| 1 | Likely change | This dataset passes the test and nothing contradicts it, but the second dataset has not fully confirmed it. |
| 0 | Not proven yet | This dataset does not pass the test. |
| 3 | Disputed | The second dataset proves the opposite, or the trend changes by more than half without volcano months, or the record jumps at a data-source change and the jump explains at least half the total change. |

## Reason codes

| Code | Id | Leads to |
|---|---|---|
| 0 | `fails_test` | Not proven yet |
| 1 | `both_agree` | Clear change |
| 2 | `witness_agrees_weakly` | Likely change |
| 3 | `witness_unsure` | Likely change |
| 4 | `no_witness` | Likely change |
| 5 | `size_differs` | Likely change |
| 6 | `opposite_sign` | Disputed |
| 7 | `event_sensitive` | Disputed |
| 8 | `data_change` | Disputed |
| 9 | `witness_jumps` | Likely change |

## trend/{dataset}/{variable}/{period}__{mask}__{method}.json

| Key | Shape | Meaning |
|---|---|---|
| `method` | text | The method id that produced this file. |
| `span` | object | `start`, `end`, `years` actually covered. |
| `slope` | grid | Trend per decade. |
| `lo`, `hi` | grid | 95% range of the slope. |
| `p`, `q` | grid | p-value after the memory correction, and its false discovery rate q-value. |
| `sig` | grid | `1` if `q <= fdr_q`, else `0`. |
| `r1`, `n` | grid | Month-to-month memory of the residuals, and months used. |
| `verdict`, `reason` | grid | Codes from the two tables above. |
| `agree` | grid | How many sound methods pass the test with the same sign as this file. |
| `step` | grid | Only for datasets with data-source changes: the largest jump at such a change. |
| `flip_hpa` | per lat | Pressure where the trend turns from positive below to negative above. |
| `regions` | object | One entry per region id. Same keys, each a list per level, plus one `flip_hpa`. |

## series/{dataset}/{variable}/lat_{NN}.json and region_{id}.json

`anom`: `[level][month]` values compared with normal for that month. Months start at
`datasets[].time.start` and run for `time.n` months with no gaps.

## pairs/{dataset}/{variable}/{period}__{method}.json

Places where two "Likely" or "Clear" trends point in opposite directions (mask `none`).

| Key | Meaning |
|---|---|
| `vertical[]` | Same place, two heights. `where` is `{region}` or `{lat}`. `low` and `high` hold `level`, `hpa`, `slope`, `verdict`. |
| `horizontal[]` | Same height, two latitude bands. `level`, `hpa`, and `a`, `b` with `lat`, `slope`, `verdict`. |
| `score` | The smaller of the two trend sizes. Lists are sorted by it. |

## validation.json

Written by `python -m lapse validate`. `rows[]`: `id`, `source`, `finding`, `dataset`,
`years`, `levels_hpa`, `ours`, `p`, `match`. Also written as `docs/validation.md`.

## web/content/glossary.json (hand-written)

`terms[]` (`id`, `plain`, `science`, `explain`), `layers[]` (`from_km`, `to_km`, `plain`,
`science`), `landmarks[]` (`km`, `label`). The site draws the height axis from it.

## Intermediate format (not read by the site)

`data/zonal/{dataset}_{variable}.nc`: one variable `value(time, level, lat)`, monthly
time, level in hPa, lat as band centre. Attribute `synthetic` is `"true"` or `"false"`.
Both `fetch.py` and `synthetic.py` write this, so everything after it is identical.
