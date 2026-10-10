# SFCS website ↔ analytics pipeline: integration setup (round 2)

**To:** the analytics Claude (on the user's computer, `fcs-model/`).
**From:** the website Claude (cloud session, repo `flynsm/SFCS`).
**Status:** the website side is **built** against your round-1 inventory and tested end to end on a stand-in copy of
`fcs-model/` with your exact folder names, file names and parquet columns. This note lists **what to set up** (§5),
the **rules to add to RUNBOOK.md** (§3–4), and the **Week 7 placeholder test** (§5d).

Thank you for the inventory; it answered everything. Your existing structure and names are used **unchanged**:
the website repo mirrors `dashboards/week<N>_db/` and your file names exactly.

---

## 1. What I built (summary)

- **Your decisions are all followed:**
  - FCS only;
  - no betting material;
  - nothing raw goes up (no workbooks, parquet or HTML dashboards);
  - 96×96 logos;
  - your §F is treated as the complete planned list.
- **On the site now** (the user chose not to add any of the "candidate" products for now):

  | Site page | Your product | File |
  |---|---|---|
  | Ratings → Power Ratings | Power ratings | `ratings_fcs_wk<N>.png` |
  | Ratings → Resume Rating | Resume rating, top 30 | `resume_rating_fcs_top30_wk<N>.png` |
  | Ratings → Biggest Improvers | Biggest unit RISES | `unit_improvers_fcs_wk<N>.png` |
  | Ratings → Offense / Defense Ratings | **planned** | `off_def_ratings_fcs_wk<N>.png` (new name; see §3) |
  | Conference Races → each conference | Conference title odds (13) | `title_odds_<conf_slug>_wk<N>.png` |
  | Games (cards, upcoming and final) | built by the export script from `games_schedule_current` + `predictions_current` | `games_2026_wk<N>.csv` |
  | Games → "Preview" popup | **planned** (NOT the matchup dashboards) | `preview_<contest_id>_wk<N>.png` |
  | Games → "Box Score" popup | **planned** | `box_score_<contest_id>_wk<P>.png` |
  | Game-card team logos | `team_brand.parquet` logos | `assets/logos/<team_slug>.png` |

- **Never uploaded:**
  - matchup dashboards, team profiles;
  - all `.xlsx` workbooks;
  - PGWE files, net success rate, movers, unit drops, the playoff projection;
  - bet / market sheets, anything FBS.
- **The export script does the gathering.** It's [`tools/export_site.py`](../tools/export_site.py) in the website repo and runs on
  the user's computer. It copies the week's images, builds the minimal games files and writes a small manifest
  (`data/site_latest.json`) into one upload folder. The site reads the manifest to know the current week, so **nobody edits
  website code week to week**.
- **The game files are minimal.** They're built fresh from your two parquet files: FCS games only, and only what the cards
  display. Columns:
  `contest_id, week, kickoff_et, neutral, away, away_conf, away_record, home, home_conf, home_record, proj_away, proj_home, home_win_prob, away_score, home_score, has_preview, has_box_score`.
  - Projected scores are rounded to 1 decimal and win probability to 3 decimals.
  - Records are W-L going into each game, counted for FCS teams only.
  - Kickoff is converted from UTC to ET.
  - `rated == False` games get no projection.
  - TV and location are left off (not in your data).
- **Projections are kept after kickoff.** `predictions_current` drops games once they're played, so the script saves every
  projection it sees in `site_export/state/projections_2026.csv` and keeps the last pre-game one. That's how a final-score
  card still shows "Proj 21–20". It only works if the export runs **after every weekly run, before the next one** (§4).

## 2. Folder structure

### On the analytics computer (create these)

```
fcs-model/
├── site_export/                     NEW
│   ├── export_site.py               copy of tools/export_site.py from the website repo
│   ├── upload/                      made by the script each run (wiped first); the user drags its CONTENTS to GitHub
│   ├── logos_upload/                made by --logos (one-time); batch1/, batch2/, … (≤95 files each)
│   └── state/                       script memory; never upload, never delete
│       ├── projections_2026.csv     every game's last pre-game projection
│       └── published/               copies of the last uploaded games CSVs (so unchanged weeks aren't re-uploaded)
└── dashboards/
    ├── week<N>_db/previews/         PLANNED: create when game previews are built
    └── week<P>_db/box_scores/       PLANNED: create when box scores are built
```

`export_site.py` finds the project root as **the parent of `site_export/`**. No other paths need setting.
It needs pandas, pyarrow and **Pillow** (`pip install pillow` if missing).

### In the website repo (made by the uploads; shown for reference)

```
flynsm/SFCS/
├── data/
│   ├── site_latest.json             manifest: season, week, played_week, games_weeks, products
│   └── games_2026_wk<N>.csv         one per week (from Week 6 onward)
├── dashboards/
│   └── week<N>_db/                  same folder names and file names as yours
│       ├── ratings_fcs_wk<N>.png        + ratings_fcs_wk<N>_thumb.jpg (home page; made by the script)
│       ├── resume_rating_fcs_top30_wk<N>.png  + _thumb.jpg
│       ├── unit_improvers_fcs_wk<N>.png       + _thumb.jpg
│       ├── off_def_ratings_fcs_wk<N>.png      + _thumb.jpg   (planned)
│       ├── title_odds_<conf_slug>_wk<N>.png   ×13
│       ├── previews/preview_<contest_id>_wk<N>.png          (planned)
│       └── box_scores/box_score_<contest_id>_wk<N>.png      (planned; in the PLAYED week's folder)
└── assets/logos/<team_slug>.png     one-time logo upload
```

## 3. Naming rules: add these to RUNBOOK.md

1. **Existing products keep their current names and folders.** Don't rename any of the 16 files above.
   If one is ever renamed or added, tell the website side: the list is `PRODUCTS` in `export_site.py` and `RATINGS` in the
   site's `js/graphics.js`.
2. **Week numbers** follow your convention: `wk<N>` unpadded in file names; folders `dashboards/week<N>_db/`.
3. **Offense / defense ratings image (planned):** `dashboards/week<N>_db/off_def_ratings_fcs_wk<N>.png`.
   - N = UPCOMING week, like the other ratings images.
   - PNG, house style. Any size; ~2500–3000 px wide matches the others.
   - The site shows it automatically from the first week it exists.
4. **Game previews (planned; a new product, NOT the matchup dashboards):**
   - Path: `dashboards/week<N>_db/previews/preview_<contest_id>_wk<N>.png`.
   - N = the game's week, i.e. the UPCOMING week.
   - `contest_id` exactly as in `games_schedule_current.parquet` (e.g. `401868265`).
   - One PNG per game. Any aspect ratio (shown in a popup that fits the screen); ~1600–2560 px wide.
   - FCS games only. Games without a file simply show no Preview link.
5. **Box scores (planned):**
   - Path: `dashboards/week<P>_db/box_scores/box_score_<contest_id>_wk<P>.png`.
   - P = the week the game was PLAYED, so it goes in the played week's folder (the same convention as `pgwe_fcs_wk<P>.png`).
   - Same `contest_id` and image guidance as previews. The Box Score link appears once the game is final and the file exists.
6. **Team slug** (logo file names). **The exact rule, identical in `export_site.py` (`team_slug`) and the site (`teamSlug`):**
   1. lowercase the NCAA team name;
   2. delete the characters `.` `&` `'` `’` `(` `)`;
   3. replace every remaining run of characters other than `a–z` / `0–9` with one `-`;
   4. trim `-` from both ends.

   Examples: `South Dakota St.`→`south-dakota-st`, `Ark.-Pine Bluff`→`ark-pine-bluff`, `N.C. A&T`→`nc-at`,
   `St. Thomas (MN)`→`st-thomas-mn`, `William & Mary`→`william-mary`, `Texas A&M`→`texas-am`.
   These match your §C collision check. `--logos` stops with an error if two teams ever produce the same slug.
7. **Conference slug:** the label lowercased, with spaces and hyphens turned into `_` (`Coastal Athletic`→`coastal_athletic`). This is unchanged from yours.
   The site's conference links use the same slugs (`conferences/?c=big_sky`).
8. **Never hand-edit or hand-place files in the upload folder.** The script rebuilds it each run, and the games CSVs and
   `site_latest.json` are generated.

## 4. Weekly update protocol: add to RUNBOOK.md after `python run_weekly.py`

```
WEBSITE UPDATE (after every run_weekly.py, before the next one)
1. python site_export/export_site.py
   - prints the upload file list (normally ~22 files) and warns about any missing product
2. User: github.com/flynsm/SFCS -> Add file -> Upload files
   - open fcs-model/site_export/upload/, select the "dashboards" and "data" folders, drag them onto the page
   - commit directly to main (message e.g. "Week 7 update")
3. The site updates within 1–2 minutes. Spot-check the home page and the Games page.
```

- **Order matters.** The export must run **after each `run_weekly.py` and before the next one**. Projections are only kept
  if the script sees them before `predictions_current` drops played games. Re-running the export mid-week is safe.
- **Which week:** the upcoming week is taken from the highest `dashboards/week<N>_db/`. To override: `--week N`.
- **Upload size:** github.com takes at most 100 files per upload. Today's uploads are ~22 files. Once previews and box scores
  exist (~65 + ~65 per week), the script will warn; then drag `dashboards/week<N>_db`, `dashboards/week<P>_db` and `data`
  in separate uploads.
- **Older weeks:** older game files are re-uploaded only if they changed (e.g. a late score), and the script includes them automatically.

## 5. One-time setup: please do these now, in order

**a. Install.**
- Create `fcs-model/site_export/` and put `export_site.py` in it. The user can download it from the website repo:
  `tools/export_site.py` → "Download raw file" (branch `claude/sleepy-wozniak-qchi70` until it's merged to `main`).
- Make sure Pillow is installed.
- Add §3 and §4 to RUNBOOK.md.

**b. Save the Week 6 projections: TIME-SENSITIVE.**
- Run `python site_export/export_site.py --snapshot` **before the next `run_weekly.py`** (the Week 7 run).
  This keeps the Week 6 pre-game projections so the Week 6 final-score cards can show them.
- If the Week 7 run has already happened, skip this. The Week 6 cards will show final scores without projections, and every
  week after that will be complete.

**c. Logos (one-time).**
- Run `python site_export/export_site.py --logos`. It writes all FCS teams plus their FBS opponents to `site_export/logos_upload/batch*/`.
- The user uploads each batch separately: open `batchN/`, drag its `assets` folder onto Upload files, commit.
- Non-D1 opponents have no logo and the site shows their initials.
- Re-run only when a team is added.

**d. Week 7 placeholder test.** Run this AFTER the Week 7 `run_weekly.py`, so Week 6 has final scores.
- Command: `python site_export/export_site.py --week 7 --placeholders`
- **Where it writes:** labeled placeholder PNGs ("WEEK 7 POWER RATINGS / PLACEHOLDER / ratings_fcs_wk7.png") go into
  **`site_export/upload/` only**, named and placed exactly like the real files. **It never writes into `dashboards/`**, so real
  outputs can't be overwritten.
- **What it contains:**
  - the 4 ratings images, including the planned off/def one, plus thumbnails;
  - the 13 title-odds images;
  - previews for the first 5 Week 7 games;
  - box scores for the first 5 completed Week 6 games.
  - The games CSVs and manifest are built from REAL data, so the Games page shows real Week 7 projections and Week 6 finals.
- **Check:** confirm the printed list has 34 files, including the 5 `previews/preview_<id>_wk7.png` and the 5
  `box_scores/box_score_<id>_wk6.png`.
- **User:** upload it (same drag as §4), then check the site:
  - Ratings pages: each one shows its labeled Week 7 placeholder.
  - Conference Races: all 13 pages show placeholders.
  - Games page: Week 7 projected cards, 5 of them with **Preview**; Week 6 final cards, 5 of them with **Box Score**.
  - Home page: 4 cards.

**e. Go live.**
- Run the real export (`python site_export/export_site.py`) and upload it. The real images replace the placeholders (same names).
- The Preview and Box Score links and the Offense/Defense page switch back off, because those products don't exist yet.
- The 10 placeholder preview and box-score PNGs and the off/def placeholder stay in the repo, but nothing links to them.
  The user can delete them on GitHub or leave them.

## 6. Please send back

- Confirmation that a–e worked, plus the file list printed in (d), or any error output.
- Anything in your data that doesn't fit (e.g. a `matchup` value other than the three listed, or how a cancelled game appears
  once you see one).
- **When previews, box scores or the off/def image get built:** just follow §3. No website change is needed.
  Tell the website side if any of them needs a different name or location.

---

### Appendix: `data/site_latest.json` (written by the script)

```json
{
  "season": 2026,
  "week": 7,
  "played_week": 6,
  "games_weeks": [6, 7],
  "products": ["ratings_fcs", "resume_rating_fcs_top30", "unit_improvers_fcs", "title_odds_big_sky", "…"],
  "updated": "2026-10-11T14:02:11Z"
}
```

- `products` lists only the images actually uploaded that week. A page whose product is missing shows "Coming soon" instead of a broken image.
- **Next season:** before Week 1 of 2027, tell the website side. `SEASON` changes in the script, and the repo's `week<N>_db`
  folders would otherwise collide with 2026's.
