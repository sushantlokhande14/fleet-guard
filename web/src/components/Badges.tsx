import type { CampaignStatus, Category } from "../api";
import { CATEGORY_COLOR, CATEGORY_LABEL, SEVERITY_LABEL } from "../format";

const STATUS_CLASS: Record<CampaignStatus, string> = {
  queued: "muted",
  running: "info",
  ingesting: "info",
  classifying: "info",
  done: "good",
  failed: "bad",
};

export function StatusBadge({ status }: { status: CampaignStatus }) {
  return <span className={`badge ${STATUS_CLASS[status]}`}>{status}</span>;
}

export function VerdictBadge({ verdict }: { verdict: "pass" | "regression" | null | undefined }) {
  if (!verdict) return <span className="muted">-</span>;
  return <span className={`badge ${verdict === "pass" ? "good" : "bad"}`}>{verdict}</span>;
}

export function CategoryBadge({ category }: { category: Category }) {
  return (
    <span className="badge" style={{ color: CATEGORY_COLOR[category] }}>
      {CATEGORY_LABEL[category]}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: number }) {
  const cls = severity >= 3 ? "bad" : severity === 2 ? "warn" : "muted";
  return <span className={`badge ${cls}`}>{SEVERITY_LABEL[severity] ?? severity}</span>;
}

export function Progress({ value }: { value: number }) {
  return (
    <div className="progress" role="progressbar" aria-valuenow={Math.round(100 * value)} aria-valuemin={0}
      aria-valuemax={100}>
      <div style={{ width: `${Math.round(100 * value)}%` }} />
    </div>
  );
}
