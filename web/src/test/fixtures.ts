import type { CampaignSummary } from "../api";

export const campaignDone: CampaignSummary = {
  id: 2,
  name: "drive-2.4.0-rc1 vs drive-2.3.0",
  baseline: "drive-2.3.0",
  candidate: "drive-2.4.0-rc1",
  families: [],
  scenario_count: 700,
  status: "done",
  progress: 1,
  error: null,
  created_at: "2026-05-02T10:00:00Z",
  started_at: "2026-05-02T10:00:01Z",
  finished_at: "2026-05-02T10:00:05Z",
  drives_per_second: 1998.4,
  verdict: "regression",
  flagged: ["latency_spike", "control_instability"],
  failures: 185,
};

export const campaignRunning: CampaignSummary = {
  ...campaignDone,
  id: 3,
  candidate: "drive-2.4.0-rc2",
  status: "running",
  progress: 0.4,
  finished_at: null,
  verdict: null,
  flagged: null,
  failures: null,
};

/** Route fetch() calls to canned JSON by URL prefix. */
export function routeFetch(routes: Record<string, unknown>) {
  return async (url: string) => {
    const key = Object.keys(routes)
      .sort((a, b) => b.length - a.length)
      .find((k) => url.startsWith(k));
    if (!key) return { ok: false, status: 404, statusText: "not found", json: async () => ({ detail: url }) };
    return { ok: true, status: 200, statusText: "OK", json: async () => routes[key] };
  };
}
