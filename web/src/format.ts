import type { Category, CampaignStatus } from "./api";

export const CATEGORY_LABEL: Record<Category, string> = {
  disengagement: "Disengagement",
  latency_spike: "Latency",
  route_deviation: "Route deviation",
  perception_error: "Perception",
  control_instability: "Control instability",
};

export const CATEGORY_COLOR: Record<Category, string> = {
  disengagement: "#f87171",
  latency_spike: "#fbbf24",
  route_deviation: "#a78bfa",
  perception_error: "#38bdf8",
  control_instability: "#fb923c",
};

export const SEVERITY_LABEL: Record<number, string> = { 1: "low", 2: "medium", 3: "high" };

export function num(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "-";
  if (Math.abs(v) >= 10000) return Math.round(v).toLocaleString("en-US");
  const s = v.toFixed(digits);
  return s.includes(".") ? s.replace(/0+$/, "").replace(/\.$/, "") : s;
}

export function pct(v: number | null | undefined, digits = 1): string {
  return v === null || v === undefined ? "-" : `${(100 * v).toFixed(digits)}%`;
}

export function duration(fromIso: string | null, toIso: string | null): string {
  if (!fromIso || !toIso) return "-";
  const s = (Date.parse(toIso) - Date.parse(fromIso)) / 1000;
  if (s < 60) return `${s.toFixed(1)} s`;
  return `${Math.floor(s / 60)} min ${Math.round(s % 60)} s`;
}

export function ago(iso: string, now: number = Date.now()): string {
  const s = Math.max(0, (now - Date.parse(iso)) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}

export function isActive(status: CampaignStatus): boolean {
  return status === "queued" || status === "running" || status === "ingesting" || status === "classifying";
}

/** Whether an increase in a metric is a regression. */
export const HIGHER_IS_WORSE: Record<string, boolean> = {
  disengagements_per_1000km: true,
  hard_brakes_per_100km: true,
  recall: false,
  precision: false,
  planner_p99_p99_ms: true,
  deadline_misses: true,
  cte_p95_mean: true,
  steer_reversal_rate: true,
  accel_reversal_rate: true,
  jerk_rms: true,
};

export type Direction = "worse" | "better" | "same";

/** Classify a baseline -> candidate change, ignoring changes under `tolerance` (relative). */
export function direction(metric: string, base: number | null, cand: number | null, tolerance = 0.02): Direction {
  if (base === null || cand === null) return "same";
  const scale = Math.max(Math.abs(base), 1e-9);
  if (Math.abs(cand - base) / scale <= tolerance) return "same";
  const up = cand > base;
  return up === (HIGHER_IS_WORSE[metric] ?? true) ? "worse" : "better";
}

export function signedDelta(base: number | null, cand: number | null, digits = 2): string {
  if (base === null || cand === null) return "";
  const d = cand - base;
  return `${d >= 0 ? "+" : "-"}${num(Math.abs(d), digits)}`;
}
