import type { FailureDetail } from "../api";

const drive = (role: "baseline" | "candidate", steer: number, events: FailureDetail["baseline"]["events"]) => ({
  id: role === "baseline" ? 10 : 11,
  role,
  build: role === "baseline" ? "drive-2.3.0" : "drive-2.4.0-rc1",
  outcome: "completed",
  reason: "",
  duration_s: 29.5,
  route_completion: 1,
  cte_max: role === "baseline" ? 0.044 : 0.057,
  steer_reversal_rate: steer,
  recall: 1,
  events,
  has_telemetry: true,
});

export const failureDetail: FailureDetail = {
  failure: {
    id: 41,
    scenario_id: "construction_shift-50",
    family: "construction_shift",
    weather: "fog",
    category: "control_instability",
    secondary: [],
    severity: 2,
    score: 0.57,
    first_t: 15.65,
    signature: "control_instability/construction_shift/steer",
    repro_verified: null,
    evidence: { steer_reversals_per_s: [0.169, 0.305], oscillation_events: 3, axes: ["steer_oscillation"] },
    signals: {},
  },
  campaign: { id: 2, name: "x", baseline: "drive-2.3.0", candidate: "drive-2.4.0-rc1", status: "done" },
  scenario: { id: "construction_shift-50", family: "construction_shift", seed: 50, weather: "fog", route_length_m: 462.1 },
  pair: {},
  baseline: drive("baseline", 0.169, [{ t: 2.4, kind: "phantom_object", severity: 2, value: 28.7, duration: 0, detail: "" }]),
  candidate: drive("candidate", 0.305, [
    { t: 2.4, kind: "phantom_object", severity: 2, value: 28.7, duration: 0, detail: "" },
    { t: 15.65, kind: "steer_oscillation", severity: 2, value: 4, duration: 1.2, detail: "" },
    { t: 3.1, kind: "latency_spike", severity: 1, value: 84, duration: 0.08, detail: "near_budget" },
  ]),
  build_diff: [
    { key: "control.actuator_delay_ms", baseline: 40, candidate: 95 },
    { key: "control.steer_gain", baseline: 1, candidate: 1.25 },
  ],
  repro_command: "fgsim compare --family construction_shift --seed 50 --baseline baseline.json --candidate candidate.json",
};
