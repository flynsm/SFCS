/* ==========================================================================
   Games page: week + conference filters, game cards, preview/box score popup.
   Weeks come from data/site_latest.json; each week's games from
   data/games_<season>_wk<N>.csv (see js/data.js).
   ========================================================================== */

(function () {
  const D = window.SFCSData;

  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const norm = (s) => String(s ?? "").toLowerCase().replace(/[^a-z0-9]/g, "");

  let latest = null;
  let games = [];               // games of the selected week
  const cache = {};             // week -> games
  const state = { week: null, conf: "all" };
  let el = {};

  // ---------- Conferences ----------
  // Match a data conference ("Big Sky", "big_sky") to the site list.
  function confId(name) {
    const n = norm(name);
    return window.SFCS.CONFERENCES.find((c) => norm(c.id) === n || norm(c.label) === n)?.id ?? null;
  }

  // ---------- Formatting ----------
  const fmtDate = (d) =>
    d ? d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" }) : "";
  const whole = (v) => (v == null ? "–" : Math.round(v));

  function initials(name) {
    const words = name.replace(/[.'’()]/g, "").split(/[\s&-]+/).filter(Boolean);
    return (words.length === 1 ? words[0].slice(0, 3) : words.map((w) => w[0]).join("").slice(0, 3)).toUpperCase();
  }

  function logo(team) {
    // Initials show until/unless assets/logos/<slug>.png loads (non-D1 teams have none).
    return `<span class="team-logo">
        <span class="team-mono" aria-hidden="true">${esc(initials(team.name))}</span>
        <img src="${D.logo(team.name)}" alt="" loading="lazy"
             onload="this.previousElementSibling.remove()" onerror="this.remove()">
      </span>`;
  }

  // ---------- Card ----------
  function teamRow(g, side) {
    const t = g[side];
    const other = g[side === "away" ? "home" : "away"];
    const won = g.final && t.score > other.score;
    const lost = g.final && t.score < other.score;
    const sub = [t.record, t.conf].filter(Boolean).map(esc).join(" · ");
    return `<div class="team-row${won ? " is-winner" : ""}${lost ? " is-loser" : ""}">
        ${logo(t)}
        <div class="team-name">
          <span>${esc(t.name)}</span>
          ${sub ? `<small>${sub}</small>` : ""}
        </div>
        <div class="team-score">${g.final ? t.score : whole(t.proj)}</div>
      </div>`;
  }

  const hasProj = (g) => g.away.proj != null && g.home.proj != null;

  // Projected winner + margin, e.g. "Montana St. by 9.2 · 76%".
  function projText(g) {
    if (!hasProj(g)) return "No projection";
    const { away: a, home: h } = g;
    const margin = Math.abs(h.proj - a.proj);
    if (margin < 0.05) return "Projected even";
    const fav = h.proj > a.proj ? h : a;
    let text = `${esc(fav.name)} by ${margin.toFixed(1)}`;
    if (g.homeWinProb != null) {
      const p = fav === h ? g.homeWinProb : 1 - g.homeWinProb;
      text += ` · ${Math.round(p * 100)}%`;
    }
    return text;
  }

  function card(g, i) {
    const meta = [fmtDate(g.date), g.time].filter(Boolean).map(esc).join(" · ");
    let note, link = "";
    if (g.final) {
      note = hasProj(g) ? `Proj ${whole(g.away.proj)}–${whole(g.home.proj)}` : "";
      if (g.hasBoxScore) link = `<button class="game-link" type="button" data-i="${i}" data-kind="box">Box Score</button>`;
    } else {
      note = projText(g);
      if (g.hasPreview) link = `<button class="game-link" type="button" data-i="${i}" data-kind="preview">Preview</button>`;
    }

    return `<article class="game-card${g.final ? " is-final" : ""}">
        <header class="game-meta">
          <span>${meta}</span>
          <span class="game-status">${g.final ? "Final" : "Projected"}</span>
        </header>
        <div class="game-teams">
          ${teamRow(g, "away")}
          <div class="game-at">${g.neutral ? "vs (neutral site)" : "at"}</div>
          ${teamRow(g, "home")}
        </div>
        <footer class="game-foot"><span class="game-note">${note}</span>${link}</footer>
      </article>`;
  }

  // ---------- Page ----------
  function syncUrl() {
    const q = new URLSearchParams();
    q.set("week", state.week);
    if (state.conf !== "all") q.set("conf", state.conf);
    history.replaceState(null, "", `?${q}`);
  }

  function renderChips() {
    el.weeks.innerHTML = latest.games_weeks
      .map((w) => `<button type="button" data-week="${w}"${w === state.week ? ' aria-pressed="true"' : ""}>Wk ${w}</button>`)
      .join("");

    // Conferences that appear this week, in site order.
    const present = new Set(games.flatMap((g) => [confId(g.away.conf), confId(g.home.conf)]));
    const confs = window.SFCS.CONFERENCES.filter((c) => present.has(c.id));
    el.confs.innerHTML = [{ id: "all", label: "All" }, ...confs]
      .map((c) => `<button type="button" data-conf="${c.id}"${c.id === state.conf ? ' aria-pressed="true"' : ""}>${esc(c.label)}</button>`)
      .join("");

    for (const row of [el.weeks, el.confs]) {
      const b = row.querySelector('[aria-pressed="true"]');
      if (b && (b.offsetLeft + b.offsetWidth > row.scrollLeft + row.clientWidth || b.offsetLeft < row.scrollLeft)) {
        row.scrollLeft = b.offsetLeft - row.offsetLeft - 16;
      }
    }
  }

  function render() {
    const label = state.week === latest.week ? " · This week" : state.week === latest.played_week ? " · Last week" : "";
    el.eyebrow.textContent = `${latest.season} Season · Week ${state.week}${label}`;
    el.title.textContent = `Week ${state.week} Games`;
    document.title = `Week ${state.week} Games · SFCS`;
    renderChips();

    const shown = (state.conf === "all"
      ? games
      : games.filter((g) => confId(g.away.conf) === state.conf || confId(g.home.conf) === state.conf)
    ).sort((a, b) => (a.date ?? 0) - (b.date ?? 0) || a.minutes - b.minutes);

    el.summary.textContent = `${shown.length} game${shown.length === 1 ? "" : "s"}`;
    el.grid.innerHTML = shown.length
      ? shown.map((g) => card(g, games.indexOf(g))).join("")
      : `<div class="placeholder"><strong>No games</strong>Nothing scheduled for this filter.</div>`;
  }

  async function loadWeek(w) {
    el.grid.setAttribute("aria-busy", "true");
    try {
      games = cache[w] ??= await D.games(latest.season, w);
    } catch (err) {
      console.error(err);
      games = [];
    }
    el.grid.removeAttribute("aria-busy");
    // Keep the conference filter only if that conference plays this week.
    if (state.conf !== "all" && !games.some((g) => [confId(g.away.conf), confId(g.home.conf)].includes(state.conf))) {
      state.conf = "all";
    }
    render();
  }

  // ---------- Popup ----------
  function openModal(g, kind) {
    const src = kind === "box" ? D.boxScore(g.id, g.week) : D.preview(g.id, g.week);
    const label = kind === "box" ? "Box Score" : "Game Preview";
    el.modalTitle.textContent = `${g.away.name} ${g.neutral ? "vs" : "at"} ${g.home.name} · ${label}`;
    el.modalBody.innerHTML = `<img src="${src}" alt="${esc(label)}: ${esc(g.away.name)} at ${esc(g.home.name)}">`;
    el.modalBody.querySelector("img").onerror = () => {
      el.modalBody.innerHTML = `<div class="placeholder"><strong>Not posted yet</strong>Check back soon.</div>`;
      el.modalFull.hidden = true;
    };
    el.modalFull.href = src;
    el.modalFull.hidden = false;
    el.modal.showModal();
  }

  document.addEventListener("DOMContentLoaded", async () => {
    const $ = (id) => document.getElementById(id);
    el = {
      eyebrow: $("games-eyebrow"), title: $("games-title"), weeks: $("week-chips"), confs: $("conf-chips"),
      summary: $("games-summary"), grid: $("games-grid"), modal: $("game-modal"),
      modalTitle: $("game-modal-title"), modalBody: $("game-modal-body"), modalFull: $("game-modal-full"),
    };

    latest = await D.latest();
    if (!latest?.games_weeks?.length) {
      el.grid.innerHTML = `<div class="placeholder"><strong>Coming soon</strong>Game projections will appear here after the next weekly update.</div>`;
      document.querySelector(".filters").hidden = true;
      return;
    }

    const q = new URLSearchParams(location.search);
    const askedWeek = Number(q.get("week"));
    state.week = latest.games_weeks.includes(askedWeek)
      ? askedWeek
      : latest.games_weeks.includes(latest.week) ? latest.week : latest.games_weeks.at(-1);
    state.conf = window.SFCS.CONFERENCES.some((c) => c.id === q.get("conf")) ? q.get("conf") : "all";
    await loadWeek(state.week);

    el.weeks.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-week]");
      if (!b) return;
      state.week = Number(b.dataset.week);
      syncUrl();
      loadWeek(state.week);
    });
    el.confs.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-conf]");
      if (!b) return;
      state.conf = b.dataset.conf;
      syncUrl();
      render();
    });
    el.grid.addEventListener("click", (e) => {
      const b = e.target.closest(".game-link");
      if (b) openModal(games[Number(b.dataset.i)], b.dataset.kind);
    });
    el.modal.addEventListener("click", (e) => {
      if (e.target === el.modal || e.target.closest("[data-close]")) el.modal.close();
    });
  });
})();
