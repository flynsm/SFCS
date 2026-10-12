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
Everything marked  TODO(analytics)  below is a guess or an unknown that the
analytics Claude must confirm. Rows whose data source isn't connected yet are
drawn as hatched "SOURCE TBD" cells with a ◆ marker, and the image carries a
DRAFT banner, so a placeholder can never be mistaken for a real number.

Design decisions (from the user, 2026-10-11/12):
  * Games: every FCS game vs a D1 opponent (FCS-FCS and FBS-FCS). No FBS-FBS images.
  * Shading: percentile vs ALL D1-vs-D1 single-game team performances, pooled
    (both sides of FBS-vs-FCS games included). Green = good for that team.
  * Garbage-time plays are excluded from the stats (one footnote says so).
  * EPA rows wait for the EP model rebuild: shown greyed as "PENDING" until
    EPA_READY = True.
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
# columns Date, Winner, Loser, Winner score, Loser score, Neutral site, Winner PGWE.
# TODO(analytics): which sheet holds FBS-vs-FCS games, "FCS" or "FBS"? Both are searched.
# TODO(analytics): is "Winner PGWE" stored as 0-1 or 0-100? Auto-detected below.
PGWE_SHEETS = ["FCS", "FBS"]

# Per-team, per-game stats. Round 1 named team_games.parquet but not its folder or columns.
TEAM_GAMES = {
    "path": ROOT / "processed" / "team_games.parquet",   # TODO(analytics): confirm location
    "game_col": None,      # TODO(analytics): game id column (contest_id?)
    "team_col": None,      # TODO(analytics): team column
    "team_names": "ncaa",  # TODO(analytics): "ncaa" or "cfbd" (cfbd names are mapped via conferences.parquet)
    # stat -> column name; None = not connected yet (drawn as SOURCE TBD)
    "cols": {
        "success_rate": None,     # TODO(analytics): offensive success rate (used if the play file isn't connected)
        "sack_rate": None,        # TODO(analytics): sacks / dropbacks, offense
        "stuff_rate": None,       # TODO(analytics): share of rushes stopped at or behind the line, offense
        "garbage_share": None,    # TODO(analytics): share of offensive scrimmage plays flagged garbage time
    },
}

# Play-by-play ("the play file" from the round-2 conversation). Needed for passing /
# rushing success rate and the four quarter success rates.
PLAYS = {
    "path": None,          # TODO(analytics): path to the play-level file (parquet/csv)
    "team_names": "ncaa",  # TODO(analytics): "ncaa" or "cfbd"
    "cols": {              # TODO(analytics): confirm every name
        "game": "contest_id",
        "offense": "offense",
        "down": "down",
        "distance": "distance",
        "yards": "yards_gained",
        "quarter": "period",
        "is_pass": "pass",          # bool; dropbacks incl. sacks
        "is_rush": "rush",          # bool
        "garbage": "garbage_time",  # bool
        "exclude": None,            # optional bool column: kneels/spikes/penalties to drop
    },
}

# Drives, for scoring-opportunity rate and points per opportunity
# (drive_metrics.py: trips inside the opponent's 40).
# TODO(analytics): round 2 said these may only be stored per season; confirm a per-game source.
DRIVES = {
    "path": None,          # TODO(analytics)
    "team_names": "ncaa",
    "cols": {
        "game": None,            # TODO(analytics)
        "team": None,            # TODO(analytics)
        "drives": None,          # offensive drives
        "opportunities": None,   # drives that reached the opponent's 40
        "opp_points": None,      # offensive points scored on those drives
    },
}

EPA_READY = False   # flip to True after the EP model rebuild; then connect EPA_SOURCE
EPA_SOURCE = None   # TODO(analytics, after EP rebuild): per-team-game EPA columns

