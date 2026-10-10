import { direction } from "../format";

interface Props {
  label: string;
  metric: string;
  baseline: number | null;
  candidate: number | null;
  format: (v: number | null) => string;
  hint?: string;
}

/** Candidate value, baseline value and the change, coloured by whether it is a regression. */
export default function KpiDelta({ label, metric, baseline, candidate, format, hint }: Props) {
  const dir = direction(metric, baseline, candidate);
  const delta = baseline !== null && candidate !== null ? candidate - baseline : null;
  return (
    <div className="panel kpi" title={hint}>
      <div className="label">{label}</div>
      <div className="values">
        <span className="cand">{format(candidate)}</span>
        {dir !== "same" && (
          <span className={`delta ${dir}`} data-testid={`delta-${metric}`}>
            {delta !== null && `${delta >= 0 ? "+" : "-"}${format(Math.abs(delta))}`}
          </span>
        )}
      </div>
      <div className="muted">baseline {format(baseline)}</div>
    </div>
  );
}
