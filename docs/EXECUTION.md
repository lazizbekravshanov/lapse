# Lapse execution plan

**Target: feature complete by Saturday 14 Nov, 18:00 ET. Sunday is for the pitch only.**

This plan is written so one person or one coding agent can execute it top to bottom.
Each task has a goal, the files it touches, steps, and checks that must pass before
the task is called done. Do the tasks in order. Commit after every task.

---

## Status: Saturday 14 Nov, early morning

| Task | State | Note |
|---|---|---|
| T1 Real AIRS on the site | Done | 289 months, no gaps |
| T2 MERRA-2 and the second-dataset check | Done | 560 of 561 months. June 1998 failed to download; rerun `python -m lapse fetch merra2` once to fill it |
| T3 Verdict ladder | Done | Rules refined after seeing real data, see T3 |
| T4 Plain-language layer | Done | Words live in `web/content/glossary.json` and `pipeline/lapse/config.py` |
| T5 Guided start | Done | Three questions, shareable address for every view |
| T6 Case files and validation | Done | `docs/validation.md`, five published results checked |
| T7 Methods page | Done | `web/methods.html` |
| T8 Deploy | Done | Live at https://lazizbekravshanov.github.io/lapse/. Every push to main that changes `web/` redeploys |
| T9 Submission pack | Drafted | `docs/submission.md`, `docs/pitch.md`. Video is the owner's |
| T10 User tests | Open | Needs three people. Sheet in `docs/user-tests.md` |
| T11 Opposite-pair finder | Done | Listed under the charts |
| T12 Phone layout and keyboard | Done | One column under 860 px, arrow keys on both charts |
| T13, T14 | Not started | Stretch only |

### Added Saturday evening: three layers and the hub

The project is now organised as backend -> hub -> frontend (see `docs/architecture.md`).

| Piece | State |
|---|---|
| Backend split into `data`, `operations`, `actions` | Done |
| Hub registry: 2 data sources, 4 methods, 4 checks, described in plain words | Done |
| Hub router: resolves "auto", reads the published answer, `python -m lapse ask` | Done |
| Every method precomputed for every view (schema 3, `catalog.json`) | Done |
| Frontend toolbox, Auto, and "does the method change the answer?" table | Done |
| 38 tests at the time, including false-alarm rates for every method | Pass |

### Added Saturday night: backend hardening and the agent door

| Piece | State |
|---|---|
| The four reduced NASA cubes committed (`data/zonal`, about 11 MB) | Done |
| `python -m lapse verify`: recompute every published number and compare | Done. 3.7 million numbers, 0 differences |
| GitHub runs the tests and `verify` on every push (`.github/workflows/tests.yml`) | Written |
| Auto rules in one place (`registry.auto_choices` -> `manifest.auto`, schema 4) | Done |
| Water vapor limit lowered from 16 km to 8 km, with the published reason | Done |
| Limits named on the methods page: grid thinning, missing spots, the missing month, the jump check | Done |
| Agent: 11 read-only tools over the hub (`pipeline/lapse/agent/tools.py`) | Done |
| Number guard: no number reaches the reader unless a tool produced it | Done |
| Harness with a no-model fallback, `python -m lapse agent` | Done. Works with no API key |
| MCP server, `python -m lapse mcp` | Done. Checked with the official MCP client |
| Adapters for Claude and OpenAI-style servers | Written. Not yet run against a live model |
| 85 tests | Pass |

### Added late Saturday: new front page, ask box, Vercel

| Piece | State |
|---|---|
| Front page rebuilt around the finding: headline, three figures, the sky column | Done |
| Light, minimal style on both pages | Done |
| Ask box on the site (`api/ask.py`, same harness and number guard) | Done. Checked locally in a browser, rule mode |
| Gemini preset (`GEMINI_API_KEY`, default `gemini-2.5-flash`) | Written. Not yet run against the live API |
| Vercel | Live at https://lapse-earth.vercel.app. Site, data and the ask function all work. Every push to main redeploys |
| 87 tests | Pass |

Open for the owner: run the agent once with a real model key; fill June 1998
(`python -m lapse fetch merra2 && python -m lapse export`).

What the methods say on real data (AIRS, whole globe): all three sound methods agree at 16
of 24 heights, and at every height from 25 km to 41 km. The textbook method flags 607 of
862 cells where the sound methods flag 324 to 424.

### What the real data showed

