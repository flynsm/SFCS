# Game preview images: graphic template (hand-off to the analytics Claude)

**From:** the website Claude. **Status:** graphic template (portrait, chosen by the user). **It computes no statistics.**

## What it is

[`tools/previews.py`](../tools/previews.py) draws one pregame preview PNG per FCS game (FCS-FCS and FBS-FCS) in SFCS house style:

- **Header** (the same layout as the box score):
  - each team's logo, its name in the team's `ink` color, and its record line ("5-1 (3-0) Big Sky");
  - **projected points** in large type beside each logo, under a centered "PROJECTED SCORE" label;
  - "WIN PROB" under each score, with the percentage below it;
  - "AT" (or "VS" at neutral sites) between the scores, and the game date (plus "NEUTRAL SITE" when it applies) in the center.
- **Two panels:** "<away> OFF vs <home> DEF" and "<home> OFF vs <away> DEF", with team names in their ink colors. Each row shows the offense's value and rank, the stat name, then the defense's rank and value.
- **Stats:** Rating (side-of-ball rating), Success Rate, EPA/Dropback, EPA/Rush, Havoc Rate, Stuff Rate, Quality Drives, Finishing Drives.
- **Rank badges:** shaded with the user's rule, applied exactly as written:
  - percentile = round((n − rank)/(n − 1)·100), with n = `div_n`;
  - continuous blend from neutral #e6e4df to blue #2f5aa8 (best) or red #bf4a43 (worst);
  - white text at a percentile ≥ 80 or < 20, otherwise #1c1c1c.
- **Footnote:** "Ranks within each team's division. Definitions for statistics at sfcsratings.com/definitions. @SFCSratings". The SF|CS watermark is at 4%.
- **Output:** `dashboards/week<N>_db/previews/preview_<contest_id>_wk<N>.png`, where N is the upcoming week. The website already looks there, so a game's **Preview** link appears once its file exists.
- **Size:** 1080 × ~1880 (phone).

## The one input it needs: `PREVIEW_INPUT` (set its path)

The script expects one row per team per game:

| column | meaning |
|---|---|
| `contest_id`, `team` | the same id and NCAA team name as the schedule |
| `record`, `conf_record`, `conf_name` | header line, e.g. `5-1`, `3-0`, `Big Sky` |
| `proj_pts` | projected points |
| `win_prob` | 0–1 |
| `div_n` | number of teams in this team's subdivision (FCS or FBS) |
| `off_<key>`, `off_<key>_rank` | this team's **offense**: value and rank (1 = best) |
| `def_<key>`, `def_<key>_rank` | this team's **defense**: value and rank (1 = best) |

**Keys:** `rating, success_rate, epa_dropback, epa_rush, havoc, stuff_rate, quality_drives, finishing_drives`.

**Value formats:**
- Rates are 0–1 (`0.412` prints as `41.2%`): success_rate, havoc, stuff_rate, quality_drives.
- `rating` prints with 1 decimal, EPA with 3 decimals, and finishing_drives with 2.

You can change the formats or labels in `STATS`.

**Ranks:** "1 = best" means best **for that side of the ball**. For example, a defense that allows the lowest success rate is rank 1.

**Missing data:** a missing value shows as "–" with no badge, and the console reports it.

## Other settings to confirm

- **Fonts and SFCS mark:** `FONTS_*` and `MARK`, the same as `box_scores.py`.
- **Footnote wording:** `FOOTNOTE`.

## Try it

- `python site_export/previews.py --demo` draws a layout preview with made-up numbers.
- `python site_export/previews.py --week 7` draws real games once `PREVIEW_INPUT` is set.
