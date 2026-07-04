# PREFLIGHT — data-source terms & verdicts

Standing practice: review each source's license/terms **before** writing ingestion code.
One verdict per source. Terms verified 2026-07-02; anything I could not confirm at build
time is marked `[CONFIRM]`.

**Global posture (applies to every source):** raw and row-level data is gitignored and
never published. Only aggregate results, metrics, charts, and code are committed — always
with the attribution footer below. Every outbound call uses a descriptive User-Agent,
throttling, exponential backoff on 429/5xx, and cache-first re-use.

## Summary

| # | Source | Provides | Auth | Verdict |
|---|--------|----------|------|---------|
| 1 | MLB Stats API | schedules, teams, people, boxscores, full play-by-play | none | **GO-WITH-CONDITIONS** |
| 2 | Statcast / Baseball Savant | pitch-level (velo, spin, release, EV, LA, xwOBA) | none | **GO-WITH-CONDITIONS** |
| 3 | Chadwick Bureau register | MLBAM↔BBRef↔FanGraphs↔Retrosheet player-id crosswalk | none | **GO** (mandatory) |
| 4 | Lahman database | season-level aggregates, long history | none | **GO** (attribution + share-alike) |
| 5 | Retrosheet | historical play-by-play | none | **GO** (required notice) |
| 6 | Betting lines | moneylines for the game-model market benchmark | key (The Odds API) | **RESOLVED — free tier, forward-only; baselines for v1** |
| 7 | FanGraphs | wOBA/"Guts" constants, published leaderboards | — | **REJECT for scraping; wOBA self-derived** |

---

## 1. MLB Stats API — GO-WITH-CONDITIONS

- **Endpoint:** `https://statsapi.mlb.com/api/v1` (+ live feed `…/api/v1.1/game/{gamePk}/feed/live`). No key, no registration.
- **Provides:** `/schedule`, teams, people, boxscores, full play-by-play.
- **Terms** (`gdx.mlb.com/components/copyright.txt`, verified verbatim):
  > "The accounts, descriptions, data and presentation in the referring page (the 'Materials') are proprietary content of MLB Advanced Media, L.P ('MLBAM'). Only individual, non-commercial, non-bulk use of the Materials is permitted and any other use of the Materials is prohibited without prior written authorization from MLBAM."
- **Constraints & how we honor them:** *non-commercial* → portfolio use only, no ads/sale. *non-bulk* → we cache and never redistribute raw data; only aggregates are published. Rate: throttle + backoff, descriptive User-Agent.
- **Attribution:** include the MLBAM notice verbatim in README + dashboard footer.

## 2. Statcast via Baseball Savant — GO-WITH-CONDITIONS

- **Access:** the `/statcast_search/csv` endpoint; we use the `pybaseball` client (MIT-licensed wrapper) which pulls from Savant. Savant is an MLBAM property → same proprietary, non-commercial, non-bulk posture as #1.
- **Provides:** pitch-level velo, spin, release point, exit velocity, launch angle, xwOBA, etc. (~700k+ pitches/season, 90+ columns).
- **Constraints encoded in the ingester:**
  - **~30,000-row query cap** → chunk pulls **day-by-day** (this is exactly why `pybaseball` itself paginates by date). `[CONFIRM]` the exact current cap at first run via the returned row counts; the day-grain chunking is safe regardless of the precise number.
  - **Retroactive corrections** on prior seasons → freshness policy (Phase 1): a completed season gets ONE scheduled re-pull ~30 days after season end; checksum mismatch triggers a partition replace + logged diff. Never silently mutate bronze.
  - **Volume test:** returned row counts checked against boxscore-derived expected pitch counts.

## 3. Chadwick Bureau register — GO (mandatory, pull in Phase 0)

- **Repo:** `github.com/chadwickbureau/register`.
- **License:** **Open Data Commons Attribution License (ODC-By 1.0)** — free use with attribution.
- **Role:** the player-id crosswalk (MLBAM ↔ Baseball-Reference ↔ FanGraphs ↔ Retrosheet). Seeds `dim_player_xref`; prevents silent join loss later. Attribute ODC-By in the footer.

## 4. Lahman database — GO (attribution + share-alike aware)