- **AIRS, whole globe, 2002 to 2026:** warming of +0.24 °C per ten years near 1 km and +0.27 near 8 km,
  cooling of -0.59 near 32 km. The direction flips at about 19 km. Of 24 heights: 12 "Clear change",
  7 "Likely change", 5 "Not proven yet", 0 "Disputed".
- **Both datasets agree** on warming below about 10 km and cooling from about 25 km to 32 km.
- **Our number matches the literature:** above 6 hPa, 2003 to 2012, we get -0.65 K per decade.
  The published value is -0.65 ± 0.11.
- **MERRA-2 jumps high up.** At about 41 km its record drops 2.7 °C in one step when its data source
  changed in 2004. The jump check labels those heights "Disputed" without being told where to look.
- **The 2022 volcano does not explain the cooling.** In the southern middle latitudes at 32 km the trend
  moves from -0.77 to -0.70 without the Hunga months.
- **Water vapor** is shown only up to about 8 km (300 hPa). MERRA-2 takes in humidity measurements
  only up to there (Davis et al., 2017, Table 2).

---

## 0. Mission

Lapse answers one question for people with no science background:

> **What is changing in the atmosphere, at which height, and how sure are we?**

Challenge: 2026 NASA Space Apps, "Be An Earth System Trend Detective!".
Audience named by the challenge: high school and college students, and the public
with some science background.

### Definition of done

- [ ] The site runs on real NASA data only. No synthetic banner.
- [ ] A first-time visitor gets a correct one-sentence answer in under 30 seconds.
- [ ] Every number on the site traces to a file written by the pipeline.
- [ ] Two independent datasets are compared, and disagreements are shown, not hidden.
- [ ] Three case files work as guided demos.
- [ ] A validation table compares our numbers with published science.
- [x] The site is deployed at a public URL: https://lazizbekravshanov.github.io/lapse/
- [ ] The submission text, a 30-second pitch and a demo video script exist.

---

## 1. Rules that do not bend

| Rule | Why |
|---|---|
| Statistics are computed only in `pipeline/lapse/`. The website never calculates a trend, a p-value or a verdict. | One source of truth. Judges can audit it. |
| Never show synthetic and real data together. If any cube is synthetic, the banner shows. | Trust. |
| "Not significant" is always worded as "not proven", never "no change". | It is the correct reading of the test. |
| No cause is stated unless a cited paper supports it. | A trend shows what changed, not why. |
| Plain words first, the science term beside it in small text. | The audience. |
| Never commit a token, a `.netrc` or a `.env`. | Credentials. |
| `make test` passes before every commit. | No broken main during the weekend. |
| One task, one commit. Message says what changed and why. | Easy to revert. |
| Commits use the repo owner's identity. No tool attribution lines. | Owner's standing rule. |

---

## 2. Where things stand (Friday night)

### Working

- Pipeline: catalog search, download, month cache, zonal cubes, statistics, JSON export.
- Website: curtain, profile, history, verdict sentence, three demo cases, event shading,
  two-dataset comparison.
- 16 tests pass.
- **Real AIRS temperature is downloaded: 289 months, Sept 2002 to Sept 2026, no gaps,
  99.75% of cells filled.**
- MERRA-2 download is in progress (561 months, three variables).

### First real result (AIRS, global mean, Sept 2002 to Sept 2026)

Computed by the pipeline from the real cache on 13 Nov. Not yet on the site.

| Height | Level | Trend, K per decade | 95% range | Passes test |
|---|---|---|---|---|
| ~1 km | 925 hPa | +0.24 | +0.16 to +0.31 | Yes |
| ~4 km | 600 hPa | +0.13 | +0.07 to +0.20 | Yes |
| ~8 km | 300 hPa | +0.27 | +0.17 to +0.36 | Yes |
| ~13 km | 150 hPa | +0.02 | -0.16 to +0.20 | No |
| ~21 km | 50 hPa | -0.07 | -0.22 to +0.10 | No |
| ~27 km | 20 hPa | -0.46 | -0.54 to -0.38 | Yes |
| ~32 km | 10 hPa | -0.59 | -0.71 to -0.47 | Yes |
| ~41 km | 3 hPa | -0.80 | -0.94 to -0.65 | Yes |
| ~48 km | 1 hPa | -0.63 | -0.72 to -0.53 | Yes |

- The sign flips at about 63 hPa, roughly 19 km.
- 424 of 862 curtain cells pass the false discovery test.
- Leaving out the Hunga months (2022 to 2023) changes the upper-level trends by
  only 0.01 to 0.04 K per decade. The cooling is not a volcano artefact.
