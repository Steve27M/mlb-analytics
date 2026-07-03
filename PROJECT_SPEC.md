# mlb-analytics — Polyglot MLB Analytics Pipeline — Build Spec

## Context

This is a port of a completed project (`cfb-analytics`) to Major League Baseball.
The prior project ingested college football data from the CFBD API into DuckDB,
transformed it with dbt (medallion -> Kimball star, incl. SCD2), implemented the
models from *Football Analytics with Python & R* in both R and Python with a
committed R<->Python parity gate, and rendered a Quarto dashboard to GitHub Pages.

This project applies the same architecture and discipline to MLB, grounded in the
direct baseball equivalent of that book: **Analyzing Baseball Data with R**
(Albert, Baumer & Marchi, 3rd ed., CRC Press). **The print book is NOT required.**
The authors publish the full third edition free online, plus companion data/code
and a long-running methods blog. These are the canonical references — when a
chapter-specific detail matters (RE construction, transition probabilities,
streak tests), consult the source rather than implementing from recall:

- Online edition: https://beanumber.github.io/abdwr3e/
- Companion data/code (`abdwr3edata`): https://github.com/beanumber/abdwr3edata
- Authors' blog: https://baseballwithr.wordpress.com

Baseball is better-served by open data than CFB, with one exception (betting
lines — see Phase 0).

**Strategy: local-first, then AWS.** Phases 0-5 run entirely on the local machine
(DuckDB + dbt + R + Python + Quarto). Phase 6 lifts the ELT to AWS free tier.
Nothing in Phases 0-5 may assume AWS; nothing may block the AWS lift (concretely:
bronze is date-partitioned Parquet from day one, stages are independent
subprocesses, all config via env vars).

**Stack:** Python (`uv`, `dbt-duckdb`, `statsmodels`, `scikit-learn`, `polars` or
`pandas`) · R (`baseballr`, `tidyverse`, `tidymodels`, `lme4`, `gt`) · DuckDB ·
dbt · Quarto. Orchestrated by a Python CLI (`run.py`) that runs each stage as a
subprocess; a non-zero exit aborts the run.

Work through the phases IN ORDER. Stop at every DECISION POINT and wait for my
answer. Gates must pass before the next phase begins.

---

## The polyglot contract (non-negotiable, carried over from cfb-analytics)

- R and Python NEVER share memory. No `rpy2`, no `reticulate`, ever — including
  in the dashboard render.
- The interface between languages is **files**: the DuckDB warehouse plus flat
  Parquet/CSV feeds. R reads/writes `data/results/` and reads `data/gold/`;
  Python owns ALL DuckDB and Parquet I/O and writes `data/gold/` feeds.
- Every stage is an independent subprocess with a clean exit code. Killing any
  stage must fail the pipeline cleanly.
- The dashboard honors the contract too: a Python pre-render step reads DuckDB
  and hands Quarto/knitr flat files.

## Directory layout

```
mlb-analytics/
  run.py                  # orchestrator CLI (stages below)
  pyproject.toml          # uv-managed
  renv.lock               # R env
  .env.example            # ODDS_API_KEY=..., no real values
  ingest/                 # Python: statsapi + Savant + Chadwick + odds pulls
  dbt/                    # dbt-duckdb project: staging/, snapshots/, silver/, gold/
  models_r/               # M1-M8 + game model, R
  models_py/              # parity fits, Python
  parity/                 # load_results + tolerance gate
  dashboard/              # Quarto project -> docs/
  data/
    bronze/               # date-partitioned Parquet, raw API shapes. GITIGNORED
    warehouse.duckdb      # GITIGNORED
    gold/                 # model feeds (Parquet). GITIGNORED
    results/              # model outputs, metrics JSON. Aggregates only; committed selectively
  docs/                   # rendered site (GitHub Pages)
```