# Fonts: heavy display + bold body. First file found wins.
FONTS_HEAVY = [
    ROOT / "resources" / "fonts" / "ArchivoBlack-Regular.ttf",   # TODO(analytics): the font the house graphics use
    "C:/Windows/Fonts/ariblk.ttf", "ariblk.ttf", "Arial Black.ttf",
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
# SFCS mark for dark-on-light graphics. TODO(analytics): confirm file name in resources/sfcs-logo-final/
MARK = ROOT / "resources" / "sfcs-logo-final" / "sfcs-mark-light-256.png"

D1_MATCHUPS = {"FBS-FBS", "FCS-FCS", "FBS-FCS"}   # baseline pool
IMAGE_MATCHUPS = {"FCS-FCS", "FBS-FCS"}           # games that get an image

# House colors (sampled from the SFCS graphics)
INK, PAPER, CARD, ROW_ALT = "#161616", "#f4f2ed", "#fbfaf7", "#f0ede6"
GOLD, MUTED, LINE = "#c9a961", "#6b6760", "#d6d1c4"
BAD, MID, GOOD = (205, 92, 70), (251, 250, 247), (46, 125, 79)   # red - neutral - green

# ===========================================================================
# Rows
# ===========================================================================

@dataclass
class Row:
    key: str
    label: str
    kind: str                  # "pct" (0-1 shown as %), "num2" (2 decimals), "score", "share"
    higher_is_better: bool | None = True    # None = not shaded
    epa: bool = False


ROWS = [
    Row("score", "Final Score", "score", None),
    Row("pgwe", "Postgame Win Expectancy", "pct"),
    Row("success_rate", "Success Rate", "pct"),
    Row("epa_play", "EPA per Play", "num2", epa=True),
    Row("epa_early", "Early Down EPA", "num2", epa=True),
    Row("epa_late", "Late Down EPA", "num2", epa=True),
    Row("epa_explosive", "Explosive EPA", "num2", epa=True),
    Row("sack_rate", "Sack Rate Allowed", "pct", False),
    Row("pass_sr", "Passing Success Rate", "pct"),
    Row("rush_sr", "Rushing Success Rate", "pct"),
    Row("stuff_rate", "Stuffed Rushes Allowed", "pct", False),
    Row("ppo", "Points per Opportunity", "num2"),
    Row("opp_rate", "Scoring Opportunity Rate", "pct"),
    Row("q1_sr", "1st Quarter Success Rate", "pct"),
    Row("q2_sr", "2nd Quarter Success Rate", "pct"),
    Row("q3_sr", "3rd Quarter Success Rate", "pct"),
    Row("q4_sr", "4th Quarter Success Rate", "pct"),
    Row("garbage_share", "Offensive Plays in Garbage Time", "share", None),
]

# ===========================================================================
# Data
# ===========================================================================

def _name_map(style: str) -> dict[str, str]:
    """cfbd -> ncaa team names (identity for 'ncaa')."""
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


def team_game_stats(d1_ids: set[str]) -> tuple[pd.DataFrame, set[str]]:
    """One row per (contest_id, team) for every D1-vs-D1 game, with every
    connected stat. Returns (table, set of connected stat keys)."""
    frames, connected = [], set()

    # --- team_games.parquet -------------------------------------------------
    tg = TEAM_GAMES
    cols = {k: v for k, v in tg["cols"].items() if v}
    if tg["path"] and Path(tg["path"]).exists() and tg["game_col"] and tg["team_col"] and cols:
        df = pd.read_parquet(tg["path"])
        out = pd.DataFrame({"contest_id": df[tg["game_col"]].astype(str),
                            "team": df[tg["team_col"]].replace(_name_map(tg["team_names"]))})
        for key, col in cols.items():
            out[key] = _as_fraction(df[col])
        frames.append(out)
        connected |= set(cols)

    # --- play file: passing/rushing/quarter success (and overall if needed) -
    pl = PLAYS
    if pl["path"] and Path(pl["path"]).exists():
        c = pl["cols"]
        p = pd.read_parquet(pl["path"]) if str(pl["path"]).endswith(".parquet") else pd.read_csv(pl["path"])
        p = p.rename(columns={v: k for k, v in c.items() if v})
        p["game"] = p["game"].astype(str)
        p = p[p["game"].isin(d1_ids)]
        p = p[(p["is_pass"].astype(bool) | p["is_rush"].astype(bool)) & p["down"].between(1, 4)]
        if "garbage" in p:
            p = p[~p["garbage"].fillna(False).astype(bool)]
        if "exclude" in p:
            p = p[~p["exclude"].fillna(False).astype(bool)]
        # Success: 1st down >= 50% of distance, 2nd >= 70%, 3rd/4th >= 100%.
        need = p["down"].map({1: 0.5, 2: 0.7, 3: 1.0, 4: 1.0}) * p["distance"]
        p["success"] = (p["yards"] >= need).astype(float)
        p["offense"] = p["offense"].replace(_name_map(pl["team_names"]))
        g = p.groupby(["game", "offense"])
        out = pd.DataFrame({
            "success_rate": g["success"].mean(),
            "pass_sr": p[p["is_pass"].astype(bool)].groupby(["game", "offense"])["success"].mean(),
            "rush_sr": p[p["is_rush"].astype(bool)].groupby(["game", "offense"])["success"].mean(),
        })
        for q in (1, 2, 3, 4):
            out[f"q{q}_sr"] = p[p["quarter"] == q].groupby(["game", "offense"])["success"].mean()
        out = out.reset_index().rename(columns={"game": "contest_id", "offense": "team"})
        frames.append(out)
        connected |= {"success_rate", "pass_sr", "rush_sr", "q1_sr", "q2_sr", "q3_sr", "q4_sr"}

    # --- drives: scoring opportunities --------------------------------------
    dr = DRIVES
    if dr["path"] and Path(dr["path"]).exists() and all(dr["cols"].values()):
        c = dr["cols"]
        d = pd.read_parquet(dr["path"])
        out = pd.DataFrame({
            "contest_id": d[c["game"]].astype(str),
            "team": d[c["team"]].replace(_name_map(dr["team_names"])),
            "opp_rate": d[c["opportunities"]] / d[c["drives"]],
            "ppo": d[c["opp_points"]] / d[c["opportunities"]].replace(0, np.nan),
        })
        frames.append(out)
        connected |= {"opp_rate", "ppo"}

    if not frames:
        return pd.DataFrame(columns=["contest_id", "team"]), connected
    table = frames[0]
    for f in frames[1:]:
        # later sources win on overlapping columns (play-file success rate beats team_games)
        overlap = [k for k in f.columns if k in table.columns and k not in ("contest_id", "team")]
        table = table.drop(columns=overlap).merge(f, on=["contest_id", "team"], how="outer")
    table = table[table["contest_id"].isin(d1_ids)]
    return table, connected


def pgwe_lookup(week: int) -> dict[tuple[str, str], float]:
    """(winner, loser) -> winner PGWE (0-1), from dashboards/week<P>_db/pgwe_week<P>.xlsx."""
    path = DASHBOARDS / f"week{week}_db" / f"pgwe_week{week}.xlsx"
    if not path.exists():
        return {}
    out = {}
    for sheet in PGWE_SHEETS:
        try:
            df = pd.read_excel(path, sheet_name=sheet)
        except ValueError:
            continue
        vals = _as_fraction(df["Winner PGWE"])
        for w, l, v in zip(df["Winner"], df["Loser"], vals):
            if pd.notna(v):
                out[(str(w), str(l))] = float(v)
    return out


def percentile(baseline: np.ndarray, value: float) -> float:
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
    a, b = (MID, GOOD) if t >= 0 else (MID, BAD)
    t = min(1.0, abs(t)) ** 0.85
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def fmt(row: Row, v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    if row.kind in ("pct", "share"):
        return f"{v * 100:.1f}%"
    if row.kind == "num2":
        return f"{v:+.2f}".replace("+", "") if v >= 0 else f"−{abs(v):.2f}"
    return str(int(v))


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
    """game: week, date_text, away, home, neutral; values/pcts: {side: {key: v}};
    status: {key: 'ok' | 'tbd' | 'pending'}."""
    from PIL import Image, ImageDraw

    W, M = 1500, 60
    COL = 340                      # team value columns
    ROW_H = 86
    head_h, team_h = 270, 230
    foot_h = 210 + (70 if draft_note else 0)
    H = head_h + team_h + ROW_H * len(ROWS) + foot_h
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    F = lambda c, s: _font(c, s)

    # Title block (house style: mark left, heavy title, gold rule)
    if MARK.exists():
        mk = Image.open(MARK).convert("RGBA")
        mk.thumbnail((150, 150), Image.LANCZOS)
        im.paste(mk, (M, 50), mk)
    d.text((W / 2 + 60, 105), f"WEEK {game['week']} BOX SCORE", font=F(FONTS_HEAVY, 76), fill=INK, anchor="mm")
    at = "VS" if game["neutral"] else "AT"
    d.text((W / 2 + 60, 180), f"{game['away'].upper()} {at} {game['home'].upper()} · {game['date_text']}",
           font=F(FONTS_BOLD, 30), fill=MUTED, anchor="mm")
    d.rectangle((M, 238, W - M, 242), fill=GOLD)

    # Team header
    xl, xr = M, W - M - COL                 # left / right value column x
    xc0, xc1 = M + COL, W - M - COL          # center column
    y = head_h
    for side, x in (("away", xl), ("home", xr)):
        lg = logo_image(game[side], 130)
        im.paste(lg, (int(x + COL / 2 - lg.width / 2), y + 10), lg)
        d.text((x + COL / 2, y + 170), game[side].upper(), font=F(FONTS_HEAVY, 30), fill=INK, anchor="mm")
        rec = game.get(f"{side}_record")
        if rec:
            d.text((x + COL / 2, y + 205), rec, font=F(FONTS_REGULAR, 22), fill=MUTED, anchor="mm")
    d.text(((xc0 + xc1) / 2, y + 95), at, font=F(FONTS_HEAVY, 40), fill=GOLD, anchor="mm")
    y += team_h

    # Rows
    d.rectangle((M, y - 4, W - M, y), fill=INK)
    for i, row in enumerate(ROWS):
        y0, y1 = y + i * ROW_H, y + (i + 1) * ROW_H
        st = status[row.key]
        bg = CARD if i % 2 == 0 else ROW_ALT
        d.rectangle((xc0, y0, xc1, y1), fill=bg)
        label = row.label + ("  ◆" if st == "tbd" else "")
        d.text(((xc0 + xc1) / 2, (y0 + y1) / 2 - (10 if st == "pending" else 0)), label,
               font=F(FONTS_HEAVY, 30), fill=INK if st == "ok" else "#9a958b", anchor="mm")
        if st == "pending":
            d.text(((xc0 + xc1) / 2, (y0 + y1) / 2 + 24), "PENDING EP MODEL REBUILD",
                   font=F(FONTS_BOLD, 17), fill=GOLD, anchor="mm")

        for side, x in (("away", xl), ("home", xr)):
            box = (x, y0, x + COL, y1)
            v, pc = values[side].get(row.key), pcts[side].get(row.key)
            if row.key == "score":
                other = values["home" if side == "away" else "away"]["score"]
                won = v is not None and other is not None and v > other
                d.rectangle(box, fill=INK)
                d.text((x + COL / 2, (y0 + y1) / 2), fmt(row, v), font=F(FONTS_HEAVY, 46),
                       fill="#ffffff" if won else "#8d887e", anchor="mm")
                continue
            if st != "ok":
                cell = Image.new("RGB", (COL, ROW_H), "#ebe8e1")   # hatch, clipped to the cell
                cd = ImageDraw.Draw(cell)
                for k in range(-ROW_H, COL, 18):
                    cd.line((k, ROW_H, k + ROW_H, 0), fill="#ddd9cf", width=3)
                im.paste(cell, (x, y0))
                d.text((x + COL / 2, (y0 + y1) / 2), "SOURCE TBD" if st == "tbd" else "—",
                       font=F(FONTS_BOLD, 20 if st == "tbd" else 34), fill="#9a958b", anchor="mm")
                continue
            has_pct = pc is not None and not math.isnan(pc) and row.higher_is_better is not None
            good = (pc if row.higher_is_better else 100 - pc) if has_pct else 50
            fill = shade(good) if has_pct else bg
            d.rectangle(box, fill=fill)
            strong = has_pct and abs(good - 50) > 36
            txt = "#ffffff" if strong else INK
            sub = "#eef3ee" if strong else "#5f5a52"
            if has_pct:
                d.text((x + COL / 2, y0 + 34), fmt(row, v), font=F(FONTS_HEAVY, 36), fill=txt, anchor="mm")
                d.text((x + COL / 2, y0 + 66), f"{ordinal(round(good))} %ile", font=F(FONTS_BOLD, 19),
                       fill=sub, anchor="mm")
            else:
                d.text((x + COL / 2, (y0 + y1) / 2), fmt(row, v), font=F(FONTS_HEAVY, 36), fill=txt, anchor="mm")
        d.line((M, y1, W - M, y1), fill=LINE, width=2)
    d.line((xc0, y, xc0, y + ROW_H * len(ROWS)), fill=LINE, width=2)
    d.line((xc1, y, xc1, y + ROW_H * len(ROWS)), fill=LINE, width=2)
    y += ROW_H * len(ROWS)
    d.rectangle((M, y, W - M, y + 4), fill=INK)

    # Footer: color key + the one footnote
    y += 40
    kx0, kx1 = M, M + 420
    for k in range(kx1 - kx0):
        d.line((kx0 + k, y, kx0 + k, y + 22), fill=shade(100 * k / (kx1 - kx0)))
    d.text((kx0, y + 34), "WORSE", font=F(FONTS_BOLD, 17), fill=MUTED, anchor="la")
    d.text((kx1, y + 34), "BETTER", font=F(FONTS_BOLD, 17), fill=MUTED, anchor="ra")
    d.text((kx1 + 30, y - 2),
           "Percentile vs. every D1-vs-D1 single-game team performance this season.",
           font=F(FONTS_REGULAR, 21), fill=MUTED, anchor="la")
    d.text((kx1 + 30, y + 28), "Higher = better for that team. Garbage-time plays excluded.",
           font=F(FONTS_REGULAR, 21), fill=MUTED, anchor="la")
    if draft_note:
        y += 90
        d.rectangle((M, y, W - M, y + 56), fill="#fff4d6", outline=GOLD, width=3)
        d.text((W / 2, y + 28), draft_note, font=F(FONTS_BOLD, 20), fill="#7a5c12", anchor="mm")

    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, optimize=True)


# ===========================================================================
# Build
# ===========================================================================

def build_week(week: int, only_game: str | None = None):
    sched = load_schedule()
    d1_ids = set(sched.loc[sched["matchup"].isin(D1_MATCHUPS), "contest_id"])
    table, connected = team_game_stats(d1_ids)
    pg = pgwe_lookup(week)

    status = {}
    for r in ROWS:
        if r.epa:
            status[r.key] = "ok" if EPA_READY and EPA_SOURCE else "pending"
        elif r.key == "score":
            status[r.key] = "ok"
        elif r.key == "pgwe":
            status[r.key] = "ok" if pg else "tbd"
        else:
            status[r.key] = "ok" if r.key in connected else "tbd"

    baselines = {k: np.sort(table[k].dropna().to_numpy()) for k in table.columns
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
        for side, team, score in (("away", g.away_team, g.away_score), ("home", g.home_team, g.home_score)):
            row = table[(table["contest_id"] == g.contest_id) & (table["team"] == team)]
            v = {"score": score}
            for k in baselines:
                v[k] = float(row[k].iloc[0]) if len(row) and pd.notna(row[k].iloc[0]) else None
            values[side] = v
        # PGWE: the workbook gives the winner's number; the loser's is 1 - it.
        home_won = g.home_score > g.away_score
        win, lose = (g.home_team, g.away_team) if home_won else (g.away_team, g.home_team)
        w = pg.get((win, lose))
        values["home" if home_won else "away"]["pgwe"] = w
        values["away" if home_won else "home"]["pgwe"] = None if w is None else 1 - w

        for side in values:
            pcts[side] = {k: percentile(baselines[k], values[side].get(k)) for k in baselines
                          if values[side].get(k) is not None}
            if values[side].get("pgwe") is not None:       # PGWE is already a probability: shade by its value
                pcts[side]["pgwe"] = 100 * values[side]["pgwe"]

        info = dict(week=week, away=g.away_team, home=g.home_team, neutral=bool(g.neutral),
                    date_text=g.kickoff.tz_convert("America/New_York").strftime("%a, %b %-d").upper()
                    if sys.platform != "win32" else g.kickoff.tz_convert("America/New_York").strftime("%a, %b %#d").upper())
        out = DASHBOARDS / f"week{week}_db" / "box_scores" / f"box_score_{g.contest_id}_wk{week}.png"
        render(info, values, pcts, status, out, draft)
        made += 1
    print(f"Wrote {made} box score(s) to {DASHBOARDS / f'week{week}_db' / 'box_scores'}")
    if tbd:
        print("Rows still drawn as SOURCE TBD:", ", ".join(tbd))


def demo(out: Path):
    """Design preview with made-up numbers; every row connected."""
    rng = np.random.default_rng(7)
    status = {r.key: ("pending" if r.epa and not EPA_READY else "ok") for r in ROWS}
    values = {"away": {"score": 27}, "home": {"score": 21}}
    pcts = {"away": {}, "home": {}}
    for r in ROWS:
        if r.key == "score" or status[r.key] != "ok":
            continue
        for side in values:
            if r.kind == "num2":
                v = float(rng.uniform(1.5, 5.5))
            elif r.key == "pgwe":
                v = 0.742 if side == "away" else 0.258
            else:
                v = float(rng.uniform(0.02, 0.15) if r.key in ("sack_rate", "garbage_share") else rng.uniform(0.2, 0.6))
            values[side][r.key] = v
            pcts[side][r.key] = 100 * v if r.key == "pgwe" else float(rng.uniform(1, 99))
    values["away"]["garbage_share"] = values["home"]["garbage_share"] = 0.0
    info = dict(week=6, away="Montana", home="Montana St.", neutral=False, date_text="SAT, OCT 10",
                away_record="5-1", home_record="5-1")
    render(info, values, pcts, status, out, "DEMO · made-up numbers for design review")
    print(f"Wrote demo to {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--week", type=int, help="week the games were PLAYED")
    ap.add_argument("--game", help="one contest_id only")
    ap.add_argument("--demo", action="store_true", help="design preview with made-up numbers")
    ap.add_argument("--out", default="box_score_demo.png", help="--demo output file")
    a = ap.parse_args()
    if a.demo:
        demo(Path(a.out))
    elif a.week:
        build_week(a.week, a.game)
    else:
        ap.error("give --week N (or --demo)")


if __name__ == "__main__":
    main()
