"""Pull MLB Stats API -> bronze: the game spine (schedule) + team-game boxscore lines.

Two date-partitioned sources:
  * statsapi_schedule/game_date=DATE   — one row per game (game_pk, game_number, teams, status)
  * statsapi_boxscore/game_date=DATE   — one row per team-game (runs/hits/pitches)

The boxscore `pitches` (pitching.numberOfPitches, summed home+away) is the reference pitch
count that powers the Phase 1 VOLUME TEST against Statcast rows per game.

Discipline: game_pk / team ids written BIGINT; idempotent per date; throttled + backoff.
Terms: MLBAM proprietary, individual non-commercial non-bulk use; raw not redistributed.

Bounded runs: MLB_INGEST_DATES="2024-07-01,..." pulls just those days. Otherwise the full
MLB_SEASONS expansion runs (heavy — ~2,400 games/season of boxscore calls). Don't launch that
until the day-pull is validated.
"""
from __future__ import annotations

import os
import time
from datetime import date, timedelta

import pandas as pd

from _common import get_json, log, partition_exists, read_manifest, seasons, write_partition

API = "https://statsapi.mlb.com/api/v1"
SEASON_START = (3, 15)
SEASON_END = (11, 15)
# Scope = regular season + postseason. Exclude S(spring), E(exhibition), A(all-star).
# The window overlaps spring training (and 2024's Seoul Series put regular + spring games on
# the SAME dates), so game_type — not the date — is what separates them.
REG_POST = {"R", "F", "D", "L", "W"}  # regular, wildcard, division, LCS, World Series


def _schedule(day: str) -> list[dict]:
    data = get_json(f"{API}/schedule", params={"sportId": 1, "date": day})
    dates = data.get("dates", [])
    return dates[0]["games"] if dates else []


def _boxscore_lines(game_pk: int, day: str, game_number: int) -> list[dict]:
    box = get_json(f"{API}/game/{game_pk}/boxscore")
    rows = []
    for side in ("home", "away"):
        t = box["teams"][side]
        opp = "away" if side == "home" else "home"
        bat = t.get("teamStats", {}).get("batting", {})
        pit = t.get("teamStats", {}).get("pitching", {})
        rows.append({
            "game_date": day,
            "game_pk": game_pk,
            "game_number": game_number,
            "team_id": t["team"]["id"],
            "team_name": t["team"].get("name"),
            "opp_id": box["teams"][opp]["team"]["id"],
            "is_home": side == "home",
            "runs": bat.get("runs"),
            "hits": bat.get("hits"),
            "pitches": pit.get("numberOfPitches"),
        })
    return rows


def pull_day(day: str, force: bool) -> None:
    # Fast resume: if BOTH partitions for this day are done, skip without hitting the API.
    # Keeps re-runs O(1) per completed day so a killed multi-hour pull resumes cheaply.
    if (not force
            and partition_exists("statsapi_schedule", "game_date", day)
            and day in read_manifest("statsapi_schedule")
            and partition_exists("statsapi_boxscore", "game_date", day)
            and day in read_manifest("statsapi_boxscore")):
        log("ingest", "statsapi", event="cache_hit", game_date=day)
        return

    games = [g for g in _schedule(day) if g.get("gameType") in REG_POST]
    if not games:
        log("ingest", "statsapi", event="empty", game_date=day)  # off-day or spring-only
        return

    # --- schedule spine ---
    if not (partition_exists("statsapi_schedule", "game_date", day)
            and day in read_manifest("statsapi_schedule") and not force):
        sched_rows = [{
            "game_date": day,
            "game_pk": g["gamePk"],
            "game_number": g.get("gameNumber", 1),
            "game_type": g.get("gameType"),
            "status": g["status"]["detailedState"],
            "home_id": g["teams"]["home"]["team"]["id"],
            "home_name": g["teams"]["home"]["team"].get("name"),
            "away_id": g["teams"]["away"]["team"]["id"],
            "away_name": g["teams"]["away"]["team"].get("name"),
        } for g in games]
        rows, checksum, replaced = write_partition(
            pd.DataFrame(sched_rows), "statsapi_schedule", "game_date", day,
            id_cols=["game_pk", "home_id", "away_id"], sort_cols=["game_pk"],
        )
        log("ingest", "statsapi_schedule", event="wrote", game_date=day, rows=rows,
            replaced=replaced, checksum=checksum[:12])
    else:
        log("ingest", "statsapi_schedule", event="cache_hit", game_date=day)

    # --- boxscore team-game lines (Final games only) ---
    if (partition_exists("statsapi_boxscore", "game_date", day)
            and day in read_manifest("statsapi_boxscore") and not force):
        log("ingest", "statsapi_boxscore", event="cache_hit", game_date=day)
        return

    t0 = time.monotonic()
    box_rows: list[dict] = []
    for g in games:
        if g["status"]["detailedState"] != "Final":
            continue
        box_rows.extend(_boxscore_lines(g["gamePk"], day, g.get("gameNumber", 1)))
    if not box_rows:
        log("ingest", "statsapi_boxscore", event="no_final_games", game_date=day)
        return
    rows, checksum, replaced = write_partition(
        pd.DataFrame(box_rows), "statsapi_boxscore", "game_date", day,
        id_cols=["game_pk", "team_id", "opp_id"], sort_cols=["game_pk", "team_id"],
    )
    log("ingest", "statsapi_boxscore", event="wrote", game_date=day, rows=rows,
        team_games=len(box_rows), replaced=replaced, checksum=checksum[:12],
        duration_s=round(time.monotonic() - t0, 1))


def _season_days(year: int) -> list[str]:
    d, end, out = date(year, *SEASON_START), date(year, *SEASON_END), []
    while d <= end:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def main() -> None:
    force = os.getenv("MLB_FORCE") == "1"
    override = os.getenv("MLB_INGEST_DATES", "").strip()
    days = ([d.strip() for d in override.split(",") if d.strip()] if override
            else [d for y in seasons() for d in _season_days(y)])
    log("ingest", "statsapi", event="bounded_run" if override else "full_run", days=len(days))
    failures = []
    for day in days:
        try:
            pull_day(day, force)
        except Exception as e:  # one bad day must not abort a multi-season chain
            failures.append(day)
            log("ingest", "statsapi", event="error", game_date=day, error=str(e))
    log("ingest", "statsapi", event="run_done", days=len(days), failures=len(failures),
        failed_days=failures[:20])


if __name__ == "__main__":
    main()
