# Box score images: hand-off to the analytics Claude

**From:** the website Claude. **Status:** DRAFT script, written without access to `fcs-model/`.
**The user's instruction:** nothing goes into the weekly run until they say the EP model rebuild is done. This is groundwork only.

## What it is

[`tools/box_scores.py`](../tools/box_scores.py) draws one postgame box score PNG per FCS game, in SFCS house style.
- **Layout:** away value | stat | home value.
- **Percentiles:** each value shows its percentile against every D1-vs-D1 single-game team performance this season,
  pooled (both sides of FBS-vs-FCS games included), and is shaded red → green by it ("higher = better for that team").
- **Output:** the path the website already reads, so a finished image shows up as the **Box Score** link on that game's card
  with no website changes: `dashboards/week<P>_db/box_scores/box_score_<contest_id>_wk<P>.png`.

The decisions recorded in your memory and FINDINGS 246 are followed:
- games covered: FCS-FCS and FBS-FCS;
- the pooled D1 baseline;
- garbage time excluded, with one footnote;
- the EPA rows held back.

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
| Postgame win expectancy | `dashboards/week<P>_db/pgwe_week<P>.xlsx`: Winner / Loser / Winner PGWE; loser = 1 − winner | which sheet holds FBS-vs-FCS games (both `FCS` and `FBS` are searched). 0–1 vs 0–100 is auto-detected. Shaded by its own value rather than a percentile. |
| Success rate, passing SR, rushing SR, Q1–Q4 SR | play-level file, aggregated per (game, offense) with the success rule: 1st down ≥50% of distance, 2nd ≥70%, 3rd/4th 100% | `PLAYS.path` and every column name (game, offense, down, distance, yards, quarter, pass flag, rush flag, garbage flag, optional exclude flag for kneels/spikes). If you'd rather use `team_games`' own success rate for the overall row, set `TEAM_GAMES.cols.success_rate`. |
| Sack rate allowed, stuffed rushes allowed, offensive plays in garbage time | `team_games.parquet` | its folder, the game-id and team columns, the three stat columns. Rates may be 0–1 or 0–100 (auto-detected). |
| Points per opportunity, scoring opportunity rate | a per-game drives table (`drive_metrics.py`: trips inside the opponent's 40) | whether a per-game version is stored at all, its path, and its columns (game, team, drives, opportunities, points on those drives). |
| EPA ×4 | n/a | waits for the EP rebuild: set `EPA_READY = True` and connect `EPA_SOURCE` (not yet written). They currently show "PENDING EP MODEL REBUILD". |

Also:
- **Team names:** for each source, `team_names: "ncaa" | "cfbd"`. CFBD names are mapped to NCAA names through
  `processed/conferences.parquet`, because the schedule uses NCAA names.
- **Fonts:** `FONTS_HEAVY` / `FONTS_BOLD` / `FONTS_REGULAR` should point to the font files the house graphics use.
  The script falls back to Arial Black / Arial on Windows.
- **SFCS mark:** `MARK` points to `resources/sfcs-logo-final/sfcs-mark-light-256.png`. Fix it if that file has a different name.
- **The baseline** is built from whatever is connected: each stat is pooled over every team-game in a D1-vs-D1 game
  (from the schedule's `matchup`) that has a value. It's the current season only, since the schedule file holds 2026.

## Tested (on a stand-in `fcs-model/` with your round-1 file names and columns, plus made-up play, team-game, drive and PGWE files)

- **Nothing connected:** every unconfirmed row draws as SOURCE TBD, with the DRAFT banner.
- **Everything connected:** 16 games drew. One team's passing success rate recomputed by hand from the plays matched the
  script exactly (0.7407). Percent-scale inputs were converted, and a low sack rate correctly shades green.

## When it's ready for the weekly run (after the EP rebuild, per the user)

- **Order:** run `box_scores.py --week <P>` after `run_weekly.py` and **before** `export_site.py`.
- **Upload:** the export already detects box scores and sets the Box Score links. Its upload will then exceed 100 files,
  so it will tell the user to drag in batches.
