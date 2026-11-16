# Submission

Paste-ready text for the project page: profile icon > My Team > Project tab > Edit.

- Challenge: Be An Earth System Trend Detective! (2026 NASA Space Apps Challenge, Cincinnati)
- Team: Lapse
- Deadline: Sunday 15 November 2026, 11:59 p.m. Eastern. Submitting is final. Nothing can be
  edited afterwards.

The field names below follow the 2025 Project Submission Guide, the newest one we could
read. If the 2026 form words a field differently, the text still fits.

## Before you press "Submit for Judging"

- [ ] The demo is a video of 30 seconds or less with English subtitles (or 7 slides or fewer),
      and its link opens in a private browser window with no login.
- [ ] https://lapse-earth.vercel.app opens in a private browser window.
- [ ] Every field below is pasted. Everything is in English.
- [ ] "What was built when" is read and decided (see that section).
- [ ] "Use of Artificial Intelligence" is edited so that every sentence is true for you.
- [ ] Every team member is on the Members tab.
- [ ] Both boxes are ticked: the guide and terms, and original work.

## Project Name

Lapse

## High-Level Project Summary

Everyone asks whether the planet is warming. The honest answer depends on how high you look.

Lapse turns 24 years of NASA's AIRS satellite record and 47 years of the MERRA-2 reanalysis
into one climb. Scroll, and the page rises from the ground to 48 km while the height, the
rate of change and the colour change with you. Averaged over the globe, the air is warming
low down (+0.27 °C per ten years near 8 km) and cooling more than twice as fast higher up
(-0.59 °C per ten years near 32 km). The direction flips near 19 km.

Every height carries one of four plain labels: Clear change, Likely change, Not proven yet,
or Disputed. The labels come from rules, not opinion: a statistical test, a second
independent dataset, a check that removes volcano months, and a check for jumps when a data
source changed.

Visitors can also ask questions in their own words. Every number in an answer is checked
against the NASA results before it is shown.

It matters because the surface is only the bottom of the story. In 1967 physicists
predicted that rising carbon dioxide would warm the air below and cool the air above.
NASA's records show that pattern. Lapse lets anyone see it, check it, and see how sure we
are.

## Link to Project Demo

Paste the video link here. The script is in [pitch.md](pitch.md).

## Link to Final Project

https://lapse-earth.vercel.app

## Detailed Project Description

**What it does**

Lapse is a website about trends in the atmosphere at every height, built for people with no
science background.

- **The ascent.** The front page opens with the finding in four words: "Warming below.
  Cooling above." Scroll, drag the column or press Play, and the page rises from the ground
  to the top of the record. At each measured height it shows the rate of change, its label
  and one plain sentence. The background follows the direction: warm colours where the air
  is warming, cool colours where it is cooling. Familiar heights are marked: Mount Everest,
  where airliners cruise, the ozone layer, where weather balloons pop.
- **Guess first.** Before the climb, one question: which is changing faster, the warming
  below or the cooling above? The reply gives both rates.
- **Above you.** Share a location or type a city, and the climb replays for the band of sky
  at that latitude. The page says plainly that this is the band all the way around the
  Earth, not one city. The location never leaves the browser.
- **Ask the data.** A question box. "Is the Arctic warming?" "Did the 2022 volcano change the
  trend at 32 km?" The answer comes only from the NASA results, lists the files it read, and
  carries a tick when every number in it was traced to them.
- **Three cases.** Guided demonstrations: one cause with opposite trends, a volcano in the
  record, and a jump in a data source that could fake a trend.
- **The evidence.** Three charts of the same measurements: every latitude and height at once,
  every height at one place with its likely range and a second dataset, and the
  month-by-month history with known events shaded.
- **Investigate it yourself.** Every data source, method and check in one place. Pick your
  own or leave it on Auto, and a table shows whether the method changes the answer.

Air temperature, water vapor and ozone are available. Places are the whole globe, five
regions, or any five-degree band of latitude.

**How it meets the challenge**

