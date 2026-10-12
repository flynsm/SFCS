#!/usr/bin/env python3
"""
SFCS postgame box scores: graphic template. Draws only; computes NO statistics.

Install: copy to  <fcs-model>/site_export/box_scores.py   (next to export_site.py)
Needs:   pandas, pyarrow, Pillow

Usage:
  python site_export/box_scores.py --week 6                 every FCS game played in week 6
  python site_export/box_scores.py --week 6 --game 401868265
  python site_export/box_scores.py --demo                   design preview with made-up numbers

Output (the path the website already reads):
  dashboards/week<P>_db/box_scores/box_score_<contest_id>_wk<P>.png
  P = the week the game was PLAYED.

All stat values and their color percentiles come from the analytics pipeline
through ONE input table (STATS_INPUT below). This script does not compute,
derive or check any statistic. Any value it isn't given is drawn as a hatched
"SOURCE TBD" placeholder (label greyed), and the image carries a DRAFT banner.
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

import pandas as pd

# ===========================================================================
# CONFIG
# ===========================================================================

ROOT = Path(__file__).resolve().parent.parent          # fcs-model/
DASHBOARDS = ROOT / "dashboards"
SCHEDULE = ROOT / "processed" / "games_schedule_current.parquet"   # header only: teams, score, date, neutral
TEAM_BRAND = ROOT / "processed" / "team_brand.parquet"             # logos

# PLACEHOLDER: the box score stats table, produced by the analytics pipeline.
# The script expects one row per team per game:
#   contest_id, team (NCAA name, as in the schedule),
#   and for every row key in ROWS below:
#     <key>       the value to print (rates as 0-1, e.g. 0.412 prints as 41.2%)
#     <key>_pct   0-100 color position, 100 = best for that team (blank = unshaded)
# Missing file, column or cell -> drawn as SOURCE TBD.
STATS_INPUT = None   # PLACEHOLDER: e.g. DASHBOARDS / "week{week}_db" / "box_score_stats_wk{week}.parquet"

IMAGE_MATCHUPS = {"FCS-FCS", "FBS-FCS"}   # games that get an image (user decision)

# Fonts: heavy display + bold + regular. First file found wins.
FONTS_HEAVY = [
    ROOT / "resources" / "fonts" / "ArchivoBlack-Regular.ttf",   # PLACEHOLDER: the house display font
    "C:/Windows/Fonts/ariblk.ttf", "ariblk.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
FONTS_BOLD = [
    ROOT / "resources" / "fonts" / "Archivo-Bold.ttf",            # PLACEHOLDER
    "C:/Windows/Fonts/arialbd.ttf", "arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
FONTS_REGULAR = [
    ROOT / "resources" / "fonts" / "Archivo-Regular.ttf",         # PLACEHOLDER
    "C:/Windows/Fonts/arial.ttf", "arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
MARK = ROOT / "resources" / "sfcs-logo-final" / "sfcs-mark-light-256.png"   # PLACEHOLDER: confirm file name

# House colors (sampled from the SFCS graphics)
INK, PAPER, CARD, ROW_ALT = "#161616", "#f4f2ed", "#fbfaf7", "#f0ede6"
GOLD, MUTED, LINE = "#c9a961", "#6b6760", "#d6d1c4"
BAD, MID, GOOD = (205, 92, 70), (251, 250, 247), (46, 125, 79)   # red - neutral - green

# Footer text. PLACEHOLDER wording: confirm with the analytics side.
FOOTNOTES = [
    "Color: rank vs. every D1-vs-D1 single-game performance this season.",
    "Garbage-time plays excluded.",
]

# ===========================================================================
# Rows (the user's list; the final score sits in the header)
# ===========================================================================

@dataclass
class Row:
    key: str      # column name in STATS_INPUT
    label: str
    kind: str     # "pct" = 0-1 printed as %, "num2" = 2 decimals


ROWS = [
    Row("pgwe", "Postgame Win Expectancy", "pct"),
    Row("epa_play", "EPA per Play", "num2"),
    Row("yards_play", "Yards per Play", "num2"),
    Row("pass_sr", "Passing Success Rate", "pct"),
    Row("rush_sr", "Rushing Success Rate", "pct"),
    Row("explosive_rate", "Explosive Play Rate", "pct"),
    Row("late_down_sr", "3rd/4th Down Success Rate", "pct"),
    Row("line_yards", "Line Yards", "num2"),
    Row("def_stuff_rate", "Defensive Stuff Rate", "pct"),
    Row("havoc_rate", "Havoc Rate", "pct"),
    Row("quality_drive_rate", "Quality Drive Rate", "pct"),
    Row("finishing_drives", "Finishing Drives", "num2"),
    Row("garbage_share", "Offensive Plays in Garbage Time", "pct"),
]

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


def _missing(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def shade(pos: float) -> tuple[int, int, int]:
    """Color for a 0-100 position: 0 red, 50 neutral, 100 green."""
    t = (pos - 50) / 50
    target = GOOD if t >= 0 else BAD
    t = min(1.0, abs(t)) ** 0.85
    return tuple(round(MID[i] + (target[i] - MID[i]) * t) for i in range(3))


def fmt(row: Row, v) -> str:
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
    # No logo (e.g. non-D1): lettered badge
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 8, fill=INK)
    letters = "".join(w[0] for w in re.sub(r"[.'()&]", "", team).split()[:3]).upper()
    d.text((size / 2, size / 2), letters, font=_font(FONTS_HEAVY, size // 3), fill=GOLD, anchor="mm")
    return im


def render(game: dict, values: dict, colors: dict, out: Path, banner: str | None):
    """game: week, date_text, away, home, neutral, away_score, home_score
    values / colors: {"away"|"home": {row key: value / 0-100 color position}}"""
    from PIL import Image, ImageDraw

    W, M = 1500, 60
    COL = 340                              # team value columns
    ROW_H = 92
    head_h, team_h = 270, 250
    foot_h = 170 + (80 if banner else 0)
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

    # Team header: logo + name, final score beside it, AT/VS centered
    xl, xr = M, W - M - COL
    xc0, xc1 = M + COL, W - M - COL
    cx = (xc0 + xc1) / 2
    y = head_h
    a, h = game["away_score"], game["home_score"]
    for side, x, sx in (("away", xl, xc0 + 120), ("home", xr, xc1 - 120)):
        lg = logo_image(game[side], 140)
        im.paste(lg, (int(x + COL / 2 - lg.width / 2), y + 12), lg)
        d.text((x + COL / 2, y + 190), game[side].upper(), font=F(FONTS_HEAVY, 30), fill=INK, anchor="mm")
        mine, theirs = (a, h) if side == "away" else (h, a)
        d.text((sx, y + 95), str(int(mine)), font=F(FONTS_HEAVY, 110),
               fill=INK if mine >= theirs else "#a39e94", anchor="mm")
    d.text((cx, y + 95), at, font=F(FONTS_HEAVY, 40), fill=GOLD, anchor="mm")
    d.text((cx, y + 190), "FINAL", font=F(FONTS_BOLD, 22), fill=MUTED, anchor="mm")
    y += team_h

    # Rows
    d.rectangle((M, y - 5, W - M, y), fill=INK)
    for i, row in enumerate(ROWS):
        y0, y1 = y + i * ROW_H, y + (i + 1) * ROW_H
        bg = CARD if i % 2 == 0 else ROW_ALT
        tbd = any(_missing(values[s].get(row.key)) for s in ("away", "home"))
        d.rectangle((xc0, y0, xc1, y1), fill=bg)
        d.text((cx, (y0 + y1) / 2), row.label,
               font=F(FONTS_HEAVY, 31), fill="#9a958b" if tbd else INK, anchor="mm")

        for side, x in (("away", xl), ("home", xr)):
            v, c = values[side].get(row.key), colors[side].get(row.key)
            if _missing(v):
                cell = Image.new("RGB", (COL, ROW_H), "#ebe8e1")     # hatch, clipped to the cell
                cd = ImageDraw.Draw(cell)
                for k in range(-ROW_H, COL, 18):
                    cd.line((k, ROW_H, k + ROW_H, 0), fill="#ddd9cf", width=3)
                im.paste(cell, (x, y0))
                d.text((x + COL / 2, (y0 + y1) / 2), "SOURCE TBD", font=F(FONTS_BOLD, 21),
                       fill="#9a958b", anchor="mm")
                continue
            shaded = not _missing(c)
            d.rectangle((x, y0, x + COL, y1), fill=shade(c) if shaded else bg)
            d.text((x + COL / 2, (y0 + y1) / 2), fmt(row, v), font=F(FONTS_HEAVY, 46),
                   fill="#ffffff" if shaded and abs(c - 50) > 36 else INK, anchor="mm")
        d.line((M, y1, W - M, y1), fill=LINE, width=2)
    rows_bottom = y + ROW_H * len(ROWS)
    d.line((xc0, y, xc0, rows_bottom), fill=LINE, width=2)
    d.line((xc1, y, xc1, rows_bottom), fill=LINE, width=2)
    d.rectangle((M, rows_bottom, W - M, rows_bottom + 5), fill=INK)

    # Footer: color key + footnotes
    y = rows_bottom + 45
    kx0, kx1 = M, M + 420
    for k in range(kx1 - kx0):
        d.line((kx0 + k, y, kx0 + k, y + 22), fill=shade(100 * k / (kx1 - kx0)))
    d.text((kx0, y + 34), "WORSE", font=F(FONTS_BOLD, 17), fill=MUTED, anchor="la")
    d.text((kx1, y + 34), "BETTER", font=F(FONTS_BOLD, 17), fill=MUTED, anchor="ra")
    for n, line in enumerate(FOOTNOTES):
        d.text((kx1 + 30, y - 2 + 30 * n), line, font=F(FONTS_REGULAR, 21), fill=MUTED, anchor="la")
    if banner:
        y += 95
        d.rectangle((M, y, W - M, y + 56), fill="#fff4d6", outline=GOLD, width=3)
        d.text((W / 2, y + 28), banner, font=F(FONTS_BOLD, 20), fill="#7a5c12", anchor="mm")

    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, optimize=True)


# ===========================================================================
# Build
# ===========================================================================

def _date_text(ts) -> str:
    et = pd.Timestamp(ts).tz_convert("America/New_York")
    return f"{et.strftime('%a, %b')} {et.day}".upper()


def load_stats(week: int) -> pd.DataFrame | None:
    if not STATS_INPUT:
        return None
    path = Path(str(STATS_INPUT).format(week=week))
    if not path.exists():
        return None
    df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    df["contest_id"] = df["contest_id"].astype(str)
    return df


def build_week(week: int, only_game: str | None = None):
    sched = pd.read_parquet(SCHEDULE)
    sched["contest_id"] = sched["contest_id"].astype(str)
    if "season_type" in sched.columns:
        sched = sched[sched["season_type"].fillna("regular") == "regular"]
    games = sched[(sched["week"] == week) & sched["matchup"].isin(IMAGE_MATCHUPS)
                  & sched["completed"].fillna(False).astype(bool) & sched["home_score"].notna()]
    if only_game:
        games = games[games["contest_id"] == only_game]
    if games.empty:
        sys.exit(f"No completed FCS games found for week {week}" + (f" with id {only_game}" if only_game else ""))

    stats = load_stats(week)
    made, incomplete = 0, 0
    for g in games.itertuples():
        values, colors = {}, {}
        for side, team in (("away", g.away_team), ("home", g.home_team)):
            r = None
            if stats is not None:
                m = stats[(stats["contest_id"] == g.contest_id) & (stats["team"] == team)]
                r = m.iloc[0] if len(m) else None
            get = lambda col: (None if r is None or col not in r.index or pd.isna(r[col]) else float(r[col]))
            values[side] = {row.key: get(row.key) for row in ROWS}
            colors[side] = {row.key: get(f"{row.key}_pct") for row in ROWS}
        tbd = sum(_missing(v) for s in values for v in values[s].values())
        banner = "DRAFT · cells marked SOURCE TBD have no stat source connected yet (see STATS_INPUT)" if tbd else None
        incomplete += bool(tbd)
        info = dict(week=week, away=g.away_team, home=g.home_team, neutral=bool(g.neutral),
                    away_score=g.away_score, home_score=g.home_score, date_text=_date_text(pd.to_datetime(g.game_date, utc=True)))
        out = DASHBOARDS / f"week{week}_db" / "box_scores" / f"box_score_{g.contest_id}_wk{week}.png"
        render(info, values, colors, out, banner)
        made += 1
    print(f"Wrote {made} box score(s) to {DASHBOARDS / f'week{week}_db' / 'box_scores'}"
          + (f"  ({incomplete} with SOURCE TBD placeholders)" if incomplete else ""))


def demo(out: Path, neutral: bool = False, placeholders: bool = False):
    """Design preview. Made-up values and color positions; nothing is computed."""
    import random
    rnd = random.Random(7)
    values, colors = {"away": {}, "home": {}}, {"away": {}, "home": {}}
    for row in ROWS:
        for side in values:
            if placeholders:
                values[side][row.key] = None
                continue
            values[side][row.key] = rnd.uniform(0.2, 0.6) if row.kind == "pct" else rnd.uniform(-0.3, 5.5)
            colors[side][row.key] = rnd.uniform(1, 99)
    info = dict(week=6, away="Montana", home="Montana St.", neutral=neutral, away_score=27, home_score=21,
                date_text="SAT, OCT 10")
    render(info, values, colors, out,
           "DRAFT · cells marked SOURCE TBD have no stat source connected yet" if placeholders else "DEMO · made-up numbers for design review")
    print(f"Wrote demo to {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--week", type=int, help="week the games were PLAYED")
    ap.add_argument("--game", help="one contest_id only")
    ap.add_argument("--demo", action="store_true", help="design preview with made-up numbers")
    ap.add_argument("--neutral", action="store_true", help="--demo: neutral-site game")
    ap.add_argument("--placeholders", action="store_true", help="--demo: show every stat as SOURCE TBD")
    ap.add_argument("--out", default="box_score_demo.png", help="--demo output file")
    a = ap.parse_args()
    if a.demo:
        demo(Path(a.out), a.neutral, a.placeholders)
    elif a.week:
        build_week(a.week, a.game)
    else:
        ap.error("give --week N (or --demo)")


if __name__ == "__main__":
    main()
