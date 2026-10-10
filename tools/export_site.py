#!/usr/bin/env python3
"""
SFCS website export.

Builds ONE folder, site_export/upload/, holding exactly the files the website
needs this week, laid out like the website repo. The user drags its contents
into the repo on github.com (Add file -> Upload files). Nothing else from the
model goes to the website.

Install: copy this file to  <fcs-model>/site_export/export_site.py
Needs:   pandas + pyarrow (already used by the model), Pillow (thumbnails,
         placeholders and logos).

Usage (run from anywhere):
  python site_export/export_site.py                  weekly export (after run_weekly.py)
  python site_export/export_site.py --week 7         same, but force the upcoming week
  python site_export/export_site.py --snapshot       only save current projections (no upload)
  python site_export/export_site.py --placeholders   test run: labeled placeholder images
  python site_export/export_site.py --logos          one-time team logo export

The full rules (folders, names, columns) are in the website repo:
docs/SITE_INTEGRATION.md
"""

from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SEASON = 2026

ROOT = Path(__file__).resolve().parent.parent          # fcs-model/
DASHBOARDS = ROOT / "dashboards"
SCHEDULE = ROOT / "processed" / "games_schedule_current.parquet"
PREDICTIONS = ROOT / "processed" / "predictions_current.parquet"
TEAM_BRAND = ROOT / "processed" / "team_brand.parquet"

EXPORT = ROOT / "site_export"
UPLOAD = EXPORT / "upload"                  # rebuilt every run; drag its contents to GitHub
LOGOS_UPLOAD = EXPORT / "logos_upload"      # rebuilt by --logos
STATE = EXPORT / "state"                    # script memory; never upload
PROJ_STORE = STATE / f"projections_{SEASON}.csv"
PUBLISHED = STATE / "published"             # copy of the last published data files

FCS_CONFERENCES = [
    "Big Sky", "Coastal Athletic", "FCS Independents", "Ivy", "MEAC", "MVFC", "NEC",
    "OVC", "Patriot", "Pioneer", "Southern", "Southland", "SWAC", "UAC",
]
FCS_MATCHUPS = {"FCS-FCS", "FBS-FCS", "FCS-nonD1"}
ET = ZoneInfo("America/New_York")

GITHUB_MAX_FILES = 100   # github.com accepts at most 100 files per upload
PLACEHOLDER_GAMES = 5    # --placeholders: how many games get a preview / box score


def conf_slug(label: str) -> str:
    """'Big Sky' -> 'big_sky' (the slug used in title_odds_<slug>_wk<N>.png)."""
    return re.sub(r"[\s-]+", "_", label.strip().lower())


