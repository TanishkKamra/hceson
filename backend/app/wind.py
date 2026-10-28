"""Wind forecast vs actual analysis. Pure functions over an in-memory snapshot."""

import gzip
import json
import math
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from pathlib import Path

SNAPSHOT = Path(__file__).resolve().parent.parent / "data" / "wind_jan2026.json.gz"
MAX_HORIZON_H = 48  # slider range: day-ahead decisions sit within two days of delivery
MAX_FORECAST_AGE_H = 72  # WINDFOR runs reach ~66h ahead; anything older is stale
FIRST_DAY, LAST_DAY = date(2026, 1, 1), date(2026, 2, 1)


def parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class Snapshot:
    fetched: str
    actuals: dict[datetime, float]
    # target time -> (publish times ascending, matching generation values)
    forecasts: dict[datetime, tuple[list[datetime], list[float]]]


def build_snapshot(raw: dict) -> Snapshot:
    by_target: dict[datetime, list[tuple[datetime, float]]] = {}
    for pub, rows in raw["forecasts"].items():
        p = parse(pub)
        for start, gen in rows.items():
            by_target.setdefault(parse(start), []).append((p, gen))
    forecasts = {}
    for t, runs in by_target.items():
        runs.sort()
        forecasts[t] = ([p for p, _ in runs], [g for _, g in runs])
    return Snapshot(
        fetched=raw.get("fetched", ""),
        actuals={parse(k): v for k, v in raw["actuals"].items()},
        forecasts=forecasts,
    )


@lru_cache(maxsize=1)
def load() -> Snapshot:
    with gzip.open(SNAPSHOT, "rt", encoding="utf-8") as f:
        return build_snapshot(json.load(f))


def latest_forecast(snap: Snapshot, target: datetime, cutoff: datetime) -> tuple[datetime, float] | None:
    """Most recent forecast for `target` published at or before `cutoff`, no older than MAX_FORECAST_AGE_H."""
    runs = snap.forecasts.get(target)
    if not runs:
        return None
    pubs, gens = runs
    i = bisect_right(pubs, cutoff) - 1
    if i < 0 or target - pubs[i] > timedelta(hours=MAX_FORECAST_AGE_H):
        return None
    return pubs[i], gens[i]


def cutoff_for(target: datetime, horizon_h: float | None, gate_hour: int | None) -> datetime:
    """Decision time for a target: either a fixed horizon before it, or a daily gate on D-1."""
    if gate_hour is not None:
        d1 = target.date() - timedelta(days=1)
        return datetime.combine(d1, time(gate_hour), tzinfo=timezone.utc)
    return target - timedelta(hours=horizon_h or 0)


def targets(snap: Snapshot, start: date, end: date) -> list[datetime]:
    lo = datetime.combine(start, time(), tzinfo=timezone.utc)
    hi = datetime.combine(end + timedelta(days=1), time(), tzinfo=timezone.utc)
    return sorted(t for t in snap.actuals if lo <= t < hi)


def compare(snap: Snapshot, start: date, end: date, horizon_h: float | None = None, gate_hour: int | None = None):
    """Rows of actual vs chosen forecast. Forecasts are hourly, so half-hour rows have forecast=None."""
    rows = []
    for t in targets(snap, start, end):
        hit = latest_forecast(snap, t, cutoff_for(t, horizon_h, gate_hour))
        rows.append(
            {
                "time": iso(t),
                "actual": snap.actuals[t],
                "forecast": hit[1] if hit else None,
                "publishTime": iso(hit[0]) if hit else None,
                "horizonH": round((t - hit[0]).total_seconds() / 3600, 1) if hit else None,
            }
        )
    return rows


def percentile(values: list[float], q: float) -> float:
    """Linear-interpolated percentile, q in [0, 100]. Values need not be sorted."""
    s = sorted(values)
    k = (len(s) - 1) * q / 100
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def metrics(rows: list[dict]) -> dict | None:
    """Error stats over rows that have a forecast. error = forecast - actual (MW)."""
    pairs = [(r["forecast"], r["actual"]) for r in rows if r["forecast"] is not None]
    if not pairs:
        return None
    err = [f - a for f, a in pairs]
    abs_err = [abs(e) for e in err]
    n = len(err)
    mean_actual = sum(a for _, a in pairs) / n
    mae = sum(abs_err) / n
    return {
        "n": n,
        "mae": mae,
        "rmse": math.sqrt(sum(e * e for e in err) / n),
        "bias": sum(err) / n,
        "nmae": mae / mean_actual if mean_actual else None,
        "meanActual": mean_actual,
        "p50AbsError": percentile(abs_err, 50),
        "p90AbsError": percentile(abs_err, 90),
        "maxAbsError": max(abs_err),
        # Over-forecast is what forces the buyer to top up: forecast said more wind than came.
        "p90Shortfall": max(0.0, percentile(err, 90)),
        "p10Error": percentile(err, 10),
        "p90Error": percentile(err, 90),
    }


def horizon_curve(snap: Snapshot, start: date, end: date, max_h: int = MAX_HORIZON_H) -> list[dict]:
    """How forecast error grows with lead time, one point per whole hour of horizon."""
    out = []
    for h in range(0, max_h + 1):
        m = metrics(compare(snap, start, end, horizon_h=h))
        if m:
            out.append({"horizonH": h, "mae": m["mae"], "rmse": m["rmse"], "p90AbsError": m["p90AbsError"], "n": m["n"]})
    return out