`data/bronze`, `warehouse.duckdb`, and anything containing row-level MLB data are
gitignored and never published. Only aggregate results, metrics, charts, and code
are published, always with attribution.

## run.py stages

```
uv run python run.py ingest     # statsapi + Savant + Chadwick + odds -> data/bronze/  (throttled, cached)
uv run python run.py land       # bronze Parquet -> DuckDB bronze.* (typed on load)
uv run python run.py build      # dbt: staging -> snapshots (SCD2) -> silver -> gold (+ tests)
uv run python run.py export     # gold/silver -> data/gold/*.parquet model feeds
uv run python run.py models     # M1-M8 + game win-prob model, in R
uv run python run.py parity     # Python parity fits + market eval + load_results (parity GATE)
uv run python run.py dashboard  # Python pre-render -> Quarto render -> docs/
uv run python run.py backfill --season YYYY   # bounded historical pull for one season
```

---

## Phase 0 — Environment + data-source pre-flight

### 0.1 Toolchain check

Verify and report versions: `uv`, Python >= 3.11, R >= 4.3, `dbt-duckdb`, DuckDB,
Quarto, `renv`. If anything is missing, print the install command and stop.
Initialize the repo skeleton above, `.gitignore` (env files, keys, `data/` except
`.gitkeep` and committed aggregates, `__pycache__`, `.venv`, `renv/library`,
`.Rproj.user`, `.quarto`, `.DS_Store`), and `.env.example`.

### 0.2 Source pre-flight (write up as `PREFLIGHT.md`, one verdict per source)

For each source, document: what it provides, auth, rate/volume constraints,
redistribution terms, and a verdict (GO / GO-WITH-CONDITIONS / REJECT). Verify
current terms at build time — mark anything unverifiable `[CONFIRM]`.

1. **MLB Stats API** (`https://statsapi.mlb.com/api/v1`, live game feed at
   `/api/v1.1/game/{gamePk}/feed/live`). Free, no key. Schedules (`/schedule`),
   teams, people, boxscores, full play-by-play. Terms are personal,
   non-commercial with a required copyright notice — include the notice verbatim
   in README + dashboard footer. Expected verdict: GO-WITH-CONDITIONS
   (non-commercial portfolio use, attributed, raw data never redistributed).
2. **Statcast via Baseball Savant** (`/statcast_search/csv` endpoint; the
   `pybaseball` and `baseballr` clients wrap it). Pitch-level data: velo, spin,
   release point, exit velocity, launch angle, xwOBA, etc. ~700k+ pitches/season,
   90+ columns. Constraints to encode in the ingester: **30,000-row query cap**
   (chunk pulls by day), and **prior seasons receive retroactive corrections**
   (see freshness policy in Phase 1). Same redistribution posture as statsapi.
3. **Chadwick Bureau register** (github.com/chadwickbureau/register). The player
   ID crosswalk: MLBAM <-> Baseball-Reference <-> FanGraphs <-> Retrosheet.
   Open data. Verdict: GO. This is mandatory — pull it in Phase 0, it seeds
   `dim_player_xref` and prevents silent join loss later.
4. **Lahman database** (season-level aggregates, long history) and **Retrosheet**
   (historical play-by-play; requires their standard usage notice). Optional
   depth for M1 stability analysis. Verdict expected: GO with notices.
5. **Betting lines — DECISION POINT.** MLB has no CFBD-style bundled lines. The
   game model's market benchmark needs moneylines. Present me the tradeoff and
   wait:
   - **The Odds API** free tier (~500 credits/month): enough for a daily
     closing-line snapshot going forward, but no deep history on free tier.
     Budget credits the way CFBD calls were budgeted.
   - **Historical closing-lines dataset** (one-time acquisition) for backtest
     seasons; verify licensing before committing anything derived from it.
   - **Fallback:** ship the game model benchmarked against an Elo/home-field
     baseline only, add the market benchmark later. Honest but weaker.
