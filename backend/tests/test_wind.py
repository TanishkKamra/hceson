from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from app import wind
from app.main import app


def utc(s: str) -> datetime:
    return wind.parse(s)


@pytest.fixture
def snap():
    # Target 2026-01-02T12:00Z has three runs: 60h, 30h and 2h before it.
    return wind.build_snapshot(
        {
            "actuals": {"2026-01-02T12:00:00Z": 1000, "2026-01-02T12:30:00Z": 1100},
            "forecasts": {
                "2025-12-31T00:00:00Z": {"2026-01-02T12:00:00Z": 500},
                "2026-01-01T06:00:00Z": {"2026-01-02T12:00:00Z": 900},
                "2026-01-02T10:00:00Z": {"2026-01-02T12:00:00Z": 1050},
            },
        }
    )


T = "2026-01-02T12:00:00Z"


@pytest.mark.parametrize(
    "horizon, expected",
    [
        (0, 1050),  # latest run wins
        (2, 1050),  # publish exactly at the cutoff counts
        (3, 900),  # 2h-old run is too fresh, fall back to the 30h one
        (30, 900),
        (31, 500),  # only the 60h run is old enough
        (61, None),  # nothing that old
    ],
)
def test_latest_forecast_respects_horizon(snap, horizon, expected):
    hit = wind.latest_forecast(snap, utc(T), wind.cutoff_for(utc(T), horizon, None))
    assert (hit[1] if hit else None) == expected


def test_gate_uses_day_before(snap):
    # Gate 09:00 on 1 Jan: the 06:00 run on 1 Jan is the latest before it.
    cutoff = wind.cutoff_for(utc(T), None, 9)
    assert cutoff == utc("2026-01-01T09:00:00Z")
    assert wind.latest_forecast(snap, utc(T), cutoff)[1] == 900


def test_half_hour_rows_have_no_forecast(snap):
    rows = wind.compare(snap, date(2026, 1, 2), date(2026, 1, 2), horizon_h=0)
    assert [r["forecast"] for r in rows] == [1050, None]
    assert rows[0]["horizonH"] == 2.0


def test_metrics():
    rows = [
        {"forecast": 110, "actual": 100},
        {"forecast": 80, "actual": 100},
        {"forecast": None, "actual": 100},
    ]
    m = wind.metrics(rows)
    assert m["n"] == 2
    assert m["mae"] == 15
    assert m["bias"] == -5
    assert m["rmse"] == pytest.approx((250) ** 0.5)
    assert wind.metrics([{"forecast": None, "actual": 1}]) is None


def test_percentile():
    assert wind.percentile([3, 1, 2], 50) == 2
    assert wind.percentile([0, 10], 90) == 9
    assert wind.percentile([5], 90) == 5


client = TestClient(app)


def test_api_compare_on_real_snapshot():
    r = client.get("/api/compare", params={"start": "2026-01-10", "end": "2026-01-10", "horizon": 24})
    assert r.status_code == 200
    body = r.json()
    assert len(body["rows"]) == 48
    assert body["metrics"]["n"] == 24
    assert all(r["horizonH"] >= 24 for r in body["rows"] if r["horizonH"] is not None)


def test_api_rejects_bad_range():
    assert client.get("/api/compare", params={"start": "2026-01-05", "end": "2026-01-01"}).status_code == 422
    assert client.get("/api/compare", params={"start": "2025-12-01", "end": "2026-01-01"}).status_code == 422
    assert client.get("/api/compare", params={"horizon": 49}).status_code == 422


def test_api_horizon_curve_error_grows():
    curve = client.get("/api/horizon-curve").json()
    assert curve[0]["horizonH"] == 0
    assert curve[-1]["mae"] > curve[0]["mae"]
