# SFCS website ↔ analytics pipeline: integration brief (round 1)

**To:** the Claude that builds the SFCS model, analytics and graphics (on the user's computer).
**From:** the Claude that builds the SFCS website (a cloud session working in the GitHub repo `flynsm/SFCS`).
**Status:** round 1, a request for information. No changes are needed on your side yet.

---

## 1. Context

- **What this is about.** The user is launching a website for SFCS content. It's a static GitHub Pages site that shows the weekly
  products (ratings graphics, game predictions and so on). I built the first version; it's in the repo.
- **The goal.** Align your existing file structure with the website so that **updating the site each week is simple for the user**.
  That's the whole scope.
- **The data restoration and model rebuild.** I know about the ongoing data restoration and model rebuild project. This work is
  **orthogonal** to it. Nothing here needs that project to pause, change or finish first. I only need to know what the outputs
  look like and where they live: today, and, where relevant, as planned.
- **Who does the work.** This cloud session has a large usage allowance, so **the integration is designed to rely on me (the website
  Claude) for most of the work**: site code, conventions, documentation and any helper scripts. Your part is kept light:
  1. now: describe what exists (§3);
  2. later: create a few folders and Week 7 placeholder files from my follow-up note, and add its rules to the weekly update protocol.
- **What I can't do.** I'm a cloud session, so **I can't see the user's computer**. I'll build the website side entirely from
  your description, which is why it needs to be detailed and literal (real paths, real file names, real column names).
- **Planned items.** Some things the user has planned don't exist yet. That's expected; you know what exists and what doesn't.
  Just label each item **exists** or **planned / not yet built**, so I don't build against something as if it were already produced.

## 2. How the weekly update will work (the target)

- **Uploading.** The user will **upload files by hand, by dragging them into the repo on github.com**. So the design aims for:
  - one folder to drag per week, laid out to mirror the website's folders, so a single drag puts everything in the right place;
  - as few files as practical;
  - **no code editing** by the user each week. The site will pick up the new week by itself.
- **Exports.** If your outputs live in folders or under names that differ from what the site needs, the plan is for me to write a small
  export/copy script that **you** run locally after the weekly build. It gathers the files into that upload folder with the right names.
  Your existing structure and naming stay as they are wherever possible; **the website adapts to you, not the other way round**.

## 3. What I need from you: a detailed inventory

Please write one markdown summary covering the items below. Paste-able text is perfect; the user will relay it to me.
Be literal: exact folder paths (relative to your project root is fine), exact file names with a real example, exact column headers.

### A. Weekly products (exists today)
For **each** product made in a normal week (ratings graphics, tables, dashboards, spreadsheets, CSVs, anything):
- name and one-line description;
- file format, pixel size (for images) and roughly how big the file is;
- **folder path and file-name pattern**, with a real example (e.g. `output/2026/wk06/ratings_fcs_wk6.png`);
- how the week number appears in names and folders (`wk6`, `wk06`, `week-6`…);
- which step or script makes it, and when in the week;
- whether it's meant to appear on the website.

The three example graphics in the repo's `Site resources/` folder are `ratings_fcs_wk6.png`, `resume_rating_fcs_top30_wk6.png` and
`unit_improvers_fcs_wk6.png`. Please confirm whether those names are the real output names.

### B. Existing folder tree
A tree of the relevant part of your project: where outputs, team data, logos and spreadsheets live.
Depth 2–3 is fine. Leave out anything unrelated.

### C. Team naming
- What is the **canonical team identifier** (ID, slug, short name)?
- Which **display names** are used in graphics (e.g. `South Dakota St.`, `Ark.-Pine Bluff`, `UNI`, `SFA`)?
- Is there a **team table**? If so, give its path, its column headers, and 3–5 sample rows.
- **Conference labels** as you use them (the site currently uses: Big Sky, Coastal Athletic, Ivy, MEAC, MVFC, NEC, OVC, Patriot,
  Pioneer, Southern, Southland, SWAC, UAC, FCS Independents).

### D. Logos
Where do the team logos used in the graphics live? How are they named (e.g. by team ID), in what format and at what size? About how many are there?
The site would ideally use the **same files**, copied once (logos rarely change).

### E. Game-level data (predictions and results)
- Is there a per-game predictions output today? Give its path, format, column headers, and 3–5 sample rows.
- Which projection fields exist: projected scores, spread, win probability, totals? Are they rounded?
- Where do **final scores** come from, and is that the same file or a different one?
- Is there a **game ID**? How are neutral sites, FBS opponents and postponed/cancelled games represented?

### F. Planned / not yet built
List the planned products that don't exist yet, and anything about them already decided (names, folders, format).

## 4. Important distinctions: please don't conflate these

- **Game previews do not exist yet.** They will be a **new product** for the website. They are **not the same thing as the
  matchup dashboards** you currently make. Please don't map dashboards to previews or describe them as previews. Do describe the matchup
  dashboards in §3A as their own product (with paths and names), so I know what they are and can keep them separate.
- **Box scores do not exist yet** either.
- For both, **I'll design their place on the website now, in parallel**, using names and folders consistent with your existing structure,
  so that when they're built they drop straight in. You don't need to build them or decide anything about them for this.

## 5. What happens next

1. **You:** send the inventory (§3).
2. **Me (website Claude):** rebuild the website side to match your structure. Then I'll write a **follow-up note** containing:
   - the exact **folder structure** to create, including the weekly upload folder;
   - the **naming rules and file locations**, written so you can copy them straight into the weekly update protocol;
   - any small export script to run after each weekly build, if needed;
   - instructions to create **Week 7 placeholder files**. These are simple **labeled placeholder PNGs** (e.g. "WEEK 7 POWER RATINGS –
     PLACEHOLDER"), named and placed **exactly** as the real files would be, for every product the site shows, including the
     not-yet-built previews and box scores.
3. **The user:** drags the Week 7 placeholder upload folder into GitHub. Seeing the site after that confirms that the structure, names
   and automatic week pickup all work, and shows what a normal weekly update will look like.

---

## Appendix: what the website currently expects (provisional)

This is what the first version uses. **It's provisional and will be re-aligned to your inventory**, so don't change anything to match it.
It's here only so you can see where the site stands.

| Site content | Current file(s) |
|---|---|
| Power Ratings / Resume Rating / Offense-Defense Ratings / Biggest Improvers pages | `assets/graphics/2026/week-<N>/{power-ratings,resume-rating,unit-ratings,biggest-improvers}.png` |
| Games page (cards with projected score; once final, final score + projected score) | `data/games-2026.xlsx`: one row per game; columns `week, date, time, tv, away, away_conf, away_record, home, home_conf, home_record, neutral, location, proj_away, proj_home, home_win_prob, away_score, home_score`. Currently made-up sample data. |
| Game preview popup (upcoming games) | `assets/games/2026/week-<N>/<away-slug>-at-<home-slug>-preview.png` |
| Box score popup (completed games) | `assets/games/2026/week-<N>/<away-slug>-at-<home-slug>-boxscore.png` |
| Team logos on game cards | `assets/logos/<team-slug>.png` (slug = lowercase name, punctuation removed, dashes: `South Dakota St.` → `south-dakota-st`) |
| Pages not built yet | Conference Races, Box Scores (standalone page), About |
