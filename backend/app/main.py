from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from . import wind

app = FastAPI(title="Wind Forecast Monitor API")
app.add_middleware(GZipMiddleware, minimum_size=1000)


def check_range(start: date, end: date) -> None:
    if start > end:
        raise HTTPException(422, "start must be on or before end")
    if start < wind.FIRST_DAY or end > wind.LAST_DAY:
        raise HTTPException(422, f"dates must be within {wind.FIRST_DAY}..{wind.LAST_DAY}")


@app.get("/api/meta")
def meta():
    return {
        "firstDay": wind.FIRST_DAY.isoformat(),
        "lastDay": wind.LAST_DAY.isoformat(),
        "maxHorizonH": wind.MAX_HORIZON_H,
        "fetched": wind.load().fetched,
    }


@app.get("/api/compare")
def compare(
    start: date = Query(wind.FIRST_DAY),
    end: date = Query(wind.LAST_DAY),
    horizon: float = Query(24, ge=0, le=wind.MAX_HORIZON_H, description="hours between forecast publish and target"),
    gate: int | None = Query(None, ge=0, le=23, description="if set, use the latest forecast before D-1 at this UTC hour"),
):
    check_range(start, end)
    rows = wind.compare(wind.load(), start, end, horizon_h=horizon, gate_hour=gate)
    return {"rows": rows, "metrics": wind.metrics(rows)}


@app.get("/api/horizon-curve")
def horizon_curve(start: date = Query(wind.FIRST_DAY), end: date = Query(wind.LAST_DAY)):
    check_range(start, end)
    return wind.horizon_curve(wind.load(), start, end)


# In Docker the built frontend sits next to the API; on Vercel it is served separately.
STATIC = Path(__file__).resolve().parent.parent / "static"
if STATIC.is_dir():
    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
