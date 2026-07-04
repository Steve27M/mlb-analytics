# Engineering decisions log

Non-trivial judgment calls (date, decision, alternatives, rationale), per the operating
rules in `PROJECT_SPEC.md`. Newest first.

## 2026-07-04 — Live-2026 foundation: frozen/live season split (design A)

Ingested the current 2026 season; keeping the validated retrospective analysis FROZEN on complete
seasons (2023-2025) while 2026 becomes an additive live layer (sim/betting only). Per FEEDBACK
§10.4 (sealed 2025 holdout stays frozen; never retrain into it).
- **dbt `analysis_seasons` var (default [2023,2024,2025])** filters the three staging entry points
  (schedule, boxscore, statcast). Scopes ALL gold — including the POOLED tables (RE24, transitions)
  that can't be filtered at export — so the frozen analysis reproduces EXACTLY with 2026 in bronze.
  Verified: RE24(empty,0) 0.5084, 560715 PAs, and all 9 headline metrics + the 13-model parity gate
  reproduce to the committed values. The `accepted_values` season test became `accepted_range(>=2023)`.
- **BUG found + fixed — `pull_people` overwrote the frozen people set.** It pulled only the current
  MLB_SEASONS roster and overwrote the single people partition, so the 2026 pull DROPPED players who
  retired by 2026 → their birth years vanished → B3 aging peak jumped 30.0 -> 51.5 (KAT fail). Fixed
  to be CUMULATIVE (union with the existing partition; birth years are stable so a union never
  changes a value). Re-pulled 2023-2025 -> people back to 2235 players -> B3 peak restored to
  exactly 30.0026.
- **`n_pitches` scoped to gold's seasons** (was `count(*) from bronze.statcast`, which now includes
  2026 -> inflated the footer on every page). Now counts only frozen-season pitches (2.18M).
- **B4 Markov sim made byte-reproducible** (sort pa_transitions on from/to/runs before the
  fixed-seed RNG, both R + Python) — same latent row-order non-determinism as the season sim. The
  displayed sim RE was drifting within MC error across rebuilds (0.497 vs 0.486); now stable at 0.486.
- Net: frozen retrospective rebuilds byte-identical; 2026 sits in bronze ready for the live layer.

## 2026-07-04 — Site restructure (FEEDBACK.md): reviewer decisions + Python-only data layer

Implementing the audience-oriented site restructure (fan / data-eng / data-science / betting +
compare/simulator/glossary), driven by `FEEDBACK.md`. Reviewer-approved decisions:
- **Deploy: Dagster-on-GitHub-Actions now, AWS later.** The §10 Dagster+Actions (no daemon, $0)
  approach supersedes the PROJECT_SPEC Phase-6 AWS Lambda/Step Functions plan as the near-term
  target; AWS is a later lift the same deployment-agnostic Dagster assets can move to.
