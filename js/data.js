/* ==========================================================================
   Shared data access for every page.

   The weekly export (tools/export_site.py, run on the analytics computer)
   uploads files in the SAME layout the model uses:
     data/site_latest.json                         which week is current + what was posted
     data/games_<season>_wk<N>.csv                 one file per week of games
     dashboards/week<N>_db/<product>_wk<N>.png     weekly images (model file names)
     dashboards/week<N>_db/previews/preview_<contest_id>_wk<N>.png
     dashboards/week<N>_db/box_scores/box_score_<contest_id>_wk<N>.png
     assets/logos/<team-slug>.png
   Full rules: docs/SITE_INTEGRATION.md
   ========================================================================== */

window.SFCSData = (function () {
  const root = new URL("..", document.currentScript.src);
  const url = (p) => new URL(p, root).href;

  // Data files change weekly; ask the browser to re-check them instead of
  // trusting its cache.
  const fresh = { cache: "no-cache" };

  let latestPromise;
  function latest() {
    latestPromise ??= fetch(url("data/site_latest.json"), fresh)
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null);
    return latestPromise;
  }

  const weekDir = (w) => `dashboards/week${w}_db`;
  const image = (key, w) => url(`${weekDir(w)}/${key}_wk${w}.png`);
  const thumb = (key, w) => url(`${weekDir(w)}/${key}_wk${w}_thumb.jpg`);
  const preview = (id, w) => url(`${weekDir(w)}/previews/preview_${id}_wk${w}.png`);
  const boxScore = (id, w) => url(`${weekDir(w)}/box_scores/box_score_${id}_wk${w}.png`);

  /* Team name -> logo file name. MUST match team_slug() in tools/export_site.py.
     lowercase; delete . & ' ’ ( ); every other run of non [a-z0-9] -> "-"; trim "-". */
  function teamSlug(name) {
    return String(name)
      .toLowerCase()
      .replace(/[.&'’()]/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }
  const logo = (name) => url(`assets/logos/${teamSlug(name)}.png`);

  /* Minimal CSV reader (handles quoted fields). Returns an array of objects. */
  function parseCsv(text) {
    const rows = [];
    let row = [], field = "", quoted = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (quoted) {
        if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
        else if (c === '"') quoted = false;
        else field += c;
      } else if (c === '"') quoted = true;
      else if (c === ",") { row.push(field); field = ""; }
      else if (c === "\n" || c === "\r") {
        if (c === "\r" && text[i + 1] === "\n") i++;
        row.push(field); rows.push(row); row = []; field = "";
      } else field += c;
    }
    if (field || row.length) { row.push(field); rows.push(row); }
    const [header, ...body] = rows.filter((r) => r.some((v) => v !== ""));
    return body.map((r) => Object.fromEntries(header.map((h, i) => [h.trim(), (r[i] ?? "").trim()])));
  }

  const num = (v) => (v === "" || v == null || isNaN(Number(v)) ? null : Number(v));

  function toGame(r) {
    // kickoff_et is "YYYY-MM-DD HH:MM" in US Eastern time.
    const [d, t = ""] = r.kickoff_et.split(" ");
    const [y, mo, da] = d.split("-").map(Number);
    const [hh, mm] = t.split(":").map(Number);
    const side = (s) => ({
      name: r[s],
      conf: r[`${s}_conf`],
      record: r[`${s}_record`],
      score: num(r[`${s}_score`]),
      proj: num(r[`proj_${s}`]),
    });
    const g = {
      id: r.contest_id,
      week: num(r.week),
      date: y ? new Date(y, mo - 1, da) : null,
      minutes: isNaN(hh) ? 24 * 60 : hh * 60 + mm,
      time: isNaN(hh) ? "" : `${hh % 12 || 12}:${String(mm).padStart(2, "0")} ${hh < 12 ? "AM" : "PM"} ET`,
      neutral: r.neutral === "1",
      away: side("away"),
      home: side("home"),
      homeWinProb: num(r.home_win_prob),
      hasPreview: r.has_preview === "1",
      hasBoxScore: r.has_box_score === "1",
    };
    g.final = g.away.score != null && g.home.score != null;
    return g;
  }

  async function games(season, week) {
    const res = await fetch(url(`data/games_${season}_wk${week}.csv`), fresh);
    if (!res.ok) throw new Error(`Couldn't load week ${week} games (${res.status})`);
    return parseCsv(await res.text()).map(toGame);
  }

  return { url, latest, image, thumb, preview, boxScore, teamSlug, logo, games };
})();
