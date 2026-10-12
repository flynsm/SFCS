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
derive or check any statistic. A value it isn't given is drawn as a plain "–"
(the console reports which games had missing values).
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
# Missing file, column or cell -> drawn as "–" (and reported in the console).
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

# Credit, drawn at the end of the footnote.
HANDLE = "@SFCSratings"
WATERMARK_OPACITY = 0.04   # SF|CS mark behind the stat-name column

# Footer text (wording from the user).
FOOTNOTE = ("Garbage time excluded. Shading indicates performance as percentile "
            "relative to all D1 football games since 2023.")

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
    Row("early_down_sr", "Early Down Success Rate", "pct"),
    Row("late_down_sr", "Late Down Success Rate", "pct"),
    Row("line_yards", "Line Yards", "num2"),
    Row("def_stuff_rate", "Defensive Stuff Rate", "pct"),
    Row("havoc_rate", "Havoc Rate", "pct"),
    Row("quality_drive_rate", "Quality Drive Rate", "pct"),
    Row("pts_per_quality_drive", "Pts/Quality Drive", "num2"),
    Row("garbage_share", "Off Plays in Garbage Time", "pct"),
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


def _fit(text: str, candidates, size: int, max_w: float, min_size: int):
    """Largest font (size down to min_size) at which text fits in max_w."""
    for sz in range(size, min_size - 1, -1):
        f = _font(candidates, sz)
        if f.getlength(text) <= max_w:
            return f
    return _font(candidates, min_size)


def _wrap(text: str, font, max_w: float) -> list[str]:
    lines = [""]
    for w in text.split():
        trial = f"{lines[-1]} {w}".strip()
        if font.getlength(trial) <= max_w or not lines[-1]:
            lines[-1] = trial
        else:
            lines.append(w)
    return lines


