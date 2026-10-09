/* ==========================================================================
   Weekly graphics.
   To post a new week: put the images in assets/graphics/<SEASON>/week-<N>/
   and add the week number to each graphic's `weeks` list below.
   The ratings pages (week picker) and the home page "Latest" feed both
   read from this list.
   Optional: run tools/make_thumbs.py to create small home-page previews.
   ========================================================================== */

const SEASON = 2026;

const GRAPHICS = {
  power: {
    title: "FCS Power Ratings",
    file: "power-ratings",
    blurb: "Every FCS team ranked by SFCS power rating, with week-over-week movement.",
    weeks: [6],
  },
  resume: {
    title: "FCS Resume Rating",
    file: "resume-rating",
    blurb: "Top 30 résumés: record, expected wins and points per game above expectation.",
    weeks: [6],
  },
  units: {
    title: "FCS Offense / Defense Ratings",
    file: "unit-ratings",
    blurb: "Opponent-adjusted offensive and defensive efficiency for every FCS team.",
    weeks: [],
  },
  improvers: {
    title: "FCS Biggest Improvers",
    file: "biggest-improvers",
    blurb: "Scoring efficiency relative to D1 average, adjusted for opponent, pace and field position.",
    weeks: [6],
  },
};

(function () {
  const root = new URL("..", document.currentScript.src);
  const url = (p) => new URL(p, root).href;
  const img = (g, week, suffix = ".png") =>
    url(`assets/graphics/${SEASON}/week-${week}/${g.file}${suffix}`);
  const latest = (g) => Math.max(...g.weeks);

  // ---- Ratings page: <div id="graphic-page" data-graphic="power"> ----
  function renderGraphicPage(el) {
    const g = GRAPHICS[el.dataset.graphic];
    const weeks = [...g.weeks].sort((a, b) => a - b);

    if (!weeks.length) {
      el.innerHTML = `
        <header class="page-head">
          <p class="eyebrow">Ratings · ${SEASON}</p>
          <h1>${g.title}</h1>
          <p class="lede">${g.blurb}</p>
        </header>
        <div class="placeholder"><strong>Coming soon</strong>No weeks posted yet.</div>`;
      document.title = `${g.title} · SFCS`;
      return;
    }

    const asked = Number(new URLSearchParams(location.search).get("week"));
    const week = weeks.includes(asked) ? asked : latest(g);
    const src = img(g, week);
    const chips = weeks
      .map((w) => `<a href="?week=${w}"${w === week ? ' aria-current="page"' : ""}>Wk ${w}</a>`)
      .join("");

    el.innerHTML = `
      <header class="page-head">
        <p class="eyebrow">Ratings · ${SEASON} · Week ${week}</p>
        <h1>Week ${week} ${g.title}</h1>
        <p class="lede">${g.blurb}</p>
      </header>
      <nav class="week-picker" aria-label="Choose week">${chips}</nav>
      <figure class="graphic">
        <img src="${src}" alt="Week ${week} ${g.title}">
        <figcaption><a href="${src}" target="_blank" rel="noopener">Open full-size image</a></figcaption>
      </figure>`;
    document.title = `Week ${week} ${g.title} · SFCS`;
  }

  // ---- Home page: <div id="latest-feed"> ----
  function renderLatest(el) {
    const posted = Object.entries(GRAPHICS).filter(([, g]) => g.weeks.length);
    const newest = Math.max(...posted.map(([, g]) => latest(g)));
    const label = document.getElementById("latest-week");
    if (label) label.textContent = `Week ${newest}`;

    el.innerHTML = posted
      .filter(([, g]) => latest(g) === newest)
      .map(([key, g]) => `
        <a class="card" href="${url(`ratings/${key}.html`)}">
          <div class="card-thumb">
            <img src="${img(g, newest, "-thumb.jpg")}" alt="" loading="lazy" width="800" height="500"
                 onerror="this.onerror=null;this.src='${img(g, newest)}'">
          </div>
          <div class="card-body">
            <span class="card-tag">Ratings</span>
            <h3>Week ${newest} ${g.title}</h3>
          </div>
        </a>`)
      .join("");
  }

  document.addEventListener("DOMContentLoaded", () => {
    const page = document.getElementById("graphic-page");
    if (page) renderGraphicPage(page);
    const feed = document.getElementById("latest-feed");
    if (feed) renderLatest(feed);
  });
})();
