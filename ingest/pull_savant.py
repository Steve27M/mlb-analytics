"""Pull Statcast (Baseball Savant) pitch-level data -> bronze, one day per partition.

Savant caps a query at ~30k rows, so we pull DAY BY DAY (well under the cap) — the same
chunking pybaseball does internally. Each day is one Parquet partition:
    bronze/statcast/game_date=YYYY-MM-DD/data.parquet

Discipline enforced here:
  * game_pk / batter / pitcher written as BIGINT (cfb float-id lesson).
  * pitch_key = sha1(game_pk, at_bat_number, pitch_number) minted AFTER exact-dup removal;
    uniqueness asserted, fails loudly.
  * Idempotent: a day already in the manifest is skipped (cache hit) unless MLB_FORCE=1.
  * Freshness: a re-pull whose checksum differs replaces the partition and logs it.

Smoke / bounded runs: set MLB_INGEST_DATES="2024-07-01,2024-07-02" to pull just those days.
Otherwise the (heavy) full-season expansion over MLB_SEASONS runs — do NOT launch that until
the day-pull is validated.

Terms: MLBAM proprietary, individual non-commercial non-bulk use; raw data never redistributed.
"""
from __future__ import annotations

import hashlib
import os
import time
from datetime import date, timedelta

import pybaseball as pb

from _common import log, partition_exists, read_manifest, seasons, write_partition
from _dlq import drain, enqueue, prior_attempts, stats

SOURCE = "statcast"
ID_COLS = ["game_pk", "batter", "pitcher", "at_bat_number", "pitch_number"]
REG_POST = {"R", "F", "D", "L", "W"}  # regular + postseason; drop spring/exhibition/all-star
# Regular season roughly spans late Mar -> early Oct; postseason into Nov. Pull a wide window
# and let empty days (off-days / offseason) no-op.
SEASON_START = (3, 15)
SEASON_END = (11, 15)


def _mint_pitch_key(df):
    key = (df["game_pk"].astype("Int64").astype(str) + "_"
           + df["at_bat_number"].astype("Int64").astype(str) + "_"
           + df["pitch_number"].astype("Int64").astype(str))
    return key.map(lambda s: hashlib.sha1(s.encode()).hexdigest())


def pull_day(day: str, force: bool) -> None:
    if partition_exists(SOURCE, "game_date", day) and day in read_manifest(SOURCE) and not force:
        log("ingest", SOURCE, event="cache_hit", game_date=day)
        return

    t0 = time.monotonic()
    df = pb.statcast(start_dt=day, end_dt=day, verbose=False)
    if df is None or df.empty:
        log("ingest", SOURCE, event="empty", game_date=day)
        return

    df = df[df["game_type"].isin(REG_POST)].reset_index(drop=True)
    if df.empty:
        log("ingest", SOURCE, event="empty", game_date=day, reason="no reg/post games")
        return

    before = len(df)
    df = df.drop_duplicates().reset_index(drop=True)  # exact-dup removal BEFORE key mint
    df["pitch_key"] = _mint_pitch_key(df)

    n_keys, n_rows = df["pitch_key"].nunique(), len(df)
    if n_keys != n_rows:
        raise AssertionError(
            f"pitch_key not unique for {day}: {n_rows} rows, {n_keys} keys "
            f"(game_pk/at_bat_number/pitch_number should be unique per pitch)"
        )

    rows, checksum, replaced = write_partition(
        df, SOURCE, part_col="game_date", part_val=day,
        id_cols=ID_COLS, sort_cols=["game_pk", "at_bat_number", "pitch_number"],
    )
    log("ingest", SOURCE, event="wrote", game_date=day, rows=rows,
        raw_rows=before, exact_dups=before - rows, checksum=checksum[:12],
        replaced=replaced, duration_s=round(time.monotonic() - t0, 1))


def _season_days(year: int) -> list[str]:
    d = date(year, *SEASON_START)
    end = date(year, *SEASON_END)
    out = []
    while d <= end:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def main() -> None:
    force = os.getenv("MLB_FORCE") == "1"
    override = os.getenv("MLB_INGEST_DATES", "").strip()
    if override:
        days = [d.strip() for d in override.split(",") if d.strip()]
        log("ingest", SOURCE, event="bounded_run", days=len(days))
    else:
        days = [d for y in seasons() for d in _season_days(y)]
        log("ingest", SOURCE, event="full_run", seasons=seasons(), days=len(days))

    # Drain the DLQ first: quarantine anything that has failed MAX_ATTEMPTS times (stop retrying);
    # skip quarantined days. Retryable failures are simply re-attempted by the loop below.
    quarantined = drain()
    attempts = prior_attempts()
    failures = []
    for day in days:
        if (SOURCE, day) in quarantined:
            log("ingest", SOURCE, event="quarantined_skip", game_date=day)
            continue
        try:
            pull_day(day, force)
        except Exception as e:  # one bad day must not abort a multi-season chain -> DLQ it
            att = attempts.get((SOURCE, day), 0) + 1
            enqueue(SOURCE, day, "baseballsavant/statcast", e, att)
            failures.append(day)
            log("ingest", SOURCE, event="error", game_date=day, error=str(e), attempt=att)
    log("ingest", SOURCE, event="run_done", days=len(days), failures=len(failures),
        failed_days=failures[:20], dlq=stats())


if __name__ == "__main__":
    main()
