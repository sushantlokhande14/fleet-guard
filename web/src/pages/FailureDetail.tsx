import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, type Drive, type FailureDetail as Detail } from "../api";
import { CategoryBadge, SeverityBadge } from "../components/Badges";
import Replay from "../components/Replay";
import { CATEGORY_LABEL, num } from "../format";
import { useAsync } from "../hooks";

const METRICS: [string, string][] = [
  ["outcome", "outcome"],
  ["reason", "end reason"],
  ["duration_s", "duration (s)"],
  ["route_completion", "route completed"],
  ["cte_max", "max cross-track error (m)"],
  ["min_ttc", "min time to collision (s)"],
  ["min_gap", "min gap (m)"],
  ["recall", "perception recall"],
  ["planner_p99_ms", "planner p99 (ms)"],
  ["deadline_misses", "deadline misses"],
  ["steer_reversal_rate", "steering reversals / s"],
  ["accel_reversal_rate", "accel reversals / s"],
  ["jerk_rms", "jerk RMS"],
  ["hard_brakes", "hard brakes"],
];

function show(v: unknown): string {
  if (v === null || v === undefined || v === "") return "-";
  if (typeof v === "number") return num(v, 3);
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (Array.isArray(v)) {
    if (v.length === 2 && v.every((x) => typeof x === "number")) return `${num(v[0], 3)} -> ${num(v[1], 3)}`;
    return v.map((x) => (typeof x === "object" ? JSON.stringify(x) : String(x))).join(", ");
  }
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function Timeline({ baseline, candidate }: { baseline: Drive; candidate: Drive }) {
  const events = [
    ...baseline.events.map((e) => ({ ...e, role: "baseline" as const })),
    ...candidate.events.map((e) => ({ ...e, role: "candidate" as const })),
  ]
    .filter((e) => !(e.kind === "latency_spike" && e.severity < 2))
    .sort((a, b) => a.t - b.t || a.role.localeCompare(b.role));
  if (events.length === 0) return <p className="muted">No events on either drive.</p>;
  return (
    <table>
      <thead>
        <tr>
          <th className="num">t (s)</th>
          <th>build</th>
          <th>event</th>
          <th className="num">value</th>
          <th>detail</th>
        </tr>
      </thead>
      <tbody>
        {events.map((e, i) => (
          <tr key={i}>
            <td className="num">{num(e.t, 2)}</td>
            <td style={{ color: e.role === "baseline" ? "var(--baseline)" : "var(--candidate)" }}>{e.role}</td>
            <td>
              {e.kind}
              {e.duration > 0 && <span className="muted"> ({num(e.duration, 1)} s)</span>}
            </td>
            <td className="num">{num(e.value, 2)}</td>
            <td className="muted">{e.detail}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function Overview({ d }: { d: Detail }) {
  const f = d.failure;
  return (
    <>
      <div className="panel stack" style={{ gap: 6 }}>
        <div className="row" style={{ alignItems: "center", gap: 12 }}>
          <h1 style={{ margin: 0 }}>
            {CATEGORY_LABEL[f.category]}: {d.scenario.id}
          </h1>
          <CategoryBadge category={f.category} />
          <SeverityBadge severity={f.severity} />
        </div>
        <div className="muted">
          <span className="mono">{f.signature}</span> · campaign{" "}
          <Link to={`/campaigns/${d.campaign.id}`}>
            #{d.campaign.id} {d.campaign.candidate} vs {d.campaign.baseline}
          </Link>{" "}
          · {d.scenario.family} seed {d.scenario.seed} · {d.scenario.weather} · {num(d.scenario.route_length_m, 0)} m
          {f.first_t !== null && <> · first symptom at {num(f.first_t, 1)} s</>}
          {f.secondary.length > 0 && <> · also {f.secondary.map((s) => CATEGORY_LABEL[s]).join(", ")}</>}
        </div>
      </div>

      <div className="grid-2">
        <div className="panel">
          <h2>Evidence</h2>
          <table>
            <tbody>
              {Object.entries(f.evidence).map(([k, v]) => (
                <tr key={k}>
                  <td className="muted">{k.replace(/_/g, " ")}</td>
                  <td>{show(v)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="panel">
          <h2>What changed</h2>
          {d.build_diff.length === 0 ? (
            <p className="muted">The builds have identical parameters.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>parameter</th>
                  <th>baseline</th>
                  <th>candidate</th>
                </tr>
              </thead>
              <tbody>
                {d.build_diff.map((c) => (
                  <tr key={c.key}>
                    <td className="mono">{c.key}</td>
                    <td>{show(c.baseline)}</td>
                    <td>{show(c.candidate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="grid-2">
        <div className="panel">
          <h2>Metrics</h2>
          <table>
            <thead>
              <tr>
                <th>metric</th>
                <th className="num">baseline</th>
                <th className="num">candidate</th>
              </tr>
            </thead>
            <tbody>
              {METRICS.map(([k, label]) => {
                const b = d.baseline[k];
                const c = d.candidate[k];
                return (
                  <tr key={k}>
                    <td className="muted">{label}</td>
                    <td className="num">{show(b)}</td>
                    <td className="num" style={{ fontWeight: show(b) !== show(c) ? 600 : 400 }}>
                      {show(c)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="panel">
          <h2>Timeline</h2>
          <Timeline baseline={d.baseline} candidate={d.candidate} />
        </div>
      </div>
    </>
  );
}

export default function FailureDetail() {
  const id = Number(useParams().id);
  const detail = useAsync(() => api.failure(id), [id]);
  const [cursor, setCursor] = useState<number | null>(null);
  if (detail.error) return <div className="panel error">Failure {id}: {detail.error.message}</div>;
  if (!detail.data) return <div className="panel muted">Loading failure {id}...</div>;
  return (
    <div className="stack">
      <Overview d={detail.data} />
      <Replay failureId={id} candidate={detail.data.candidate} cursor={cursor} onCursor={setCursor} />
    </div>
  );
}