6. **FanGraphs** — do NOT scrape or depend on it without an explicit ToS check
   presented to me first. Savant + statsapi should cover M1-M7 without it.

GATE: `PREFLIGHT.md` reviewed and the odds decision made before Phase 1.

---

## Phase 1 — Ingestion (Python -> bronze Parquet)

Scope: start with seasons **2023-2025** regular season + postseason; the current
season (2026) is pulled incrementally.

1. **Bronze format is date-partitioned Parquet**, not CSV
   (`data/bronze/statcast/game_date=YYYY-MM-DD/…`). Reasons: 2M+ rows x 90+
   columns across three seasons, and the layout must lift to S3/Athena unchanged.
2. **Politeness + idempotency:** throttled requests, descriptive User-Agent,
   exponential backoff on 429/5xx, and a local cache — a (season, date) already
   in bronze is never re-pulled, EXCEPT under the freshness policy:
3. **Freshness policy (Statcast retro-corrections):** store a pull manifest
   (date pulled, row count, checksum). A completed season gets ONE scheduled
   re-pull ~30 days after season end; mismatched checksums trigger a partition
   replace and a logged diff summary. Never silently mutate bronze.
4. **Type discipline on land:** all MLBAM IDs (`game_pk`, `batter`, `pitcher`,
   player IDs) are typed `BIGINT` at load. (cfb-analytics lesson: an upstream
   float-rounding of 18-digit IDs collapsed 531k plays to 266k keys. Do not let
   pandas infer ID columns — pass explicit dtypes.)
5. **Deterministic surrogate keys:** mint
   `pitch_key = hash(game_pk, at_bat_number, pitch_number)` after exact-duplicate
   removal; assert uniqueness and fail loudly if violated.
6. **Savant chunking:** pull day-by-day to stay under the 30k-row cap; verify
   returned row counts against the boxscore-derived expected pitch counts as a
   volume test.
7. Odds ingestion per the Phase 0 decision, with its own quota ledger logged per
   run.
8. Structured logging throughout (JSON lines: stage, source, date range, rows,
   duration, cache hit/miss, quota spent). This log format is reused verbatim in
   the AWS Lambda lift.

GATE: a full 2024-season bronze pull completes, re-running `ingest` is a no-op
(all cache hits), and volume tests pass.

---

## Phase 2 — Warehouse (dbt: medallion -> Kimball star)

Grain declarations first, in `dbt/models/*/schema.yml`, before any SQL:

- `fct_pitch` — one row per pitch (`pitch_key`).
- `fct_plate_appearance` — one row per PA.
- `fct_game` — one row per game (`game_pk`).
- `fct_team_game` — one row per team per game.

Dimensions:

- **`dim_player` — SCD2 via dbt snapshot, and the showcase.** Midseason trades
  give dozens of legitimate SCD2 transitions per season (vs. one realignment
  event in CFB). Replay the snapshot **date-by-date** (orchestrator loops
  transaction dates), not season-by-season, so trade-deadline moves land as
  correctly-bounded validity ranges. Seed identity from the Chadwick crosswalk
  (`dim_player_xref`).
- **`dim_team`** — mostly static; SCD2 anyway (Oakland -> Sacramento/Vegas era
  makes it non-trivial).
- **`dim_venue` — SCD2**: park dimension changes, humidor adoption. Feeds park
  factors.
- **Placeholder members** ("Unknown Player", "Unknown Venue") + `COALESCE` for
  any fact row that fails a dimension join — never drop fact rows silently, and
  test that placeholder usage stays under a threshold (< 0.5% of rows) so real
  join regressions surface.

Gold layer:

- **`gold_run_expectancy` — the RE24 matrix, built from our own play-by-play.**
  24 base-out states -> expected runs to inning end, computed per season. This is
  the EPA analog and, unlike the CFB project (where rebuilding EP was correctly
  rejected as duplicative), building it here is right: it is well-specified,
  validates against published matrices (assert within tolerance of a published
  reference season), and every downstream model consumes it.
