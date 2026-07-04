# Architecture decision records

One short ADR per major decision: context, options, decision, consequences, and the trigger that
would make us revisit. Newest concerns first. Summaries are surfaced on `data-eng.html`.

---

## ADR-1 — DuckDB over a served database

- **Context.** ~2.2M pitches/season; single-writer, batch, analytical workload; a portfolio budget of $0.
- **Options.** (a) DuckDB embedded, warehouse as a file; (b) Postgres/served OLAP (Redshift/BigQuery/Snowflake).
- **Decision.** DuckDB. Columnar, vectorized, reads Parquet directly; the whole warehouse rebuilds in
  ~2 min with zero running services.
- **Consequences.** No concurrent writers, no always-on endpoint, no network latency — none of which
  this workload needs. Cost and uptime burden are zero.
- **Revisit when.** Multiple concurrent writers, sub-second serving to many clients, or data that
  outgrows a single node.

## ADR-2 — Static site over an app server

- **Context.** The dashboard is read-only aggregates; the data changes at most nightly.
- **Options.** (a) Pre-rendered static HTML on GitHub Pages; (b) a served app (Flask/FastAPI + a DB).
- **Decision.** Static. The builder queries the warehouse at build time and emits self-contained HTML;
  Pages serves it for free.
- **Consequences.** No backend, no CVE surface, no scaling story needed; the tradeoff is no live
  per-request computation (fine — the live 2026 layer is precomputed nightly; the *real-time* leg is
  client-side, see ADR-4).
- **Revisit when.** Per-user state, auth, or genuinely interactive server-side computation is required.

## ADR-3 — Ephemeral Dagster on GitHub Actions, not a daemon

- **Context.** One nightly linear DAG (ingest → build → models/parity → publish).
- **Options.** (a) Dagster asset graph invoked by Actions cron, no standing process; (b) a
  dagster-daemon / Dagster+ / a VPS scheduler.
- **Decision.** (a). Actions cron is $0 and the Dagster asset definitions stay portable; the Typer CLI
  and the Dagster assets are thin wrappers over one `pipeline/stages.py` implementation, so they can't
  drift. dbt tests + the parity gate are blocking asset checks.
- **Consequences.** No persistent event-log UI and no intraday triggering — neither is needed at
  nightly cadence. Given up: a hosted scheduler dashboard (ops.html replaces the essential part).
- **Revisit when.** Intraday runs, backfill fan-out, or a team that needs the Dagster UI.

## ADR-4 — Client-side polling over SSE for the live game exhibit

- **Context.** A live game-day win-probability page (`live.html`) on a static host.
- **Options.** (a) Browser polls MLB's public GUMBO live feed every 15–20s and computes probability
  client-side from exported model coefficients; (b) SSE fan-out via an edge-worker free tier — one
  upstream poller, server-side rate control, but standing infrastructure + a deploy surface.
- **Decision.** (a) at current scale. Zero infrastructure; the page stays static. The cost is that
  N viewers = N pollers, so rate-limit exposure scales with traffic.
- **Consequences.** Client must handle it properly (backoff, ETag, re-derive state from the full feed
  to absorb corrected calls, explicit "stale feed" banner). Correct for a demo page with light traffic.
- **Revisit when.** Sustained concurrent viewers or first contact with an upstream rate limit — then
  move to (b) (one poller, fan-out).

## ADR-5 — Scaled-integer summation for byte-determinism

- **Context.** Rolling run-value features must rebuild byte-identically (a determinism gate guards it).
- **Options.** (a) Sum floats and round; (b) sum scaled integers (micro-runs), divide at the end.
- **Decision.** (b). DuckDB's parallel float summation is non-associative and drifted ~1e-15 across
  rebuilds; rounding couldn't save boundary flips. Integer addition is associative → order-independent.
- **Consequences.** Feeds are byte-identical; the determinism gate passes. Applies only to float
  aggregates.
- **Revisit when.** N/A — this is a settled correctness fix.

## ADR-6 — Phase 6 (AWS lift): **rejected, by TCO** (decided, not deferred)

- **Context.** An earlier plan floated lifting the ELT to AWS (Lambda/Step Functions/S3/Athena). This
  ADR replaces the README's old "Phase 6 open" line with a verdict.
- **Options.** (a) Reject — keep DuckDB + static Pages + Actions; (b) do it as fully Terraform-defined
  deploy-and-teardown IaC where the artifact is the code.
- **Decision.** **(a) — reject at this scale.** Knowing when *not* to deploy infrastructure is the point.

  | | Current ($0 stack) | AWS lift |
  |---|---|---|
  | Scheduling | Actions cron ($0) | EventBridge ($0) |
  | Compute | Actions runner ($0) | Lambda (container, cold starts) |
  | Storage | Git + cache ($0) | S3 (5 GB free, then $) |
  | Serving | Pages ($0) | Athena (per-query $) |
  | Ops surface | one workflow file | IAM roles, VPC-less networking, Terraform state, drift |
  | Capability gained at 2M rows/season | — | ~none |

  The lift adds standing services, an IAM surface, and eventual cost for near-zero capability at this
  data size. The Dagster assets are deployment-agnostic, so the *option* stays open in code.
- **Consequences.** The README's "Phase 6 open" is replaced by this decision. No AWS bill, no IAM to
  maintain.
- **Revisit when.** Data outgrows a single node, a served low-latency API is required, or the goal
  becomes demonstrating AWS IaC specifically — then do option (b) as deploy-and-teardown, teardown
  documented, so the artifact is the Terraform, not a running (billing) stack.