def team_slug(name: str) -> str:
    """Team name -> logo file name. MUST match teamSlug() in the site's js/data.js.
    lowercase; delete . & ' ’ ( ); every other run of non [a-z0-9] -> '-'; trim '-'.
    'South Dakota St.' -> 'south-dakota-st', 'N.C. A&T' -> 'nc-at'."""
    s = str(name).lower()
    s = re.sub(r"[.&'’()]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


# Weekly images shown on the site: (product key, label, home-page card?).
# File name = <key>_wk<N>.png in dashboards/week<N>_db/.
PRODUCTS = [
    ("ratings_fcs", "Power Ratings", True),
    ("resume_rating_fcs_top30", "Resume Rating", True),
    ("unit_improvers_fcs", "Biggest Improvers", True),
    ("off_def_ratings_fcs", "Offense / Defense Ratings", True),   # planned
] + [
    (f"title_odds_{conf_slug(c)}", f"{c} Title Odds", False)
    for c in FCS_CONFERENCES if c != "FCS Independents"
]

# Placeholder sizes (w, h), scaled down from the real outputs.
PLACEHOLDER_SIZE = {
    "ratings_fcs": (1600, 1800),
    "resume_rating_fcs_top30": (1600, 958),
    "unit_improvers_fcs": (1600, 855),
    "off_def_ratings_fcs": (1600, 1000),
    "title_odds": (1600, 1300),
    "preview": (1600, 900),
    "box_score": (1600, 900),
}

GAME_COLUMNS = [
    "contest_id", "week", "kickoff_et", "neutral",
    "away", "away_conf", "away_record", "home", "home_conf", "home_record",
    "proj_away", "proj_home", "home_win_prob",
    "away_score", "home_score", "has_preview", "has_box_score",
]


def week_dir(week: int) -> Path:
    return DASHBOARDS / f"week{week}_db"


def preview_name(cid: str, week: int) -> str:
    return f"preview_{cid}_wk{week}.png"


def box_score_name(cid: str, week: int) -> str:
    return f"box_score_{cid}_wk{week}.png"


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def load_schedule() -> pd.DataFrame:
    df = pd.read_parquet(SCHEDULE)
    df = df[df["matchup"].isin(FCS_MATCHUPS)].copy()
    df["contest_id"] = df["contest_id"].astype(str)
    df["week"] = df["week"].astype(int)
    df["kickoff"] = pd.to_datetime(df["game_date"], utc=True)
    df["final"] = df["completed"].fillna(False).astype(bool) & df["home_score"].notna() & df["away_score"].notna()
    return df


def update_projection_store() -> pd.DataFrame:
    """Keep the LAST projection made for every game. predictions_current only holds
    remaining games, so once a game is played its pre-game projection lives on here."""
    pred = pd.read_parquet(PREDICTIONS)
    pred = pd.DataFrame({
        "contest_id": pred["contest_id"].astype(str),
        "week": pred["week"].astype(int),
        "proj_away": pred["proj_away"].round(1),
        "proj_home": pred["proj_home"].round(1),
        "home_win_prob": pred["p_home"].round(3),
        "rated": pred["rated"].fillna(False).astype(bool),
    })
    pred.loc[~pred["rated"], ["proj_away", "proj_home", "home_win_prob"]] = None
    pred["saved_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if PROJ_STORE.exists():
        old = pd.read_csv(PROJ_STORE, dtype={"contest_id": str})
        old = old[~old["contest_id"].isin(pred["contest_id"])]
        store = pd.concat([old, pred], ignore_index=True)
    else:
        store = pred
    STATE.mkdir(parents=True, exist_ok=True)
    store.sort_values(["week", "contest_id"]).to_csv(PROJ_STORE, index=False)
    return store


def records_before(schedule: pd.DataFrame) -> dict[tuple[str, str], str]:
    """(contest_id, team) -> 'W-L' going into that game. FCS teams only."""
    fcs = set(FCS_CONFERENCES)
    played = schedule[schedule["final"]]
    results: dict[str, list[tuple[pd.Timestamp, bool]]] = {}
    for g in played.itertuples():
        home_won = g.home_score > g.away_score
        results.setdefault(g.home_team, []).append((g.kickoff, home_won))
        results.setdefault(g.away_team, []).append((g.kickoff, not home_won))
    out = {}
    for g in schedule.itertuples():
        for team, conf in ((g.home_team, g.home_conf), (g.away_team, g.away_conf)):
            if conf not in fcs:
                continue
            prior = [won for t, won in results.get(team, []) if t < g.kickoff]
            out[(g.contest_id, team)] = f"{sum(prior)}-{len(prior) - sum(prior)}"
    return out


def build_week_rows(week, schedule, store, records, previews, box_scores) -> list[dict]:
    games = schedule[schedule["week"] == week].merge(
        store[["contest_id", "proj_away", "proj_home", "home_win_prob"]], on="contest_id", how="left")
    rows = []
    for g in games.sort_values(["kickoff", "contest_id"]).itertuples():
        num = lambda v, nd=1: "" if pd.isna(v) else (int(v) if nd == 0 else round(float(v), nd))
        txt = lambda v: "" if pd.isna(v) else str(v)
        rows.append({
            "contest_id": g.contest_id,
            "week": week,
            "kickoff_et": g.kickoff.tz_convert(ET).strftime("%Y-%m-%d %H:%M"),
            "neutral": 1 if pd.notna(g.neutral) and bool(g.neutral) else 0,
            "away": g.away_team,
            "away_conf": txt(g.away_conf),
            "away_record": records.get((g.contest_id, g.away_team), ""),
            "home": g.home_team,
            "home_conf": txt(g.home_conf),
            "home_record": records.get((g.contest_id, g.home_team), ""),
            "proj_away": num(g.proj_away),
            "proj_home": num(g.proj_home),
            "home_win_prob": num(g.home_win_prob, 3),
            "away_score": num(g.away_score, 0) if g.final else "",
            "home_score": num(g.home_score, 0) if g.final else "",
            "has_preview": 1 if g.contest_id in previews else 0,
            "has_box_score": 1 if g.final and g.contest_id in box_scores else 0,
        })
    return rows


def csv_text(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=GAME_COLUMNS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------

def _font(size):
    from PIL import ImageFont
    for f in ("arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf",
              "C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def make_placeholder(path: Path, size, title: str, subtitle: str):
    from PIL import Image, ImageDraw
    w, h = size
    im = Image.new("RGB", (w, h), "#f4f2ed")
    d = ImageDraw.Draw(im)
    d.rectangle((40, 40, w - 40, h - 40), outline="#c9a961", width=6)
    cy = min(h / 2, 420)   # near the top, so home-page thumbnails (top crop) show the label
    d.text((w / 2, cy - 70), title, font=_font(64), fill="#161616", anchor="mm")
    d.text((w / 2, cy + 10), "PLACEHOLDER", font=_font(44), fill="#a8873f", anchor="mm")
    d.text((w / 2, cy + 80), subtitle, font=_font(28), fill="#6b6760", anchor="mm")
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, optimize=True)


def make_thumb(src: Path, dest: Path, width=800):
    try:
        from PIL import Image
    except ImportError:
        print("  ! Pillow not installed: skipping thumbnails (site falls back to full images)")
        return False
    im = Image.open(src).convert("RGB")
    im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.save(dest, quality=82)
    return True


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def detect_week() -> int:
    weeks = [int(m.group(1)) for p in DASHBOARDS.glob("week*_db")
             if (m := re.fullmatch(r"week(\d+)_db", p.name))]
    if not weeks:
        sys.exit(f"No dashboards/week<N>_db folders found in {DASHBOARDS}")
    return max(weeks)


def export(week: int, placeholders: bool):
    played = week - 1
    print(f"SFCS site export: upcoming week {week}, played week {played}"
          + ("  [PLACEHOLDER TEST]" if placeholders else ""))

    # Fresh upload folder (only ever the script's own folder).
    if UPLOAD.exists():
        shutil.rmtree(UPLOAD)
    UPLOAD.mkdir(parents=True)
    dest_week = UPLOAD / "dashboards" / f"week{week}_db"

    # 1. Weekly images ------------------------------------------------------
    products = []
    for key, label, home_card in PRODUCTS:
        name = f"{key}_wk{week}.png"
        src = week_dir(week) / name
        dest = dest_week / name
        if placeholders:
            size = PLACEHOLDER_SIZE.get(key) or PLACEHOLDER_SIZE["title_odds"]
            make_placeholder(dest, size, f"WEEK {week} {label.upper()}", name)
        elif src.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        else:
            if key != "off_def_ratings_fcs":   # planned product; silence expected
                print(f"  ! missing {src.relative_to(ROOT)}")
            continue
        products.append(key)
        if home_card:
            make_thumb(dest, dest.with_name(f"{key}_wk{week}_thumb.jpg"))

    # 2. Games data ---------------------------------------------------------
    schedule = load_schedule()
    store = update_projection_store()
    records = records_before(schedule)
    first_week = int(store["week"].min())
    games_weeks = [w for w in range(first_week, week + 1) if (schedule["week"] == w).any()]

    PUBLISHED.mkdir(parents=True, exist_ok=True)
    published_files = []
    for w in games_weeks:
        wdir = week_dir(w)
        previews = {m.group(1) for p in (wdir / "previews").glob(f"preview_*_wk{w}.png")
                    if (m := re.fullmatch(rf"preview_(.+)_wk{w}\.png", p.name))}
        boxes = {m.group(1) for p in (wdir / "box_scores").glob(f"box_score_*_wk{w}.png")
                 if (m := re.fullmatch(rf"box_score_(.+)_wk{w}\.png", p.name))}
        rows = build_week_rows(w, schedule, store, records, previews, boxes)

        if placeholders and w == week:
            for r in rows[:PLACEHOLDER_GAMES]:
                r["has_preview"] = 1
                make_placeholder(UPLOAD / "dashboards" / f"week{w}_db" / "previews" / preview_name(r["contest_id"], w),
                                 PLACEHOLDER_SIZE["preview"], "GAME PREVIEW",
                                 f"{r['away']} at {r['home']} · {preview_name(r['contest_id'], w)}")
        if placeholders and w == played:
            for r in [r for r in rows if r["home_score"] != ""][:PLACEHOLDER_GAMES]:
                r["has_box_score"] = 1
                make_placeholder(UPLOAD / "dashboards" / f"week{w}_db" / "box_scores" / box_score_name(r["contest_id"], w),
                                 PLACEHOLDER_SIZE["box_score"], "BOX SCORE",
                                 f"{r['away']} at {r['home']} · {box_score_name(r['contest_id'], w)}")

        text = csv_text(rows)
        fname = f"games_{SEASON}_wk{w}.csv"
        old = PUBLISHED / fname
        changed = not old.exists() or old.read_text(encoding="utf-8") != text
        if w in (week, played) or changed:
            out = UPLOAD / "data" / fname
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
            published_files.append(out)
            if not placeholders:   # real images referenced by this CSV go up with it
                if w == week:
                    for cid in previews:
                        _copy(wdir / "previews" / preview_name(cid, w))
                else:
                    for cid in boxes:
                        _copy(wdir / "box_scores" / box_score_name(cid, w))

    # 3. Manifest the site reads ------------------------------------------
    manifest = {
        "season": SEASON,
        "week": week,
        "played_week": played,
        "games_weeks": games_weeks,
        "products": products,
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (UPLOAD / "data").mkdir(parents=True, exist_ok=True)
    (UPLOAD / "data" / "site_latest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    # Remember what was published (real runs only), so next week only changed
    # older game files are re-uploaded.
    if not placeholders:
        for f in published_files:
            shutil.copy2(f, PUBLISHED / f.name)

    files = [p for p in UPLOAD.rglob("*") if p.is_file()]
    print(f"\nUpload folder ready: {UPLOAD}  ({len(files)} files)")
    for p in sorted(files):
        print("   ", p.relative_to(UPLOAD).as_posix())
    if len(files) > GITHUB_MAX_FILES:
        print(f"\n  ! More than {GITHUB_MAX_FILES} files: github.com takes at most {GITHUB_MAX_FILES} per upload."
              " Drag the folders inside 'dashboards' in two batches.")
    print("\nNext: github.com -> flynsm/SFCS -> Add file -> Upload files ->"
          " drag the CONTENTS of the upload folder (the 'dashboards' and 'data' folders) -> Commit to main.")


def _copy(src: Path):
    dest = UPLOAD / src.relative_to(ROOT)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def export_logos():
    """One-time: team_brand.parquet logos -> assets/logos/<slug>.png for every FCS
    team and every opponent of an FCS team. Split into batches of <=100 files."""
    schedule = load_schedule()
    teams = sorted(set(schedule["home_team"]) | set(schedule["away_team"]))
    brand = pd.read_parquet(TEAM_BRAND).set_index("team")
    if LOGOS_UPLOAD.exists():
        shutil.rmtree(LOGOS_UPLOAD)
    written, missing, slugs = 0, [], {}
    batch_size = GITHUB_MAX_FILES - 5
    for team in teams:
        logo = brand["logo"].get(team) if team in brand.index else None
        if not isinstance(logo, str) or "base64," not in logo:
            missing.append(team)   # non-D1 opponents: the site shows initials
            continue
        slug = team_slug(team)
        if slug in slugs:
            sys.exit(f"Slug collision: {team!r} and {slugs[slug]!r} -> {slug}")
        slugs[slug] = team
        dest = LOGOS_UPLOAD / f"batch{written // batch_size + 1}" / "assets" / "logos" / f"{slug}.png"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(base64.b64decode(logo.split("base64,", 1)[1]))
        written += 1
    print(f"Wrote {written} logos to {LOGOS_UPLOAD} in {len(list(LOGOS_UPLOAD.glob('batch*')))} batch(es).")
    print(f"No logo (initials shown on site): {len(missing)} teams")
    print("Upload each batch separately: drag the 'assets' folder inside batchN onto Upload files.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--week", type=int, help="upcoming week (default: highest dashboards/week<N>_db)")
    ap.add_argument("--snapshot", action="store_true", help="only save current projections; no upload")
    ap.add_argument("--placeholders", action="store_true", help="test run with labeled placeholder images")
    ap.add_argument("--logos", action="store_true", help="one-time team logo export")
    a = ap.parse_args()

    if a.logos:
        export_logos()
    elif a.snapshot:
        store = update_projection_store()
        print(f"Saved projections: {len(store)} games in {PROJ_STORE}")
    else:
        export(a.week or detect_week(), a.placeholders)


if __name__ == "__main__":
    main()
