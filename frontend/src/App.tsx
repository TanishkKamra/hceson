// (c) 2026 Tanishk Kamra | All rights reserved | github.com/TanishkKamra/hceson | tkp-2603f7a67b-32f1c3󠀁󠁴󠁫󠁰󠀭󠀲󠀶󠀰󠀳󠁦󠀷󠁡󠀶󠀷󠁢󠀭󠀳󠀲󠁦󠀱󠁣󠀳󠁿
import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchCompare, fetchCurve, fetchMeta, type CurvePoint, type Meta, type Metrics, type Query, type Row } from "./api";

const GW = (mw: number) => `${(mw / 1000).toFixed(2)} GW`;
const pct = (x: number | null) => (x === null ? "–" : `${(x * 100).toFixed(1)}%`);
const fmtTime = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", { timeZone: "UTC", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
const fmtDay = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { timeZone: "UTC", day: "numeric", month: "short" });

const COLORS = { actual: "#2563eb", forecast: "#ea580c", p90: "#9333ea" };

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setV(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return v;
}

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [q, setQ] = useState<Query>({ start: "2026-01-01", end: "2026-02-01", horizon: 24, gate: null });
  const [rows, setRows] = useState<Row[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [curve, setCurve] = useState<CurvePoint[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const query = useDebounced(q, 150);

  useEffect(() => {
    fetchMeta().then(setMeta, (e) => setError(e.message));
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    setLoading(true);
    fetchCompare(query, ctrl.signal)
      .then((r) => {
        setRows(r.rows);
        setMetrics(r.metrics);
        setError(null);
      })
      .catch((e) => e.name !== "AbortError" && setError(e.message))
      .finally(() => !ctrl.signal.aborted && setLoading(false));
    return () => ctrl.abort();
  }, [query]);

  useEffect(() => {
    const ctrl = new AbortController();
    fetchCurve(query.start, query.end, ctrl.signal).then(setCurve, (e) => e.name !== "AbortError" && setError(e.message));
    return () => ctrl.abort();
  }, [query.start, query.end]);

  const set = (patch: Partial<Query>) => setQ((prev) => ({ ...prev, ...patch }));
  const gateMode = q.gate !== null;
  const decision = gateMode ? `the day before delivery at ${String(q.gate).padStart(2, "0")}:00 UTC` : `${q.horizon}h ahead`;

  return (
    <div className="page">
      <header>
        <div>
          <h1>Wind Forecast Monitor</h1>
          <p className="sub">GB national wind generation · forecast vs actual · January 2026</p>
        </div>
        <p className="source">
          Source: Elexon BMRS <code>WINDFOR</code> &amp; <code>FUELHH</code>
          {meta && <> · snapshot {meta.fetched.slice(0, 10)}</>}
        </p>
      </header>

      <section className="controls" aria-label="Filters">
        <label>
          From
          <input type="date" value={q.start} min={meta?.firstDay} max={q.end} onChange={(e) => e.target.value && set({ start: e.target.value })} />
        </label>
        <label>
          To
          <input type="date" value={q.end} min={q.start} max={meta?.lastDay} onChange={(e) => e.target.value && set({ end: e.target.value })} />
        </label>

        <fieldset className="mode">
          <legend>Decision point</legend>
          <div className="seg" role="radiogroup">
            <button role="radio" aria-checked={!gateMode} className={!gateMode ? "on" : ""} onClick={() => set({ gate: null })}>
              Fixed horizon
            </button>
            <button role="radio" aria-checked={gateMode} className={gateMode ? "on" : ""} onClick={() => set({ gate: 9 })}>
              Day-ahead gate
            </button>
          </div>
        </fieldset>

        {gateMode ? (
          <label>
            Decide on D-1 at (UTC)
            <select value={q.gate!} onChange={(e) => set({ gate: Number(e.target.value) })}>
              {Array.from({ length: 24 }, (_, h) => (
                <option key={h} value={h}>
                  {String(h).padStart(2, "0")}:00
                </option>
              ))}
            </select>
          </label>
        ) : (
          <label className="slider">
            Forecast horizon: <strong>{q.horizon}h</strong>
            <input
              type="range"
              min={0}
              max={meta?.maxHorizonH ?? 48}
              step={1}
              value={q.horizon}
              onChange={(e) => set({ horizon: Number(e.target.value) })}
            />
          </label>
        )}
      </section>

      {error && <p className="error" role="alert">{error}</p>}

      <p className="headline" aria-live="polite">
        {metrics ? (
          <>
            Using the latest forecast available <strong>{decision}</strong>, wind was off by{" "}
            <strong>{GW(metrics.mae)}</strong> on average ({pct(metrics.nmae)} of mean output).
            {metrics.bias > 0 ? " Forecasts ran high" : " Forecasts ran low"} by <strong>{GW(Math.abs(metrics.bias))}</strong>; to cover 9 in 10
            shortfalls, plan for <strong>{GW(metrics.p90Shortfall)}</strong> less wind than forecast.
          </>
        ) : (
          !loading && "No forecasts available for this selection."
        )}
      </p>

      {metrics && (
        <section className="kpis" aria-label="Forecast error">
          <Kpi label="Mean absolute error" value={GW(metrics.mae)} note={`${pct(metrics.nmae)} of mean output`} />
          <Kpi label="RMSE" value={GW(metrics.rmse)} note="penalises big misses" />
          <Kpi label="Bias (forecast − actual)" value={GW(metrics.bias)} note={metrics.bias > 0 ? "over-forecast" : "under-forecast"} />
          <Kpi label="P90 shortfall" value={GW(metrics.p90Shortfall)} note="extra power to buy, 9 in 10 hours" />
          <Kpi
            label="80% error band"
            value={`${(metrics.p10Error / 1000).toFixed(1)} / +${(metrics.p90Error / 1000).toFixed(1)}`}
            note={`GW, P10 / P90 · worst miss ${GW(metrics.maxAbsError)}`}
          />
          <Kpi label="Hours compared" value={metrics.n.toLocaleString()} note={`mean wind ${GW(metrics.meanActual)}`} />
        </section>
      )}

      <section className="card">
        <h2>Actual vs forecast generation</h2>
        <div className={`chart ${loading ? "busy" : ""}`}>
          <ResponsiveContainer width="100%" height={360}>
            <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="time" tickFormatter={fmtDay} minTickGap={40} stroke="var(--muted)" fontSize={12} />
              <YAxis tickFormatter={(v) => `${v / 1000}`} stroke="var(--muted)" fontSize={12} unit=" GW" width={64} />
              <Tooltip content={<RowTooltip />} />
              <Legend />
              <Line name="Actual" dataKey="actual" stroke={COLORS.actual} dot={false} strokeWidth={1.5} isAnimationActive={false} />
              <Line name="Forecast" dataKey="forecast" stroke={COLORS.forecast} dot={false} strokeWidth={1.5} connectNulls isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="card">
        <h2>How error grows with forecast horizon</h2>
        <p className="hint">Each point re-runs the comparison for the selected dates using forecasts published at least that many hours ahead.</p>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={curve} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis dataKey="horizonH" unit="h" stroke="var(--muted)" fontSize={12} />
            <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(1)}`} stroke="var(--muted)" fontSize={12} unit=" GW" width={64} />
            <Tooltip formatter={(v: number) => GW(v)} labelFormatter={(h) => `${h}h ahead`} />
            <Legend />
            {!gateMode && <ReferenceLine x={q.horizon} stroke="var(--muted)" strokeDasharray="4 4" />}
            <Line name="Mean absolute error" dataKey="mae" stroke={COLORS.forecast} dot={false} strokeWidth={2} isAnimationActive={false} />
            <Line name="P90 absolute error" dataKey="p90AbsError" stroke={COLORS.p90} dot={false} strokeWidth={2} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </section>

      <footer>
        Forecasts are hourly; actuals are half-hourly, so error is measured on the hour. Forecasts more than 72h old are ignored.
      </footer>
    </div>
  );
}

function Kpi({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="kpi">
      <span className="label">{label}</span>
      <span className="value">{value}</span>
      <span className="note">{note}</span>
    </div>
  );
}

function RowTooltip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="tip">
      <strong>{fmtTime(r.time)} UTC</strong>
      <div>
        <span style={{ color: COLORS.actual }}>Actual</span> {GW(r.actual)}
      </div>
      {r.forecast !== null && (
        <>
          <div>
            <span style={{ color: COLORS.forecast }}>Forecast</span> {GW(r.forecast)} ({r.forecast > r.actual ? "+" : ""}
            {GW(r.forecast - r.actual)})
          </div>
          <div className="muted">
            published {fmtTime(r.publishTime!)} · {r.horizonH}h ahead
          </div>
        </>
      )}
    </div>
  );
}
