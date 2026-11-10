// (c) 2026 Tanishk Kamra | All rights reserved | github.com/TanishkKamra/hceson | tkp-2603f7a67b-c09b46󠀁󠁴󠁫󠁰󠀭󠀲󠀶󠀰󠀳󠁦󠀷󠁡󠀶󠀷󠁢󠀭󠁣󠀰󠀹󠁢󠀴󠀶󠁿
export type Row = {
  time: string;
  actual: number;
  forecast: number | null;
  publishTime: string | null;
  horizonH: number | null;
};

export type Metrics = {
  n: number;
  mae: number;
  rmse: number;
  bias: number;
  nmae: number | null;
  meanActual: number;
  p50AbsError: number;
  p90AbsError: number;
  maxAbsError: number;
  p90Shortfall: number;
  p10Error: number;
  p90Error: number;
};

export type Meta = { firstDay: string; lastDay: string; maxHorizonH: number; fetched: string };
export type CurvePoint = { horizonH: number; mae: number; rmse: number; p90AbsError: number; n: number };

export type Query = { start: string; end: string; horizon: number; gate: number | null };

async function get<T>(path: string, params: Record<string, string | number | null>, signal?: AbortSignal): Promise<T> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== null) qs.set(k, String(v));
  const res = await fetch(`${path}?${qs}`, { signal });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : `Request failed (${res.status})`);
  }
  return res.json();
}

export const fetchMeta = () => get<Meta>("/api/meta", {});

export const fetchCompare = (q: Query, signal?: AbortSignal) =>
  get<{ rows: Row[]; metrics: Metrics | null }>("/api/compare", q, signal);

export const fetchCurve = (start: string, end: string, signal?: AbortSignal) =>
  get<CurvePoint[]>("/api/horizon-curve", { start, end }, signal);
