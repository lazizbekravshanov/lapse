# Pitch

## The 30-second demo video

The rules: 30 seconds at most, English subtitles, hosted on an outside site (YouTube, Google
Drive) with a link anyone can open. A longer video is not eligible for Global Judging.

The video as recorded is 25 seconds: the site filmed frame by frame, the team's own voice,
and the spoken words as subtitles.

| Time | On screen | Words (also the subtitles) |
|---|---|---|
| 0:00 | Front page: "Warming below. Cooling above." | I'm Lazizbek, team Lapse. Is the air warming? It depends how high you look. |
| 0:07 | The climb. Red at the bottom, a pause at 19 km where the direction flips, blue at 32 km. | In NASA satellite data, the air near the ground is warming. Past nineteen kilometres it flips. Higher up, it cools twice as fast. |
| 0:16 | The top: "One sky. Two directions." Then the ask box with one answer and its "Every number traced to the data" tick. | Every height gets an honest label, and every answer is checked against NASA's records. |
| 0:22 | End card: lapse-earth.vercel.app | This is Lapse. |

## 2-minute demo, click by click

For judges in the room. Open https://lapse-earth.vercel.app before you start.

| Time | Do | Say |
|---|---|---|
| 0:00 | Point at the headline. | "Is the planet warming? It depends how high you look." |
| 0:10 | Ask the judge the guess question and click their answer. | "Which is changing faster, the warming below or the cooling above?" Read the reply aloud. |
| 0:25 | Press **Play the ascent**. Let it rise. | "Every step is a height NASA measured. Warming, clear change. Here it cannot tell, and it says so: not proven yet. The dashed line is where the direction flips, about 19 km. Above it, cooling." |
| 0:50 | The top: "One sky. Two directions." | "Same planet, same years, opposite directions. Physicists predicted this pattern in 1967 as the mark of rising carbon dioxide." |
| 1:00 | Scroll back up. Click **Above you**, type "Cincinnati". | "This is the band of sky at our latitude, all the way around the Earth." |
| 1:10 | Scroll to **Ask the data**. Click "Did the 2022 volcano change the trend at 32 km?" | "It can only read NASA's results. A program rejects any number that is not in them." Point at the tick. |
| 1:25 | Open the case **When the data source jumps**. Click **Next** once. | "Here the second dataset drops 2.7 degrees in one step, when its satellites changed. Lapse caught that by itself and labels it 'Disputed'." |
| 1:40 | Open **Investigate it yourself**. Click **Textbook, no memory**, then **Auto**. | "Every method in one place. The textbook test claims far more than it should. The table shows when the method changes the answer." |
| 1:50 | Click **Method** at the top. Scroll to the published-science table. | "Our number for the upper air, 2003 to 2012: minus 0.65. The published number: minus 0.65." |
| 2:00 | Stop. | "Lapse: what is changing in the air, at which height, and how sure we are." |

## If a judge asks

| Question | Answer |
|---|---|
| Why not a map of the surface? | About twenty public entries we found do that. The challenge text asks about levels of the atmosphere, and we found none that works on them. |
| Is this a discovery? | No. The pattern is known science, predicted in 1967 and found in satellite records by a 2023 study. What is new is that anyone can see it in thirty seconds, check it, and see how sure we are at every height. |
| How do you know it is significant? | Mann-Kendall test with a correction for month-to-month memory, and false discovery control across all cells. Then a second dataset has to agree. |
| Is the cooling caused by the 2022 volcano? | We checked. Without those months the trend moves from -0.77 to -0.70 at 32 km in the southern middle latitudes. |
| Can the AI make numbers up? | No. It can only call read-only tools over the published results, and a program rejects any answer with a number that no tool produced. With no AI model at all, the box still answers by rule. |
| Did AI write the code? | Most of it, with an AI coding assistant that I directed. That is why every number can be recomputed from the repository with one command, and why 88 tests and a published-science check run on every change. |
| What can it not do? | It cannot tell you about your town, the cause, or the future. The methods page says so. |
| What would you do next? | Regional boxes instead of full rings, and a third dataset (Aura MLS) to settle the heights where the two disagree. |
