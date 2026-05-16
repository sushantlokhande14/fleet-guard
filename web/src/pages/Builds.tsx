import { useState } from "react";

import { api } from "../api";
import { ago } from "../format";
import { useAsync } from "../hooks";

function show(v: unknown): string {
  if (typeof v === "boolean") return v ? "yes" : "no";
  return v === null || v === undefined ? "-" : String(v);
}

export default function Builds() {
  const builds = useAsync(() => api.builds(), []);
  const names = (builds.data ?? []).map((b) => b.name);
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const left = a || names[0] || "";
  const right = b || names[names.length - 1] || "";
  const diff = useAsync(() => (left && right ? api.buildDiff(left, right) : Promise.resolve([])), [left, right]);

  return (
    <div className="stack">
      <h1>Builds</h1>
      <div className="panel">
        {builds.error && <div className="error">{builds.error.message}</div>}
        <table>
          <thead>
            <tr>
              <th>build</th>
              <th>parent</th>
              <th>changes vs parent</th>
              <th>registered</th>
            </tr>
          </thead>
          <tbody>
            {(builds.data ?? []).map((bd) => (
              <tr key={bd.name}>
                <td>
                  <div className="mono">{bd.name}</div>
                  <div className="muted">{bd.description}</div>
                </td>
                <td className="mono">{bd.parent ?? "-"}</td>
                <td className="mono muted" style={{ fontSize: 12 }}>
                  {Object.entries(bd.overrides)
                    .filter(([k]) => k !== "name")
                    .map(([section, params]) =>
                      Object.entries(params as Record<string, unknown>).map(([k, v]) => `${section}.${k}=${show(v)}`),
                    )
                    .flat()
                    .join("  ") || "(stack defaults)"}
                </td>
                <td className="muted nowrap">{ago(bd.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel stack">
        <h2>Compare</h2>
        <div className="row" style={{ alignItems: "center" }}>
          <select aria-label="left build" value={left} onChange={(e) => setA(e.target.value)}>
            {names.map((n) => (
              <option key={n}>{n}</option>
            ))}
          </select>
          <span className="muted">to</span>
          <select aria-label="right build" value={right} onChange={(e) => setB(e.target.value)}>
            {names.map((n) => (
              <option key={n}>{n}</option>
            ))}
          </select>
        </div>
        {diff.data && diff.data.length === 0 && <p className="muted">Identical effective parameters.</p>}
        {diff.data && diff.data.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>parameter</th>
                <th>{left}</th>
                <th>{right}</th>
              </tr>
            </thead>
            <tbody>
              {diff.data.map((c) => (
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
  );
}
