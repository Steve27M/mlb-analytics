"""Pull player birth years from MLB Stats API -> bronze (for B3 aging curves).

statsapi /sports/1/players?season=YYYY returns every player active that season with birthDate,
so three calls cover 2023-2025. Reference table (not date-partitioned): bronze/people/set=all.
Terms: MLBAM proprietary, individual non-commercial non-bulk use; raw not redistributed.
"""
from __future__ import annotations

import pandas as pd

from _common import get_json, log, seasons, write_partition

API = "https://statsapi.mlb.com/api/v1"


def main() -> None:
    birth: dict[int, int] = {}
    for season in seasons():
        data = get_json(f"{API}/sports/1/players", params={"season": season})
        for p in data.get("people", []):
            bd = p.get("birthDate")
            if bd and p.get("id") is not None:
                birth[p["id"]] = int(bd[:4])
    df = pd.DataFrame([{"player_id": k, "birth_year": v} for k, v in birth.items()])
    rows, checksum, _ = write_partition(
        df, "people", part_col="set", part_val="all",
        id_cols=["player_id", "birth_year"], sort_cols=["player_id"],
    )
    log("ingest", "people", event="wrote", rows=rows, checksum=checksum[:12])


if __name__ == "__main__":
    main()
