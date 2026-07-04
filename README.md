# mlb-analytics

**A polyglot MLB analytics pipeline that builds every statistical model twice — once in R,
once in Python — and refuses to ship unless the two languages agree.**

Statcast + statsapi → DuckDB (medallion → Kimball star, daily-grain SCD2) → **13 models in
R *and* Python behind an enforced parity gate** → a static DIAMONDIQ dashboard on GitHub Pages.
Built to be lifted to AWS free tier (Phase 6).

### 🔗 Live dashboard: **https://steve27m.github.io/mlb-analytics/**

> **Status:** Phases 0–5 complete. 2.18M pitches across 2023–2025, 27 warehouse tables,
> 50 dbt data tests, **13/13 models green on the parity gate** (exact / label-invariant /
> distributional tiers). Phase 6 (AWS ELT lift) is the remaining open work.

This is a portfolio build. The interesting part is not the numbers — it's the discipline that
makes them trustworthy: a warehouse that rebuilds byte-for-byte, a sealed holdout that is opened
exactly once, and a two-language parity gate that catches the bugs a single implementation hides.

---

## Headline results (all honest, all reproducible)

- **Skill vs. luck, quantified.** Strikeout rate repeats year-to-year at *r* = 0.82 and walk rate
  at 0.73 (real, stable skills); BABIP only 0.30 (mostly noise). So we trust the first two and
  statistically shrink the third (M1, M7).
- **Run expectancy rebuilt from scratch.** The RE24 matrix is derived from our own play-by-play and
  reproduces the canonical linear weights — HR ≈ +1.40 runs, single ≈ +0.47 — without copying
  anyone's published constants (B1, B2, RE24).
- **Can we predict a game?** The win-probability model, trained on 2023–24 and evaluated **once**
  on a sealed 2025, scores Brier **0.2470** — beating *both* a naive home-field baseline (0.2488)
  *and* a Bill-James-log5 Pythagorean baseline (0.2719). AUC ~0.55. A small, real edge: MLB games
  are close to coin-flips, and we say so.
- **The draft is a crapshoot.** Among drafted position players who reach the majors, draft slot
  explains ~1% of production (corr(pick, OPS) = −0.10). Data gathered by an *ethical* Wikipedia
  scrape, not a paid feed.
- **Season simulator.** 10,000 Monte-Carlo 2025 seasons driven by the model's leakage-safe game
  probabilities recover the actual standings order at *r* = 0.91 and put 10 of the 12 real playoff
  teams in the top 12 by odds — even though projected win totals correctly compress toward .500.

---

## The parity contract (the whole point)

R and Python **never share memory** — no `rpy2`, no `reticulate`. They communicate only through
files (DuckDB tables and flat Parquet feeds). Every model is implemented independently in both, and
`parity/load_results.py` fails the build unless they agree at one of three tiers:

| Tier | What must match | Why not exact |
| --- | --- | --- |
| **Exact** | Coefficients / correlations within 1e-5 | Deterministic fits should be identical |
| **Label-invariant** | PCA principal-component \|corr\|, cluster ARI, mixed-model BLUP corr | R and Python label clusters/components in different orders |
| **Distributional** | Deterministic inputs exact; simulated outputs within Monte-Carlo error | R's Mersenne-Twister and NumPy's PCG64 diverge even with identical seeds — matching seeds across languages is a known trap, so we never try |

If a single-language build is quietly wrong, the other language usually isn't wrong the *same* way.
The gate turns "looks plausible" into "two toolchains independently agree."

---

## The 13 models

