# SFCS — FCS Football Analytics website

Plain HTML/CSS site, built for GitHub Pages (no build step).

## Layout

```
index.html              Home page ("Latest" graphics feed)
ratings/                Power, Resume, Offense/Defense, Biggest Improvers (newest week)
games.html              Game cards with week + conference filters (data from data/games-2026.xlsx)
data/                   Spreadsheets the site reads
conferences/index.html  One page for every conference: conferences/?c=mvfc
box-scores.html         Placeholder
about.html              About page (fill in your bio)
css/style.css           All styling; brand colors are at the top
js/site.js              Shared header, nav and footer. Edit the NAV list to add or rename menu items
js/graphics.js          List of weekly graphics: feeds the week pickers and the home page
js/games-data.js        Reads the games spreadsheet (column names live here)
js/games.js             Games page: filters, cards, preview/box score popup
js/vendor/              read-excel-file 9.3.10 (MIT), reads .xlsx in the browser
tools/make_thumbs.py    Optional: makes small home-page previews of new graphics
assets/brand/           Logos used by the site
assets/graphics/        Weekly graphics, e.g. 2026/week-6/
Site resources/         Original logo and reference files
```

## Posting a new week's graphics

1. Put the images in `assets/graphics/2026/week-7/`, using the same file names as before
   (`power-ratings.png`, `resume-rating.png`, `unit-ratings.png`, `biggest-improvers.png`).
2. In `js/graphics.js`, add `7` to the `weeks` list of each graphic you posted.
3. Optional: run `python3 js/games-data.js        Reads the games spreadsheet (column names live here)
js/games.js             Games page: filters, cards, preview/box score popup
js/vendor/              read-excel-file 9.3.10 (MIT), reads .xlsx in the browser
tools/make_thumbs.py` so the home page loads faster.

The ratings pages default to the newest week, and the home page shows the newest week automatically.

## Games spreadsheet

Full data spec for the analytics pipeline: [`docs/SITE_INTEGRATION.md`](docs/SITE_INTEGRATION.md).

`data/games-2026.xlsx`, first sheet, one row per game, headers in row 1.
**The current file is sample data**: overwrite it with your own.

| Column | Example | Notes |
|---|---|---|
| week | 7 | required |
| date | 10/10/2026 | Excel date or text |
| time | 2:00 PM | text or Excel time |
| tv | ESPN+ | optional |
| away / home | Montana St. | required; team names |
| away_conf / home_conf | Big Sky | drives the conference filter (names as in the nav, e.g. MVFC, Coastal Athletic) |
| away_record / home_record | 5-1 | optional |
| neutral | yes | optional; shows "vs" instead of "at" |
| location | Bozeman, MT | optional |
| proj_away / proj_home | 21 / 30 | projected score |
| home_win_prob | 0.76 or 76% | optional |
| away_score / home_score | 27 / 31 | **leave blank until the game is played.** Once filled, the card shows the final score and a Box Score link instead of Preview |
| preview_image / boxscore_image | | optional; if blank the site looks for `assets/games/2026/week-7/montana-at-montana-st-preview.png` (or `-boxscore.png`) |

The page opens on the first week that still has unplayed games.
If your headers are named differently, edit `COLUMNS` in `js/games-data.js`.

**Team logos:** `assets/logos/<team>.png`, named from the team name in lowercase with
dashes and no periods (`South Dakota St.` → `south-dakota-st.png`). Teams without a logo show their initials.

## Turning on GitHub Pages

In the repo, go to Settings → Pages, choose "Deploy from a branch", select `main` and `/ (root)`.
