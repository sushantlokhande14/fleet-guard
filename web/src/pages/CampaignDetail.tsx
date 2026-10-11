import { Link, useParams } from "react-router-dom";

import { api, type RoleMetrics } from "../api";
import { CategoryBadge, Progress, SeverityBadge, StatusBadge, VerdictBadge } from "../components/Badges";
import CategoryBars from "../components/CategoryBars";
import CopySummary from "../components/CopySummary";
import FailureTable from "../components/FailureTable";
import FamilyTable from "../components/FamilyTable";
import KpiDelta from "../components/KpiDelta";
import { duration, isActive, num, pct } from "../format";
import { useAsync } from "../hooks";

const KPIS: { metric: keyof RoleMetrics; label: string; format: (v: number | null) => string; hint: string }[] = [
  { metric: "disengagements_per_1000km", label: "Disengagements / 1000 km", format: (v) => num(v, 1),
    hint: "Safety-driver takeovers, watchdog trips and collisions per 1000 km driven" },
  { metric: "recall", label: "Perception recall", format: (v) => pct(v, 2),
    hint: "Share of relevant real objects with a confirmed track, every tick" },
  { metric: "planner_p99_p99_ms", label: "Planner p99 (ms)", format: (v) => num(v, 1),
    hint: "99th percentile over drives of each drive's planner p99 cycle time; budget 100 ms" },
  { metric: "steer_reversal_rate", label: "Steering reversals / s", format: (v) => num(v, 3),
    hint: "Mean steering direction reversals per second (ringing shows up here)" },
  { metric: "cte_p95_mean", label: "p95 cross-track error (m)", format: (v) => num(v, 3),
    hint: "Mean over drives of the 95th percentile distance from the lane centre" },
  { metric: "hard_brakes_per_100km", label: "Hard brakes / 100 km", format: (v) => num(v, 1),
    hint: "Episodes below -4 m/s^2 per 100 km" },
];

export default function CampaignDetail() {
  const id = Number(useParams().id);
  const campaign = useAsync(() => api.campaign(id), [id], {
    pollMs: 2000,
    poll: (c) => !c || isActive(c.status),
  });
  const c = campaign.data;
  const done = c?.status === "done";
  const metrics = useAsync(() => (done ? api.campaignMetrics(id) : Promise.resolve(undefined)), [id, done]);
  const clusters = useAsync(() => (done ? api.clusters(id) : Promise.resolve([])), [id, done]);

  if (campaign.error) return <div className="panel error">Campaign {id}: {campaign.error.message}</div>;
  if (!c) return <div className="panel muted">Loading campaign {id}...</div>;

  const role = (r: "baseline" | "candidate") => metrics.data?.roles.find((m) => m.role === r);
  const base = role("baseline");
  const cand = role("candidate");
  const v = c.verdict;

  return (
    <div className="stack">
      <div className="panel stack" style={{ gap: 6 }}>
        <div className="row" style={{ alignItems: "center", gap: 12 }}>
          <h1 style={{ margin: 0 }}>
            #{c.id} {c.candidate} <span className="muted">vs {c.baseline}</span>
          </h1>
          <StatusBadge status={c.status} />
          <VerdictBadge verdict={v?.status} />
          <div className="spacer" style={{ flex: 1 }} />
          {v && <CopySummary campaignId={c.id} />}
        </div>
        {isActive(c.status) && <Progress value={c.progress} />}
        {c.error && <div className="error mono">{c.error}</div>}
        <div className="muted">
          {c.scenario_count.toLocaleString()} scenarios x 2 builds = {(2 * c.scenario_count).toLocaleString()}{" "}
          drives · seeds from {c.seed_start} · {c.families.length} families · ran in{" "}
          {duration(c.started_at, c.finished_at)}
          {c.drives_per_second ? ` · ${num(c.drives_per_second, 0)} drives/s` : ""}
        </div>
      </div>

      {base && cand && (
        <div className="row">
          {KPIS.map((k) => (
            <KpiDelta key={k.metric} label={k.label} metric={k.metric} hint={k.hint} format={k.format}
              baseline={base[k.metric] as number | null} candidate={cand[k.metric] as number | null} />
          ))}
        </div>
      )}

      {v && (
        <div className="grid-2">
          <div className="panel stack">
            <h2>Failures by category</h2>
            <CategoryBars verdict={v} />
            <div className="muted">
              {v.failures} failing scenarios of {v.scenarios}. A category is flagged at 3 or more failures and at least
              5 per 1000 scenarios.
            </div>
          </div>
          <div className="panel">
            <h2>Clusters</h2>
            <p className="muted" style={{ marginTop: 0 }}>
              Same signature, very likely the same bug. Each links to its strongest failure.
            </p>
            <table>
              <thead>
                <tr>
                  <th className="num">failures</th>
                  <th>signature</th>
                  <th>category</th>
                  <th>max severity</th>
                </tr>
              </thead>
              <tbody>
                {(clusters.data ?? []).slice(0, 12).map((cl) => (
                  <tr key={cl.signature}>
                    <td className="num">{cl.failures}</td>
                    <td className="mono" style={{ fontSize: 12 }}>
                      <Link to={`/failures/${cl.example_id}`} aria-label={cl.signature}>
                        {/* break long signatures at the slashes, not mid-word */}
                        {cl.signature.split("/").map((part, i) => (
                          <span key={i}>
                            {i > 0 && "/"}
                            {i > 0 && <wbr />}
                            {part}
                          </span>
                        ))}
                      </Link>
                    </td>
                    <td>
                      <CategoryBadge category={cl.category} />
                    </td>
                    <td>
                      <SeverityBadge severity={cl.severity} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {metrics.data && metrics.data.families.length > 0 && <FamilyTable rows={metrics.data.families} />}

      {done && <FailureTable campaignId={id} families={c.families} />}
    </div>
  );
}
