import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { routeFetch } from "../test/fixtures";
import CampaignDetail from "./CampaignDetail";

afterEach(() => vi.unstubAllGlobals());

const zero = { failures: 0, critical: 0, per_1000: 0, flagged: false };
const campaign = {
  id: 2, name: "x", baseline: "drive-2.3.0", candidate: "drive-2.4.0-rc1", families: ["s_curve", "highway_follow"],
  scenario_count: 700, seed_start: 0, status: "done", progress: 1, error: null, created_at: "2026-05-05T10:00:00Z",
  started_at: "2026-05-05T10:00:01Z", finished_at: "2026-05-05T10:00:05Z", drives_per_second: 1795, sim_seconds: 0.8,
  verdict: {
    status: "regression", flagged: ["control_instability"], top_category: "control_instability", scenarios: 700,
    failures: 64, top_clusters: [],
    categories: {
      disengagement: { failures: 3, critical: 3, per_1000: 4.3, flagged: false },
      latency_spike: zero, route_deviation: zero, perception_error: zero,
      control_instability: { failures: 61, critical: 0, per_1000: 87.1, flagged: true },
    },
  },
};
const role = (r: string, recall: number, steer: number) => ({
  role: r, build: r, drives: 700, completed: 690, disengaged: 9, collisions: 0, timeouts: 0, km: 300,
  disengagements_per_1000km: 30, hard_brakes_per_100km: 20, recall, precision: 0.99, planner_p99_median_ms: 47,
  planner_p99_p99_ms: 104, deadline_misses: 10, cte_p95_mean: 0.03, steer_reversal_rate: steer,
  accel_reversal_rate: 0.3, jerk_rms: 1.2,
});
const failures = {
  total: 1,
  items: [{ id: 86, scenario_id: "s_curve-0", family: "s_curve", weather: "clear", category: "control_instability",
    secondary: [], severity: 2, score: 0.6, first_t: 14.9, signature: "control_instability/s_curve/steer",
    repro_verified: true }],
};

function renderPage() {
  const fetch = vi.fn(routeFetch({
    "/api/campaigns/2/metrics": {
      roles: [role("baseline", 0.995, 0.17), role("candidate", 0.995, 0.31)],
      families: [
        { family: "s_curve", role: "baseline", drives: 100, failed: 1, collisions: 0, recall: 1, planner_p99_p99_ms: 88,
          steer_reversal_rate: 0.1 },
        { family: "s_curve", role: "candidate", drives: 100, failed: 1, collisions: 0, recall: 1,
          planner_p99_p99_ms: 88, steer_reversal_rate: 0.3 },
      ],
    },
    "/api/campaigns/2/clusters": [{ signature: "control_instability/s_curve/steer", category: "control_instability",
      family: "s_curve", failures: 59, severity: 2, mean_score: 0.5, example_id: 86 }],
    "/api/campaigns/2/failures": failures,
    "/api/campaigns/2": campaign,
  }));
  vi.stubGlobal("fetch", fetch);
  render(
    <MemoryRouter initialEntries={["/campaigns/2"]}>
      <Routes>
        <Route path="/campaigns/:id" element={<CampaignDetail />} />
      </Routes>
    </MemoryRouter>,
  );
  return fetch;
}

describe("Campaign detail", () => {
  it("shows the verdict, KPI deltas, flagged categories and clusters", async () => {
    renderPage();
    expect(await screen.findByText("regression")).toBeInTheDocument();
    // steering reversals went up: a regression, shown as a worse delta; recall unchanged: no delta
    expect(await screen.findByTestId("delta-steer_reversal_rate")).toHaveClass("worse");
    expect(screen.queryByTestId("delta-recall")).toBeNull();
    expect(screen.getByTestId("bar-control_instability")).toHaveTextContent("flagged");
    expect(screen.getByTestId("bar-disengagement")).not.toHaveTextContent("flagged");
    expect(screen.getByRole("link", { name: "control_instability/s_curve/steer" })).toHaveAttribute(
      "href", "/failures/86");
    expect(await screen.findByRole("link", { name: "#86" })).toBeInTheDocument();
    // steering got worse on s_curve, failures did not
    const row = screen.getByTestId("family-s_curve");
    expect(row.querySelectorAll(".error")).toHaveLength(1);
    expect(row).toHaveTextContent("0.1 -> 0.3");
  });

  it("filters failures by category", async () => {
    const fetch = renderPage();
    const select = await screen.findByLabelText("category filter");
    fireEvent.change(select, { target: { value: "route_deviation" } });
    await vi.waitFor(() =>
      expect(fetch.mock.calls.some(([u]) => String(u).includes("category=route_deviation"))).toBe(true));
  });
});
