/* ==========================================================================
   Games data — the one place the Games page gets its data from.

   Today this reads an Excel file (first sheet, one row per game, a header
   row on top). When your pipeline is ready you can either keep overwriting
   that file, or replace loadGames() with something that returns the same
   shape (e.g. fetch a JSON file). The page code doesn't care where it came from.

   Each game becomes:
   {
     week, date (Date|null), time, tv, location, neutral (bool),
     away: { name, conf, record, slug, score, proj },
     home: { name, conf, record, slug, score, proj },
     homeWinProb (0–1 | null), final (bool),
     previewImage, boxScoreImage   (site-relative paths)
   }
   ========================================================================== */

const GAMES_SEASON = 2026;
const GAMES_FILE = `data/games-${GAMES_SEASON}.xlsx`;

/* Spreadsheet header names. If your column headers differ, change the
   right-hand side (matching ignores case and spaces/underscores). */
const COLUMNS = {
  week: "week",
  date: "date",
  time: "time",
  tv: "tv",
  away: "away",
  awayConf: "away_conf",
  awayRecord: "away_record",
  home: "home",
  homeConf: "home_conf",
  homeRecord: "home_record",
  neutral: "neutral",
  location: "location",
  projAway: "proj_away",
  projHome: "proj_home",
  homeWinProb: "home_win_prob",
  awayScore: "away_score",
  homeScore: "home_score",
  previewImage: "preview_image",   // optional override, see defaultImage()
  boxScoreImage: "boxscore_image", // optional override
};

/* "South Dakota St." -> "south-dakota-st". Used for logo file names
   (assets/logos/<slug>.png) and default image names. */
function teamSlug(name) {
  return String(name)
    .toLowerCase()
    .replace(/&/g, "and")
    .replace(/[.'’()]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

/* If the preview_image / boxscore_image cells are empty, the page looks for
   assets/games/<season>/week-<N>/<away>-at-<home>-preview.png (or -boxscore.png). */
function defaultImage(game, kind) {
  return `assets/games/${GAMES_SEASON}/week-${game.week}/${game.away.slug}-at-${game.home.slug}-${kind}.png`;
}

async function loadGames(rootUrl) {
  const res = await fetch(new URL(GAMES_FILE, rootUrl));
  if (!res.ok) throw new Error(`Couldn't load ${GAMES_FILE} (${res.status})`);
  const result = await readXlsxFile(await res.blob());
  const rows = Array.isArray(result[0]?.data) ? result[0].data : result; // first sheet

  const key = (s) => String(s ?? "").toLowerCase().replace(/[\s_]+/g, "");
  const header = rows[0].map(key);
  const col = {};
  for (const [field, name] of Object.entries(COLUMNS)) col[field] = header.indexOf(key(name));

  return rows
    .slice(1)
    .map((r) => {
      const get = (field) => {
        const v = col[field] >= 0 ? r[col[field]] : null;
        return v === "" || v === undefined ? null : v;
      };
      return toGame(get);
    })
    .filter((g) => g.week != null && g.away.name && g.home.name);
}

function toGame(get) {
  const num = (v) => (v == null || isNaN(Number(v)) ? null : Number(v));
  const text = (v) => (v == null ? "" : String(v).trim());

  const side = (s) => ({
    name: text(get(s)),
    slug: teamSlug(text(get(s))),
    conf: text(get(`${s}Conf`)),
    record: text(get(`${s}Record`)),
    score: num(get(`${s}Score`)),
    proj: num(get(`proj${s[0].toUpperCase()}${s.slice(1)}`)),
  });

  let prob = num(get("homeWinProb"));
  if (prob != null && prob > 1) prob /= 100; // accept 74 or 0.74

  const game = {
    week: num(get("week")),
    date: toDate(get("date")),
    time: toTime(get("time")),
    tv: text(get("tv")),
    location: text(get("location")),
    neutral: /^(y|yes|true|1|x)$/i.test(text(get("neutral"))),
    away: side("away"),
    home: side("home"),
    homeWinProb: prob,
  };
  game.final = game.away.score != null && game.home.score != null;
  game.previewImage = text(get("previewImage")) || defaultImage(game, "preview");
  game.boxScoreImage = text(get("boxScoreImage")) || defaultImage(game, "boxscore");
  return game;
}

function toDate(v) {
  if (v instanceof Date) return new Date(v.getUTCFullYear(), v.getUTCMonth(), v.getUTCDate());
  if (v == null) return null;
  const d = new Date(v);
  return isNaN(d) ? null : d;
}

/* Times can be typed as text ("2:00 PM") or stored as Excel times. */
function toTime(v) {
  if (v instanceof Date) {
    const h = v.getUTCHours(), m = v.getUTCMinutes();
    return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`;
  }
  if (typeof v === "number" && v < 1) { // fraction of a day
    const mins = Math.round(v * 1440);
    const h = Math.floor(mins / 60), m = mins % 60;
    return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`;
  }
  return v == null ? "" : String(v).trim();
}
