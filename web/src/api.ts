// Typed client for the Fleet Guard API.

export type Category =
  | "disengagement"
  | "latency_spike"
  | "route_deviation"
  | "perception_error"
  | "control_instability";

export const CATEGORIES: Category[] = [
  "disengagement",
  "latency_spike",
  "route_deviation",
  "perception_error",
  "control_instability",
];

export type CampaignStatus = "queued" | "running" | "ingesting" | "classifying" | "done" | "failed";

export interface CategoryVerdict {
  failures: number;
  critical: number;
  per_1000: number;
  flagged: boolean;
}

export interface Verdict {
  status: "pass" | "regression";
  flagged: Category[];
  top_category: Category | null;
  scenarios: number;
  failures: number;
  categories: Record<Category, CategoryVerdict>;
  top_clusters: { signature: string; category: Category; n: number; severity: number }[];
}

export interface CampaignSummary {
  id: number;
  name: string;
  baseline: string;
  candidate: string;
  families: string[];
  scenario_count: number;
  status: CampaignStatus;
  progress: number;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  drives_per_second: number | null;
  verdict: "pass" | "regression" | null;
  flagged: Category[] | null;
  failures: number | null;
}

export interface Campaign extends Omit<CampaignSummary, "verdict" | "flagged" | "failures"> {
  seed_start: number;
  sim_seconds: number | null;
  verdict: Verdict | null;
}

export interface RoleMetrics {
  role: "baseline" | "candidate";
  build: string;
  drives: number;
  completed: number;
  disengaged: number;
  collisions: number;
  timeouts: number;
  km: number;
  disengagements_per_1000km: number | null;
  hard_brakes_per_100km: number | null;
  recall: number | null;
  precision: number | null;
  planner_p99_median_ms: number | null;
  planner_p99_p99_ms: number | null;
  deadline_misses: number;
  cte_p95_mean: number | null;
  steer_reversal_rate: number | null;
  accel_reversal_rate: number | null;
  jerk_rms: number | null;
}

export interface FamilyMetrics {
  family: string;
  role: "baseline" | "candidate";
  drives: number;
  failed: number;
  collisions: number;
  recall: number | null;
  planner_p99_p99_ms: number | null;
  steer_reversal_rate: number | null;
}

export interface FailureRow {
  id: number;
  scenario_id: string;
  family: string;
  weather: string;
  category: Category;
  secondary: Category[];
  severity: 1 | 2 | 3;
  score: number;
  first_t: number | null;
  signature: string;
  repro_verified: boolean | null;
}

export interface Cluster {
  signature: string;
  category: Category;
  family: string;
  failures: number;
  severity: number;
  mean_score: number;
  example_id: number;
}

export interface DriveEvent {
  t: number;
  kind: string;
  severity: number;
  value: number | null;
  duration: number;
  detail: string;
}

export interface Drive {
  id: number;
  role: "baseline" | "candidate";
  build: string;
  outcome: string;
  reason: string;
  duration_s: number;
  events: DriveEvent[];
  has_telemetry: boolean;
  [metric: string]: unknown;
}

export interface ParamChange {
  key: string;
  baseline: unknown;
  candidate: unknown;
}

export interface FailureDetail {
  failure: FailureRow & { evidence: Record<string, unknown>; signals: Record<string, unknown> };
  campaign: { id: number; name: string; baseline: string; candidate: string; status: CampaignStatus };
  scenario: { id: string; family: string; seed: number; weather: string; route_length_m: number };
  pair: Record<string, unknown>;
  baseline: Drive;
  candidate: Drive;
  build_diff: ParamChange[];
  repro_command: string;
}

export type Series = Record<string, (number | null)[]>;

export interface Telemetry {
  source: "stored" | "replayed";
  columns: string[];
  baseline: Series;
  candidate: Series;
}

export interface ScenarioGeometry {
  id: string;
  family: string;
  geometry: { route: [number, number][]; map_route?: [number, number][]; lane_width: number };
}

export interface Report {
  id: number;
  failure_id: number;
  generator: "template" | "llm";
  model: string | null;
  markdown: string;
  meta: Record<string, unknown>;
  created_at: string;
}

export interface Build {
  name: string;
  parent: string | null;
  description: string;
  overrides: Record<string, unknown>;
  created_at: string;
}

export interface Alert {
  fingerprint: string;
  alertname: string;
  status: "firing" | "resolved";
  severity: string | null;
  campaign_id: number | null;
  labels: Record<string, string>;
  annotations: Record<string, string>;
  starts_at: string;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  builds: () => request<Build[]>("/api/builds"),
  buildDiff: (a: string, b: string) =>
    request<ParamChange[]>(`/api/builds/${encodeURIComponent(a)}/diff/${encodeURIComponent(b)}`),
  families: () => request<string[]>("/api/families"),
  campaigns: () => request<CampaignSummary[]>("/api/campaigns"),
  campaign: (id: number) => request<Campaign>(`/api/campaigns/${id}`),
  campaignMetrics: (id: number) =>
    request<{ roles: RoleMetrics[]; families: FamilyMetrics[] }>(`/api/campaigns/${id}/metrics`),
  createCampaign: (body: {
    baseline: string;
    candidate: string;
    scenario_count: number;
    families?: string[];
  }) => request<Campaign>("/api/campaigns", { method: "POST", body: JSON.stringify(body) }),
  failures: (id: number, params: Record<string, string | number | undefined> = {}) => {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") q.set(k, String(v));
    return request<{ total: number; items: FailureRow[] }>(`/api/campaigns/${id}/failures?${q}`);
  },
  clusters: (id: number) => request<Cluster[]>(`/api/campaigns/${id}/clusters`),
  failure: (id: number) => request<FailureDetail>(`/api/failures/${id}`),
  telemetry: (id: number) => request<Telemetry>(`/api/failures/${id}/telemetry`),
  scenario: (id: number) => request<ScenarioGeometry>(`/api/failures/${id}/scenario`),
  repro: (id: number) =>
    request<{ reproduced: boolean; mismatches: string[]; command: string }>(`/api/failures/${id}/repro`, {
      method: "POST",
    }),
  report: (id: number) => request<Report>(`/api/failures/${id}/report`),
  generateReport: (id: number, llm: boolean) =>
    request<Report>(`/api/failures/${id}/report?llm=${llm}`, { method: "POST" }),
  alerts: () => request<Alert[]>("/api/alerts"),
};