- **License:** **CC BY-SA 3.0.** Latest release (2025 season) published 2026-01-02.
- **Role:** optional depth for M1 stability, B3 aging curves (season-level history).
- **Conditions:** attribute Sean Lahman. Share-alike governs redistributed *derivative databases* — we do **not** republish the Lahman DB; we publish aggregates/charts/code and cite it. If we ever committed a transformed copy of the tables, that copy would need CC BY-SA. We won't.

## 5. Retrosheet — GO (required notice)

- **Role:** historical play-by-play; optional depth.
- **Required notice** (verbatim, verified `retrosheet.org/notice.txt`):
  > "The information used here was obtained free of charge from and is copyrighted by Retrosheet. Interested parties may contact Retrosheet at 'www.retrosheet.org'."
- Include verbatim in README + dashboard footer if Retrosheet data is used.

## 6. Betting lines — DECISION POINT (unresolved — needs your call)

MLB has no CFBD-style bundled lines. The game model's market benchmark needs moneylines.
**Verified constraint (The Odds API, 2026):** free tier = **500 credits/month**, reset on the
1st. A `/odds` call costs `markets × regions` credits. The **historical** endpoint costs **10×**
and is **paid-only** ($30/mo+). ⇒ **the free tier gives going-forward lines only.**

**Free sources for prior seasons surveyed** (SportsBookReviewsOnline, Princeton DSS, Kaggle,
sports-statistics.com): reliably cover seasons **through ~2023**; 2024 spotty, **2025 not
available for free**; licensing on the scraped-sportsbook archives is unstated → not clean to
derive from. **MLB.com is not an option:** `statsapi.mlb.com` has no odds (stats only);
odds on mlb.com are sportsbook-partner widgets served from `/api/` paths that `robots.txt`
disallows, and harvesting them is "bulk use" the MLBAM terms forbid. So there is **no fair,
free source for the 2025 holdout.**

**RESOLVED (2026-07-02) — stay free (Option A + free forward accrual):**
- **v1 game model** is benchmarked on **Elo + home-field + B1 Pythagorean** baselines. No paid
  data, no `ODDS_API_KEY` required. This unblocks the whole build at $0.
- **Free forward accrual:** the odds ingester targets **The Odds API free tier** (sanctioned,
  ToS-clean) and banks **2026 closing moneylines going forward** for a *live* market benchmark.
  The stage **no-ops when `ODDS_API_KEY` is unset**, so it costs nothing and blocks nothing;
  drop a free key in `.env` to start collecting.
- **Sealed 2025 holdout** stays benchmarked on the baselines only, honestly labeled on the
  dashboard ("market benchmark: live 2026 games; 2025 holdout vs Elo/HFA/Pythagorean").
- Paid historical ($30 one-month backfill of 2023–2025) remains a documented v2 option; not
  taken now.

## 7. FanGraphs — REJECT for scraping (ToS), with a wOBA-constants question

- **ToS (verified):** §17 — "You agree not to access the Service by any means other than
  through the interface that is provided by Fangraphs." §11 prohibits commercial
  reproduction/resale. ⇒ **no automated scraping or crawling of FanGraphs.**
