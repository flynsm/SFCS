# SFCS — FCS Football Analytics website

Plain HTML/CSS site, built for GitHub Pages (no build step).

## Layout

```
index.html              Home page ("Latest" graphics feed)
ratings/                Power Ratings, Resume Rating, Biggest Improvers
predictions/            Weekly Picks, Season Projections (placeholders)
conferences/index.html  One page for every conference: conferences/?c=mvfc
box-scores.html         Placeholder
about.html              About page (fill in your bio)
css/style.css           All styling; brand colors are at the top
js/site.js              Shared header, nav and footer. Edit the NAV list to add or rename menu items
assets/brand/           Logos used by the site
assets/graphics/        Weekly graphics, e.g. 2026/week-6/
Site resources/         Original logo and reference files
```

## Posting a new week's graphics

1. Put the images in `assets/graphics/2026/week-7/`.
2. On each ratings page, change the `<img>`/link path and the "Week 6" text.
3. On `index.html`, update the cards in the "Latest" section.

## Turning on GitHub Pages

In the repo, go to Settings → Pages, choose "Deploy from a branch", select `main` and `/ (root)`.