- **Odds capture: yes, PENDING a terms pre-flight.** Activate the existing `ODDS_API_KEY` hook to
  bank 2026 closing lines (can't be backfilled) — but only after a PREFLIGHT.md verdict on The Odds
  API (free tier, ToS, ethics/legal) is presented and approved, per the standing pre-flight rule.
  Needs a user-provided free API key. Deferred into the Phase-2 nightly pipeline work.
- **`run.py` stage refactor into importable functions (shared by Typer + Dagster): DEFERRED** to
  the Phase-2 pipeline build.
- **Theming: one dark system, distinct per-audience motifs/accents/layout. No light page** (a lone
  light page in a dark site reads as broken; "lighter panels" = a lighter dark shade).
- **New site data is a Python-only prep-layer rollup, NOT re-gated** (same precedent as the season
  simulator — no new statistical estimation, just aggregation of the already-parity-gated
  warehouse/models). Added to `prepare_dashboard_data.py`: calibration (game-model reliability, 5
  EQUAL-COUNT quantile buckets with n — predictions cluster near .50 so equal-width would be empty
  at the tails; the honest reliability curve is a short near-diagonal segment ~.46-.59), YoY skill
  stability per stat (K% .82 / BB% .73 / OPS .51 / BABIP .30), Pythagorean luck (W - pythW) per
  team-season, head-to-head season series, and data-mined fun facts.
- **Pythagorean exponent unified to B1's FITTED value (1.733)** site-wide (was a hardcoded 1.83) —
  on-brand ("derived from our own data") and consistent between the luck/pyth figures.
- **Provenance strip is data-derived** ("through <max game_date>", seed 777), NOT wall-clock, so
  `docs/` rebuilds stay byte-identical (§11 zero-diff). Wall-clock build time waits for the
  Phase-2 `runs.json` (§10.4).

## 2026-07-04 — Phase 5 clean-clone GATE stamped (from-empty re-ingest; 2 bugs found)

- **Ran the literal clean-clone end-to-end into an ISOLATED env** (all `MLB_*` roots pointed at a
  scratch dir, real `data/` untouched) — a faithful fresh-clone test that also proves the Phase-6
  env-var portability claim. Full from-empty pull of 2023-2025 (statcast 624 partitions / 2.18M
  pitches, statsapi 625/624, draft 12, people 1), then land -> build (PASS=77) -> export (14 feeds)
  -> models (R) -> parity (13/13 GATE green) -> dashboard. **Every headline metric reproduces the
  committed numbers EXACTLY to 6 dp** (game Brier 0.246954, M1 0.819705, B1 1.733103, M8 -0.095828,
  M6 ARI 0.9952, ...). Completed seasons are frozen, so no source drift; the pipeline is fully
  reproducible.
- **The clean-clone surfaced two real bugs (both fixed + committed):** (1) `run.py ingest` never
  called `pull_people`/`pull_draft` though `land.py` loads them — a fresh clone would die at land
  (B3 aging + M8 draft starved). (2) The draft pull hit a Wikipedia 429 (12 pages back-to-back) and
  aborted because `get_json` ignored the server `Retry-After`; now it honors it (cap 60s) and draft
  throttles at 2s. This is exactly what the gate exists to catch.
- **Season simulator made env-deterministic** by sorting game rows on `game_pk` before the
  fixed-seed RNG draws. Previously the sim zipped RNG to whatever order DuckDB/parquet returned, so
  it drifted within MC noise across environments (0.902 vs 0.908). Now identical everywhere: r=0.906
  (rounds to 0.91), 10/12 playoff teams. Aggregate model metrics were never affected (order-
  invariant). README/DECISIONS updated 0.90 -> 0.91.
- Background ingest jobs get killed at a ~1-2h ceiling; the pull's per-(source,date) idempotency
  makes resume a fast cache-hit rescan, so the full crawl completes across a few relaunches.

## 2026-07-03 — Phase 5 local hardening (README, pre-commit, lint gates)

- **Full README written from THIS build's real results and war stories** (not recycled from
  cfb-analytics): headline results, the parity-contract table, the 13-model table with anchor
  results, an engineering case-study section (jsonlite 4-sig-fig truncation, integer micro-run
  determinism, suspended-game game_pk collisions, Seoul-Series game_type filter, MixedLM
  Nelder-Mead, analytical SCD2, the ethical/free data stance, and the honest Pythagorean-baseline
  wrinkle), quickstart, repo layout, and source terms.
- **Pre-commit: ruff + sqlfluff + gitleaks + hard data-artifact block.** `ruff` (check --fix) only
  — NOT `ruff-format`: the repo's established standard is the linter (passes clean repo-wide), and
  `ruff format` would reformat 27 files for zero functional gain and disrupt intentional
  alignment. Dropped the whitespace/eof hooks too — they would fight the generated `docs/` HTML.
  A local `no-data-artifacts` hook blocks staging anything under `data/bronze|gold`, `*.duckdb`.
  gitleaks + `detect-private-key` cover secrets; a manual pattern scan is clean and `.env.example`
  holds no real values.
