import { useState } from "react";
import { Link } from "react-router-dom";

import { CATEGORIES, api } from "../api";
import { CATEGORY_LABEL, num } from "../format";
import { useAsync } from "../hooks";
import { CategoryBadge, SeverityBadge } from "./Badges";

const PAGE = 50;

export default function FailureTable({ campaignId, families }: { campaignId: number; families: string[] }) {
  const [category, setCategory] = useState("");
  const [family, setFamily] = useState("");
  const [page, setPage] = useState(0);
  const res = useAsync(
    () => api.failures(campaignId, { category, family, limit: PAGE, offset: page * PAGE }),
    [campaignId, category, family, page],
  );
  const total = res.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE));

  return (
    <div className="panel stack">
      <div className="row" style={{ alignItems: "center" }}>
        <h2 style={{ flex: 1, margin: 0 }}>Failures ({total})</h2>
        <select aria-label="category filter" value={category}
          onChange={(e) => { setCategory(e.target.value); setPage(0); }}>
          <option value="">all categories</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>{CATEGORY_LABEL[c]}</option>
          ))}
        </select>
        <select aria-label="family filter" value={family} onChange={(e) => { setFamily(e.target.value); setPage(0); }}>
          <option value="">all families</option>
          {families.map((f) => (
            <option key={f}>{f}</option>
          ))}
        </select>
      </div>
      {res.error && <div className="error">{res.error.message}</div>}
      <table>
        <thead>
          <tr>
            <th>failure</th>
            <th>scenario</th>
            <th>category</th>
            <th>also</th>
            <th>severity</th>
            <th className="num">score</th>
            <th className="num">first at (s)</th>
            <th>repro</th>
          </tr>
        </thead>
        <tbody>
          {(res.data?.items ?? []).map((f) => (
            <tr key={f.id}>
              <td className="mono">
                <Link to={`/failures/${f.id}`}>#{f.id}</Link>
              </td>
              <td className="nowrap">
                {f.scenario_id} <span className="muted">{f.weather}</span>
              </td>
              <td>
                <CategoryBadge category={f.category} />
              </td>
              <td className="muted">{f.secondary.map((s) => CATEGORY_LABEL[s]).join(", ") || "-"}</td>
              <td>
                <SeverityBadge severity={f.severity} />
              </td>
              <td className="num">{num(f.score, 2)}</td>
              <td className="num">{num(f.first_t, 1)}</td>
              <td>{f.repro_verified === null ? <span className="muted">-</span> : f.repro_verified ? "verified" : "MISMATCH"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {pages > 1 && (
        <div className="row" style={{ alignItems: "center", justifyContent: "flex-end" }}>
          <button disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
            Previous
          </button>
          <span className="muted">
            page {page + 1} of {pages}
          </span>
          <button disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)}>
            Next
          </button>
        </div>
      )}
    </div>
  );
}
