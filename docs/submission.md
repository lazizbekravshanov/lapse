# Submission draft

Challenge: Be An Earth System Trend Detective! (2026 NASA Space Apps, Cincinnati)
Team: Lapse

## Summary (150 words)

Most trend tools look at the surface of the Earth. Lapse looks at the whole column
of air above it. Using 24 years of NASA's AIRS satellite record and 46 years of the
MERRA-2 reanalysis, it shows how temperature, water vapor and ozone are changing at
every height from the ground to about 65 km, and labels every trend with one of four
plain verdicts: Clear change, Likely change, Not proven yet, or Disputed. The labels
come from rules, not opinion: a statistical test, a second independent dataset, a
check that removes volcano months, and a check for jumps when a data source changed.
The headline result is one cause with opposite trends: the lower atmosphere is
warming while the upper atmosphere is cooling, and the direction flips near 19 km.
A visitor gets that answer in one sentence, sees the chart that proves it, and can
open the exact numbers.

## How it meets the challenge objectives

| Objective in the challenge | What Lapse does |
|---|---|
| Identify variables of interest | Three questions (where, how high, what) lead to air temperature, water vapor or ozone. Every variable has a one-line definition. |
| Acquire the data for a region | Whole globe, five regions, or any five-degree ring around the Earth, at up to 42 heights. |
| Generate and visualize a time series | A month-by-month history for any place and height, with known events shaded. |
| Rate of change and significance | Theil-Sen slope with a 95% range, Mann-Kendall test with memory correction, false discovery control, shown as four plain labels. |

The challenge also suggests demonstration examples and simple definitions. Lapse has
three guided case files and a "Words we use" section on every page.

## What is new

- **Height.** The challenge text mentions trends at "levels of the atmosphere". We found
  no public entry that works on them.
- **Same process, opposite trends.** The challenge's central idea, shown in one column of
  air and found automatically in a list of opposite pairs.
- **Labels that can say "we don't know".** "Not proven yet" and "Disputed" are first-class
  answers, with the reason given.
- **It caught a known data problem by itself.** The jump check flags MERRA-2 above about
  40 km, where its record steps by several degrees when its input satellites changed.

## Data

| Product | Provider | Use |
|---|---|---|
| AIRS3STM v7.0, monthly, 1°, 24 pressure levels | NASA GES DISC | Air temperature, Sept 2002 to Sept 2026 |
| M2IMNPASM v5.12.4 (MERRA-2), monthly, 42 pressure levels | NASA GMAO / GES DISC | Temperature, water vapor, ozone, Jan 1980 to Sept 2026 |

Access: NASA CMR catalog and OPeNDAP, with an Earthdata login.

## Validation

See `docs/validation.md`. Five published results were checked on the same years and
heights. Four match. The fifth (a 37-year layer total from MERRA-2) has the same
direction but a larger size, at heights where our own jump check distrusts MERRA-2.

## Limits we state on the site

- Values are averages around the whole Earth, not local.
- A trend shows what changed, not why. The one cause we name is cited.
- Kilometres are converted from pressure and are approximate.
- MERRA-2 water vapor is shown only up to about 16 km.

## Prepared before the event

Fill in honestly before submitting: what was set up before the hackathon started
(repository scaffold, download code, statistics, first version of the site) and what
was built during it.

## Use of AI tools

Fill in according to the event rules.

## Links

- Code: https://github.com/lazizbekravshanov/lapse
- Site: add the GitHub Pages address once Pages is turned on.
