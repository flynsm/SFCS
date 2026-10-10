# SFCS — FCS Football Analytics website

Plain HTML/CSS/JS site, built for GitHub Pages (no build step).

## Weekly update

1. On the analytics computer, after `python run_weekly.py`, run `python site_export/export_site.py`.
2. On github.com: **Add file → Upload files**. Open `fcs-model/site_export/upload/`, drag its `dashboards` and `data`
   folders onto the page, and commit to `main`.
3. The site picks up the new week by itself within a minute or two.

Full rules (folders, file names, one-time setup, placeholder test): [`docs/SITE_INTEGRATION.md`](docs/SITE_INTEGRATION.md).

## Layout

```
index.html              Home page ("Latest" ratings cards)
ratings/                Power, Resume, Offense/Defense (planned), Biggest Improvers: newest week
games.html              Game cards with week + conference filters
conferences/index.html  Conference title odds: conferences/?c=big_sky (all conferences without ?c)
box-scores.html         Placeholder (box scores open from the Games page once they exist)
about.html              About page (fill in your bio)

data/site_latest.json   Written by the export: current week + which images were posted
data/games_<season>_wk<N>.csv   Written by the export: one file per week of games
dashboards/week<N>_db/  Weekly images, same folder and file names as the model
assets/logos/           Team logos (<team-slug>.png), one-time upload
assets/brand/           SFCS logos used by the site

css/style.css           All styling; brand colors are at the top
js/site.js              Shared header, nav, footer and the conference list
js/data.js              Reads the manifest and games files; file-name rules
js/graphics.js          Ratings, conference and home pages
js/games.js             Games page: filters, cards, preview/box score popup
tools/export_site.py    The weekly export script (runs on the analytics computer)
docs/SITE_INTEGRATION.md  Integration rules for the analytics pipeline
Site resources/         Original logo and reference files
```

## Viewing locally

Browsers block the data files when you open the HTML straight from disk. Run `python3 -m http.server` in this folder
and open http://localhost:8000.

## Turning on GitHub Pages

In the repo, go to Settings → Pages, choose "Deploy from a branch", select `main` and `/ (root)`.
