#!/usr/bin/env python3
"""
SFCS postgame box scores: one PNG per game.

Install: copy to  <fcs-model>/site_export/box_scores.py   (next to export_site.py)
Needs:   pandas, pyarrow, numpy, Pillow, openpyxl (for the PGWE workbook)

Usage:
  python site_export/box_scores.py --week 6                 every FCS game played in week 6
  python site_export/box_scores.py --week 6 --game 401868265
  python site_export/box_scores.py --demo                   design preview with made-up numbers

Output (the path the website already reads):
  dashboards/week<P>_db/box_scores/box_score_<contest_id>_wk<P>.png
  P = the week the game was PLAYED.

STATUS: DRAFT. The website Claude wrote this without access to the model's files.
Everything marked  TODO(analytics)  is a guess or an unknown the analytics Claude
must confirm. A row whose data source isn't connected is drawn as a hatched
"SOURCE TBD" cell with a ◆ marker, and the image gets a DRAFT banner, so a
placeholder can never pass for a real number.

Decisions (from the user, 2026-10-11/12):
  * Games: every FCS game vs a D1 opponent (FCS-FCS and FBS-FCS). No FBS-FBS images.
  * Shading: percentile vs ALL D1-vs-D1 single-game team performances this season,
    pooled (both sides of FBS-vs-FCS games). Green = good for that team. The
    percentile itself is not printed; the color carries it.
  * Garbage-time plays are excluded from every stat except the garbage-time row
    (one footnote says so).
  * Not part of the weekly run until the user says the EP model rebuild is done.
"""

from __future__ import annotations

import argparse
import base64
import io
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

# ===========================================================================
# CONFIG: the analytics Claude should review every TODO in this block.
# ===========================================================================

SEASON = 2026
ROOT = Path(__file__).resolve().parent.parent          # fcs-model/
DASHBOARDS = ROOT / "dashboards"
SCHEDULE = ROOT / "processed" / "games_schedule_current.parquet"    # confirmed (round 1)
TEAM_BRAND = ROOT / "processed" / "team_brand.parquet"              # confirmed (round 1)
CONFERENCES = ROOT / "processed" / "conferences.parquet"            # confirmed (round 1)

# PGWE workbook (confirmed in round 1): dashboards/week<P>_db/pgwe_week<P>.xlsx,
# columns Winner, Loser, Winner PGWE. The loser's PGWE = 1 - winner's.
# TODO(analytics): which sheet holds FBS-vs-FCS games, "FCS" or "FBS"? Both are searched.
PGWE_SHEETS = ["FCS", "FBS"]

# Play-by-play ("the play file" from round 2). Most rows are computed from it.
PLAYS = {
    "path": None,          # TODO(analytics): path to the play-level file (parquet or csv)
    "team_names": "ncaa",  # TODO(analytics): "ncaa" or "cfbd" (cfbd names are mapped via conferences.parquet)
    "cols": {              # TODO(analytics): confirm every name; None = not available
        "game": "contest_id",
        "offense": "offense",
        "defense": "defense",
        "down": "down",
        "distance": "distance",
        "yards": "yards_gained",
        "is_pass": "pass",          # bool; dropbacks incl. sacks
        "is_rush": "rush",          # bool
        "garbage": "garbage_time",  # bool
        "exclude": None,            # optional bool: kneels / spikes / no-plays to drop
        "epa": None,                # EPA per play. Leave None until the EP model rebuild is done.
        "havoc": None,              # optional bool, DEFENSIVE havoc on the play (TFL, forced fumble, INT, pass defensed)
    },
}

# Per-team-game overrides: any stat key below can be taken from a table instead of
# being computed from plays (e.g. if havoc already exists per game).
TEAM_GAMES = {
    "path": ROOT / "processed" / "team_games.parquet",   # TODO(analytics): confirm location
    "game_col": None,      # TODO(analytics): game id column
    "team_col": None,      # TODO(analytics): team column
    "team_names": "ncaa",  # TODO(analytics)
    "cols": {              # stat key -> column; rates may be 0-1 or 0-100 (auto-detected)
        "havoc_rate": None,   # TODO(analytics): defensive havoc rate, if stored per game
    },
}

