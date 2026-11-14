# Prior art

Checked on 13 Nov 2026. About 20 public repositories for this challenge were found.
None works on trends by height. This list is what is visible in public, not the full field.

## Common to almost every public entry

- A globe or map, Mann-Kendall test, Sen's slope.
- False discovery rate control and an autocorrelation correction (at least seven teams).
- An AI narrator limited to computed numbers.
- NASA POWER as the data source, surface variables only.

## Entries worth reading

| Repo | Angle |
|---|---|
| [entitySource/trend_detective](https://github.com/entitySource/trend_detective) | Global map, 15 variables, Monte Carlo checks of the test |
| [Buyja047/earth_trending](https://github.com/Buyja047/earth_trending/pull/1) | Mongolia, live screen of about 1,300 variables, "year detectable", step tests |
| [SeytekM/Nasa_crack](https://github.com/SeytekM/Nasa_crack) | Evidence board of 19 tests, years to significance |
| [Ommps246/spacejammers-casefiles](https://github.com/Ommps246/spacejammers-casefiles) | Solved cases with counter-arguments |
| [Tenstral/nasa-2026-earth-detective](https://github.com/Tenstral/nasa-2026-earth-detective) | GRACE water storage, bootstrap intervals |
| [samir11441S/EarthScope](https://github.com/samir11441S/EarthScope) | Independent ERA5 cross-check |

## Existing professional tools

- NASA Giovanni: time series and maps for 2,000+ variables, including vertical profiles.
- NOAA STAR and Remote Sensing Systems: trend maps for four broad atmospheric layers.
- NOAA PSL reanalysis tool: vertical profiles and height-by-time plots.

None of these takes a question, tests the trend at every height on NASA data, and
explains the answer in plain language.

## Science to reproduce

- Santer et al. 2023 (PNAS): including the 25 to 50 km layer makes the human
  fingerprint about five times easier to detect.
- JPL AIRS trend visualisations, 2002 to 2020: warming in the lower troposphere,
  strong cooling in the upper stratosphere.
- Stocker et al. 2024: the Hunga eruption cooled the tropical middle stratosphere
  by up to 4 K until mid 2023.
