/* ==========================================================================
   Weekly images: ratings pages, conference title odds, home page feed.
   Which week is shown comes from data/site_latest.json (written by the
   weekly export), so nothing here changes week to week.
   ========================================================================== */

(function () {
  // Site page -> model product key (file: <key>_wk<N>.png)
  const RATINGS = {
    power: {
      key: "ratings_fcs",
      title: "FCS Power Ratings",
      blurb: "Every FCS team ranked by SFCS power rating, with week-over-week movement.",
    },
    resume: {
      key: "resume_rating_fcs_top30",
      title: "FCS Resume Rating",
      blurb: "Top 30 résumés: record, expected wins and points per game above expectation.",
    },
    units: {
      key: "off_def_ratings_fcs",
      title: "FCS Offense / Defense Ratings",
      blurb: "Opponent-adjusted offensive and defensive efficiency for every FCS team.",
    },
    improvers: {
      key: "unit_improvers_fcs",
      title: "FCS Biggest Improvers",
      blurb: "Scoring efficiency relative to D1 average, adjusted for opponent, pace and field position.",
    },
  };

  const D = window.SFCSData;
  const comingSoon = (msg) => `<div class="placeholder"><strong>Coming soon</strong>${msg}</div>`;

  function figure(src, alt) {
    return `<figure class="graphic">
        <img src="${src}" alt="${alt}">
        <figcaption><a href="${src}" target="_blank" rel="noopener">Open full-size image</a></figcaption>
      </figure>`;
  }

  // ---- Ratings page: <div id="graphic-page" data-graphic="power"> ----
  function renderRatings(el, latest) {
    const g = RATINGS[el.dataset.graphic];
    const posted = latest?.products.includes(g.key);
    const week = latest?.week;
    el.innerHTML = `
      <header class="page-head">
        <p class="eyebrow">Ratings${posted ? ` · ${latest.season} · Week ${week}` : ""}</p>
        <h1>${posted ? `Week ${week} ` : ""}${g.title}</h1>
        <p class="lede">${g.blurb}</p>
      </header>
      ${posted ? figure(D.image(g.key, week), `Week ${week} ${g.title}`) : comingSoon("Not posted yet.")}`;
    document.title = `${posted ? `Week ${week} ` : ""}${g.title} · SFCS`;
  }

  // ---- Conference Races: <div id="conference-page"> (?c=<conf slug>) ----
  function renderConference(el, latest) {
    const confs = window.SFCS.CONFERENCES.filter((c) => c.races);
    const conf = confs.find((c) => c.id === new URLSearchParams(location.search).get("c"));

    if (!conf) {
      el.innerHTML = `
        <header class="page-head">
          <p class="eyebrow">Conference Races${latest ? ` · Week ${latest.week}` : ""}</p>
          <h1>Conference Races</h1>
          <p class="lede">Title odds for every FCS conference.</p>
        </header>
        <div class="conf-grid">
          ${confs.map((c) => `<a class="conf-tile" href="?c=${c.id}">${c.label}</a>`).join("")}
        </div>`;
      return;
    }

    const key = `title_odds_${conf.id}`;
    const posted = latest?.products.includes(key);
    el.innerHTML = `
      <header class="page-head">
        <p class="eyebrow">Conference Races${posted ? ` · Week ${latest.week}` : ""}</p>
        <h1>${conf.label} Title Odds</h1>
      </header>
      ${posted ? figure(D.image(key, latest.week), `Week ${latest.week} ${conf.label} title odds`) : comingSoon("Not posted yet.")}`;
    document.title = `${conf.label} Title Odds · SFCS`;
  }

  // ---- Home page: <div id="latest-feed"> ----
  function renderLatest(el, latest) {
    const label = document.getElementById("latest-week");
    const cards = Object.entries(RATINGS).filter(([, g]) => latest?.products.includes(g.key));
    if (!cards.length) {
      el.innerHTML = comingSoon("This week's ratings will appear here.");
      return;
    }
    if (label) label.textContent = `Week ${latest.week}`;
    el.innerHTML = cards
      .map(([page, g]) => `
        <a class="card" href="${D.url(`ratings/${page}.html`)}">
          <div class="card-thumb">
            <img src="${D.thumb(g.key, latest.week)}" alt="" loading="lazy" width="800" height="500"
                 onerror="this.onerror=null;this.src='${D.image(g.key, latest.week)}'">
          </div>
          <div class="card-body">
            <span class="card-tag">Ratings</span>
            <h3>Week ${latest.week} ${g.title}</h3>
          </div>
        </a>`)
      .join("");
  }

  document.addEventListener("DOMContentLoaded", async () => {
    const latest = await D.latest();
    const $ = (id) => document.getElementById(id);
    if ($("graphic-page")) renderRatings($("graphic-page"), latest);
    if ($("conference-page")) renderConference($("conference-page"), latest);
    if ($("latest-feed")) renderLatest($("latest-feed"), latest);
  });
})();
