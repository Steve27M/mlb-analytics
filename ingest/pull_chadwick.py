"""Pull the Chadwick Bureau register -> bronze (the player-id crosswalk).

MLBAM <-> Baseball-Reference <-> FanGraphs <-> Retrosheet. Seeds dim_player_xref and prevents
silent join loss later. Source: github.com/chadwickbureau/register, Open Data Commons
Attribution License (ODC-By 1.0) — attribute in README + dashboard footer.

Reference table, not date-partitioned: written to bronze/chadwick/set=register/. Small enough
to refresh every run; the manifest checksum flags when the register actually changed.
"""
from __future__ import annotations

import time

import pybaseball as pb

from _common import log, write_partition

SOURCE = "chadwick"
KEEP = [
    "key_mlbam", "key_retro", "key_bbref", "key_fangraphs",
    "name_first", "name_last", "mlb_played_first", "mlb_played_last",
]
ID_COLS = ["key_mlbam", "key_fangraphs"]  # key_retro / key_bbref are string ids


def main() -> None:
    t0 = time.monotonic()
    log("ingest", SOURCE, event="start")

    reg = pb.chadwick_register(save=False)
    # Keep only players with MLB service time — that's all our joins ever touch.
    mlb = reg[reg["mlb_played_last"].notna()].copy()
    mlb = mlb[[c for c in KEEP if c in mlb.columns]]

    rows, checksum, replaced = write_partition(
        mlb, SOURCE, part_col="set", part_val="register",
        id_cols=ID_COLS, sort_cols=["key_mlbam"],
    )
    log("ingest", SOURCE, event="wrote", rows=rows, checksum=checksum[:12],
        replaced=replaced, duration_s=round(time.monotonic() - t0, 1))


if __name__ == "__main__":
    main()
