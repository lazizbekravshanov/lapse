# Weekend plan

Goal for the demo: three cases that work on real NASA data, a clear verdict sentence,
and a 30-second story.

## Before coding (Saturday, first hour)

- [ ] Confirm the local rules on code written before the event, and say in the
      submission what was prepared in advance.
- [ ] Everyone has an Earthdata login and can run `make demo` and `make serve`.
- [ ] Run `python -m lapse inspect airs` and `inspect merra2`. Fix names in `config.py`.
- [ ] Start `python -m lapse fetch airs` (small files, finishes first).
- [ ] Start `python -m lapse fetch merra2` in a second terminal (the long one).

## Saturday

| Block | Data and statistics | Website and story |
|---|---|---|
| Morning | Get AIRS temperature through fetch and export. Compare the global profile with JPL's published AIRS trend picture. | Plain-language labels, km first and hPa second. Variable definitions. |
| Midday | MERRA-2 temperature in. Turn on the two-witness comparison. | Guided walkthrough for the three cases. |
| Afternoon | Validation table: upper-stratosphere cooling and lower-troposphere warming against published values. | Methods page. Mobile layout. |
| Evening | Water vapor and ozone from MERRA-2 if time allows. | Deploy. Record a backup video of the demo. |

## Sunday

- [ ] Freeze features by midday.
- [ ] Remove the synthetic banner only when every cube on the site is real.
- [ ] Write the submission: challenge fit, data used, method, limits, what was prepared early.
- [ ] Rehearse the pitch twice.

## Stretch goals, in order

1. Regional boxes (not only full latitude circles), so "click a place" is truly local.
2. Question-driven start: "What do you want to investigate?" picks the variable and view.
3. Aura MLS as a third witness in the stratosphere.
4. Opposite-pair finder: list pairs of heights or regions with opposite proven trends.

## Risks

| Risk | Plan B |
|---|---|
| MERRA-2 download is slow | Raise `--stride`, or fetch 2002 onward only. AIRS alone still tells the story. |
| AIRS variable names differ from `config.py` | `lapse inspect airs` prints the real ones. |
| Upper-level reanalysis jumps dominate | Show them as the third case. That is what the event shading is for. |
| Real trends are weaker than the synthetic ones | Expected. The verdict already says "not proven" where the test fails. |