- Rolling-form features ordered by **`(game_date, game_number)`** — the
  doubleheader tiebreaker. (cfb-analytics lesson: `week`-only ordering produced
  order-dependent features. Same trap, daily grain.) Feeds must be
  byte-identical across rebuilds; add a rebuild-determinism test that hashes a
  feed twice.
- Park-factor adjustments from `dim_venue` history.

dbt tests: uniqueness on every declared grain, not-null on keys, relationship
tests to dims, freshness on bronze, volume (row-count vs. manifest), and the
determinism test above.

GATE: `dbt build` green including snapshots and all tests; SCD2 spot-check shows
a known trade-deadline move (pick one from 2024) with correct validity dates.

---

## Phase 3 — Models (R first, Python parity, gated)

Every model consumes ONLY `data/gold/` feeds. Each is implemented in R
(`models_r/`) and Python (`models_py/`) on the identical feed; coefficients and
metrics land in `data/results/metrics.json`.

| # | Method (book grounding) | MLB application |
|---|---|---|
| M1 | EDA + metric stability | Which stats are skill vs noise: year-over-year correlation by stat (K% stabilizes fast; BABIP is mostly noise) |
| M2/M3 | Simple -> multiple linear regression | **xwOBA-over-expected**: launch speed + angle -> batted-ball value; residuals = hitter over/under-performance |
| M4 | Logistic GLM + odds ratios | **Called-strike probability** from pitch location -> catcher framing runs; report odds ratios |
| M5 | Poisson regression | Strikeout counts per start -> prop-bet framing (K totals) |
| M6 | PCA + clustering | **Pitcher arsenal archetypes** from pitch mix / velo / spin / movement |
| M7 | Multilevel / mixed-effects | **BABIP shrinkage** (batter random effects); report ICC — regression to the mean is baseball-native |
| M8 | Ethical web scrape | Draft position vs career production. Wikipedia ONLY (CC BY-SA, robots-respecting, team/round-level tables, descriptive UA, rate-limited, cached). Validate scraped values against an API-sourced sample. Present the source pre-flight to me before scraping anything. |

The M-track ports the football book's methods to baseball. The **B-track** covers
the canonical material of *Analyzing Baseball Data with R* itself (chapter refs
are to the free online 3rd edition above). Same rules apply: gold feeds only,
implemented in both R and Python, results into `metrics.json`.

| # | Method (book ch.) | Application |
|---|---|---|
| B1 | Runs and wins (ch. 4) | Pythagorean expectation: fit the exponent, estimate marginal runs-per-win; becomes a third baseline for the game model |
| B2 | Count effects (ch. 6) | Expected run value by count (chains RE24 down to pitch level); swing and pitch-selection tendencies by count |
| B3 | Career trajectories (ch. 8) | Aging curves: quadratic performance-vs-age fits over Lahman history; peak-age estimates |
| B4 | Simulation (ch. 9) | Markov-chain half-inning simulation from base-out transition probabilities (matrix MUST reconcile with `gold_run_expectancy`) + Bradley-Terry season and postseason simulation |
| B5 | Streaky performances (ch. 10) | Streak detection, moving averages, permutation tests for whether specific players are unusually streaky |

**Game model:** win probability from team efficiency features (RE24-derived
run-value rates, rolling form, park-adjusted, starting-pitcher features),
trained on 2023-2024, evaluated on a **sealed 2025 holdout** — the holdout is
exported once and never touched during development. Benchmarks: (a) home-field-
naive baseline, (b) the moneyline (per Phase 0 decision). Report Brier, AUC,
accuracy, calibration; leakage-safe time-aware CV only. The honest expected
result is approaching-but-not-beating the market — say so on the dashboard.

**Parity gate (`run.py parity`):** `load_results` FAILS the build on any
violation, across THREE tiers:

