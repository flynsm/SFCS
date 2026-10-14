#!/usr/bin/env python3
"""
SFCS game previews: graphic template. Draws only; computes NO statistics.

Install: copy to  <fcs-model>/site_export/previews.py   (next to export_site.py)
Needs:   pandas, pyarrow, Pillow

Usage:
  python site_export/previews.py --week 7                    every FCS game in week 7
  python site_export/previews.py --week 7 --game 401868265
  python site_export/previews.py --demo                      layout preview with made-up numbers

Output (the path the website already reads; a game's Preview link appears once it exists):
  dashboards/week<N>_db/previews/preview_<contest_id>_wk<N>.png      N = the UPCOMING week

All values, ranks and team info come from the analytics pipeline through ONE
input table (PREVIEW_INPUT). The only thing computed here is the badge color,
from the supplied rank and division size, using the user's shading rule.
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
SCHEDULE = ROOT / "processed" / "games_schedule_current.parquet"   # games, date, neutral
TEAM_BRAND = ROOT / "processed" / "team_brand.parquet"             # logo + ink

# The preview stats table, produced by the analytics pipeline. One row per team per game:
#   contest_id, team (NCAA name, as in the schedule)
#   record, conf_record, conf_name      header line, e.g. "5-1 (3-0) Big Sky"
#   proj_pts                            projected points
#   win_prob                            0-1
#   div_n                               number of teams in this team's subdivision (FCS or FBS)
#   for every stat key in STATS:
#     off_<key>, off_<key>_rank         this team's offense: value + rank (1 = best)
#     def_<key>, def_<key>_rank         this team's defense: value + rank (1 = best)
# Missing file, column or cell -> drawn as "–" (and reported in the console).
PREVIEW_INPUT = None   # e.g. DASHBOARDS / "week{week}_db" / "preview_stats_wk{week}.parquet"

IMAGE_MATCHUPS = {"FCS-FCS", "FBS-FCS"}   # games that get a preview

FONTS_HEAVY = [ROOT / "resources" / "fonts" / "ArchivoBlack-Regular.ttf",
               "C:/Windows/Fonts/ariblk.ttf", "ariblk.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
FONTS_BOLD = [ROOT / "resources" / "fonts" / "Archivo-Bold.ttf",
              "C:/Windows/Fonts/arialbd.ttf", "arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
FONTS_REGULAR = [ROOT / "resources" / "fonts" / "Archivo-Regular.ttf",
                 "C:/Windows/Fonts/arial.ttf", "arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
MARK = ROOT / "resources" / "sfcs-logo-final" / "sfcs-mark-light-256.png"

HANDLE = "@SFCSratings"
DEFINITIONS_URL = "sfcsratings.com/definitions"
WATERMARK_OPACITY = 0.04
FOOTNOTE = ("Ranks within each team's division. "
            f"Definitions for stats at {DEFINITIONS_URL}. {HANDLE}")

# House colors
INK, PAPER, CARD, ROW_ALT = "#161616", "#f4f2ed", "#fbfaf7", "#f0ede6"
GOLD, MUTED, LINE = "#c9a961", "#6b6760", "#d6d1c4"

# Rank shading (the user's rule)
NEUTRAL, BLUE, RED = (230, 228, 223), (47, 90, 168), (191, 74, 67)
BODY_INK = "#1c1c1c"

# ===========================================================================
# Rows of each matchup panel (offense of one team vs defense of the other)
# ===========================================================================

@dataclass
class Stat:
    key: str      # column stem in PREVIEW_INPUT
    label: str
    kind: str     # "pct" 0-1 shown as %, "num1"/"num2"/"num3" decimals


STATS = [
    Stat("rating", "Rating", "num1"),
    Stat("success_rate", "Success Rate", "pct"),
    Stat("epa_dropback", "EPA/Dropback", "num3"),
    Stat("epa_rush", "EPA/Rush", "num3"),
    Stat("havoc", "Havoc Rate", "pct"),
    Stat("stuff_rate", "Stuff Rate", "pct"),
    Stat("quality_drives", "Quality Drives", "pct"),
    Stat("finishing_drives", "Finishing Drives", "num2"),
]

# ===========================================================================
# Helpers
# ===========================================================================

def _font(candidates, size):
    from PIL import ImageFont
    for f in candidates:
        try:
            return ImageFont.truetype(str(f), size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _fit(text, candidates, size, max_w, min_size):
    for sz in range(size, min_size - 1, -1):
        f = _font(candidates, sz)
        if f.getlength(text) <= max_w:
            return f
    return _font(candidates, min_size)


def _wrap(text, font, max_w):
    lines = [""]
    for w in text.split():
        trial = f"{lines[-1]} {w}".strip()
        if font.getlength(trial) <= max_w or not lines[-1]:
            lines[-1] = trial
        else:
            lines.append(w)
    return lines


def _missing(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def rank_percentile(rank, n):
    """User rule: percentile = round((n - rank) / (n - 1) * 100); none if rank missing or n < 2."""
    if _missing(rank) or _missing(n) or n < 2:
        return None
    return round((n - rank) / (n - 1) * 100)


def rank_colors(pct):
    """User rule: continuous blend neutral -> blue (best) / red (worst); white text at >=80 or <20."""
    t = (pct - 50) / 50
    target, k = (BLUE, t) if t >= 0 else (RED, -t)
    bg = tuple(round(NEUTRAL[i] + (target[i] - NEUTRAL[i]) * k) for i in range(3))
    return bg, "#ffffff" if pct >= 80 or pct < 20 else BODY_INK


def fmt(kind, v) -> str:
    if _missing(v):
        return "–"
    if kind == "pct":
        return f"{v * 100:.1f}%"
    d = int(kind[-1])
    s = f"{abs(v):.{d}f}"
    return f"−{s}" if v < 0 else s


_BRAND = None


def _brand():
    global _BRAND
    if _BRAND is None:
        _BRAND = pd.read_parquet(TEAM_BRAND).set_index("team") if TEAM_BRAND.exists() else pd.DataFrame()
    return _BRAND


def team_ink(team) -> str:
    """The `ink` column of team_brand.parquet, used as-is."""
    b = _brand()
    if "ink" in b.columns and team in b.index and isinstance(b.at[team, "ink"], str):
        return b.at[team, "ink"]
    return INK


def logo_image(team, size):
    from PIL import Image, ImageDraw
    b = _brand()
    uri = b["logo"].get(team) if "logo" in b.columns and team in b.index else None
    if isinstance(uri, str) and "base64," in uri:
        im = Image.open(io.BytesIO(base64.b64decode(uri.split("base64,", 1)[1]))).convert("RGBA")
        im.thumbnail((size, size), Image.LANCZOS)
        return im
    # No logo: ink badge with white bold letters (house rule)
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 8, fill=team_ink(team))
    letters = "".join(w[0] for w in re.sub(r"[.'()&]", "", team).split()[:3]).upper()
    d.text((size / 2, size / 2), letters, font=_font(FONTS_HEAVY, size // 3), fill="#ffffff", anchor="mm")
    return im


# ===========================================================================
# Drawing blocks
# ===========================================================================

def draw_badge(d, cx, cy, rank, n, w=78, h=46):
    pct = rank_percentile(rank, n)
    if pct is None:
        return
    bg, fg = rank_colors(pct)
    d.rounded_rectangle((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), radius=7, fill=bg)
    d.text((cx, cy + 1), str(int(rank)), font=_font(FONTS_HEAVY, 26), fill=fg, anchor="mm")


def draw_header(im, d, W, M, y, game, away, home):
    """Box-score-style header: logo + name (ink) + record line in the outer columns,
    projected points in large type beside each logo, win probability under it,
    AT/VS and the date in the center. Returns the bottom y."""
    COL = 270
    xc0, xc1 = M + COL, W - M - COL
    cx = W / 2
    at = "VS" if game["neutral"] else "AT"
    for side, info, x, sx in (("away", away, M, xc0 + 88), ("home", home, W - M - COL, xc1 - 88)):
        team = game[side]
        lg = logo_image(team, 120)
        im.paste(lg, (int(x + COL / 2 - lg.width / 2), y + 18), lg)
        name = team.upper()
        d.text((x + COL / 2, y + 172), name, font=_fit(name, FONTS_HEAVY, 28, COL - 16, 18), fill=team_ink(team), anchor="mm")
        line = " ".join(p for p in [info.get("record") or "",
                                     f"({info['conf_record']})" if info.get("conf_record") else "",
                                     info.get("conf_name") or ""] if p) or "–"
        d.text((x + COL / 2, y + 206), line, font=_fit(line, FONTS_BOLD, 21, COL - 10, 13), fill=MUTED, anchor="mm")
        pts = fmt("num1", info.get("proj_pts"))
        d.text((sx, y + 92), pts, font=_fit(pts, FONTS_HEAVY, 84, 180, 50), fill=INK, anchor="mm")
        wp = fmt("pct", info.get("win_prob"))
        d.text((sx, y + 152), "WIN PROB", font=_font(FONTS_BOLD, 16), fill=MUTED, anchor="mm")
        d.text((sx, y + 182), wp, font=_fit(wp, FONTS_HEAVY, 30, 180, 18), fill=INK, anchor="mm")
    d.text((cx, y + 26), "PROJECTED SCORE", font=_font(FONTS_BOLD, 16), fill=MUTED, anchor="mm")
    d.text((cx, y + 92), at, font=_font(FONTS_HEAVY, 32), fill=GOLD, anchor="mm")
    when = [game["date_text"]] + (["NEUTRAL SITE"] if game["neutral"] else [])
    for k, w in enumerate(when):
        d.text((cx, y + 206 + 24 * k), w, font=_fit(w, FONTS_BOLD, 19, 200, 12), fill=MUTED, anchor="mm")
    return y + 236


def draw_panel(im, d, x0, x1, y, off_team, def_team, off, dfn, row_h=74):
    """Panel: <off_team> OFF vs <def_team> DEF. Returns the bottom y."""
    head_h = 70
    d.rounded_rectangle((x0, y, x1, y + head_h + row_h * len(STATS)), radius=12, fill=CARD, outline=LINE, width=2)
    # header: team names in their ink
    cx = (x0 + x1) / 2
    parts = [(off_team.upper(), team_ink(off_team)), (" OFF  vs  ", MUTED), (def_team.upper(), team_ink(def_team)), (" DEF", MUTED)]
    f = _fit("".join(p for p, _ in parts), FONTS_HEAVY, 28, x1 - x0 - 40, 16)
    tx = cx - f.getlength("".join(p for p, _ in parts)) / 2
    for text, color in parts:
        d.text((tx, y + head_h / 2), text, font=f, fill=color, anchor="lm")
        tx += f.getlength(text)
    d.line((x0, y + head_h, x1, y + head_h), fill=LINE, width=2)

    W = x1 - x0
    val_w = 0.2 * W
    l_val, l_badge = x0 + 20 + val_w / 2, x0 + 20 + val_w + 48
    r_badge, r_val = x1 - 20 - val_w - 48, x1 - 20 - val_w / 2
    label_w = (r_badge - 45) - (l_badge + 45)
    for i, s in enumerate(STATS):
        y0 = y + head_h + i * row_h
        cy = y0 + row_h / 2
        if i % 2:
            d.rectangle((x0 + 2, y0, x1 - 2, y0 + row_h), fill=ROW_ALT)
        ov, orank = off.get(f"off_{s.key}"), off.get(f"off_{s.key}_rank")
        dv, drank = dfn.get(f"def_{s.key}"), dfn.get(f"def_{s.key}_rank")
        d.text((l_val, cy), fmt(s.kind, ov), font=_font(FONTS_HEAVY, 32), fill=INK, anchor="mm")
        draw_badge(d, l_badge, cy, orank, off.get("div_n"))
        d.text((cx, cy), s.label.upper(), font=_fit(s.label.upper(), FONTS_HEAVY, 25, label_w, 16), fill=INK, anchor="mm")
        draw_badge(d, r_badge, cy, drank, dfn.get("div_n"))
        d.text((r_val, cy), fmt(s.kind, dv), font=_font(FONTS_HEAVY, 32), fill=INK, anchor="mm")
    d.rounded_rectangle((x0, y, x1, y + head_h + row_h * len(STATS)), radius=12, outline=LINE, width=2)
    return y + head_h + row_h * len(STATS)


def _watermark(im, cx, cy, max_w, max_h):
    from PIL import Image
    if not MARK.exists() or WATERMARK_OPACITY <= 0:
        return
    wm = Image.open(MARK).convert("RGBA")
    wm.thumbnail((int(max_w), int(max_h)), Image.LANCZOS)
    wm.putalpha(wm.getchannel("A").point(lambda v: int(v * WATERMARK_OPACITY)))
    im.paste(wm, (int(cx - wm.width / 2), int(cy - wm.height / 2)), wm)


def _title(im, d, W, M, week):
    from PIL import Image
    if MARK.exists():
        mk = Image.open(MARK).convert("RGBA")
        mk.thumbnail((90, 90), Image.LANCZOS)
        im.paste(mk, (M, 26), mk)
    tx = M + 116
    title = f"WEEK {week} GAME PREVIEW"
    d.text((tx, 72), title, font=_fit(title, FONTS_HEAVY, 52, W - M - tx, 30), fill=INK, anchor="lm")
    d.rectangle((M, 130, W - M, 133), fill=GOLD)


def _footnote(d, W, M, y):
    reg = _font(FONTS_REGULAR, 22)
    lines = _wrap(FOOTNOTE, reg, W - 2 * M)
    for n, line in enumerate(lines):
        d.text((M, y + 30 * n), line, font=reg, fill=MUTED, anchor="lm")
    return y + 30 * len(lines)


def render(game, away, home, out: Path):
    """game: week, away, home, neutral, date_text; away/home: dicts of that team's input row.
    Sized for phones: 1080 wide."""
    from PIL import Image, ImageDraw
    W, M = 1080, 36
    panel_h = 70 + 74 * len(STATS)
    im = Image.new("RGB", (W, 150 + 260 + 2 * panel_h + 36 + 200), PAPER)
    d = ImageDraw.Draw(im)
    _title(im, d, W, M, game["week"])
    top = draw_header(im, d, W, M, 150, game, away, home) + 14
    mid = draw_panel(im, d, M, W - M, top, game["away"], game["home"], away, home) + 30
    bottom = draw_panel(im, d, M, W - M, mid, game["home"], game["away"], home, away)
    _watermark(im, W / 2, (top + bottom) / 2, 420, 460)
    end = _footnote(d, W, M, bottom + 40)
    im = im.crop((0, 0, W, end + 30))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, optimize=True)


# ===========================================================================
# Build
# ===========================================================================

def _date_text(ts) -> str:
    et = pd.Timestamp(ts).tz_convert("America/New_York")
    return f"{et.strftime('%a, %b')} {et.day}".upper()


def load_input(week):
    if not PREVIEW_INPUT:
        return None
    path = Path(str(PREVIEW_INPUT).format(week=week))
    if not path.exists():
        return None
    df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    df["contest_id"] = df["contest_id"].astype(str)
    return df


def _row(df, cid, team) -> dict:
    if df is None:
        return {}
    m = df[(df["contest_id"] == cid) & (df["team"] == team)]
    if not len(m):
        return {}
    return {k: (None if pd.isna(v) else v) for k, v in m.iloc[0].items()}


def build_week(week, only_game=None):
    sched = pd.read_parquet(SCHEDULE)
    sched["contest_id"] = sched["contest_id"].astype(str)
    if "season_type" in sched.columns:
        sched = sched[sched["season_type"].fillna("regular") == "regular"]
    games = sched[(sched["week"] == week) & sched["matchup"].isin(IMAGE_MATCHUPS)]
    if only_game:
        games = games[games["contest_id"] == only_game]
    if games.empty:
        sys.exit(f"No FCS games found for week {week}" + (f" with id {only_game}" if only_game else ""))
    df = load_input(week)
    made = incomplete = 0
    for g in games.itertuples():
        away, home = _row(df, g.contest_id, g.away_team), _row(df, g.contest_id, g.home_team)
        incomplete += not (away and home)
        info = dict(week=week, away=g.away_team, home=g.home_team, neutral=bool(g.neutral),
                    date_text=_date_text(pd.to_datetime(g.game_date, utc=True)))
        out = DASHBOARDS / f"week{week}_db" / "previews" / f"preview_{g.contest_id}_wk{week}.png"
        render(info, away, home, out)
        made += 1
    print(f"Wrote {made} preview(s) to {DASHBOARDS / f'week{week}_db' / 'previews'}"
          + (f"  ({incomplete} missing input rows, drawn as '–'; check PREVIEW_INPUT)" if incomplete else ""))


def demo(out: Path):
    """Layout preview with made-up values and ranks (design review only)."""
    import random
    rnd = random.Random(11)

    def team(record, conf_rec, conf, pts, wp):
        r = dict(record=record, conf_record=conf_rec, conf_name=conf, proj_pts=pts, win_prob=wp, div_n=128)
        for s in STATS:
            for side in ("off", "def"):
                v = {"pct": rnd.uniform(0.3, 0.55), "num1": rnd.uniform(-12, 15),
                     "num2": rnd.uniform(2.5, 5.5), "num3": rnd.uniform(-0.25, 0.25)}[s.kind]
                r[f"{side}_{s.key}"], r[f"{side}_{s.key}_rank"] = v, rnd.randint(1, 128)
        return r

    game = dict(week=7, away="Montana", home="Montana St.", neutral=False, date_text="SAT, OCT 17")
    render(game, team("5-1", "3-0", "Big Sky", 24.3, 0.284), team("5-1", "2-1", "Big Sky", 31.6, 0.716), out)
    print(f"Wrote demo to {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--week", type=int, help="the UPCOMING week")
    ap.add_argument("--game", help="one contest_id only")
    ap.add_argument("--demo", action="store_true", help="layout preview with made-up numbers")
    ap.add_argument("--out", default="preview_demo.png", help="--demo output file")
    a = ap.parse_args()
    if a.demo:
        demo(Path(a.out))
    elif a.week:
        build_week(a.week, a.game)
    else:
        ap.error("give --week N (or --demo)")


if __name__ == "__main__":
    main()
