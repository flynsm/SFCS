# SFCS — FCS Football Analytics website

Plain HTML/CSS site, built for GitHub Pages (no build step).

## Layout

```
index.html              Home page ("Latest" graphics feed)
ratings/                Power, Resume, Offense/Defense, Biggest Improvers (with week picker)
predictions.html        Placeholder
conferences/index.html  One page for every conference: conferences/?c=mvfc
box-scores.html         Placeholder
about.html              About page (fill in your bio)
css/style.css           All styling; brand colors are at the top
js/site.js              Shared header, nav and footer. Edit the NAV list to add or rename menu items
js/graphics.js          List of weekly graphics: feeds the week pickers and the home page
tools/make_thumbs.py    Optional: makes small home-page previews of new graphics
assets/brand/           Logos used by the site
assets/graphics/        Weekly graphics, e.g. 2026/week-6/
Site resources/         Original logo and reference files
```

## Posting a new week's graphics

1. Put the images in `assets/graphics/2026/week-7/`, using the same file names as before
   (`power-ratings.png`, `resume-rating.png`, `unit-ratings.png`, `biggest-improvers.png`).
2. In `js/graphics.js`, add `7` to the `weeks` list of each graphic you posted.
3. Optional: run `python3 tools/make_thumbs.py` so the home page loads faster.

The ratings pages default to the newest week, and the home page shows the newest week automatically.

## Turning on GitHub Pages

In the repo, go to Settings → Pages, choose "Deploy from a branch", select `main` and `/ (root)`.
