/* ==========================================================================
   Games page: week + conference filters, game cards, preview/box score popup.
   Data comes from loadGames() in js/games-data.js.
   ========================================================================== */

(function () {
  const root = new URL("..", document.currentScript.src);
  const url = (p) => new URL(p, root).href;

  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

  const norm = (s) => String(s ?? "").toLowerCase().replace(/[^a-z0-9]/g, "");

  let games = [];
  let state = { week: null, conf: "all" };
  let el = {};

  // ---------- Conferences ----------
  // Match a spreadsheet conference ("Big Sky", "big-sky", "BIG SKY") to the nav list.
  function confId(name) {
    const n = norm(name);
    const hit = window.SFCS.CONFERENCES.find(([id, label]) => norm(id) === n || norm(label) === n);
    return hit ? hit[0] : null;
  }

  // ---------- Formatting ----------
  const fmtDate = (d) =>
    d ? d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" }) : "";

  function initials(name) {
    const words = name.replace(/[.'’]/g, "").split(/[\s-]+/).filter(Boolean);
    return (words.length === 1 ? words[0].slice(0, 3) : words.map((w) => w[0]).join("").slice(0, 3)).toUpperCase();
  }

  function logo(team) {
    // Monogram shows until/unless assets/logos/<slug>.png loads.
    return `<span class="team-logo">
        <span class="team-mono" aria-hidden="true">${esc(initials(team.name))}</span>
        <img src="${url(`assets/logos/${team.slug}.png`)}" alt="" loading="lazy"
             onload="this.previousElementSibling.remove()" onerror="this.remove()">
      </span>`;
  }

  // ---------- Card ----------
  function teamRow(g, side) {
    const t = g[side];
    const other = g[side === "away" ? "home" : "away"];
    const score = g.final ? t.score : t.proj;
    const won = g.final && t.score > other.score;
    const lost = g.final && t.score < other.score;
    const sub = [t.record, t.conf].filter(Boolean).map(esc).join(" · ");
    return `<div class="team-row${won ? " is-winner" : ""}${lost ? " is-loser" : ""}">
        ${logo(t)}
        <div class="team-name">
          <span>${esc(t.name)}</span>
          ${sub ? `<small>${sub}</small>` : ""}
        </div>
        <div class="team-score">${score ?? "–"}</div>
      </div>`;
  }

  // Projected winner + margin, e.g. "Montana St. by 9".
  function pick(g) {
    const { away: a, home: h } = g;
    if (a.proj == null || h.proj == null) return null;
    if (a.proj === h.proj) return { team: null, text: "Projected tie" };
    const fav = a.proj > h.proj ? a : h;
    return { team: fav, text: `${fav.name} by ${Math.abs(a.proj - h.proj)}` };
  }

  function card(g, i) {
    const p = pick(g);
    const meta = [fmtDate(g.date), g.time, g.tv].filter(Boolean).map(esc).join(" · ");

    let foot;
    if (g.final) {
      foot = `<span class="game-note">Proj ${g.away.proj ?? "–"}–${g.home.proj ?? "–"}</span>
        <button class="game-link" type="button" data-i="${i}" data-kind="box">Box Score</button>`;
    } else {
      let prob = "";
      if (g.homeWinProb != null && p?.team) {
        const pr = p.team === g.home ? g.homeWinProb : 1 - g.homeWinProb;
        prob = ` · ${Math.round(pr * 100)}%`;
      }
      foot = `<span class="game-note">${p ? esc(p.text) + prob : ""}</span>
        <button class="game-link" type="button" data-i="${i}" data-kind="preview">Preview</button>`;
    }

    return `<article class="game-card${g.final ? " is-final" : ""}">
        <header class="game-meta">
          <span>${meta}</span>
          <span class="game-status">${g.final ? "Final" : "Projected"}</span>
        </header>
        <div class="game-teams">
          ${teamRow(g, "away")}
          <div class="game-at">${g.neutral ? "vs" : "at"}</div>
          ${teamRow(g, "home")}
        </div>
        ${g.location ? `<div class="game-venue">${esc(g.location)}${g.neutral ? " (neutral)" : ""}</div>` : ""}
        <footer class="game-foot">${foot}</footer>
      </article>`;
  }

  // "7:00 PM" -> minutes after midnight, for sorting; unknown times sort last.
  function kickoff(g) {
    const m = /^(\d{1,2}):(\d{2})\s*([ap])/i.exec(g.time);
    if (!m) return 24 * 60;
    return ((Number(m[1]) % 12) + (/p/i.test(m[3]) ? 12 : 0)) * 60 + Number(m[2]);
  }

  // Keep the selected chip visible when a row scrolls sideways (phones).
  function revealSelected(row) {
    const b = row.querySelector('[aria-pressed="true"]');
    if (b && (b.offsetLeft + b.offsetWidth > row.scrollLeft + row.clientWidth || b.offsetLeft < row.scrollLeft)) {
      row.scrollLeft = b.offsetLeft - row.offsetLeft - 16;
    }
  }

  // ---------- Page ----------
  function weeks() {
    return [...new Set(games.map((g) => g.week))].sort((a, b) => a - b);
  }

  // Current week = first week that still has unplayed games (else the last week).
  function currentWeek() {
    const ws = weeks();
    return ws.find((w) => games.some((g) => g.week === w && !g.final)) ?? ws[ws.length - 1];
  }

  function syncUrl() {
    const q = new URLSearchParams();
    q.set("week", state.week);
    if (state.conf !== "all") q.set("conf", state.conf);
    history.replaceState(null, "", `?${q}`);
  }

  function render() {
    const inWeek = games.filter((g) => g.week === state.week);
    const shown =
      state.conf === "all"
        ? inWeek
        : inWeek.filter((g) => confId(g.away.conf) === state.conf || confId(g.home.conf) === state.conf);
    shown.sort((a, b) => (a.date ?? 0) - (b.date ?? 0) || kickoff(a) - kickoff(b));

    const isCurrent = state.week === currentWeek() && inWeek.some((g) => !g.final);
    el.eyebrow.textContent = `${GAMES_SEASON} Season · Week ${state.week}${isCurrent ? " · This week" : ""}`;
    el.title.textContent = `Week ${state.week} Games`;
    document.title = `Week ${state.week} Games · SFCS`;

    el.weeks.innerHTML = weeks()
      .map((w) => `<button type="button" data-week="${w}"${w === state.week ? ' aria-pressed="true"' : ""}>Wk ${w}</button>`)
      .join("");

    // Only list conferences that appear in the data, in nav order.
    const present = new Set(games.flatMap((g) => [confId(g.away.conf), confId(g.home.conf)]));
    const confs = window.SFCS.CONFERENCES.filter(([id]) => present.has(id));
    el.confs.innerHTML = [["all", "All"], ...confs]
      .map(([id, label]) => `<button type="button" data-conf="${id}"${id === state.conf ? ' aria-pressed="true"' : ""}>${esc(label)}</button>`)
      .join("");

    el.summary.textContent = `${shown.length} game${shown.length === 1 ? "" : "s"}`;

    revealSelected(el.weeks);
    revealSelected(el.confs);

    el.grid.innerHTML = shown.length
      ? shown.map((g) => card(g, games.indexOf(g))).join("")
      : `<div class="placeholder"><strong>No games</strong>Nothing scheduled for this filter.</div>`;
  }

  // ---------- Popup ----------
  function openModal(g, kind) {
    const src = url(kind === "box" ? g.boxScoreImage : g.previewImage);
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

    try {
      games = await loadGames(root);
    } catch (err) {
      console.error(err);
      el.grid.innerHTML = `<div class="placeholder"><strong>Couldn't load games</strong>${esc(err.message)}</div>`;
      return;
    }
    if (!games.length) {
      el.grid.innerHTML = `<div class="placeholder"><strong>Coming soon</strong>No games posted yet.</div>`;
      return;
    }

    const q = new URLSearchParams(location.search);
    const askedWeek = Number(q.get("week"));
    state.week = weeks().includes(askedWeek) ? askedWeek : currentWeek();
    state.conf = window.SFCS.CONFERENCES.some(([id]) => id === q.get("conf")) ? q.get("conf") : "all";
    render();

    el.weeks.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-week]");
      if (!b) return;
      state.week = Number(b.dataset.week);
      syncUrl();
      render();
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
