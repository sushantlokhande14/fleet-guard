import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, type CampaignSummary } from "../api";
import { CategoryBadge, Progress, StatusBadge, VerdictBadge } from "../components/Badges";
import NewCampaign from "../components/NewCampaign";
import { ago, duration, isActive, num } from "../format";
import { useAsync } from "../hooks";

function Row({ c }: { c: CampaignSummary }) {
  const navigate = useNavigate();
  return (
    <tr className="clickable" onClick={() => navigate(`/campaigns/${c.id}`)}>
      <td className="mono">
        <Link to={`/campaigns/${c.id}`} onClick={(e) => e.stopPropagation()}>
          #{c.id}
        </Link>
      </td>
      <td className="nowrap">
        <div>{c.candidate}</div>
        <div className="muted">vs {c.baseline}</div>
      </td>
      <td className="num">{c.scenario_count.toLocaleString()}</td>
      <td>
        <StatusBadge status={c.status} />
        {isActive(c.status) && (
          <div style={{ marginTop: 6 }}>
            <Progress value={c.progress} />
          </div>
        )}
        {c.status === "failed" && <div className="error" title={c.error ?? ""}>error</div>}
      </td>
      <td>
        <VerdictBadge verdict={c.verdict} />
      </td>
      <td>
        <div className="row" style={{ gap: 6 }}>
          {(c.flagged ?? []).map((cat) => (
            <CategoryBadge key={cat} category={cat} />
          ))}
        </div>
      </td>
      <td className="num">{c.failures ?? "-"}</td>
      <td className="num">{c.drives_per_second ? num(c.drives_per_second, 0) : "-"}</td>
      <td className="muted nowrap">
        {ago(c.created_at)}
        <div>{duration(c.started_at, c.finished_at)}</div>
      </td>
    </tr>
  );
}

export default function Campaigns() {
  const [showNew, setShowNew] = useState(false);
  const navigate = useNavigate();
  const list = useAsync(() => api.campaigns(), [], {
    pollMs: 2000,
    poll: (d) => (d ?? []).some((c) => isActive(c.status)),
  });

  return (
    <div className="stack">
      <div className="row" style={{ alignItems: "center" }}>
        <h1 style={{ flex: 1 }}>Campaigns</h1>
        <button className="primary" onClick={() => setShowNew((s) => !s)}>
          {showNew ? "Close" : "New campaign"}
        </button>
      </div>
      {showNew && <NewCampaign onCreated={(id) => navigate(`/campaigns/${id}`)} />}
      <div className="panel">
        {list.error && <div className="error">Could not load campaigns: {list.error.message}</div>}
        {list.data && list.data.length === 0 && (
          <p className="muted">No campaigns yet. Queue one to compare a candidate build against its baseline.</p>
        )}
        {list.data && list.data.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>id</th>
                <th>candidate</th>
                <th className="num">scenarios</th>
                <th>status</th>
                <th>verdict</th>
                <th>flagged</th>
                <th className="num">failures</th>
                <th className="num">drives/s</th>
                <th>created</th>
              </tr>
            </thead>
            <tbody>
              {list.data.map((c) => (
                <Row key={c.id} c={c} />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