| # | Model | Method | Parity tier | Anchor result |
| --- | --- | --- | --- | --- |
| **M1** | Metric stability | Year-over-year correlation | exact | K% 0.82, BB% 0.73 (skill) ≫ BABIP 0.30 (noise) |
| **M2/M3** | xwOBA-over-expected | Simple + multiple OLS | exact | Exit velo raises value; launch angle is concave (optimal window) |
| **M4** | Catcher framing | Logistic GLM on pitch location | exact | Best framer +32 runs, worst −21 (3 seasons) |
| **M5** | Strikeouts per start | Poisson regression | exact | League ~0.21 K per plate appearance |
| **M6** | Pitcher arsenals | PCA + k-means | label-invariant | R↔Py cluster ARI = 0.995 |
| **M7** | BABIP shrinkage | Mixed-effects (random intercepts) | label-invariant | ICC 0.27 — only ~27% of BABIP is persistent skill |
| **M8** | Draft vs. production | OLS (ethical Wikipedia scrape) | exact | corr(pick, OPS) = −0.10, R² 0.009 (n=104) |
| **B1** | Pythagorean wins | OLS through origin | exact | Exponent 1.73, ~11 runs per win |
| **B2** | Count effects | RE24 aggregation | exact | 3-0 a hitter's count, 0-2 the pitcher's |
| **B3** | Aging curves | Quadratic OLS | exact | OPS peaks near age 30 (survivor bias noted) |
| **B4** | Markov innings | Base-out transition simulation | distributional | Sim RE(empty,0) 0.503 reconciles RE24 0.508 |
| **B5** | Streaky hitters | Wald–Wolfowitz + permutation null | distributional | Mean streak z = −0.12 — indistinguishable from random |
| **GAME** | Win probability | Logistic, sealed 2025 holdout | exact | Brier 0.247 beats HFA (0.249) and Pythag (0.272) baselines |

Every model is anchored by a **known-answer test** (KAT) against a published baseball result — the
parity gate proves R and Python agree; the KAT proves they agree on something *true*.

---

## Case study — engineering war stories from *this* build

The bugs worth remembering, all logged in [`DECISIONS.md`](DECISIONS.md):

- **jsonlite silently truncated to 4 significant figures** and spuriously failed exact-tier parity
  (0.819705 → 0.8197 on disk, |Δ| = 5e-6 > tol) even though the math agreed. It was a
  *serialization* artifact, not a numeric one. Fix: `write_json(..., digits = 12)` in **every** R
  model.
- **The warehouse wasn't byte-deterministic** until run values were summed as scaled integers.
  DuckDB's parallel float summation is non-associative, so `SUM(run_value)` drifted by ~1e-15
  across rebuilds and `round()` couldn't save boundary flips. Summing micro-runs
  (`SUM(CAST(ROUND(run_value*1e6) AS BIGINT))`) makes the addition order-independent. A
  rebuild-and-hash gate guards it.
- **Suspended games share one `game_pk` across two dates** (24 cases): a game suspended on day *D*
  and finished on *D+1* appears under both, so a naive `GROUP BY game_pk` double-counts. Staging
  dedupes; the rolling-form window uses `game_pk` as a final tiebreaker to stay a *total* order
  (doubleheaders already break date-only ordering).
- **Spring training pollutes a date window** — and 2024's Seoul Series put regular-season games on
  the *same dates* as domestic spring games. The scope filter has to be `game_type`, not the
  calendar.
- **statsmodels MixedLM went singular** on the BABIP model (many one-observation groups drive the
  random-effect variance to zero); Nelder-Mead (gradient-free) converges where the analytic-gradient
  optimizers crash.
- **SCD2 without 540 dbt-snapshot runs.** The spec's literal "replay date-by-date" is ~540
  sequential snapshots. An analytical window-function build yields the *identical* daily-grain SCD2
  in one deterministic pass — validated on Jazz Chisholm's 2024-07-28 Marlins→Yankees boundary.
- **Staying free, ethically.** No paid odds feed (the game model benchmarks on home-field +
  Pythagorean instead); wOBA weights self-derived from our own RE24 rather than scraping FanGraphs
  (whose ToS forbids it); the draft data came from a rate-limited Wikipedia MediaWiki-API pull after
  247Sports/Rivals were rejected over terms-of-service and minor-PII concerns. Every source got a
  written pre-flight ([`PREFLIGHT.md`](PREFLIGHT.md)) before any code was written.
- **An honest negative result kept as-is:** the Pythagorean baseline is actually *worse* than the
  naive home-field baseline — a raw 10-game rolling Pythagorean is noisier at the single-game level
  than just predicting the base rate. The fitted model beats both; we report the wrinkle rather than
  hide it.

---

## Quickstart

