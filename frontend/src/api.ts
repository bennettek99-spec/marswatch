// Typed client for the MARSWATCH FastAPI backend.

export type Status = "known_documented" | "plausible_unverified" | "likely_artifact" | "insufficient_evidence";

export interface CandidateRow {
  id: number;
  run_id: string;
  pair_id: string;
  lat: number;
  lon: number;
  area_m2: number;
  eq_diameter_m: number;
  category: string;
  score: number;
  polarity: string;
  registration_quality: number | null;
  classification: Status;
  known_match: string | null;
  chips: { chip?: string } | null;
  methods: Record<string, boolean>;
  notes: string | null;
  created_at: number;
  run_kind: string;
}

export interface Source {
  product_id: string;
  observation_id: string;
  start_time: string;
  cog_url: string;
  pds_jp2_url: string;
  uahirise_url: string;
  incidence: number;
  emission: number;
  solar_longitude: number;
  map_scale: number;
  rationale: string;
  sub_solar_azimuth: number;
}

export interface Registration {
  coarse_dx_m: number;
  coarse_dy_m: number;
  coarse_peak: number;
  n_patches: number;
  n_matched: number;
  n_inliers: number;
  check_rms_px: number | null;
  check_p90_px: number | null;
  check_rms_m: number | null;
  checkpoints: number;
  ncc_before: number;
  ncc_after: number;
  quality: number;
  status: string;
  warnings: string[];
}

export interface CandidateDetail extends CandidateRow {
  px_x: number;
  px_y: number;
  bbox: number[];
  evidence_for: string[];
  evidence_against: string[];
  features: Record<string, any>;
  sources: { before: Source; after: Source };
  registration: Registration;
  run_params: any;
  code_version: string;
  pair: any;
  run: any;
  grid: { width: number; height: number; transform: number[] };
  references_nearby: any[];
  other_observations: any[];
  processing_history: { stage: string; detail: string }[];
}

async function j<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try {
      const b = await r.json();
      if (b.detail) msg = typeof b.detail === "string" ? b.detail : JSON.stringify(b.detail);
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  const ct = r.headers.get("content-type") || "";
  return (ct.includes("json") ? r.json() : r.text()) as Promise<T>;
}

export const api = {
  overview: () => j<any>("/api/overview"),
  runs: (kind?: string) => j<any[]>(`/api/runs${kind ? `?kind=${kind}` : ""}`),
  run: (id: string) => j<any>(`/api/runs/${encodeURIComponent(id)}`),
  runReport: (id: string) => j<string>(`/api/runs/${encodeURIComponent(id)}/report`),
  candidates: (p: Record<string, string | number | undefined>) => {
    const q = new URLSearchParams();
    Object.entries(p).forEach(([k, v]) => v !== undefined && v !== "" && q.set(k, String(v)));
    return j<{ total: number; items: CandidateRow[] }>(`/api/candidates?${q}`);
  },
  candidate: (id: number | string) => j<CandidateDetail>(`/api/candidates/${id}`),
  candidateReport: (id: number | string) => j<string>(`/api/candidates/${id}/report`),
  review: (id: number, body: { notes?: string; classification?: Status }) =>
    j(`/api/candidates/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  map: () => j<any>("/api/map"),
  covering: (lat: number, lon: number) => j<any[]>(`/api/observations/covering?lat=${lat}&lon=${lon}`),
  pairs: (region?: string) => j<any[]>(`/api/pairs${region ? `?region=${encodeURIComponent(region)}` : ""}`),
  discover: (body: any) =>
    j<any>("/api/discover", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  analyze: (body: any) =>
    j<any>("/api/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  jobs: () => j<any[]>("/api/jobs"),
  retry: (id: number) => j(`/api/jobs/${id}/retry`, { method: "POST" }),
  cancel: (id: number) => j(`/api/jobs/${id}/cancel`, { method: "POST" }),
  worker: (action: "pause" | "resume") => j(`/api/worker/${action}`, { method: "POST" }),
  logs: (since: number) => j<any[]>(`/api/logs?since_id=${since}`),
  system: () => j<any>("/api/system"),
  validation: () => j<any>("/api/validation"),
  doc: (name: string) => j<string>(`/api/docs/${name}`),
};

export const STATUS_LABEL: Record<string, string> = {
  known_documented: "Known documented",
  plausible_unverified: "Plausible, unverified",
  likely_artifact: "Likely artifact",
  insufficient_evidence: "Insufficient evidence",
};

export const CATEGORY_LABEL: Record<string, string> = {
  new_impact_crater: "New impact crater",
  slope_streak: "Slope streak",
  dune_bedform_change: "Dune / bedform change",
  rockfall_or_boulder_track: "Rockfall / boulder track",
  seasonal_frost_or_albedo: "Seasonal frost / albedo",
  illumination_or_registration_artifact: "Illumination / registration artifact",
  other_change: "Other change",
};

export const fmt = (v: number | null | undefined, d = 2) =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : Number(v).toFixed(d);

export const fmtDate = (s: string) => (s ? s.slice(0, 10) : "—");
