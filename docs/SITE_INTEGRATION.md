# SFCS website: data integration brief

**Who this is for:** the Claude that builds the SFCS model, analytics pipeline and graphics.
**Written by:** the Claude that built the SFCS website (repo `flynsm/SFCS`, branch `claude/sleepy-wozniak-qchi70`).
**Purpose:** say exactly what files the website reads, so your pipeline's outputs can drop straight in.
Where your conventions already differ, the site side is easy to change; see [What's flexible](#whats-flexible-on-the-site-side).

---

## 1. What the site is

A static site (plain HTML/CSS/JS, no build step) hosted on GitHub Pages. It has no server: it reads files
committed to the repo, in the visitor's browser. Publishing new data therefore means
**writing files into the repo and pushing**.

| Page | What it shows | Reads |
|---|---|---|
| Home | Newest week's ratings graphics as cards | `js/graphics.js` list + `assets/graphics/…` |
| Ratings → Power / Resume / Offense-Defense / Biggest Improvers | Newest week's graphic (PNG) | `assets/graphics/<season>/week-<N>/<name>.png` |
| Games | Card per game: projected score; once played, final score + projected score. Week and conference filters. | `data/games-2026.xlsx` + preview / box score PNGs + team logos |
| Conference Races, Box Scores, About | Placeholders for now | n/a |

---

## 2. Games spreadsheet (most important)

**File:** `data/games-2026.xlsx`. One workbook for the whole season.
**Sheet:** the **first** sheet is read; others are ignored.
**Layout:** header names in row 1, then **one row per game**. Row order doesn't matter; the site sorts by date, then kickoff time.

| Column | Required | Type / example | Behavior |
|---|---|---|---|
| `week` | **yes** | integer, `7` | Week filter buttons are built from the distinct values. Rows without a week are skipped. |
| `date` | no | Excel date or text `2026-10-10` | Shown as "Sat, Oct 10". |
| `time` | no | text `2:00 PM`, or an Excel time | Shown as-is; used for sorting. |
| `tv` | no | `ESPN+` | Shown in the card header. |
| `away` | **yes** | team name, `Montana` | Displayed as-is. Also used to build file names; see §4. |
| `home` | **yes** | team name, `Montana St.` | Same. |
| `away_conf`, `home_conf` | no | `Big Sky` | Drives the conference filter; see §3. |
| `away_record`, `home_record` | no | `5-1` | Shown under the team name. |
| `neutral` | no | `yes` / `true` / `1` / `x` | Shows "vs" instead of "at". Blank means a home game. |
| `location` | no | `Bozeman, MT` | Shown under the teams. |
| `proj_away`, `proj_home` | no (expected) | numbers, `21`, `30` | Projected score. Also gives "Montana St. by 9". Shown with decimals if you supply them; round in the pipeline if you want whole numbers. |
| `home_win_prob` | no | `0.76`, or `76` | Home win probability. Values over 1 are treated as percentages. The card shows the favorite's probability. |
| `away_score`, `home_score` | no | integers | **Leave blank until the game is final.** When **both** are filled, that game becomes final: the card shows the final score, keeps "Proj 21–30", and the link changes from **Preview** to **Box Score**. This is decided per game, not per week. |
| `preview_image` | no | site-relative path | Overrides the default preview path (§5). |
| `boxscore_image` | no | site-relative path | Overrides the default box score path (§5). |

Notes:
- Header matching ignores case, spaces and underscores (`Proj Away`, `proj_away` and `PROJAWAY` all match). Hyphens are not ignored.
  Extra columns are ignored, so the pipeline can keep its own columns in the sheet.
- The page opens on the **first week that still has an unplayed game**, falling back to the last week.
- `data/games-2026.xlsx` is currently **made-up sample data** (weeks 6–7). Overwrite it completely.
- The sheet is read by a small browser library (read-excel-file). Plain values work best. Formulas are fine
  if the file was saved by Excel, since cached values are stored, but files written by Python libraries without computed
  values may show blanks. **Write values, not formulas.**

---

## 3. Conference names

The filter knows these conferences. A game's conference cell matches if it equals the **label** or the **id**
(case and punctuation ignored).

| id | label |
|---|---|
| big-sky | Big Sky |
| caa | Coastal Athletic |
| ivy | Ivy |
| meac | MEAC |
| mvfc | MVFC |
| nec | NEC |
| ovc | OVC |
| patriot | Patriot |
| pioneer | Pioneer |
| southern | Southern |
| southland | Southland |
| swac | SWAC |
| uac | UAC |
| independents | FCS Independents |

A conference value that matches none of these still shows under "All", but gets no filter button.
FBS opponents can be given their real conference (e.g. `Big 12`); they'll simply have no button.
Buttons only appear for conferences that occur somewhere in the season's data. The list lives in `js/site.js`
(`CONFERENCES`) and also drives the Conference Races menu.

---

## 4. Team names → file names ("slug")

The site makes a file-safe **slug** from the team name in the `away` / `home` cell:

1. lowercase
2. `&` → `and`
3. remove `.` `'` `’` `(` `)`
4. every other run of non-letters/digits → `-`
5. trim leading/trailing `-`

| Team name in sheet | Slug |
|---|---|
| South Dakota St. | `south-dakota-st` |
| Ark.-Pine Bluff | `ark-pine-bluff` |
| St. Thomas (MN) | `st-thomas-mn` |
| William & Mary | `william-and-mary` |
| Texas A&M-Commerce | `texas-aandm-commerce` |
| UT Martin | `ut-martin` |

**Team logos:** `assets/logos/<slug>.png`. Square-ish PNG with a transparent background, about 128–256 px. It shows at 44 px.
A team without a logo file shows its initials instead, so missing logos never break the page.

> **Key consistency point:** the name the pipeline writes into the sheet must produce the same slug as the logo file name.
> If the pipeline already has a canonical team key (an ID or a short name), tell us and we'll key logos and images on that instead
> (e.g. add `away_id` / `home_id` columns). See §7.

---

## 5. Game preview and box score images

When `preview_image` / `boxscore_image` are blank, the site looks for:

```
assets/games/2026/week-<N>/<away-slug>-at-<home-slug>-preview.png
assets/games/2026/week-<N>/<away-slug>-at-<home-slug>-boxscore.png
```

Example: `assets/games/2026/week-7/montana-at-montana-st-preview.png`

- They open in a popup that fits the window, with an "Open full-size image" link. Any aspect ratio works.
  Around 1600–2400 px wide keeps the files reasonably small.
- A missing image shows "Not posted yet" in the popup; nothing breaks.
- Preview images only matter for unplayed games, and box scores only for final ones.
- `assets/games/sample-preview.png` and `sample-boxscore.png` are placeholders and can be deleted.

---

## 6. Weekly ratings graphics

```
assets/graphics/2026/week-<N>/power-ratings.png
assets/graphics/2026/week-<N>/resume-rating.png
assets/graphics/2026/week-<N>/unit-ratings.png        (Offense / Defense Ratings, none posted yet)
assets/graphics/2026/week-<N>/biggest-improvers.png
```

After adding files, add `<N>` to that graphic's `weeks: [...]` list in `js/graphics.js`.
The site shows the highest week listed. Optional: `python3 tools/make_thumbs.py` creates `-thumb.jpg` previews for the home page;
without them the home page falls back to the full PNG.

---

## 7. What's flexible on the site side

All of these are small, isolated changes; tell us your preference and the site will adapt:

| Want | Change needed on the site |
|---|---|
| Different column names | Edit the `COLUMNS` map in `js/games-data.js` |
| CSV or JSON instead of .xlsx | Swap `loadGames()` in `js/games-data.js`; the rest of the page is unchanged |
| One file per week instead of per season | Small change to `loadGames()` |
| Team IDs / canonical keys instead of display names for files | Add ID columns; change `teamSlug()` or add a lookup table |
| Different image file naming / folders | Change `defaultImage()` in `js/games-data.js`, or fill the `*_image` columns |
| Spread, rankings or extra stats on the card | Add columns; the site adds them to the card |
| Graphics list generated by the pipeline | `js/graphics.js` could read a JSON manifest the pipeline writes |

---

## 8. Questions for you (the pipeline Claude)

Please answer these so the site matches the pipeline exactly:

1. **Output format:** what does the pipeline produce for game predictions and results today (xlsx, CSV, JSON, a DataFrame)? Column names?
2. **Team naming:** what's the canonical team identifier? Is the display name the same as in the graphics
   (e.g. `South Dakota St.`, `Ark.-Pine Bluff`, `UNI`, `SFA`)? Is there a team table (name, short name, conference, logo file)?
3. **Logos:** where do the logos used in the graphics live, and how are they named? Ideally the site reuses the same files.
4. **Conference labels:** do they match §3 (e.g. `Coastal Athletic`, `UAC`, `FCS Independents`)?
5. **Game identity:** is there a game ID? It would make image file names more robust than `<away>-at-<home>`.
6. **Images:** what are the output file names and paths for preview, box score and weekly ratings graphics?
7. **Projection fields:** projected scores, win probability, spread: which exist, and are they rounded?
8. **Neutral sites, FBS opponents, postponed games:** how are they represented?
9. **Publishing:** will the pipeline write into this repo directly (commit/push), or will files be copied over by hand?

## 9. How to reply

Answer in whatever form is convenient (a message, or a commit adding notes to this file under a "Pipeline answers" section).
Sample rows of real output, and the team table if there is one, are the most useful things to include.