1. **Exact (tolerance):** deterministic fits (OLS, IRLS GLM, Poisson, logistic
   MLE, Bradley-Terry MLE, Pythagorean exponent) — coefficients must agree
   between R and Python within tolerance.
2. **Label-invariant:** PCA / clustering / mixed-effects — PC correlation,
   cluster ARI, BLUP correlation.
3. **Distributional (stochastic methods — B4, B5):** do NOT attempt
   cross-language seed matching; R's Mersenne Twister and numpy's PCG64 produce
   different streams even with identical seeds, so exact-match parity is
   impossible by construction. Instead: the deterministic INPUTS (transition
   matrices, observed streak statistics) must match exactly; simulated OUTPUT
   distributions must agree within Monte Carlo error (compare means/quantiles
   with CIs sized to the simulation count, or a KS test at a documented alpha).
   Size simulation counts so MC error is small relative to the tolerance.

Watch specifically for collinear feature definitions in the game model — R's
`glm` drops aliased terms silently while sklearn splits coefficients arbitrarily
(this exact bug was caught by the gate in cfb-analytics). Prefer explicitly
non-redundant features; add a rank check on the design matrix.

**Known-answer tests (KAT — required, per model):** every model must assert at
least one externally verifiable anchor before its gate passes. A plausible-but-
wrong implementation that runs clean is the primary failure mode to defend
against, and famous sabermetric results are the free test suite. Cite the source
in each test. Anchors:

- B1: fitted Pythagorean exponent ~1.83 (within tolerance); marginal
  runs-per-win ~9-10.
- RE24 (`gold_run_expectancy`): within tolerance of a published reference matrix
  (Tango run-expectancy tables / FanGraphs) for a matching season; implied run
  value of a HR ~1.4, single ~0.45-0.5.
- RE construction rule: EXCLUDE truncated innings (walk-offs, rain-shortened
  games) from "runs to end of inning," or the matrix biases low — add an
  explicit test that truncated innings are filtered.
- M2/M3: wOBA weights are season-specific — pull FanGraphs' published constants
  (Guts page) per season; never derive blind or hardcode one set across seasons.
- M4: framing-run magnitudes sanity-checked against published leaderboard ranges
  (elite framers roughly +10 to +20 runs/season).
- B3: aging curves peak roughly ages 26-29.
- B4: simulated league run environment within tolerance of the actual season's
  runs/game; Bradley-Terry simulated win totals centered on actual team wins.
- M1: K% year-over-year correlation materially exceeds BABIP's (stability
  ordering matches the literature).

GATE: all three parity tiers green, all KAT anchors pass, B4's transition matrix
reconciles with `gold_run_expectancy`, and sealed-holdout metrics beat both the
naive baseline and B1's Pythagorean-derived baseline.

---

## Phase 4 — Dashboard (Quarto -> GitHub Pages)

Python pre-render reads DuckDB + `data/results/` and writes flat files for
Quarto/knitr (contract preserved). Pages:

1. **Main dashboard:** data-quality panel (test results, freshness, volume),
   model-accuracy panel (Brier/AUC/calibration vs baselines and market, by
   week/month), parity status badge.
2. **Team comparison** (any two teams, current season).
3. **Stat guide** (plain-English glossary: wOBA, xwOBA, RE24, framing, ICC…).
4. **Models explainer:** how each of M1-M8, B1-B5 + the game model works, and
   how well — including where it loses to the market and why, and each model's
   KAT anchors with pass status.
5. **Season simulator:** B4's Bradley-Terry output as playoff-odds / projected-
   standings tables, refreshed with each pipeline run.

Attribution footer on every page (MLB/statsapi copyright notice, Chadwick,
Retrosheet notice if used, odds source). DECISION POINT: show me the rendered
site locally before enabling Pages.

---

## Phase 5 — Local hardening

- End-to-end run from empty `data/` on a clean clone using only README
  instructions (test this literally).