- Surface warming is strongest in the Arctic: +0.90 K per decade at 77.5°N.

### Things in the real data that need a look

| Observation | What to do |
|---|---|
| The global profile is jagged: +0.05 at 500 hPa between +0.13 and +0.14, and -0.34 at 7 hPa between -0.59 and -0.48. | Check against MERRA-2 at the same levels. If MERRA-2 is smooth, label these levels "disputed". Do not smooth them away. |
| Tropical 100 hPa shows warming of about +0.4 K per decade. | Compare with MERRA-2. Mention in limits if they disagree. |
| 1000 hPa is empty at the South Pole band. | Expected: the ice sheet is above that pressure level. Show as "below ground". |

---

## 3. Architecture in one picture

```
NASA CMR catalog --> OPeNDAP subset --> data/cache/{dataset}/{var}_{YYYY-MM}.npz
                                              |
                                              v
                                 data/zonal/{dataset}_{var}.nc     (time, level, lat band)
                                              |
                              stats.py: deseasonalize, Sen slope,
                              Mann-Kendall with memory correction, FDR
                                              |
                                              v
                                   web/data/*.json  (docs/data-contract.md)
                                              |
                                              v
                                   web/  static site, no build step
```

Commands:

```bash
make setup         # install
make test          # all tests
make demo          # synthetic data, for development only
make data          # real download, then export (needs EARTHDATA_TOKEN)
python -m lapse export    # recompute trends from the cubes already on disk
make serve         # http://localhost:8000
```

---

## 4. Tasks

Priority: **P0** must ship, **P1** should ship, **P2** only if P0 and P1 are done.
Time is working time for one focused builder.

### T1. Put real AIRS on the site (P0, 45 min)

**Goal:** the deployed site shows real data even if MERRA-2 is not finished.

**Files:** `pipeline/lapse/export.py`, `web/src/main.js`, `web/data/`

**Steps**
1. Remove any synthetic cubes from `data/zonal/` so only real cubes are exported.
2. Run `python -m lapse export`.
3. In `main.js`, make the demo cases fall back to whichever dataset exists, and hide a
   case button if it cannot work with the data on hand.
4. Hide the "Compare with the other dataset" control when there is only one dataset.
5. Fix the "Mean of empty slice" warning in `stats.deseasonalize` (all-missing cells).

**Checks**
- [ ] `web/data/manifest.json` has `"synthetic": false`.
- [ ] The global profile on the site matches the table in section 2 to two decimals.
- [ ] No console errors. No dead buttons.

### T2. Bring in MERRA-2 and the two-witness check (P0, 60 min plus download time)

**Goal:** a second, independent dataset on the same screen.

**Files:** `pipeline/lapse/config.py`, `pipeline/lapse/export.py`, `web/src/*`

**Steps**
1. When the download ends, run `python -m lapse assemble merra2`, then `export`.
2. Sanity-check one month by hand: surface tropics near 299 K, tropical 100 hPa near
   192 K, the same values AIRS gave for January 2024.
3. Confirm levels below the ground are missing, not zero.
4. Check water vapor and ozone are positive everywhere and the units make sense.
5. Turn the comparison overlay on by default for temperature.

**Checks**
- [ ] `agreement/t/merra2__airs__none.json` exists and is built from real data.
- [ ] A short note in `docs/validation.md` on where the two datasets agree and where
      they do not, by height.

**If the download is slow:** export with AIRS alone (T1) and keep going. Rerun the
export when MERRA-2 lands. Nothing else waits on it.

### T3. The verdict ladder (P0, 90 min)

**Goal:** every cell and every profile level gets one of four labels, chosen by rule.

**Files:** `pipeline/lapse/verdict.py` (new), `pipeline/lapse/export.py`,
`pipeline/tests/test_verdict.py` (new), `docs/data-contract.md`, `web/src/*`

**Rules** (A is the dataset on screen, B is the second dataset over the same years)

| Code | Label | Rule |
|---|---|---|
| 2 | Clear change | A passes the test. B passes with the same sign, and the two ranges overlap. |
| 1 | Likely change | A passes and nothing contradicts it: B agrees in sign without passing, or B cannot tell, or B has no data here, or B agrees in direction but not in size, or B itself jumps at a data-source change. |
| 3 | Disputed | B passes with the opposite sign. Or A changes by more than half (or flips) when volcano months are left out. Or A's record jumps at a data-source change, the jump is unusual for the series, and it explains at least half the total change. |
| 0 | Not proven yet | A does not pass the test. |