def render(game: dict, values: dict, colors: dict, out: Path):
    """game: week, date_text, away, home, neutral, away_score, home_score
    values / colors: {"away"|"home": {row key: value / 0-100 color position}}
    Sized for phones: 1080 wide, about 9:16."""
    from PIL import Image, ImageDraw

    W, M = 1080, 36
    COL = 270                               # team value columns
    ROW_H = 100
    head_h, team_h = 150, 236
    F = _font

    reg, bold = _font(FONTS_REGULAR, 23), _font(FONTS_BOLD, 23)
    foot_lines = _wrap(FOOTNOTE, reg, W - 2 * M)
    handle_w = bold.getlength(HANDLE)
    handle_own_line = reg.getlength(foot_lines[-1]) + 30 + handle_w > W - 2 * M
    foot_h = 40 + 32 * (len(foot_lines) + handle_own_line) + 26
    H = head_h + team_h + ROW_H * len(ROWS) + foot_h
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)

    # Compact title block: small mark left, title, gold rule
    if MARK.exists():
        mk = Image.open(MARK).convert("RGBA")
        mk.thumbnail((90, 90), Image.LANCZOS)
        im.paste(mk, (M, 26), mk)
    at = "VS" if game["neutral"] else "AT"
    tx = M + 116                             # title starts right of the mark
    title = f"WEEK {game['week']} ADVANCED BOX SCORE"
    d.text((tx, 72), title, font=_fit(title, FONTS_HEAVY, 52, W - M - tx, 30), fill=INK, anchor="lm")
    d.rectangle((M, 130, W - M, 133), fill=GOLD)

    # Team header: logo + name in each value column, score beside it, AT/VS centered
    xl, xr = M, W - M - COL
    xc0, xc1 = M + COL, W - M - COL
    cx = (xc0 + xc1) / 2
    y = head_h
    a, h = game["away_score"], game["home_score"]
    for side, x, sx in (("away", xl, xc0 + 85), ("home", xr, xc1 - 85)):
        lg = logo_image(game[side], 120)
        im.paste(lg, (int(x + COL / 2 - lg.width / 2), y + 18), lg)
        name = game[side].upper()
        d.text((x + COL / 2, y + 178), name, font=_fit(name, FONTS_HEAVY, 28, COL - 16, 18), fill=INK, anchor="mm")
        mine, theirs = (a, h) if side == "away" else (h, a)
        d.text((sx, y + 92), str(int(mine)), font=F(FONTS_HEAVY, 100),
               fill=INK if mine >= theirs else "#a39e94", anchor="mm")
    d.text((cx, y + 92), at, font=F(FONTS_HEAVY, 34), fill=GOLD, anchor="mm")
    when = game["date_text"] + (" · NEUTRAL SITE" if game["neutral"] else "")
    d.text((cx, y + 178), when, font=_fit(when, FONTS_BOLD, 24, xc1 - xc0 - 150, 16), fill=MUTED, anchor="mm")
    y += team_h

    # Rows
    d.rectangle((M, y - 5, W - M, y), fill=INK)
    label_w = xc1 - xc0 - 28
    for i, row in enumerate(ROWS):
        y0, y1 = y + i * ROW_H, y + (i + 1) * ROW_H
        bg = CARD if i % 2 == 0 else ROW_ALT
        d.rectangle((xc0, y0, xc1, y1), fill=bg)
        for side, x in (("away", xl), ("home", xr)):
            v, c = values[side].get(row.key), colors[side].get(row.key)
            shaded = not _missing(v) and not _missing(c)
            d.rectangle((x, y0, x + COL, y1), fill=shade(c) if shaded else bg)
            d.text((x + COL / 2, (y0 + y1) / 2), "–" if _missing(v) else fmt(row, v), font=F(FONTS_HEAVY, 50),
                   fill="#ffffff" if shaded and abs(c - 50) > 36 else INK, anchor="mm")
        d.line((M, y1, W - M, y1), fill=LINE, width=2)
    rows_bottom = y + ROW_H * len(ROWS)

    # Faint SF|CS watermark behind the stat names (under the text)
    if MARK.exists() and WATERMARK_OPACITY > 0:
        wm = Image.open(MARK).convert("RGBA")
        wm.thumbnail((int((xc1 - xc0) * 0.85), int((rows_bottom - y) * 0.6)), Image.LANCZOS)
        wm.putalpha(wm.getchannel("A").point(lambda v: int(v * WATERMARK_OPACITY)))
        im.paste(wm, (int(cx - wm.width / 2), int((y + rows_bottom) / 2 - wm.height / 2)), wm)

    for i, row in enumerate(ROWS):                       # stat names, on top of the watermark
        y0, y1 = y + i * ROW_H, y + (i + 1) * ROW_H
        lf = _fit(row.label, FONTS_HEAVY, 30, label_w, 25)
        lines = _wrap(row.label, lf, label_w)            # one line, or two for long labels
        for n, line in enumerate(lines):
            d.text((cx, (y0 + y1) / 2 + (n - (len(lines) - 1) / 2) * 36), line, font=lf, fill=INK, anchor="mm")

    d.line((xc0, y, xc0, rows_bottom), fill=LINE, width=2)
    d.line((xc1, y, xc1, rows_bottom), fill=LINE, width=2)
    d.rectangle((M, rows_bottom, W - M, rows_bottom + 5), fill=INK)

    # Footnote + credit (credit right-aligned on the last line, or its own line if it doesn't fit)
    y = rows_bottom + 40
    for n, line in enumerate(foot_lines):
        d.text((M, y + 32 * n), line, font=reg, fill=MUTED, anchor="lm")
    hy = y + 32 * (len(foot_lines) - 1 + handle_own_line)
    d.text((W - M, hy), HANDLE, font=bold, fill=INK, anchor="rm")

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
        incomplete += any(_missing(v) for s in values for v in values[s].values())
        info = dict(week=week, away=g.away_team, home=g.home_team, neutral=bool(g.neutral),
                    away_score=g.away_score, home_score=g.home_score, date_text=_date_text(pd.to_datetime(g.game_date, utc=True)))
        out = DASHBOARDS / f"week{week}_db" / "box_scores" / f"box_score_{g.contest_id}_wk{week}.png"
        render(info, values, colors, out)
        made += 1
    print(f"Wrote {made} box score(s) to {DASHBOARDS / f'week{week}_db' / 'box_scores'}"
          + (f"  ({incomplete} with missing values, drawn as '–'; check STATS_INPUT)" if incomplete else ""))


def demo(out: Path, neutral: bool = False, placeholders: bool = False):
    """Layout preview with made-up values and color positions (design review only)."""
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
    render(info, values, colors, out)
    print(f"Wrote demo to {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--week", type=int, help="week the games were PLAYED")
    ap.add_argument("--game", help="one contest_id only")
    ap.add_argument("--demo", action="store_true", help="design preview with made-up numbers")
    ap.add_argument("--neutral", action="store_true", help="--demo: neutral-site game")
    ap.add_argument("--placeholders", action="store_true", help="--demo: no values (the empty state)")
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
