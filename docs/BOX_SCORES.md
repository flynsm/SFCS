# Box score images: graphic template (hand-off to the analytics Claude)

**From:** the website Claude. **Status:** final graphic template. **It computes no statistics.**
**The user's instruction:** nothing goes into the weekly run until they say the EP model rebuild is done.

## What it is

[`tools/box_scores.py`](../tools/box_scores.py) draws one postgame box score PNG per FCS game (FCS-FCS and FBS-FCS)
in SFCS house style. Preview: [`box_score_demo.png`](box_score_demo.png).
- **Size:** 1080 × ~1910 px (about 9:16), so it fits a phone screen.
- **Header:** a compact SFCS mark and title, then the logos with the final score beside each one. It reads "AT", or "VS" plus
  "NEUTRAL SITE" at neutral sites. The teams, score, date and neutral flag come from `games_schedule_current.parquet`;
  logos come from `team_brand.parquet`.
- **Rows** (the user's list): PGWE, EPA/play, yards/play, passing SR, rushing SR, explosive play rate, 3rd/4th down SR,
  line yards, defensive stuff rate, havoc rate, quality drive rate, finishing drives, offensive plays in garbage time.
- **Cells:** each shows the value, with the background shaded red → green by a color position **you supply**.
  The percentile isn't printed.
- **Output:** `dashboards/week<P>_db/box_scores/box_score_<contest_id>_wk<P>.png`, where the website already looks.
  A finished image shows up as the **Box Score** link on that game's card.

## The one input it needs from you: `STATS_INPUT` (currently a placeholder)

A table, one row per team per game:

| column | meaning |
|---|---|
| `contest_id` | same id as the schedule |
| `team` | NCAA team name, exactly as in the schedule |
| `<key>` | the value to print. Rates as 0–1 (`0.412` prints as `41.2%`); others print with 2 decimals |
| `<key>_pct` | 0–100 color position, **100 = best for that team** (you handle "lower is better" stats). Blank = unshaded |

Keys: `pgwe, epa_play, yards_play, pass_sr, rush_sr, explosive_rate, late_down_sr, line_yards, def_stuff_rate,
havoc_rate, quality_drive_rate, finishing_drives, garbage_share`.

- **Where it reads from:** set `STATS_INPUT` to wherever the table lives. `{week}` is filled in, e.g.
  `DASHBOARDS / "week{week}_db" / "box_score_stats_wk{week}.parquet"`. Parquet or CSV both work.
- **Missing values:** a missing file, row, column or cell is drawn as a plain "–" (unshaded). The image never shows any draft
  or placeholder marking; the console lists which games had missing values.
- **Your side owns:** all stat definitions, the percentile baseline, PGWE for both teams, garbage-time handling,
  and the EP-dependent rows.
- **Baseline (user decision):** percentiles are relative to **all D1 football games since 2023**. Build the distribution
  from the **past 3 seasons** of single-game team performances. The footnote on the image says exactly this.

## Other placeholders to confirm

- **Fonts:** `FONTS_HEAVY` / `FONTS_BOLD` / `FONTS_REGULAR`, the font files the house graphics use.
  The fallback is Arial Black / Arial.
- **SFCS mark:** `MARK`, the dark-on-light SFCS mark file.
- **Footnote** (`FOOTNOTE`, the user's wording): "Garbage time excluded. Shading indicates performance as percentile relative
  to all D1 football games since 2023." 
- **Row labels and number formats** are in `ROWS` if anything should read differently.

## Try it

- `python site_export/box_scores.py --demo` draws a preview with made-up numbers.
- `--demo --placeholders` shows the empty state (every value "–").
- `--demo --neutral` draws a neutral-site version.
- `python site_export/box_scores.py --week 6` draws real games using `STATS_INPUT`.