- **Why it matters:** the M2/M3 and RE24 known-answer tests reference season-specific
  **wOBA weights** (FanGraphs' "Guts" page) and published run-expectancy matrices. We must
  not scrape them. (Savant + statsapi cover M1–M7 feature-wise without FanGraphs.)
- **RESOLVED (2026-07-02):** **self-derive** the wOBA linear weights from our own
  play-by-play via the run-expectancy method — the RE24 matrix we build in gold yields the
  weights directly. FanGraphs is used for **nothing**. The RE24 known-answer test anchors
  against **published Tango run-expectancy tables** (a public reference), not FanGraphs. No
  FanGraphs dependency, no ToS exposure, and it's a stronger methodological showcase.

---

## 8. Wikipedia (M8 draft) — GO-WITH-CONDITIONS (approved 2026-07-03)

- **Source:** English Wikipedia per-year `20XX Major League Baseball draft` pages (first-round
  tables: overall pick + player).
- **Method:** the **MediaWiki API** (`/w/api.php?action=parse`), NOT raw HTML scraping — the
  Wikimedia Foundation explicitly prefers the API and `robots.txt` disallows `/w/` for crawlers
  (the API has its own usage policy). Descriptive User-Agent, <=1 req/sec, results cached to
  bronze so pages are fetched once.
- **License:** CC BY-SA. We publish only aggregates (draft-position-vs-production summary +
  chart), never Wikipedia prose -> attribute "Wikipedia (CC BY-SA)" in README + dashboard footer.
- **Validation:** scraped picks cross-checked against known #1 picks (Harper 2010, Cole 2011, ...)
  before use; player names matched to MLBAM ids via the Chadwick crosswalk.
- **Scope caveat:** warehouse is 2023-2025 only, so "career production" = *current* (2023-25) MLB
  production for drafted players still active. Full-career would need Lahman (not ingested).
  Labeled as such on the dashboard.
- **Verdict:** GO-WITH-CONDITIONS. Approved by SM 2026-07-03.

## Attribution footer (goes in README + every dashboard page)

> Data: MLB Advanced Media (statsapi.mlb.com, Baseball Savant) — used under the MLBAM terms,
> individual non-commercial non-bulk use; raw data not redistributed. Player-id crosswalk:
> Chadwick Bureau register (ODC-By 1.0). [If used:] Season history: Lahman Baseball Database
> (CC BY-SA 3.0). Play-by-play: "The information used here was obtained free of charge from
> and is copyrighted by Retrosheet. Interested parties may contact Retrosheet at
> 'www.retrosheet.org'." [If used:] Odds: <source per Phase 0 decision>.

## GATE — CLEARED (2026-07-02)

(a) Preflight reviewed. (b) Betting-lines source chosen: stay free — baselines for v1, free
forward accrual via The Odds API free tier (no-ops without a key). (c) wOBA self-derived; no
FanGraphs. Phase 1 (ingestion) may begin.

## 9. The Odds API — betting moneylines (approved 2026-07-04)

Source: https://the-odds-api.com (v4 REST API). Auth: free API key (email signup); stored in the
gitignored `.env` locally and as a GitHub Actions secret `ODDS_API_KEY` for the nightly pipeline —
never committed. Verdict: **APPROVED** for banking 2026 pre-game moneyline (h2h) snapshots forward.

- **Can:** use the free tier (500 credits/month; one MLB moneyline snapshot ≈ 1 credit, ~30/month
  in-season — well within quota); display derived odds comparisons on the site (the T&C explicitly
  permit user-facing display, "including commercial use, provided our data is not the primary
  product being sold or redistributed"); store our own daily snapshots.
- **Cannot / should-not:** resell, repackage, or redistribute the odds "as a standalone data
  product … through your own API, data feed, downloadable files, or any other format intended to
  serve as a source of raw data for others." Historical/closing snapshots are paid-only — we do NOT
  use them; we bank our own live pre-game snapshot each day (closing lines cannot be backfilled).
- **Binding storage rule (matches the repo's global posture):** raw per-game/per-book moneylines
  are gitignored (private, like `data/bronze/`); ONLY the derived aggregate (model-vs-market
  calibration / ROI summary) is committed, with attribution to The Odds API. This satisfies both
  their no-redistribution clause and our "aggregates and code only" policy.
- **Good-citizen:** descriptive UA, throttle + backoff, one small non-bulk pull/day; descriptive
  analytics only (the betting page carries a "no betting advice" disclaimer); no PII.
- Terms reviewed at https://the-odds-api.com/terms-and-conditions.html on 2026-07-04.

## 10. POST-FLIGHT — legal & ethical compliance review (reviewed as of 2026-07-04)

Per FEEDBACK2 §8, a full compliance review run after the Phase-3 changes. Rendered as a
"compliance reviewed 2026-07-04" line in the site footer of every page (links here).

- **Data sources — re-verified against actual usage.**
  - *MLBAM (statsapi / Baseball Savant):* nightly INCREMENTAL pulls (idempotent, throttled, backoff,
    descriptive UA); 2023-2025 cache-hit, only the 2026 delta fetched. Individual, non-commercial,
    non-bulk. **No raw/row-level redistribution** — bronze/warehouse are gitignored; only aggregates
    + code committed. COMPLIANT (§1-2).
  - *MLB GUMBO live feed* (`statsapi.mlb.com/api/v1.1/game/{pk}/feed/live`, now live on live.html):
    SAME MLBAM host and terms as statsapi (§1) — no separate pre-flight needed. Both required live
    guards are **VERIFIED in the built page (2026-07-04):** client polling throttled to `POLL=18000`
    (18s, inside the 15-20s band) with backoff to 20s on error / `If-None-Match` conditional GETs, and
    the client-fan-out rate-limit exposure is documented with a revisit trigger (ARCHITECTURE.md ADR-4,
    referenced on the page). Win probability is derived client-side from the public feed; displays
    professional on-field data only; zero raster images. COMPLIANT — forward requirement CLEARED.
  - *The Odds API:* only DERIVED aggregates published (model-vs-market comparison); raw per-book
    moneylines stay private/gitignored; not resold/redistributed as a standalone data product; key
    is a repo secret, never committed. COMPLIANT (§9). Attributed in the footer.
- **IP.** No club logos/marks anywhere — the published site has ZERO raster images and no logo files;
  team identity is colors + typographic monograms only (teams.js, 30 entries, 0 external URLs).
  Wordmarks (team names) used referentially. Footer disclaimer on all 8 content pages. COMPLIANT.
- **Gambling-adjacent content.** betting.html is DESCRIPTIVE analytics only — no staking, sizing, or
  bankroll advice; no jurisdiction-specific claims. A responsible-gambling line (1-800-GAMBLER,
  ncpgambling.org) is present. live.html now carries the same guard **(VERIFIED):** its win-probability
  card reads "Descriptive analytics, not a betting pick" and surfaces 1-800-GAMBLER. COMPLIANT —
  live.html follow-through CLEARED.
- **Citation integrity.** Funder & Ozer (2019) cited with the full reference on data-science.html and
  short-cited on betting.html, with a working DOI. Their argument is represented FAITHFULLY, including
  where it pushes AGAINST this project's original framing — the M8 write-up was rewritten to drop the
  "explains ~1% of variance" (r^2) claim the paper argues against, replaced with r translated to odds
  + a bootstrap CI + a range-restriction disclosure. No paraphrase drifts into misattribution.
- **Privacy.** Draft dataset is public-record professional data (Wikipedia, CC BY-SA); 247Sports /
  Rivals were rejected earlier over ToS + minor-PII. No minor-PII entered via any Phase-3 source; the
  live feed shows professional on-field data only. COMPLIANT.
- **Ops honesty (observability layer now shipped).** ops.html / SPC / the incident log are built and
  **VERIFIED (2026-07-04):**
  - *Incident log is REAL, not curated green* — the three entries (`docs/data/incidents.json`) are
    genuine bugs this build hit and fixed: pull_people overwriting the frozen roster (B3 aging broke),
    the Wikipedia 429 that aborted the draft pull, and the clobbered `run_results.json` test tally. No
    invented "all green" incidents.
  - *SPC canaries are aggregate-only* — the recorded series are league-mean fastball velocity, pitches
    per game, whole-warehouse row count, and pipeline wall-times (`docs/data/runs.json`). All are
    process/aggregate metrics; **no row-level or per-player data** is written to the committed ops JSON.
  - *SPC warns, never blocks* — control-chart violations render amber; the dbt tests + parity gate
    remain the only blocking gates. Honest "collecting baseline (1/15 runs)" shown until limits accrue.
    The DLQ surfaces depth/quarantine/MTTR truthfully (0/0 at first run). COMPLIANT — forward
    requirement CLEARED.

**Verdict:** COMPLIANT as of 2026-07-04. Both forward requirements from the prior review are now
CLEARED against the built pages: (1) live.html — polling throttled to 18s + client fan-out guard
documented (ADR-4) + "not a betting pick"/1-800-GAMBLER; (2) ops.html — honest (non-curated) incident
log + aggregate-only SPC canaries + non-blocking SPC. No open compliance items across the Phase-3
scope (live win-prob, ops/SPC, DLQ, effect-size honesty, The Odds API, IP, privacy). Re-review on any
new data source or before any commercial use.
