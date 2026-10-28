"""Download the January 2026 wind snapshot from Elexon BMRS into backend/data/.

January 2026 is history, so the app serves a committed snapshot instead of calling
Elexon on every request. Rerun this script to rebuild it:

    python scripts/fetch_data.py
"""

import gzip
import json
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
OUT = Path(__file__).resolve().parent.parent / "backend" / "data" / "wind_jan2026.json.gz"

# Delivery days covered: decisions made in Jan 2026 deliver from 1 Jan to 1 Feb.
TARGET_FROM, TARGET_TO = date(2026, 1, 1), date(2026, 2, 1)
# Forecasts published up to 72h before the first target can still be the latest one.
PUBLISH_FROM = TARGET_FROM - timedelta(days=3)


def get(url: str) -> list[dict]:
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                return json.load(resp)
        except OSError:
            if attempt == 3:
                raise
            time.sleep(2**attempt)
    return []


def days(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def main() -> None:
    actuals = {}
    for d in days(TARGET_FROM, TARGET_TO):
        rows = get(f"{BASE}/FUELHH/stream?settlementDateFrom={d}&settlementDateTo={d}&fuelType=WIND")
        for r in rows:
            actuals[r["startTime"]] = r["generation"]
        print("FUELHH", d, len(rows))

    forecasts = {}  # publishTime -> {startTime: generation}
    for d in days(PUBLISH_FROM, TARGET_TO):
        nxt = d + timedelta(days=1)
        rows = get(
            f"{BASE}/WINDFOR/stream?publishDateTimeFrom={d}T00:00:00Z&publishDateTimeTo={nxt}T00:00:00Z"
        )
        for r in rows:
            # The range is inclusive at both ends, so midnight runs show up twice; dict dedupes.
            forecasts.setdefault(r["publishTime"], {})[r["startTime"]] = r["generation"]
        print("WINDFOR", d, len(rows))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "source": "Elexon BMRS FUELHH (fuelType=WIND) and WINDFOR",
        "fetched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "actuals": dict(sorted(actuals.items())),
        "forecasts": {p: dict(sorted(v.items())) for p, v in sorted(forecasts.items())},
    }
    with gzip.open(OUT, "wt", encoding="utf-8") as f:
        json.dump(snapshot, f, separators=(",", ":"))
    print(f"wrote {OUT} ({len(actuals)} actuals, {len(forecasts)} forecast runs)")


if __name__ == "__main__":
    main()