Changed from the first draft after seeing real data: a disagreement about size alone is
"Likely", not "Disputed", and the data-source jump rule was added because MERRA-2 jumps by
several degrees above 40 km.

**Steps**
1. Write `verdict.py` as a pure function over arrays. No file access inside it.
2. Add a `verdict` grid and a `verdict_reason` grid to each trend file. Reasons are
   short codes: `both_agree`, `one_witness`, `no_witness`, `opposite_sign`,
   `ranges_apart`, `event_sensitive`, `fails_test`.
3. Bump `schema` to 2 in the manifest and document the new keys in the contract.
4. On the site, draw the four labels as four patterns, not only four colours.
5. The verdict sentence uses the label words exactly as written above.

**Checks**
- [ ] One unit test per rule, plus one test that every cell gets exactly one code.
- [ ] No verdict logic in any `.js` file.

### T4. Plain-language layer (P0, 90 min)

**Goal:** a visitor never needs to know what hPa, Kelvin or an anomaly is.

**Files:** `web/content/glossary.json` (hand-written, outside the generated folder), `web/src/*`, `web/index.html`

**Steps**
1. Height axis shows km first, hPa second in small text.
2. Add landmarks on the height axis: Mount Everest (about 9 km), airliner cruise
   (about 11 km), ozone layer (about 25 km), weather balloon limit (about 35 km).
3. Name the two layers in words on the curtain: "the weather layer" and "the calm
   layer above it", with the science names beside them.
4. Show the total change over the record next to the per-decade rate.
5. A "Words we use" section on every page, read from `glossary.json`.

**Glossary (use these words everywhere)**

| Science term | Words on the site |
|---|---|
| Pressure level | Height |
| K per decade | Degrees per ten years |
| Anomaly | Compared with normal for that month |
| Statistically significant | Too consistent to be chance |
| Not significant | Not proven yet |
| Confidence interval | The true value is very likely between X and Y |
| Troposphere | The weather layer |
| Stratosphere | The calm layer above |
| Reanalysis | A weather model corrected by real measurements |

**Checks**
- [ ] Read every sentence on the site aloud. No undefined term.
- [ ] The words in the glossary table appear exactly as written.

### T5. Guided start (P0, 60 min)

**Goal:** the challenge asks for a short series of questions that lead to the data.

**Files:** `web/index.html`, `web/src/start.js` (new)

**Steps**
1. Three questions, each with tap-to-choose answers:
   - Where? Whole globe, tropics, middle latitudes, Arctic, Antarctic.
   - How high? Near the ground, the weather layer, the calm layer above, everything.
   - What? Temperature, water vapor, ozone.
2. Answers set the same state the controls already use. No new data paths.
3. A "skip, let me explore" link.
4. The state lives in the URL, so any view can be shared as a link.

**Checks**
- [ ] Every combination of answers lands on a view with data and a verdict sentence.
- [ ] Reloading a shared URL shows the same view.

### T6. Case files and validation (P0, 75 min)

**Goal:** three demos that teach, and proof that our numbers match the literature.

**Files:** `web/src/cases.js` (new), `docs/validation.md` (new)

**Case files** (each: one question, three steps, one verdict)

| Case | Question | What the visitor sees |
|---|---|---|
| One cause, opposite trends | Is the whole atmosphere warming? | Warming below, cooling above, the flip height |
| A volcano in the record | Did the 2022 eruption cause the cooling? | The history chart with and without the Hunga months |
| When the data source jumps | Can a trend be fake? | A MERRA-2 upper level where the series steps at 1998 or 2004, and AIRS for comparison |

**Validation table:** generated by `python -m lapse validate` into `docs/validation.md`.
Five published results are checked on the same years and heights. Four match. The fifth
(a layer total from MERRA-2) has the same direction and a larger size.

**Checks**
- [ ] Every case runs start to finish by clicking "Next" only.
- [ ] Every row of the validation table has a number from our pipeline.
- [ ] Differences in years or method are stated in the table, not hidden.

### T7. Methods and limits page (P0, 30 min)

**Files:** `web/methods.html` (new)

One page, plain language, five short sections: where the data comes from, how a
trend is measured, how we test it, what the four labels mean, what this tool cannot
tell you. Link to the repo and to both NASA dataset pages.

**Checks**
- [ ] Linked from every screen.
- [ ] States that latitude bands average around the whole globe.

### T8. Deploy (P0, 20 min)

**Files:** `.github/workflows/pages.yml` (new)

