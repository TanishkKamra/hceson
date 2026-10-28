# Wind Forecast Monitor

A web app for a GB utility's day-ahead trading desk. It shows the national wind generation forecast that was available at decision time next to what was actually generated, and quantifies the forecast error so the desk knows how much extra power to buy.

Scope: national wind only, January 2026, from Elexon BMRS:
- Actuals: [`FUELHH`](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream), `fuelType=WIND`, half-hourly
- Forecasts: [`WINDFOR`](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream), hourly, about 8 runs a day, each reaching up to ~66h ahead

**Live app:** _<add Vercel URL>_

## What it does

1. **Latest forecast at decision time.** Pick a date range and a decision point:
   - *Fixed horizon* (0–48h): for each target hour, use the most recent forecast published at least *h* hours before it.
   - *Day-ahead gate*: for each target hour, use the most recent forecast published before a chosen hour (UTC) on the day before delivery, which is how a day-ahead auction bid is actually made.
2. **Quantified error** for that selection: MAE, RMSE, bias, P90 absolute error, and P90 shortfall (how much less wind than forecast to plan for, to be covered 9 hours in 10).
3. **Error vs horizon curve**: MAE and P90 error for every horizon from 0 to 48h, so the desk can see what an earlier decision costs in accuracy.

### What January 2026 shows

| Decision point | MAE | MAE as % of mean output | Bias (forecast − actual) | P90 shortfall |
|---|---|---|---|---|
| 0h ahead | 1.77 GW | 15.5% | +1.56 GW | 3.71 GW |
| 24h ahead | 2.01 GW | 17.6% | +1.82 GW | 4.10 GW |
| D-1 09:00 UTC gate | 2.09 GW | 18.3% | +1.82 GW | 4.25 GW |
| 47h ahead | 2.35 GW | 20.7% | +1.90 GW | 4.47 GW |

- Most of the error is **bias**: the forecast was higher than metered output nearly all month. Correcting for bias alone would remove most of the MAE. Likely causes to check with the client: wind curtailment in the Balancing Mechanism, and differences in which wind farms each dataset covers.
- Error grows steadily with horizon, by about 0.6 GW of MAE between 0h and 47h.

## How matching works

- Forecasts are hourly and actuals are half-hourly, so error is measured on the hour. Half-hour actuals are still drawn on the chart.
- For a target time *t* and decision time *c*, the forecast used is the latest run with `publishTime <= c` that contains *t*.
- Forecasts more than 72h older than their target are ignored as stale.
- Every WINDFOR run ends at 21:00 two days after publishing. So at horizons above ~46h, some late-evening hours have no forecast. The sample count (`n`) is shown in the app.
- "Decisions in January 2026" is taken to mean delivery from 1 Jan to 1 Feb 2026. All times are UTC (the same as UK time in January).

## Files and directories

```
backend/
  app/wind.py          Core logic: load snapshot, pick the latest forecast per target, error metrics, horizon curve
  app/main.py          FastAPI routes (/api/meta, /api/compare, /api/horizon-curve); serves the built frontend in Docker
  data/wind_jan2026.json.gz   Elexon snapshot for January 2026 (78 KB)
  tests/test_wind.py   Unit tests for forecast selection and metrics, plus API tests on the real snapshot
  requirements.txt
frontend/
  src/App.tsx          Dashboard: filters, headline, KPI tiles, charts (Recharts)
  src/api.ts           Typed API client
  src/styles.css
  vite.config.ts       Dev server proxies /api to the backend on :8000
api/index.py           Vercel serverless entry point that imports the FastAPI app
scripts/fetch_data.py  Rebuilds the snapshot from the Elexon API
Dockerfile             Multi-stage build: React build, then one FastAPI container serving API and UI
vercel.json            Vercel build and routing config
.github/workflows/ci.yml   Runs backend tests and the frontend build on every push
```

### Why a snapshot instead of live API calls

January 2026 is history and will not change. Serving a 78 KB snapshot makes the app fast, keeps it working if Elexon is down, and makes the tests deterministic. `scripts/fetch_data.py` rebuilds it. Making it live (for example a scheduled refresh into a database) is the obvious next step for production use.

## Running it

### Docker (one container, API + UI)

```bash
docker build -t wind-monitor .
docker run -p 8000:8000 wind-monitor
```

Then open http://localhost:8000.

### Local development

```bash
python -m venv .venv
.venv/bin/pip install -r backend/requirements.txt pytest httpx   # Windows: .venv\Scripts\pip
.venv/bin/python -m uvicorn app.main:app --app-dir backend --port 8000
```

In a second terminal:

```bash
cd frontend && npm ci && npm run dev
```

Then open http://localhost:5173.

### Tests

```bash
cd backend && ../.venv/bin/python -m pytest -q
```

### Deploying to Vercel

Import the repo in Vercel with no extra settings. `vercel.json` builds the frontend into a static site and serves `/api/*` from `api/index.py` as a Python function.

## API

| Endpoint | Params | Returns |
|---|---|---|
| `GET /api/meta` | – | date bounds, max horizon, snapshot time |
| `GET /api/compare` | `start`, `end` (YYYY-MM-DD), `horizon` (0–48, default 24), optional `gate` (0–23) | per-time rows `{time, actual, forecast, publishTime, horizonH}` and `metrics` |
| `GET /api/horizon-curve` | `start`, `end` | `[{horizonH, mae, rmse, p90AbsError, n}]` |

Dates outside 1 Jan to 1 Feb 2026, or `start > end`, return 422.

## Use of AI tools

This project was built with help from Claude (Anthropic) through Claude Code, which was used for code generation, data exploration, and drafting this README. I reviewed the design, the forecast-matching logic, and the results.
