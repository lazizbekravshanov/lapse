# Lapse

[![Tests](https://github.com/lazizbekravshanov/lapse/actions/workflows/tests.yml/badge.svg)](https://github.com/lazizbekravshanov/lapse/actions/workflows/tests.yml)

**What is changing in the atmosphere, at which height, and is it real?**

**Live site: https://lapse-earth.vercel.app**

Most trend tools look at the surface. Lapse looks at the whole column of air, from the
ground to about 65 km up, and tests the trend at every height.

The headline case: rising CO2 warms the lower atmosphere and cools the upper atmosphere.
One cause, opposite trends, in the same column of air.

Built for the 2026 NASA Space Apps Challenge, "Be An Earth System Trend Detective!".
Not affiliated with NASA.

> **Status:** running on real NASA data. AIRS: 289 months, 2002 to 2026. MERRA-2: 560 of 561
> months, 1980 to 2026. No synthetic data is on the site. The reduced data is in this
> repository, so `make verify` recomputes every published number with no NASA login.
> GitHub reruns the tests and that comparison on every push (the badge above).

## What the data says

Averaged over the whole globe, AIRS satellite record, 2002 to 2026:

| Height | Change per ten years | Label |
|---|---|---|
| Near the ground | +0.20 °C | Clear change |
| About 8 km | +0.27 °C | Clear change |
| About 21 km | -0.07 °C | Not proven yet |
| About 32 km | -0.59 °C | Clear change |

The direction flips at about 19 km. Our upper-level cooling for 2003 to 2012 is -0.65 K per
decade; the published value for the same years and heights is -0.65 ± 0.11
([docs/validation.md](docs/validation.md)).

## How it is built

Three layers, and two doors into the middle one ([docs/architecture.md](docs/architecture.md)):

| Layer | Where | Job |
|---|---|---|
| **Backend** | `pipeline/lapse/backend/` | Data (NASA download), operations (trends, tests, checks), actions (export, validate). |
| **Hub** | `pipeline/lapse/hub/` | Every tool in one catalog. The user picks a data source and a method, or leaves it on Auto. One request shape in, one answer shape out. |
| **Frontend** | `web/` | The door for people: the toolbox, the charts and the answer in plain language. |
| **Agent** | `pipeline/lapse/agent/` | The door for questions in your own words, and for other AI assistants. It can only call the hub's read-only tools, and no number reaches the reader unless a tool produced it. |

```bash
python -m lapse tools                              # everything the hub offers
python -m lapse ask --where arctic --km 32         # Auto picks the tools
python -m lapse ask --where global --km 1 --method yearly
python -m lapse agent "Is the Arctic warming?"     # plain words; works with no API key
python -m lapse mcp                                # the same tools for Claude or any MCP client
```

## Ask in your own words

```
$ python -m lapse agent "What is happening 32 km up?"
Averaged over the whole globe, about 32 km up (10 hPa): Clear change. The air is cooling:
-0.59 °C per ten years, very likely between -0.71 and -0.47. [...]

Read from:
  AIRS3STM v7.0  web/data/trend/airs/t/full__none__robust.json
Number check: passed. Every number above is in the files listed.
```

The agent answers only from the NASA records. With a key for Claude, Gemini or another model
it writes freer sentences; a number guard rejects any figure that no tool produced. Without
a key it answers by rule. The ask box on the live site runs on Google's `gemini-2.5-flash`. Off-topic questions get a polite no. See [docs/agent.md](docs/agent.md).

## What you see

| Part | What it does |
|---|---|
| **The ascent** | Scroll, drag the column or press Play, and the page rises from the ground to the top of the record. The height, the rate and its label change as you climb, and the colour follows the direction: warm below, cool above. |
| **Guess first** | One question before the climb: which is changing faster, the warming below or the cooling above? The reply gives both rates. |
| **Above you** | Share a location or type a city, and the climb replays for the band of sky at that latitude. The location stays in the browser. |
| **Ask the data** | A question box. The answer is written only from the NASA results, and every number is checked against them before it is shown. |
| **Three cases** | Guided demos: one cause with opposite trends, a volcano in the record, a jump in the data source. |
| **The evidence** | Three views of the same measurements: every latitude and height at once, every height at one place with its likely range and a second dataset, and the month-by-month history with known events shaded. |
| **Opposite directions** | A list of places where one part of the air rises while another falls. |
| **Investigate it yourself** | Every data source, method and check in one place. Pick your own or leave it on Auto, and see whether the method changes the answer. |

## The four labels

| Label | Rule |
|---|---|
| **Clear change** | Two independent datasets both pass the test, same direction, overlapping ranges. |
| **Likely change** | One dataset passes the test and nothing contradicts it. |
| **Not proven yet** | The change cannot be told apart from chance. This is not "no change". |
| **Disputed** | The second dataset proves the opposite, the trend depends on volcano months, or the record jumps when its data source changed. |

## Quick start

```bash
make setup     # install
make test      # 88 tests
make verify    # recompute every published number from data/zonal and compare
make ask       # talk to the agent (no API key needed)
make demo      # synthetic data -> web/data  (about a minute)
make serve     # the site with its ask box, http://localhost:8000
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
python -m lapse validate                    # compare with published results
```

Downloads are resumable: every month is cached, so rerunning continues where it stopped.

| Dataset | NASA product | Record | Role |
|---|---|---|---|
| AIRS | AIRS3STM v7.0, monthly, 24 levels | Sept 2002 on | Satellite witness |
| MERRA-2 | M2IMNPASM v5.12.4, monthly, 42 levels | 1980 on | Long record, three variables |

## How the numbers are made

1. Remove the seasonal cycle: each month minus that calendar month's average.
2. **Slope and test:** the chosen method. Robust (Theil-Sen with Mann-Kendall) is the default.
   Classic (least squares with a t-test) and Year by year (annual means) are the other sound ones.
3. **Memory:** every sound method allows for month-to-month memory. On made-up records with no
   trend they raise a false alarm 3 to 8 times in 100; the plain textbook test does 30 to 65.
4. **Many cells at once:** Benjamini-Hochberg false discovery rate of 0.05.
5. **Second dataset:** AIRS and MERRA-2 are compared wherever they share years and heights.
6. **Volcano check:** every trend is recomputed without the months after big eruptions.
7. **Jump check:** at documented data-source changes, the two-year shift is compared with
   every other two-year shift in the record.
8. One of four labels is assigned by rule in `pipeline/lapse/backend/operations/verdict.py`.

All statistics live in `pipeline/lapse/` and are tested in `pipeline/tests/`.
The website does no statistics of its own.

## Layout

```
pipeline/lapse/config.py                 datasets, variables, regions, events, label words
pipeline/lapse/backend/data/             fetch.py (NASA catalog + OPeNDAP), cubes.py, synthetic.py
pipeline/lapse/backend/operations/       stats.py (methods, tests, jump check), verdict.py (label rules)
pipeline/lapse/backend/actions/          export.py (cubes -> web/data), validate.py
pipeline/lapse/hub/registry.py           the tool catalog: methods and checks in plain words
pipeline/lapse/hub/router.py             resolves a request, reads back the answer
pipeline/lapse/agent/                    tools.py, guard.py, harness.py, planner.py, models.py, mcp_server.py
data/zonal/                              the four reduced NASA cubes every number is computed from
web/                                     static site, no build step
web/content/glossary.json                the plain words, landmarks and layer names
docs/                                    architecture, data contract, validation, plan, submission, pitch
```

## Limits

- Latitude bands are averages around the whole globe, so east-west differences are hidden.
- MERRA-2 jumps when its input satellites change, most of all above about 40 km. The jump check flags it.
- MERRA-2 water vapor is only shown up to about 8 km (300 hPa), the height up to which it takes in
  humidity measurements (Davis et al., Atmos. Chem. Phys., 2017).
- We read every 2nd grid point of AIRS and every 4th of MERRA-2 before averaging. Day and night
  satellite passes count equally. One MERRA-2 month (June 1998) is missing.
- Heights in km are approximate conversions from pressure.
- A trend line describes the record. It does not say the change is steady or will continue.

## Use of AI

Most of the code and text in this repository was written with an AI coding assistant, directed
and checked by the team. The ask box uses a language model at run time, held to read-only tools
and a number check ([docs/agent.md](docs/agent.md)). No number on the site is written by an AI:
each one is computed by the tested pipeline from NASA data, and `make verify` recomputes them
all. The full statement is in [docs/submission.md](docs/submission.md).
