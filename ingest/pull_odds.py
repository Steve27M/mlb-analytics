"""Pull MLB moneylines -> bronze (The Odds API free tier, forward accrual).

Per the Phase 0 decision (stay free): this stage banks going-forward closing moneylines for a
LIVE 2026 market benchmark. It **no-ops when ODDS_API_KEY is unset** — so it costs nothing and
blocks nothing; drop a free key in .env to start collecting. Historical odds are paid-only and
intentionally NOT used; the sealed 2025 holdout stays on the Elo/HFA/Pythagorean baselines.

Each run writes a dated snapshot partition (bronze/odds/snapshot_date=DATE) and logs quota
spent (from the response's x-requests-used / x-requests-remaining headers) — a quota ledger,
budgeted like the CFBD calls were.
"""
from __future__ import annotations

import os
from datetime import date

import pandas as pd
import requests

from _common import log, user_agent, write_partition

ODDS_URL = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds"


def main() -> None:
    key = os.getenv("ODDS_API_KEY", "").strip()
    if not key:
        log("ingest", "odds", event="skip", reason="no ODDS_API_KEY (staying free); no-op")
        return

    snapshot = date.today().isoformat()  # daily closing-line snapshot
    resp = requests.get(
        ODDS_URL,
        params={"apiKey": key, "regions": "us", "markets": "h2h", "oddsFormat": "american"},
        headers={"User-Agent": user_agent()}, timeout=30,
    )
    used = resp.headers.get("x-requests-used")
    remaining = resp.headers.get("x-requests-remaining")
    resp.raise_for_status()
    games = resp.json()

    rows = []
    for g in games:
        for bk in g.get("bookmakers", []):
            for mkt in bk.get("markets", []):
                if mkt.get("key") != "h2h":
                    continue
                for oc in mkt.get("outcomes", []):
                    rows.append({
                        "snapshot_date": snapshot,
                        "commence_time": g.get("commence_time"),
                        "home_team": g.get("home_team"),
                        "away_team": g.get("away_team"),
                        "book": bk.get("key"),
                        "team": oc.get("name"),
                        "moneyline": oc.get("price"),
                        "last_update": mkt.get("last_update"),
                    })

    if not rows:
        log("ingest", "odds", event="empty", snapshot_date=snapshot,
            quota_used=used, quota_remaining=remaining)
        return

    n, checksum, replaced = write_partition(
        pd.DataFrame(rows), "odds", "snapshot_date", snapshot,
        id_cols=[], sort_cols=["commence_time", "book", "team"],
    )
    log("ingest", "odds", event="wrote", snapshot_date=snapshot, rows=n,
        games=len(games), quota_used=used, quota_remaining=remaining, replaced=replaced)


if __name__ == "__main__":
    main()