- **sqlfluff configured as a templating-validity + parse + capitalization gate, not a style
  enforcer.** Uses the dbt templater (added `sqlfluff-templater-dbt`) with the duckdb dialect;
  excluded the layout/aliasing rules (LT01/LT02/LT08/AL01/AM05/ST09…) that fight this repo's
  intentional house style, plus ST03/AL10 which false-positive on correct SCD2 SQL. Net: 0
  violations across all models, while still catching broken `ref()`s, syntax errors, and casing.
- **Rewrote `dim_player`'s change-detection `is distinct from` as `coalesce(lag = team, false)`**
  purely because sqlfluff's duckdb dialect can't PARSE `is distinct from` inside a windowed CASE
  (inline noqa doesn't work — dbt templating shifts line numbers). Provably equivalent here
  (team_id is never null); GATE re-verified byte-identical: 3361 spans, 822 multi-span players,
  Jazz Chisholm's Marlins->Yankees boundary still exactly 2024-07-28. Logic unchanged, linter happy.
- **Clean-clone GATE — partial, stated honestly.** Secrets scan clean; the full downstream
  (land->build->export->models->parity->dashboard) is reproducible and byte-deterministic
  (determinism GATE green, hash 0be2591269e4); `run.py --help` is coherent and the README
  quickstart matches the actual stage commands. NOT executed: a literal from-empty re-ingest of
  2023-2025 (a multi-hour, rate-limited public-API crawl) — the one piece of the clean-clone test
  left for the human to stamp if desired. Everything else that a fresh clone needs is verified.

## 2026-07-03 — Phase 4b: game-model Pythagorean baseline (GATE closed) + season simulator

- **Game model now beats BOTH baselines on the sealed 2025 holdout — the spec GATE is closed.**
  Added a B1-Pythagorean (log5) baseline: each team's strength = its leakage-safe rolling
  Pythagorean win expectation (from `gold_team_form` rolling RS/RA, now surfaced in
  `gold_game_features`), combined via Bill James log5, plus a fixed train-derived home-field
  log-odds bump. The exponent is fit on TRAIN team-seasons ONLY (2023-24, same origin log-log fit
  as B1) so the sealed holdout is never touched. Result: model Brier **0.2470** < HFA baseline
  **0.2488** < Pythag baseline **0.2719**. Honest wrinkle worth noting: the Pythagorean baseline
  is *worse* than the naive HFA baseline — a raw 10-game rolling Pythagorean + log5 is noisier at
  the single-game level than just predicting the base rate; the fitted logistic model (small
  coefficients, stays near the base rate) beats both. R and Python agree exactly (parity EXACT
  tier); new KAT `brier < brier_pyth_baseline` enforces it.
- **Season simulator (`dashboard/season_sim.py`) is a Monte-Carlo ROLLUP, not a new model —
  Python-only by design.** It refits the same 3-feature game model on 2023-24, scores every 2025
  game with its leakage-safe P(home win), and simulates the real schedule 10,000x (fixed seed 777)
  to get projected-win distributions + playoff odds (3 division winners + 3 wildcards per league;
  ties broken by team_id — a documented simplification). No new parameter estimation happens here
  (the logistic fit is already parity-gated), and the project rules forbid cross-language RNG seed
  matching, so a one-language simulator is consistent with the rules — logged rather than parity-
  gated. Needs league/division structure absent from `dim_team`; added a static public reference
  `reference/team_divisions.csv` (30 teams). Honest result: projected wins compress toward .500
  (weak game model, AUC ~0.55 — games are near coin-flips), yet the ORDERING recovers actual
  standings at **r=0.91** and the 12 highest-odds teams include **10 of 12** actual playoff teams.
  (Sim later made env-deterministic by sorting on game_pk; see 2026-07-04 Phase 5 clean-clone entry.)
  Surfaced as a 5th dashboard page with that compression caveat stated plainly.

## 2026-07-03 — Phase 4 dashboard: static HTML pages, not Quarto

- **Built the DIAMONDIQ site as four self-contained static HTML pages
  (`dashboard/build_site.py` -> `docs/`), not a Quarto render.** The spec names
  Quarto, but the cfb-analytics dashboard the human asked to mirror is a
  hand-built multi-page site (Compare / Stat Guide / The Models / Dashboard),
  and Quarto adds a heavyweight toolchain dependency for what is ultimately
  templated HTML+JS reading one JSON. Polyglot contract preserved: Python
  (`prepare_dashboard_data.py`) owns all DuckDB I/O and writes
  `data/dashboard/site_data.json`; the pages are pure HTML/JS with no R and no
  DuckDB dependency. `run.py dashboard` = prepare -> build (Quarto path
  removed). Pages carry live model data (parity badges, headline metrics from
  `metrics.json`) and glossary distributions with named leaders/trailers.
  Rendering NOT yet visually verified — the Chrome extension is disconnected
  this session, so screenshot verification is pending; structural validation
  (embedded JSON parses, 13/13 models, 90 team-seasons, 5 glossary groups) is
  green. Quarto "season simulator" (B4 playoff odds) page = not yet built.

## 2026-07-03 — Phase 3 COMPLETE (13 models, all parity tiers green)

- **All 13 models done in R + Python with parity + KATs:** M1-M8, B1-B5, game model. Full
  `dbt build` green (77 tests); parity gate green (13 models). M8 built via the APPROVED ethical
  Wikipedia MediaWiki-API pull (2,658 draft picks, validated vs known #1 picks; 104 matched to
  current production). Honest results throughout: M8 corr(pick, OPS) = -0.10 (draft is a
  crapshoot once you reach MLB), R2 = 0.009.
- **Game-model baseline gap (documented refinement):** the model beats the naive home-field
  baseline on the sealed 2025 holdout (Brier 0.2470 < 0.2488) — the primary GATE. The spec also
  asks it to beat a B1-Pythagorean-derived baseline; that comparison is NOT yet built. Adding a
  log5/Pythagorean game baseline (from teams' rolling run rates) is a clean follow-on; report the
  result honestly whether or not the simple 3-feature model beats it.

## 2026-07-03 — Phase 3 game model + parity harness (10 models, all 3 tiers)

- **Game model — honest sealed-holdout result.** Logistic home-win model on home-minus-away
  leakage-safe rolling form (gold_team_form), trained 2023-2024, evaluated ONCE on 2025.
  Brier 0.2470 vs HFA-baseline 0.2488 (beats it), AUC 0.549, well-calibrated (0.524 vs 0.538).
  A small real edge, not domination — the spec's expected honest story (MLB games are near
  coin-flips). No market benchmark (staying free); baseline is HFA + the B1 Pythagorean context.
  Say this plainly on the dashboard.
- **Parity harness proven across all three tiers:** EXACT (M1/M2/M4/M5/B1/B2/game — coeffs to
  1e-5), LABEL-INVARIANT (M6 PC |corr|+ARI, M7 BLUP corr+ICC), DISTRIBUTIONAL (B5 — observed
  stats exact, permutation null within 5 MC-SE, NO cross-language seed matching). 10 models green.
- **statsmodels MixedLM (M7) needs Nelder-Mead**, not lbfgs: the analytic-gradient optimizers
  invert the RE covariance and crash (singular) when many 1-obs groups drive group var -> 0.
- **B3 aging needs player birthdates** — adding birth_year to the Chadwick pull (reusable).

## 2026-07-03 — Phase 3 parity gate (M1) + jsonlite precision gotcha

- **Every R model's `write_json` MUST set `digits = 12`.** jsonlite defaults to **4 significant
  digits**, which truncated M1's `k_pct_yoy_corr` 0.819705 → 0.8197 on disk and spuriously
  failed EXACT-tier parity against Python (|Δ|=5e-6 > 1e-6 tol) even though the computations
  agreed. This is a *serialization* artifact, not a numeric one. Applies to M2–M8, B1–B5, the
  game model — bake `digits = 12` into every `write_json`/`toJSON`.
- **Parity-gate result contract:** each model writes `data/results/<model>__r.json` and
  `__py.json`; `parity/load_results.py` compares them per tolerance tier + checks KATs + merges
  into `metrics.json`, non-zero exit on any violation. M1 validated: EXACT parity passes and the
  KAT holds — K% YoY corr 0.820, BB% 0.729 (skill) >> BABIP 0.298 (noise), the canonical result.
- Keep console output ASCII (no `Δ`/`…`): the Windows cp1252 console crashes on them mid-run.

## 2026-07-03 — Phase 2 rolling-form determinism (two findings)

- **Rolling-form run-value rates summed as scaled INTEGERS (micro-runs), not floats.** The
  rebuild-determinism GATE (`run.py determinism`, hashes gold_team_form twice) caught the
  float `sum(run_value)` aggregations varying by ~1e-15 across rebuilds — DuckDB's parallel
  float summation is non-associative. `round(…,6)` did NOT fix it (values within 1e-15 of a
  6th-decimal half-boundary still flip). Fix: `sum(cast(round(run_value*1e6) as bigint))` —
  integer addition is associative, so the sum is order-independent; convert back at the end.
  Feed is now byte-identical (GATE passes). Only the float columns were affected; all
  integer-derived rolling features were already deterministic.
- **`(game_date, game_number)` is NOT a total order — 24 suspension-created collisions.** A game
  suspended on date D and completed on D+1 lands on D+1 with its original `game_number=1`,
  colliding with that day's regular game_number=1. The rolling window's `ORDER BY` therefore
  includes `game_pk` (unique per grain) as the final tiebreaker to stay total/deterministic.
  Do NOT test `(team,date,game_number)` uniqueness — it legitimately fails; the determinism
  GATE (rebuild-and-compare) is the correct guard.

## 2026-07-03 — Phase 2 dim_player SCD2: analytical, not 540 dbt-snapshot runs

- **`dim_player` SCD2 built with window functions, not date-by-date dbt snapshots.** The spec
  says "SCD2 via dbt snapshot, replayed date-by-date." Literally that is ~540 sequential
  `dbt snapshot` invocations (one per game-date) — slow and fragile. Both approaches derive
  validity boundaries from *appearance dates*, so an analytical build (lag/`is distinct from` →
  span id via running sum → `lead(valid_from)` as `valid_to`) yields the **identical** daily-grain
  SCD2 in one deterministic pass. GATE proof: Jazz Chisholm Marlins→Yankees boundary = 2024-07-28
  (his Yankees debut, day after the trade); Arozarena 2024-07-27; Flaherty 3 correct spans.
  822/2068 players have >1 span. Player→team-by-date is derived from Statcast (batting team = away
  on Top / home on Bottom; pitching team opposite). If the dbt-snapshot *mechanism* itself must be
  showcased, add it for dim_team (season-grain, cheap) — flagged to SM.

## 2026-07-02 — Phase 1 GATE (full 2023-2025 pull; DQ notes)

- **Suspended/resumed games share a game_pk across two dates — Phase 2 must dedupe.** 13
  game_pks (2023-2025) appear in the schedule/boxscore under >1 `game_date` (MLB suspended
  games resumed the next day; statsapi lists the final boxscore under both dates). Date-
  partitioned bronze faithfully stores both, so a naive `SUM(pitches) GROUP BY game_pk`
  double-counts. **`fct_game` / `fct_team_game` staging must collapse to one row per game_pk**
  (pick the completion date). The volume test dedupes per (game_pk, team_id) with MAX before
  summing. Example: game_pk 716875 (2023-08-23→24).
- **Volume-test tolerance is directional, not symmetric.** Across 7,408 Final reg/post games:
  0 missing from Statcast; after suspended-game dedup, `statcast_pitches - box_pitches` ranges
  0..+24 (avg +1.06). Statcast is NEVER short (the dangerous direction = missing pitches);
  the positive tail (206 games > +6) is Statcast logging a few extra pitch-events vs the
  official count. GATE rule: **0 games missing AND statcast_pitches >= box_pitches** — not an
  exact/symmetric band.

## 2026-07-02 — Phase 1 ingestion (data-quality notes)

- **Scope filter is `game_type`, not date.** The ingest window (Mar 15 – Nov 15) overlaps
  spring training, and 2024's Seoul Series placed *regular-season* games on the SAME dates as
  domestic *spring* games — so a date window can't separate them. Both statsapi and Statcast
  filter to `game_type in {R,F,D,L,W}` (regular + wildcard/division/LCS/WS) at ingest, dropping
  S/E/A (spring/exhibition/all-star). `game_type` is also stored in the schedule bronze.
  Verified: 2024-03-15 (spring only) → empty; 2024-03-20 (Seoul) → kept 1 regular game only.
  Caught by inspecting the first minute of the full-run log (spring games appearing) — stopped,
  fixed, wiped the dirty partial bronze, re-verified, relaunched.



- **Volume test uses a small tolerance, not exact equality.** Smoke on 2024-07-05 (15 games):
  Statcast rows are consistently **+0 to +4 pitches** above the statsapi boxscore
  `numberOfPitches` (total +17 across 15 games; Statcast always ≥ boxscore). Statcast
  occasionally logs a pitch the boxscore count omits. **Phase 1/2 volume gate:** assert
  `0 <= statcast_pitches - box_pitches <= ~5` per game (or a small % band), and every
  scheduled Final game must appear in Statcast bronze — NOT `statcast == box` exactly.



- **Chadwick `key_mlbam = -1` is a "no MLBAM id" sentinel** (106 rows: pre-integration /
  Negro Leagues players like Josh Gibson, Cool Papa Bell). It is the ONLY source of
  `key_mlbam` non-uniqueness in the register (23,698 rows → 23,593 distinct = the 105 extra
  `-1` rows). Excluding it, real MLBAM ids are unique. **Phase 2 `dim_player_xref` must filter
  `key_mlbam <= 0` before asserting uniqueness on the crosswalk.** None of these players
  appear in 2023–2025 data. Bronze stores the source faithfully; the filter lives in staging.

## 2026-07-02 — Phase 0.2 preflight

- **Betting lines: stay free — baselines for v1 + free forward accrual.** No fair, free source
  exists for the 2025 holdout (free archives stop ~2023; mlb.com odds are partner widgets on
  robots-disallowed `/api/` paths + non-bulk-only terms; statsapi has no odds). v1 game model
  benchmarks on Elo + home-field + B1 Pythagorean. The odds ingester targets The Odds API free
  tier and banks 2026 closing lines going forward (no-ops without `ODDS_API_KEY`), yielding a
  live market benchmark at $0. Paid $30 one-month backfill of 2023–2025 = documented v2 option,
  not taken. Chosen by SM ("must stay free"). Alternatives rejected: paid month (cost);
  free older-season archive (unclean licensing, misses 2025); scrape mlb.com (ToS/robots).

- **wOBA constants: self-derive from our own play-by-play, not FanGraphs.** FanGraphs ToS
  (§17) forbids access outside their interface, so no scraping. We already build the RE24
  matrix (`gold_run_expectancy`) from our play-by-play; the wOBA linear weights fall out of
  the same run-expectancy framework. RE24 known-answer test anchors against published Tango
  run-expectancy tables (public reference), not FanGraphs. Alternative: hand-transcribe
  FanGraphs' Guts constants (rejected — leans on their values; self-deriving is safer and a
  better showcase). Chosen by SM.

## 2026-07-02 — Phase 0.1 scaffold

- **Python I/O stage scripts live under `ingest/`.** The spec's directory layout names
  `ingest/ dbt/ models_r/ models_py/ parity/ dashboard/` but gives no home for the
  Python `land` and `export` stages ("Python owns ALL DuckDB and Parquet I/O"). Placed
  `land.py` and `export_feeds.py` in `ingest/` as the Python data-movement layer.
  Alternative: a separate `warehouse/` dir (rejected — avoids adding a dir the spec
  doesn't list). Reversible; revisit if the module count grows.

- **`pyproject.toml` uses `package = false`.** cfb-analytics built an installed
  `src/cfb_analytics` package; here stages are invoked as scripts by path
  (`uv run python ingest/pull_savant.py`), so no wheel/package build is needed.
