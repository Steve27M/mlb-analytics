"""Pull MLB draft first-round picks from Wikipedia -> bronze (M8 draft position vs production).

Uses the MediaWiki API (action=parse), NOT HTML scraping — the Wikimedia Foundation prefers the
API and robots.txt disallows /w/ for crawlers. Descriptive User-Agent, throttled, cached per year
(a year already in bronze is not re-fetched). CC BY-SA: only aggregates are published, attributed.
See PREFLIGHT.md section 8 (approved).

Scope: draft years whose players are plausibly active in 2023-2025 (2008-2019).
"""
from __future__ import annotations

import re
import time

from bs4 import BeautifulSoup

from _common import get_json, log, partition_exists, read_manifest, write_partition

API = "https://en.wikipedia.org/w/api.php"
YEARS = list(range(2008, 2020))


def _parse_year(year: int) -> list[dict]:
    data = get_json(API, params={
        "action": "parse", "page": f"{year} Major League Baseball draft",
        "format": "json", "prop": "text",
    }, throttle=1.0)  # <= 1 req/sec (Wikipedia politeness)
    html = data.get("parse", {}).get("text", {}).get("*", "")
    soup = BeautifulSoup(html, "lxml")

    rows: list[dict] = []
    for t in soup.find_all("table", class_="wikitable"):
        heads = [th.get_text(strip=True).lower() for th in t.find_all("th")]
        if not (any("player" in h for h in heads) and any("pick" in h for h in heads)):
            continue
        for tr in t.find_all("tr")[1:]:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 4:
                continue
            pick_digits = re.sub(r"[^0-9]", "", cells[0])
            if not pick_digits:
                continue
            pick = int(pick_digits)
            player = re.sub(r"\[.*?\]", "", cells[1]).strip()
            position = re.sub(r"\[.*?\]", "", cells[3]).strip()
            if player and 1 <= pick <= 120:
                rows.append({"draft_year": year, "pick": pick,
                             "player": player, "position": position})
    return rows


def main() -> None:
    import pandas as pd
    for year in YEARS:
        yr = str(year)
        if partition_exists("draft", "draft_year", yr) and yr in read_manifest("draft"):
            log("ingest", "draft", event="cache_hit", draft_year=yr)
            continue
        t0 = time.monotonic()
        rows = _parse_year(year)
        if not rows:
            log("ingest", "draft", event="empty", draft_year=yr)
            continue
        n, checksum, _ = write_partition(
            pd.DataFrame(rows), "draft", "draft_year", yr,
            id_cols=["pick"], sort_cols=["pick"],
        )
        log("ingest", "draft", event="wrote", draft_year=yr, rows=n,
            checksum=checksum[:12], duration_s=round(time.monotonic() - t0, 1))


if __name__ == "__main__":
    main()