| Objective in the challenge | What Lapse does |
|---|---|
| Identify variables of interest | Air temperature, water vapor and ozone, each with a one-line definition. One tap switches between them. |
| Acquire the data for a region | The whole globe, five regions, or any five-degree band, at up to 42 heights. "Above you" picks the band over the visitor. |
| Generate and visualize a time series | A month-by-month history for any place and height, with known events shaded. |
| Rate of change and significance | Theil-Sen slope with a 95% range, Mann-Kendall test with a correction for memory, false discovery control, shown as four plain labels. |

The challenge also suggests demonstration examples and simple definitions. Lapse has three
guided cases and a "Words we use" list.

**How it works**

Three layers. The backend downloads the NASA data, averages it in five-degree bands of
latitude, removes the seasonal cycle and computes the trends, tests and checks. The hub
keeps every data source, method and check in one catalog, so a request always has the same
shape and so does the answer. The website draws the result and writes the sentences. It
does no statistics of its own.

A label is assigned by rule:

| Label | Rule |
|---|---|
| Clear change | Two independent datasets both pass the test, in the same direction, with overlapping ranges. |
| Likely change | One dataset passes the test and nothing contradicts it. |
| Not proven yet | The change cannot be told apart from chance. This is not "no change". |
| Disputed | The second dataset shows the opposite, the trend depends on volcano months, or the record jumps when its data source changed. |

The challenge names the t-test, the Mann-Kendall test and confidence intervals. Lapse offers
all of them as interchangeable tools. On made-up records with no trend, the three sound
methods raise a false alarm 3 to 8 times in 100. The plain textbook test does 30 to 65,
which is why it is shown for comparison only.

The question box is an agent with a short leash. It can only call eleven read-only tools
over the published results. A program rejects any answer containing a number that no tool
produced. Off-topic questions are declined. With no AI model connected it still answers,
by rule. The same tools are offered to outside AI assistants over the Model Context
Protocol.

Every published number can be recomputed from the repository with one command and no NASA
login (`make verify`). 88 automated tests and that comparison run on every change.

**What is new**

- **Height.** The challenge text mentions trends at "levels of the atmosphere". Of about
  twenty public entries we found for this challenge, none works on them.
- **Same process, opposite trends.** The challenge's central idea, shown in one column of
  air and listed automatically for every region.
- **Labels that can say "we don't know".** "Not proven yet" and "Disputed" are first-class
  answers, with the reason given.
- **It caught a known data problem by itself.** The jump check flags MERRA-2 above about
  40 km, where its record steps by several degrees when its input satellites changed.
- **An AI that cannot invent a number.** The check is a program, not a promise.

The finding itself is not new. Physicists predicted this pattern in 1967, and a 2023
study found it in satellite records. What Lapse adds is a way for anyone to see it in
half a minute and to check every number behind it.

**Does it match published science?**

Five published results were checked on the same years and heights. Four match. For example,
above about 36 km for 2003 to 2012, the published cooling is 0.65 ± 0.11 K per decade and
ours is -0.65. The fifth, a 37-year layer total from MERRA-2, has the same direction but a
larger size, at heights where our own jump check distrusts MERRA-2. The table is on the
site's Method page.

**Limits**

- Values are averages around the whole Earth at one latitude, not local.
- A trend shows what changed, not why. The one cause we name is cited.
- Kilometres are converted from pressure and are approximate.
- Water vapor and ozone rest on one dataset, so they can never be labelled "Clear change".
- MERRA-2 water vapor is shown only up to about 8 km, the height up to which it takes in
  humidity measurements.
- We read every 2nd (AIRS) or 4th (MERRA-2) grid point before averaging, and one MERRA-2
  month is missing.

**Tools**

Python (NumPy, SciPy, xarray, netCDF4, requests, pytest). Plain HTML, CSS and JavaScript
with no framework or library; the charts are drawn on Canvas and SVG. GitHub Actions for
tests. Vercel for hosting. Google Gemini for the question box. Figma for design drafts.
An AI coding assistant (see "Use of Artificial Intelligence").

Code: https://github.com/lazizbekravshanov/lapse

**What was built when**

The repository's public history shows this, so it is stated here. Decide whether to keep
this paragraph in the form, and ask the Cincinnati organizers if you are unsure what the
local rules allow.