**Prerequisites:** [`uv`](https://docs.astral.sh/uv/) (Python), R 4.6.1 with
[`renv`](https://rstudio.github.io/renv/), and ~3 GB free disk. No API keys required for the core
pipeline (odds ingestion is an optional no-op without `ODDS_API_KEY`).

```bash
# 1. Python + R environments
uv sync
Rscript scripts/install_r_packages.R          # or: R -e 'renv::restore()'

# 2. Point the warehouse at a local DuckDB file
export MLB_DUCKDB_PATH="data/warehouse.duckdb"   # Windows PowerShell: $env:MLB_DUCKDB_PATH=...

# 3. Run the pipeline, stage by stage (see `uv run python run.py --help`)
uv run python run.py ingest      # pull Statcast + statsapi to date-partitioned bronze Parquet
uv run python run.py land        # load bronze into DuckDB (all MLBAM ids typed BIGINT)
uv run python run.py build       # dbt: staging -> SCD2 -> silver -> gold (+ 50 tests)
uv run python run.py export      # write flat model feeds to data/gold/*.parquet
uv run python run.py models      # fit all 13 models in R
uv run python run.py parity      # fit all 13 in Python, then run the parity GATE
uv run python run.py dashboard   # build the static DIAMONDIQ site into docs/
uv run python run.py determinism # rebuild-and-hash gate: gold feeds are byte-identical
```

> **Note on `ingest`:** the first full 2023–2025 pull is a multi-hour, rate-limited crawl of public
> MLB endpoints (be a good API citizen — it throttles and backs off). It is idempotent: a re-run is
> all cache hits and re-pulls nothing. Everything downstream of `land` reruns in minutes.

The published dashboard lives in [`docs/`](docs/) and is served by GitHub Pages.

---

## Repo layout

```
ingest/       Python I/O layer — API pulls, land.py (->DuckDB), export_feeds.py (->Parquet)
dbt/          medallion -> Kimball star + SCD2; staging/silver/gold models, tests, RE24 anchors
models_r/     13 models in R      -.  independent implementations,
models_py/    13 models in Python -'  compared by...
parity/       load_results.py — the three-tier parity GATE, writes metrics.json
dashboard/    prepare_dashboard_data.py + season_sim.py + build_site.py -> docs/
reference/    static public reference data (team league/division map)
run.py        Typer CLI orchestrating every stage (exits non-zero on failure)
PROJECT_SPEC.md / PREFLIGHT.md / DECISIONS.md   plan, rules, source terms, decision log
```

---

## Data sources & terms

All sources were reviewed for license/terms **before** ingestion ([`PREFLIGHT.md`](PREFLIGHT.md)):

- **MLB Advanced Media** — statsapi & Baseball Savant (Statcast). Individual, non-commercial,
  non-bulk use. **Raw and row-level data are never redistributed.**
- **Chadwick Bureau** player register (player-id crosswalk) — ODC-By, attributed.
- **Wikipedia** MLB draft results (M8) — CC BY-SA, attributed, gathered via the MediaWiki API with
  rate limiting.

**Committed to this repo:** code, aggregate results, metrics, and the built dashboard only. **Never
committed:** secrets, `.env*` (except `.env.example`), `data/bronze/`, `data/gold/`, and
`warehouse.duckdb` — enforced by [`.gitignore`](.gitignore) and a pre-commit secrets scan. Clone the
repo and run the pipeline to regenerate the data yourself.

---

## Live pipeline (nightly)

The site is also a **living product**: a nightly GitHub Actions workflow refreshes the in-progress
2026 season while the 2023–2025 analysis stays frozen.

- **Orchestration decision — Dagster for the programming model, GitHub Actions cron as the trigger,
  no standing daemon.** A single nightly linear DAG doesn't justify a VPS/daemon; Actions cron is
  $0 and the Dagster asset graph (`pipeline/defs.py`) stays portable if the cadence ever grows.
  Both the Typer CLI and the Dagster assets are thin wrappers over one implementation
  (`pipeline/stages.py`), so they can't drift. The dbt tests and the R↔Python parity gate are
  **blocking asset checks** — a red gate stops the run before the site rebuilds.
- **Frozen / live split.** The 13 models + the sealed-2025 evaluation are frozen (build once,
  committed `metrics.json`); the nightly is **Python-only** (no R) — it rebuilds the frozen
  warehouse from cached bronze, builds a *separate* live 2026 warehouse, and updates only the
  simulator / betting / fan pages. A dbt `analysis_seasons` var keeps the frozen gold (including
  pooled RE24) reproducing exactly even with 2026 in bronze.
- **Cost & hygiene.** Bronze is cached between runs so ingest pulls only the daily delta (the first
  run is a one-time cold crawl — trigger it manually). No Git LFS; raw data and closing lines stay
  private; only aggregates + the built site are committed. Closing-line snapshots accrue forward
  (they can't be backfilled) into a retrospective model-vs-market record — no live picks.

## License

Code is provided for portfolio review. Baseball data belongs to its respective sources under the
terms above; this project neither claims nor redistributes it.
