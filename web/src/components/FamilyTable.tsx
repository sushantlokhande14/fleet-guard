import type { FamilyMetrics } from "../api";
import { direction, num, pct } from "../format";

/** Baseline vs candidate per scenario family: where did the candidate get worse? */
export default function FamilyTable({ rows }: { rows: FamilyMetrics[] }) {
  const families = [...new Set(rows.map((r) => r.family))].sort();
  const get = (family: string, role: "baseline" | "candidate") =>
    rows.find((r) => r.family === family && r.role === role);
  const cell = (metric: string, b: number | null | undefined, c: number | null | undefined,
    fmt: (v: number | null) => string) => {
    const dir = direction(metric, b ?? null, c ?? null);
    return (
      <td className="num">
        {fmt(b ?? null)} <span className="muted">-&gt;</span>{" "}
        <span className={dir === "worse" ? "error" : ""} style={{ fontWeight: dir === "worse" ? 600 : 400 }}>
          {fmt(c ?? null)}
        </span>
      </td>
    );
  };
  return (
    <div className="panel">
      <h2>Per family (baseline -&gt; candidate)</h2>
      <table>
        <thead>
          <tr>
            <th>family</th>
            <th className="num">failed drives</th>
            <th className="num">collisions</th>
            <th className="num">recall</th>
            <th className="num">planner p99 (ms)</th>
            <th className="num">steer reversals / s</th>
          </tr>
        </thead>
        <tbody>
          {families.map((f) => {
            const b = get(f, "baseline");
            const c = get(f, "candidate");
            return (
              <tr key={f} data-testid={`family-${f}`}>
                <td>{f}</td>
                {cell("disengagements_per_1000km", b?.failed, c?.failed, (v) => num(v, 0))}
                {cell("disengagements_per_1000km", b?.collisions, c?.collisions, (v) => num(v, 0))}
                {cell("recall", b?.recall, c?.recall, (v) => pct(v, 2))}
                {cell("planner_p99_p99_ms", b?.planner_p99_p99_ms, c?.planner_p99_p99_ms, (v) => num(v, 1))}
                {cell("steer_reversal_rate", b?.steer_reversal_rate, c?.steer_reversal_rate, (v) => num(v, 3))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