- The evening before the event opened (13 November, 11:15 p.m., to 14 November, 12:20 a.m.):
  the repository, the NASA download code, the first statistics and label rules, and a first
  version of the site running on real NASA data.
- During the event (14 and 15 November): the backend and hub layers, three more methods and
  the toolbox, the one-command recomputation and automated tests on every change, the
  water vapor limit, the agent and its number check, the redesign, the ascent, Above you,
  Guess first, and the live question box.

## NASA Data

| Product | Provider | What we took from it |
|---|---|---|
| AIRS3STM v7.0: AIRS on the Aqua satellite, monthly, 1° grid, 24 pressure levels | NASA GES DISC | Air temperature, September 2002 to September 2026 (289 months) |
| M2IMNPASM v5.12.4: MERRA-2 reanalysis, monthly, 42 pressure levels | NASA GMAO / GES DISC | Air temperature, water vapor and ozone, January 1980 to September 2026 (560 of 561 months) |

We found the files through NASA's Common Metadata Repository and read them over OPeNDAP at
GES DISC with an Earthdata login. Each month was averaged in five-degree bands of latitude
at every pressure level. From those averages we removed the seasonal cycle and computed a
trend, a 95% range and a significance test for every band and height.

AIRS is the main witness for temperature because it is one instrument that did not change.
MERRA-2 is the second, independent witness where the two overlap, and the only source for
water vapor and ozone. Where the two disagree, or where MERRA-2 jumps because its input
satellites changed, the site says so.

The reduced data (about 11 MB) is in the repository, so anyone can recompute every number
without a NASA login. NASA JPL's published AIRS temperature trends for 2002 to 2020 are two
of the five results we check our numbers against.

## Space Agency Partner & Other Data

No Space Agency Partner data was used.

Published results we compare with or cite:

- Manabe and Wetherald, Journal of the Atmospheric Sciences, 1967: the prediction that
  rising carbon dioxide warms the lower atmosphere and cools the upper atmosphere.
- Santer and others, PNAS, 2023: the pattern found in satellite records.
- Pan and others, Journal of Climate, 2017: temperature change in the upper air, 2003 to 2012.
- NASA JPL, AIRS temperature trends, 2021.
- Davis and others, Atmospheric Chemistry and Physics, 17, 12743-12778, 2017: where
  reanalysis water vapor can be trusted.

Open-source software: Python, NumPy, SciPy, xarray, netCDF4, requests, pytest. The website
uses no outside library, font or image.

Services: GitHub and GitHub Actions, Vercel, the Google Gemini API, Figma.

Images: none from outside. The small landmark icons are SVG drawings made for this project.
No music, video or copyrighted material is used. No NASA logo or branding is used.

AI tools: see the next field.

## Use of Artificial Intelligence

Edit this so that every sentence is true for you before pasting.

Yes. AI tools were used in four ways.

1. **Writing the code and text.** Most of the code (the data pipeline, the statistics, the
   tests, the website and the agent) and most of the text were written with Claude, an AI
   coding assistant made by Anthropic. I chose the challenge and the idea of trends by
   height, set the requirements, made the product and design decisions, ran the NASA
   downloads with my own Earthdata login, and checked the result in the browser.
2. **Inside the product.** The "Ask the data" box uses Google's Gemini (gemini-2.5-flash) to
   phrase answers. It can only call read-only tools over our published results. A program
   rejects any answer containing a number that no tool produced, and off-topic questions
   are declined. With no AI model connected the box still answers, by rule.
3. **Design drafts.** Layout drafts in Figma were produced with the same AI assistant.
4. **The demo video.** The voice is mine. The picture is the real site filmed frame by
   frame, and the AI assistant cut it to the voice and added the subtitles. Nothing in the
   video is AI-generated imagery.

No number on the site was written by an AI. Each one is computed by the tested pipeline
from NASA data, and one command recomputes them all from the repository. No AI-generated
photo, video or audio is used. The landmark icons are small SVG drawings written as code
with the AI assistant. No NASA logo or branding appears anywhere.

## Links

- Site: https://lapse-earth.vercel.app
- Code: https://github.com/lazizbekravshanov/lapse
- Method and published-science check: https://lapse-earth.vercel.app/methods.html