# Drives (drive_metrics.py). Quality drive rate and finishing drives.
DRIVES = {
    "path": None,          # TODO(analytics): per-game drive table (round 2: may only exist per season)
    "team_names": "ncaa",
    "cols": {
        "game": None,            # TODO(analytics)
        "team": None,            # TODO(analytics) offense
        "drives": None,          # offensive drives
        "quality": None,         # TODO(analytics): drives counted as "quality" (definition to confirm)
        "trips": None,           # drives that reached the opponent's 40
        "trip_points": None,     # offensive points scored on those trips
    },
}

# Stat definitions computed here. TODO(analytics): confirm each matches the model's.
EXPLOSIVE = {"rush": 12, "pass": 15}     # explosive = rush >= 12 yards or pass >= 15 yards


def line_yards(y: float) -> float:
    """Credited line yards on one rush: losses 120%, yards 0-4 100%, 5-10 50%, 11+ 0%."""
    if y < 0:
        return 1.2 * y
    return min(y, 4) + 0.5 * max(0.0, min(y, 10) - 4)


# Fonts: heavy display + bold + regular. First file found wins.
FONTS_HEAVY = [
    ROOT / "resources" / "fonts" / "ArchivoBlack-Regular.ttf",   # TODO(analytics): the font the house graphics use
    "C:/Windows/Fonts/ariblk.ttf", "ariblk.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
FONTS_BOLD = [
    ROOT / "resources" / "fonts" / "Archivo-Bold.ttf",            # TODO(analytics)
    "C:/Windows/Fonts/arialbd.ttf", "arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
FONTS_REGULAR = [
    ROOT / "resources" / "fonts" / "Archivo-Regular.ttf",         # TODO(analytics)
    "C:/Windows/Fonts/arial.ttf", "arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
# SFCS mark for dark-on-light graphics. TODO(analytics): confirm file name.
MARK = ROOT / "resources" / "sfcs-logo-final" / "sfcs-mark-light-256.png"

D1_MATCHUPS = {"FBS-FBS", "FCS-FCS", "FBS-FCS"}   # baseline pool
IMAGE_MATCHUPS = {"FCS-FCS", "FBS-FCS"}           # games that get an image

# House colors (sampled from the SFCS graphics)
INK, PAPER, CARD, ROW_ALT = "#161616", "#f4f2ed", "#fbfaf7", "#f0ede6"
GOLD, MUTED, LINE = "#c9a961", "#6b6760", "#d6d1c4"
BAD, MID, GOOD = (205, 92, 70), (251, 250, 247), (46, 125, 79)   # red - neutral - green

# ===========================================================================
# Rows (the final score sits in the header, next to the logos)
# ===========================================================================

@dataclass
class Row:
    key: str
    label: str
    kind: str                           # "pct" (0-1 shown as %), "num2" (2 decimals)
    higher_is_better: bool | None = True   # None = not shaded


ROWS = [
    Row("pgwe", "Postgame Win Expectancy", "pct"),
    Row("epa_play", "EPA per Play", "num2"),
    Row("yards_play", "Yards per Play", "num2"),
    Row("pass_sr", "Passing Success Rate", "pct"),
    Row("rush_sr", "Rushing Success Rate", "pct"),
    Row("explosive_rate", "Explosive Play Rate", "pct"),
    Row("late_down_sr", "3rd/4th Down Success Rate", "pct"),
    Row("line_yards", "Line Yards per Rush", "num2"),
    Row("def_stuff_rate", "Defensive Stuff Rate", "pct"),
    Row("havoc_rate", "Havoc Rate", "pct"),
    Row("quality_drive_rate", "Quality Drive Rate", "pct"),
    Row("finishing_drives", "Finishing Drives (Pts/Trip)", "num2"),
    Row("garbage_share", "Offensive Plays in Garbage Time", "pct", None),
]

# ===========================================================================
# Data
# ===========================================================================

def _name_map(style: str) -> dict[str, str]:
    """cfbd -> ncaa team names (empty for 'ncaa')."""
    if style == "ncaa" or not CONFERENCES.exists():
        return {}
    c = pd.read_parquet(CONFERENCES)
    c = c[c["season"] == SEASON]
    return dict(zip(c["cfbd_team"], c["ncaa_team"]))


def _as_fraction(s: pd.Series) -> pd.Series:
    """Rates may be stored 0-1 or 0-100; return 0-1."""
    s = pd.to_numeric(s, errors="coerce")
    return s / 100 if s.dropna().gt(1.5).any() else s


def load_schedule() -> pd.DataFrame:
    df = pd.read_parquet(SCHEDULE)
    df["contest_id"] = df["contest_id"].astype(str)
    df["kickoff"] = pd.to_datetime(df["game_date"], utc=True)
    if "season_type" in df.columns:
        df = df[df["season_type"].fillna("regular") == "regular"]
    return df


def stats_from_plays(d1_ids: set[str]) -> tuple[pd.DataFrame | None, set[str]]:
    pl = PLAYS
    if not pl["path"] or not Path(pl["path"]).exists():
        return None, set()
    c = {k: v for k, v in pl["cols"].items() if v}
    p = pd.read_parquet(pl["path"]) if str(pl["path"]).endswith(".parquet") else pd.read_csv(pl["path"])
    p = p[list(c.values())].rename(columns={v: k for k, v in c.items()})
    p["game"] = p["game"].astype(str)
    p = p[p["game"].isin(d1_ids)]
    names = _name_map(pl["team_names"])
    p["offense"] = p["offense"].replace(names)
    if "defense" in p:
        p["defense"] = p["defense"].replace(names)
    p["is_pass"] = p["is_pass"].fillna(False).astype(bool)
    p["is_rush"] = p["is_rush"].fillna(False).astype(bool)
    p = p[(p["is_pass"] | p["is_rush"]) & p["down"].between(1, 4)]
    if "exclude" in p:
        p = p[~p["exclude"].fillna(False).astype(bool)]
    garbage = p["garbage"].fillna(False).astype(bool) if "garbage" in p else pd.Series(False, index=p.index)

    key = ["game", "offense"]
    out = pd.DataFrame({"garbage_share": garbage.groupby([p["game"], p["offense"]]).mean()})
    out.index.names = key
    p = p[~garbage]                                    # everything below excludes garbage time

    need = p["down"].map({1: 0.5, 2: 0.7, 3: 1.0, 4: 1.0}) * p["distance"]
    p["success"] = (p["yards"] >= need).astype(float)
    p["explosive"] = ((p["is_rush"] & (p["yards"] >= EXPLOSIVE["rush"]))
                      | (p["is_pass"] & (p["yards"] >= EXPLOSIVE["pass"]))).astype(float)
    rush = p[p["is_rush"]]

    out["yards_play"] = p.groupby(key)["yards"].mean()
    out["pass_sr"] = p[p["is_pass"]].groupby(key)["success"].mean()
    out["rush_sr"] = rush.groupby(key)["success"].mean()
    out["explosive_rate"] = p.groupby(key)["explosive"].mean()
    out["late_down_sr"] = p[p["down"] >= 3].groupby(key)["success"].mean()
    out["line_yards"] = rush["yards"].map(line_yards).groupby([rush["game"], rush["offense"]]).mean()
    connected = {"garbage_share", "yards_play", "pass_sr", "rush_sr", "explosive_rate", "late_down_sr", "line_yards"}
    if "epa" in p:
        out["epa_play"] = p.groupby(key)["epa"].mean()
        connected.add("epa_play")

    # Defensive stats: credited to the DEFENSE (the opponent of the offense on the play).
    if "defense" in p:
        dkey = ["game", "defense"]
        stuffed = (rush["yards"] <= 0).astype(float)
        dfs = pd.DataFrame({"def_stuff_rate": stuffed.groupby([rush["game"], rush["defense"]]).mean()})
        connected.add("def_stuff_rate")
        if "havoc" in p:
            dfs["havoc_rate"] = p["havoc"].fillna(False).astype(float).groupby([p["game"], p["defense"]]).mean()
            connected.add("havoc_rate")
        dfs.index.names = key
        out = out.join(dfs, how="outer")

    out = out.reset_index().rename(columns={"game": "contest_id", "offense": "team"})
    return out, connected


def stats_from_table(spec: dict, d1_ids: set[str]) -> tuple[pd.DataFrame | None, set[str]]:
    cols = {k: v for k, v in spec["cols"].items() if v}
    if not (spec["path"] and Path(spec["path"]).exists() and spec["game_col"] and spec["team_col"] and cols):
        return None, set()
    df = pd.read_parquet(spec["path"])
    out = pd.DataFrame({"contest_id": df[spec["game_col"]].astype(str),
                        "team": df[spec["team_col"]].replace(_name_map(spec["team_names"]))})
    for k, col in cols.items():
        out[k] = _as_fraction(df[col])
    return out[out["contest_id"].isin(d1_ids)], set(cols)


def stats_from_drives(d1_ids: set[str]) -> tuple[pd.DataFrame | None, set[str]]:
    dr, c = DRIVES, DRIVES["cols"]
    if not (dr["path"] and Path(dr["path"]).exists() and c["game"] and c["team"] and c["drives"]):
        return None, set()
    d = pd.read_parquet(dr["path"])
    out = pd.DataFrame({"contest_id": d[c["game"]].astype(str),
                        "team": d[c["team"]].replace(_name_map(dr["team_names"]))})
    connected = set()
    if c["quality"]:
        out["quality_drive_rate"] = d[c["quality"]] / d[c["drives"]]
        connected.add("quality_drive_rate")
    if c["trips"] and c["trip_points"]:
        out["finishing_drives"] = d[c["trip_points"]] / d[c["trips"]].replace(0, np.nan)
        connected.add("finishing_drives")
    return out[out["contest_id"].isin(d1_ids)], connected


def team_game_stats(d1_ids: set[str]) -> tuple[pd.DataFrame, set[str]]:
    """One row per (contest_id, team) in every D1-vs-D1 game, with every connected stat.
    Later sources override earlier ones on the same stat (table > drives > plays)."""
    table, connected = pd.DataFrame(columns=["contest_id", "team"]), set()
    for frame, conn in (stats_from_plays(d1_ids), stats_from_drives(d1_ids), stats_from_table(TEAM_GAMES, d1_ids)):
        if frame is None:
            continue
        overlap = [k for k in frame.columns if k in table.columns and k not in ("contest_id", "team")]
        table = table.drop(columns=overlap).merge(frame, on=["contest_id", "team"], how="outer")
        connected |= conn
    return table, connected


def pgwe_lookup(week: int) -> dict[tuple[str, str], float]:
    """(winner, loser) -> winner PGWE (0-1)."""
    path = DASHBOARDS / f"week{week}_db" / f"pgwe_week{week}.xlsx"
    if not path.exists():
        return {}
    out = {}
    for sheet in PGWE_SHEETS:
        try:
            df = pd.read_excel(path, sheet_name=sheet)
        except ValueError:
            continue
        for w, l, v in zip(df["Winner"], df["Loser"], _as_fraction(df["Winner PGWE"])):
            if pd.notna(v):
                out[(str(w), str(l))] = float(v)
    return out


def percentile(baseline: np.ndarray, value) -> float:
    """Mid-rank percentile (0-100) of value within baseline."""
    if baseline.size == 0 or value is None or math.isnan(value):
        return float("nan")
    lo = np.searchsorted(baseline, value, side="left")
    hi = np.searchsorted(baseline, value, side="right")
    return 100.0 * (lo + hi) / 2 / baseline.size


# ===========================================================================
# Drawing
# ===========================================================================

def _font(candidates, size):
    from PIL import ImageFont
    for f in candidates:
        try:
            return ImageFont.truetype(str(f), size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def shade(goodness: float) -> tuple[int, int, int]:
    """0 (bad, red) - 50 (neutral) - 100 (good, green)."""
    t = (goodness - 50) / 50
    target = GOOD if t >= 0 else BAD
    t = min(1.0, abs(t)) ** 0.85
    return tuple(round(MID[i] + (target[i] - MID[i]) * t) for i in range(3))


def fmt(row: Row, v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    if row.kind == "pct":
        return f"{v * 100:.1f}%"
    return f"{v:.2f}" if v >= 0 else f"−{abs(v):.2f}"


def logo_image(team: str, size: int):
    from PIL import Image, ImageDraw
    if TEAM_BRAND.exists():
        brand = pd.read_parquet(TEAM_BRAND).set_index("team")
        uri = brand["logo"].get(team) if team in brand.index else None
        if isinstance(uri, str) and "base64," in uri:
            im = Image.open(io.BytesIO(base64.b64decode(uri.split("base64,", 1)[1]))).convert("RGBA")
            im.thumbnail((size, size), Image.LANCZOS)
            return im
    # Non-D1 / missing: lettered badge, like the matchup dashboards
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 8, fill=INK)
    letters = "".join(w[0] for w in re.sub(r"[.'()&]", "", team).split()[:3]).upper()
    d.text((size / 2, size / 2), letters, font=_font(FONTS_HEAVY, size // 3), fill=GOLD, anchor="mm")
    return im


def render(game: dict, values: dict, pcts: dict, status: dict, out: Path, draft_note: str | None):
    """game: week, date_text, away, home, neutral, away_score, home_score;
    values/pcts: {side: {key: v}}; status: {key: 'ok' | 'tbd'}."""
    from PIL import Image, ImageDraw

    W, M = 1500, 60
    COL = 340                              # team value columns
    ROW_H = 92
    head_h, team_h = 270, 250
    foot_h = 170 + (80 if draft_note else 0)
    H = head_h + team_h + ROW_H * len(ROWS) + foot_h
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    F = _font

    # Title block (house style: mark left, heavy title, gold rule)
    if MARK.exists():
        mk = Image.open(MARK).convert("RGBA")
        mk.thumbnail((150, 150), Image.LANCZOS)
        im.paste(mk, (M, 50), mk)
    at = "VS" if game["neutral"] else "AT"
    d.text((W / 2 + 60, 105), f"WEEK {game['week']} BOX SCORE", font=F(FONTS_HEAVY, 76), fill=INK, anchor="mm")
    sub = f"{game['away'].upper()} {at} {game['home'].upper()} · {game['date_text']}"
    if game["neutral"]:
        sub += " · NEUTRAL SITE"
    d.text((W / 2 + 60, 180), sub, font=F(FONTS_BOLD, 30), fill=MUTED, anchor="mm")
    d.rectangle((M, 238, W - M, 242), fill=GOLD)

    # Team header: logo + name in each value column, final score beside it, AT/VS centered
    xl, xr = M, W - M - COL
    xc0, xc1 = M + COL, W - M - COL
    cx = (xc0 + xc1) / 2
    y = head_h
    away_won = game["away_score"] > game["home_score"]
    for side, x, sx in (("away", xl, xc0 + 120), ("home", xr, xc1 - 120)):
        lg = logo_image(game[side], 140)
        im.paste(lg, (int(x + COL / 2 - lg.width / 2), y + 12), lg)
        d.text((x + COL / 2, y + 190), game[side].upper(), font=F(FONTS_HEAVY, 30), fill=INK, anchor="mm")
        won = away_won if side == "away" else not away_won
        d.text((sx, y + 95), str(int(game[f"{side}_score"])), font=F(FONTS_HEAVY, 110),
               fill=INK if won else "#a39e94", anchor="mm")
    d.text((cx, y + 95), at, font=F(FONTS_HEAVY, 40), fill=GOLD, anchor="mm")
    d.text((cx, y + 190), "FINAL", font=F(FONTS_BOLD, 22), fill=MUTED, anchor="mm")
    y += team_h

    # Rows
    d.rectangle((M, y - 5, W - M, y), fill=INK)
    for i, row in enumerate(ROWS):
        y0, y1 = y + i * ROW_H, y + (i + 1) * ROW_H
        st = status[row.key]
        bg = CARD if i % 2 == 0 else ROW_ALT
        d.rectangle((xc0, y0, xc1, y1), fill=bg)
        d.text((cx, (y0 + y1) / 2), row.label + ("  ◆" if st == "tbd" else ""),
               font=F(FONTS_HEAVY, 31), fill=INK if st == "ok" else "#9a958b", anchor="mm")

        for side, x in (("away", xl), ("home", xr)):
            if st != "ok":
                cell = Image.new("RGB", (COL, ROW_H), "#ebe8e1")     # hatch, clipped to the cell
                cd = ImageDraw.Draw(cell)
                for k in range(-ROW_H, COL, 18):
                    cd.line((k, ROW_H, k + ROW_H, 0), fill="#ddd9cf", width=3)
                im.paste(cell, (x, y0))
                d.text((x + COL / 2, (y0 + y1) / 2), "SOURCE TBD", font=F(FONTS_BOLD, 21),
                       fill="#9a958b", anchor="mm")
                continue
            v, pc = values[side].get(row.key), pcts[side].get(row.key)
            shaded = row.higher_is_better is not None and pc is not None and not math.isnan(pc)
            good = (pc if row.higher_is_better else 100 - pc) if shaded else 50
            d.rectangle((x, y0, x + COL, y1), fill=shade(good) if shaded else bg)
            d.text((x + COL / 2, (y0 + y1) / 2), fmt(row, v), font=F(FONTS_HEAVY, 46),
                   fill="#ffffff" if shaded and abs(good - 50) > 36 else INK, anchor="mm")
        d.line((M, y1, W - M, y1), fill=LINE, width=2)
    rows_bottom = y + ROW_H * len(ROWS)
    d.line((xc0, y, xc0, rows_bottom), fill=LINE, width=2)
    d.line((xc1, y, xc1, rows_bottom), fill=LINE, width=2)
    d.rectangle((M, rows_bottom, W - M, rows_bottom + 5), fill=INK)

    # Footer: color key + the one footnote
    y = rows_bottom + 45
    kx0, kx1 = M, M + 420
    for k in range(kx1 - kx0):
        d.line((kx0 + k, y, kx0 + k, y + 22), fill=shade(100 * k / (kx1 - kx0)))
    d.text((kx0, y + 34), "WORSE", font=F(FONTS_BOLD, 17), fill=MUTED, anchor="la")
    d.text((kx1, y + 34), "BETTER", font=F(FONTS_BOLD, 17), fill=MUTED, anchor="ra")
    d.text((kx1 + 30, y - 2), "Color: rank vs. every D1-vs-D1 single-game performance this season.",
           font=F(FONTS_REGULAR, 21), fill=MUTED, anchor="la")
    d.text((kx1 + 30, y + 28), "Garbage-time plays excluded.", font=F(FONTS_REGULAR, 21), fill=MUTED, anchor="la")
    if draft_note:
        y += 95
        d.rectangle((M, y, W - M, y + 56), fill="#fff4d6", outline=GOLD, width=3)
        d.text((W / 2, y + 28), draft_note, font=F(FONTS_BOLD, 20), fill="#7a5c12", anchor="mm")

    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, optimize=True)


# ===========================================================================
# Build
# ===========================================================================

def _date_text(ts: pd.Timestamp) -> str:
    et = ts.tz_convert("America/New_York")
    return f"{et.strftime('%a, %b')} {et.day}".upper()


def build_week(week: int, only_game: str | None = None):
    sched = load_schedule()
    d1_ids = set(sched.loc[sched["matchup"].isin(D1_MATCHUPS), "contest_id"])
    table, connected = team_game_stats(d1_ids)
    pg = pgwe_lookup(week)

    status = {r.key: "ok" if (r.key in connected or (r.key == "pgwe" and pg)) else "tbd" for r in ROWS}
    baselines = {k: np.sort(table[k].dropna().to_numpy(dtype=float)) for k in table.columns
                 if k not in ("contest_id", "team")}
    tbd = [r.label for r in ROWS if status[r.key] == "tbd"]
    draft = (f"DRAFT · ◆ source not connected yet: {len(tbd)} row{'s' if len(tbd) != 1 else ''}"
             " (see TODOs in box_scores.py)") if tbd else None

    games = sched[(sched["week"] == week) & sched["matchup"].isin(IMAGE_MATCHUPS)
                  & sched["completed"].fillna(False).astype(bool) & sched["home_score"].notna()]
    if only_game:
        games = games[games["contest_id"] == only_game]
    if games.empty:
        sys.exit(f"No completed FCS games found for week {week}" + (f" with id {only_game}" if only_game else ""))

    made = 0
    for g in games.itertuples():
        values, pcts = {}, {}
        for side, team in (("away", g.away_team), ("home", g.home_team)):
            row = table[(table["contest_id"] == g.contest_id) & (table["team"] == team)]
            values[side] = {k: float(row[k].iloc[0]) if len(row) and pd.notna(row[k].iloc[0]) else None
                            for k in baselines}
        # PGWE: the workbook gives the winner's number; the loser's is 1 - it.
        home_won = g.home_score > g.away_score
        win, lose = (g.home_team, g.away_team) if home_won else (g.away_team, g.home_team)
        w = pg.get((win, lose))
        values["home" if home_won else "away"]["pgwe"] = w
        values["away" if home_won else "home"]["pgwe"] = None if w is None else 1 - w

        for side in values:
            pcts[side] = {k: percentile(baselines[k], values[side][k]) for k in baselines
                          if values[side].get(k) is not None}
            if values[side].get("pgwe") is not None:       # PGWE is a probability: shade by its value
                pcts[side]["pgwe"] = 100 * values[side]["pgwe"]

        info = dict(week=week, away=g.away_team, home=g.home_team, neutral=bool(g.neutral),
                    away_score=g.away_score, home_score=g.home_score, date_text=_date_text(g.kickoff))
        out = DASHBOARDS / f"week{week}_db" / "box_scores" / f"box_score_{g.contest_id}_wk{week}.png"
        render(info, values, pcts, status, out, draft)
        made += 1
    print(f"Wrote {made} box score(s) to {DASHBOARDS / f'week{week}_db' / 'box_scores'}")
    if tbd:
        print("Rows still drawn as SOURCE TBD:", ", ".join(tbd))


def demo(out: Path, neutral: bool = False):
    """Design preview with made-up numbers; every row connected."""
    rng = np.random.default_rng(7)
    status = {r.key: "ok" for r in ROWS}
    values, pcts = {"away": {}, "home": {}}, {"away": {}, "home": {}}
    ranges = {"pct": (0.25, 0.55), "num2": (0.5, 6.5)}
    for r in ROWS:
        for side in values:
            v = float(rng.uniform(*ranges[r.kind]))
            if r.key == "epa_play":
                v = float(rng.uniform(-0.4, 0.4))
            if r.key == "pgwe":
                v = 0.742 if side == "away" else 0.258
            if r.key == "garbage_share":
                v = 0.0
            values[side][r.key] = v
            pcts[side][r.key] = 100 * v if r.key == "pgwe" else float(rng.uniform(1, 99))
    info = dict(week=6, away="Montana", home="Montana St.", neutral=neutral, away_score=27, home_score=21,
                date_text="SAT, OCT 10")
    render(info, values, pcts, status, out, "DEMO · made-up numbers for design review")
    print(f"Wrote demo to {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--week", type=int, help="week the games were PLAYED")
    ap.add_argument("--game", help="one contest_id only")
    ap.add_argument("--demo", action="store_true", help="design preview with made-up numbers")
    ap.add_argument("--neutral", action="store_true", help="--demo: draw as a neutral-site game")
    ap.add_argument("--out", default="box_score_demo.png", help="--demo output file")
    a = ap.parse_args()
    if a.demo:
        demo(Path(a.out), a.neutral)
    elif a.week:
        build_week(a.week, a.game)
    else:
        ap.error("give --week N (or --demo)")


if __name__ == "__main__":
    main()
