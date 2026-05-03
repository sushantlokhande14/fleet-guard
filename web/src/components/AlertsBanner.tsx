import { Link } from "react-router-dom";

import { api } from "../api";
import { ago } from "../format";
import { useAsync } from "../hooks";

/** Firing alerts delivered by Alertmanager, linked to the campaign they are about. */
export default function AlertsBanner() {
  const alerts = useAsync(() => api.alerts(), [], { pollMs: 15000 });
  const firing = alerts.data ?? [];
  if (firing.length === 0) return null;
  return (
    <div className="panel alert-banner stack" role="alert" style={{ gap: 6 }}>
      <strong>
        {firing.length} firing alert{firing.length > 1 ? "s" : ""}
      </strong>
      {firing.slice(0, 5).map((a) => (
        <div key={a.fingerprint} className="row" style={{ gap: 10, alignItems: "baseline" }}>
          <span className={`badge ${a.severity === "critical" ? "bad" : "warn"}`}>{a.severity ?? "alert"}</span>
          <span>{a.annotations.summary ?? a.alertname}</span>
          {a.campaign_id !== null && <Link to={`/campaigns/${a.campaign_id}`}>campaign #{a.campaign_id}</Link>}
          <span className="muted">{ago(a.starts_at)}</span>
        </div>
      ))}
    </div>
  );
}