- README for the repo itself, modeled on cfb-analytics: status, model table,
  case-study section with the real engineering decisions and war stories from
  THIS build (do not recycle the CFB ones), quickstart, source terms section.
- Pre-commit: ruff + sqlfluff + a secrets scan (gitleaks if available). Nothing
  under `data/` bronze/warehouse ever staged.

GATE: clean-clone run passes; secrets scan clean.

---

## Phase 6 — AWS lift (free-tier, ELT only)

**Free-tier reality check first (this deliberately deviates from typical
Glue/Redshift/Kinesis reference architectures):** Glue jobs have no meaningful
free tier, Redshift is a 2-month trial, Kinesis/DMS bill from the first
shard/instance, QuickSight is a 30-day trial. At ~2M rows/season none of them
are warranted. The layers stay; the services change:

| Layer | Service | Free-tier basis |
|---|---|---|
| Raw/curated storage | S3 (bronze/silver/gold Parquet, same layout as local) | 5 GB, 12 months |
| Ingestion + transform | Lambda **container image** running the same Python ingesters and `dbt-duckdb` (DuckDB reads/writes S3 via `httpfs`) | 1M req + 400k GB-s, always free |
| Scheduling | EventBridge Scheduler (daily, in-season) | free |
| Orchestration | Step Functions: ingest -> land/build -> export, retries + catch -> SNS | 4k transitions/mo free |
| Serving | Athena external tables over gold Parquet (partition projection) | no free tier; cents/month at this scale with partition pruning |
| Alerting | SNS + CloudWatch alarms on Lambda errors/duration | free tier |
| Models + dashboard | **GitHub Actions** (scheduled): pull gold feeds from S3, run R models + parity + Quarto, publish to Pages | free for public repos |

Notes:
- Lambda must be a container image (R-free; Python+DuckDB+dbt exceeds the 250 MB
  zip limit comfortably but fits the 10 GB image limit). R and Quarto stay OUT
  of Lambda — they run in Actions. This split is deliberate: right tool per
  layer, and it keeps Lambda cold-starts and image size sane.
- The DuckDB "warehouse" in AWS mode is ephemeral-per-run: Lambda materializes
  from S3 Parquet, runs dbt, writes Parquet back. State lives in S3, not in a
  .duckdb file.
- Same code paths as local: stages read config from env vars; `run.py` locally
  and Step Functions in AWS invoke the identical stage entrypoints.
- IaC: Terraform (single small stack). DECISION POINT: confirm Terraform vs SAM
  before writing IaC.
- Budget guardrails: an AWS Budget alert at $5/month, and a `COST.md` that
  publishes the actual monthly bill — "runs for under $1/month" is part of the
  portfolio story.

GATE: one full scheduled cloud run (EventBridge -> Step Functions -> Lambda ->
S3 -> Actions -> Pages) completes green with zero manual steps, and the month's
bill is documented.

---

## Roadmap after v1 (do not build now)

CI on PRs (lint + `dbt build` against a fixture season) · preseason priors model
+ next-season forecast · live in-game win probability from the GUMBO feed
(streaming story) · BigQuery or Iceberg-on-S3 push of gold tables.

---

## Operating rules

- Stop at every DECISION POINT and wait. Do not pick for me.
- Gates must pass before the next phase. Report gate results explicitly.
- Never commit: secrets, `.env`, raw or row-level MLB data, the DuckDB file,
  odds data. Aggregates/metrics/charts only, with attribution.
- Respect every source: throttle, cache, identify, and honor ToS. If a ToS
  question arises mid-build, stop and present it.
- Prefer boring, verifiable choices; when you make a judgment call, log it in
  `DECISIONS.md` (date, decision, alternatives, rationale).
- Report what you did after each phase; never run phases silently back-to-back.
- If a tool is missing, print the install command and continue with a fallback
  where safe; otherwise stop.
