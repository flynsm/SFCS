# Box score images: hand-off to the analytics Claude

**From:** the website Claude. **Status:** DRAFT script, written without access to `fcs-model/`.
**The user's instruction:** nothing goes into the weekly run until they say the EP model rebuild is done. This is groundwork only.

## What it is

[`tools/box_scores.py`](../tools/box_scores.py) draws one postgame box score PNG per FCS game, in SFCS house style.
- **Header:** the logos, with the final score beside each one and "AT", or "VS" plus "NEUTRAL SITE" for neutral-site games.
- **Rows:** away value | stat | home value.
- **Shading:** each value is shaded red → green by its percentile against every D1-vs-D1 single-game team performance this
  season, pooled (both sides of FBS-vs-FCS games included). Green = good for that team. The percentile number isn't printed.
- **Output:** the path the website already reads, so a finished image shows up as the **Box Score** link on that game's card:
  `dashboards/week<P>_db/box_scores/box_score_<contest_id>_wk<P>.png`.

**Rows (the user's list):**
- PGWE, EPA/play, yards/play;
- passing SR, rushing SR, explosive play rate, 3rd/4th down SR;
- line yards per rush, defensive stuff rate, havoc rate;
- quality drive rate, finishing drives (points per trip inside the 40);
- offensive plays in garbage time.

Garbage time is excluded from every stat except that last row, and one footnote says so.

## Install and try

1. Copy `tools/box_scores.py` to `fcs-model/site_export/box_scores.py`. Needs pandas, pyarrow, numpy, Pillow and openpyxl.
2. `python site_export/box_scores.py --demo` draws a design preview with made-up numbers.
3. `python site_export/box_scores.py --week 6` (optionally `--game <contest_id>`) draws real games.
   - Any row whose source isn't connected is drawn as a hatched **SOURCE TBD** cell with a ◆.
   - The image gets a yellow **DRAFT** banner, and the console lists the unconnected rows.
   - So a placeholder can't pass for a real number.

## What you need to fill in (CONFIG block at the top of the script, every line marked `TODO(analytics)`)

| Rows | Source the script expects | What's unknown |
|---|---|---|
| Final score | `processed/games_schedule_current.parquet` | none (confirmed in round 1) |
| Postgame win expectancy | `dashboards/week<P>_db/pgwe_week<P>.xlsx`: Winner / Loser / Winner PGWE; loser = 1 − winner | which sheet holds FBS-vs-FCS games (both `FCS` and `FBS` are searched). Shaded by its own value. |
| Yards/play, passing SR, rushing SR, explosive rate, 3rd/4th down SR, line yards, defensive stuff rate, garbage-time share | the play-level file (`PLAYS`), aggregated per (game, offense); defensive stats are credited to the defense | `PLAYS.path` and every column name: game, offense, defense, down, distance, yards, pass flag, rush flag, garbage flag, optional exclude flag |
| EPA per play | `PLAYS.cols.epa` | leave `None` until the EP rebuild is done |
| Havoc rate | a per-play defensive havoc flag (`PLAYS.cols.havoc`), **or** a per-game column (`TEAM_GAMES.cols.havoc_rate`) | whether either exists |
| Quality drive rate, finishing drives | a per-game drives table (`DRIVES`): drives, quality drives, trips inside the 40, points on those trips | whether a per-game table exists, and **how the model defines a "quality drive"** |

**Definitions the script computes. Confirm they match the model's or tell me the right ones:**
- **Success:** 1st down ≥50% of distance, 2nd ≥70%, 3rd/4th 100%.
- **Explosive:** a rush of 12+ yards or a pass of 15+.
- **Line yards per rush:** losses count 120%, yards 0–4 100%, 5–10 50%, 11+ 0%.
- **Defensive stuff rate:** the share of the opponent's rushes gaining 0 or fewer yards.
- **Finishing drives:** points per trip inside the opponent's 40.

Also:
- **Team names:** for each source, `team_names: "ncaa" | "cfbd"`. CFBD names are mapped to NCAA names through
  `processed/conferences.parquet`, because the schedule uses NCAA names.
- **Fonts:** `FONTS_HEAVY` / `FONTS_BOLD` / `FONTS_REGULAR` should point to the font files the house graphics use.
  The script falls back to Arial Black / Arial on Windows.
- **SFCS mark:** `MARK` points to `resources/sfcs-logo-final/sfcs-mark-light-256.png`. Fix it if that file has a different name.
- **The baseline** is built from whatever is connected: each stat is pooled over every team-game in a D1-vs-D1 game
  (from the schedule's `matchup`) that has a value. It's the current season only, since the schedule file holds 2026.

## Tested (on a stand-in `fcs-model/` with your round-1 file names and columns, plus made-up play, drive and PGWE files)

- **Nothing connected:** every unconfirmed row draws as SOURCE TBD, with the DRAFT banner.
- **Everything connected:** 16 games drew. These all matched hand calculations from the made-up plays exactly:
  - passing success rate;
  - line yards per rush;
  - defensive stuff rate (credited to the right team).
- **Neutral-site game:** shows "VS" and "NEUTRAL SITE".

## When it's ready for the weekly run (after the EP rebuild, per the user)

- **Order:** run `box_scores.py --week <P>` after `run_weekly.py` and **before** `export_site.py`.
- **Upload:** the export already detects box scores and sets the Box Score links. Its upload will then exceed 100 files,
  so it will tell the user to drag in batches.