**Steps**
1. Add a GitHub Pages workflow that publishes the `web/` folder on every push to main.
2. **Owner action:** in the repo settings, set Pages to "GitHub Actions".
3. Put the public URL in the README and the team page.

**Checks**
- [ ] The public URL loads on a phone in under 3 seconds on mobile data.
- [ ] Data size check: if `web/data` is over 25 MB, round series to one decimal.

### T9. Submission pack (P0, 60 min)

**Files:** `docs/submission.md` (new), `docs/pitch.md` (new)

- Project summary, 150 words.
- How it addresses the four objectives in the challenge text, one line each.
- Data used, with product names and versions.
- What was prepared before the event started.
- 30-second pitch: one case, one sentence, one chart.
- 2-minute demo script, click by click.
- How AI tools were used, if the event rules ask for it.

### T10. Test with real people (P0, 30 min, needs humans)

Three people with no science background. Thirty seconds on the site, then two questions:

1. What is happening to the air?
2. How sure are we?

Write their answers down word for word in `docs/user-tests.md`. Change the wording
on the site where they got it wrong.

### T11. Opposite-pair finder (P1, 90 min)

**Goal:** the challenge's central idea, automated.

List pairs of heights in the same latitude band, or pairs of bands at the same
height, where both trends are "Clear" or "Likely" and the signs are opposite.
Rank by the smaller of the two absolute trends. Computed in the pipeline, written
to `web/data/pairs/{dataset}/{variable}.json`, shown as a list that jumps to the view.

### T12. Phone layout and access (P1, 45 min)

- Curtain, profile and history stack in one column under 860 px.
- All controls reachable by keyboard.
- Patterns as well as colours for the four labels and for cooling and warming.
- Text contrast checked.

### T13. Regional boxes (P2, 2 to 3 hours)

Keep six longitude sectors per latitude band in the fetch step, so "click a place"
is local. This changes the cache format and needs a new download. Do not start it
before T1 to T10 are done.

### T14. Third witness (P2, 2 hours)

Aura MLS temperature for the stratosphere, 2004 onward, as a tie-breaker where AIRS
and MERRA-2 disagree.

---

## 5. Timeline

| When (ET) | Work |
|---|---|
| Fri 23:45 to Sat 01:30 | T1, T3 |
| Sat 08:00 to 10:00 | T2 (MERRA-2 will be on disk), T4 |
| Sat 10:00 to 12:30 | T5, T6 |
| Sat 12:30 to 14:00 | T7, T8, first deploy |
| Sat 14:00 to 15:00 | T10 user tests at the event |
| Sat 15:00 to 16:30 | Fix what testers misread, T12 |
| Sat 16:30 to 18:00 | T9, T11 if time allows |
| **Sat 18:00** | **Feature freeze** |
| Sunday | Rehearse the pitch, record the demo video, submit |

---

## 6. Who has to do what

| Needs the owner | Can be done by a coding agent |
|---|---|
| Keep `make data` running in a terminal with the token set | T1 to T9, T11, T12 |
| Turn on GitHub Pages in the repo settings | All tests and checks |
| Run the three user tests | Drafts of the submission and pitch |
| Record the demo video | |
| Submit on the Space Apps site | |

---

## 7. Risks

| Risk | Sign | Response |
|---|---|---|
| MERRA-2 download stalls | Month count stops rising | Rerun the same command. It resumes. Ship with AIRS alone if needed. |
| The two datasets disagree high up | Many "Disputed" cells above 10 hPa | This is the third case file. Show it. |
| Real trends look weak next to the synthetic demo | Fewer coloured cells | Expected. Hatching and "not proven" already cover it. |
| Jagged AIRS levels look like errors | Zig-zag profile | Label by the verdict ladder. Explain on the methods page. |
| Site data too large for phones | Slow first load | Round series, load a latitude file only when clicked (already the case). |
| Wording drifts from the glossary | Mixed terms on screen | T4 check: one glossary file, read by the site. |

---

## 8. Starting an agent on this plan

Paste this into a coding session opened in the repo folder:

> Read `docs/EXECUTION.md`, `docs/data-contract.md` and `README.md`. Execute tasks
> T1 to T9 in order. For each task: do the steps, run `make test`, verify every
> check in the task, then commit with a message naming the task. Follow section 1
> without exception. Use the repo owner's git identity and add no attribution lines.
> Do not handle the Earthdata token and do not start downloads. If a check cannot
> pass, stop and report what failed and what you tried. When real numbers differ
> from the tables in this file, update the tables in the same commit.
