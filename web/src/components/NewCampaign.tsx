import { useState } from "react";

import { api, type Build } from "../api";
import { useAsync } from "../hooks";

interface Props {
  onCreated: (id: number) => void;
}

export default function NewCampaign({ onCreated }: Props) {
  const builds = useAsync(() => api.builds(), []);
  const families = useAsync(() => api.families(), []);
  const [baseline, setBaseline] = useState("");
  const [candidate, setCandidate] = useState("");
  const [count, setCount] = useState(700);
  const [picked, setPicked] = useState<string[]>([]);
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  const names = (builds.data ?? []).map((b: Build) => b.name);
  const base = baseline || names[0] || "";
  const cand = candidate || names[names.length - 1] || "";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(undefined);
    try {
      const c = await api.createCampaign({
        baseline: base,
        candidate: cand,
        scenario_count: count,
        families: picked.length ? picked : undefined,
      });
      onCreated(c.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  function toggle(f: string) {
    setPicked((p) => (p.includes(f) ? p.filter((x) => x !== f) : [...p, f]));
  }

  return (
    <form className="panel stack" onSubmit={submit} aria-label="new campaign">
      <h2>New campaign</h2>
      <div className="row" style={{ alignItems: "end" }}>
        <label>
          <div className="muted">Baseline</div>
          <select value={base} onChange={(e) => setBaseline(e.target.value)} aria-label="baseline">
            {names.map((n) => (
              <option key={n}>{n}</option>
            ))}
          </select>
        </label>
        <label>
          <div className="muted">Candidate</div>
          <select value={cand} onChange={(e) => setCandidate(e.target.value)} aria-label="candidate">
            {names.map((n) => (
              <option key={n}>{n}</option>
            ))}
          </select>
        </label>
        <label>
          <div className="muted">Scenarios</div>
          <input type="number" min={1} max={200000} step={7} value={count} aria-label="scenarios"
            onChange={(e) => setCount(Number(e.target.value))} style={{ width: 110 }} />
        </label>
        <button className="primary" disabled={busy || !base || !cand}>
          {busy ? "Queueing..." : "Queue campaign"}
        </button>
      </div>
      <div className="row" style={{ gap: 12 }}>
        <span className="muted">Families (none = all):</span>
        {(families.data ?? []).map((f) => (
          <label key={f} style={{ display: "flex", gap: 4, alignItems: "center" }}>
            <input type="checkbox" checked={picked.includes(f)} onChange={() => toggle(f)} />
            {f}
          </label>
        ))}
      </div>
      <div className="muted">
        Each scenario is driven by both builds: {count.toLocaleString()} scenarios = {(2 * count).toLocaleString()}{" "}
        drives.
      </div>
      {error && <div className="error">{error}</div>}
    </form>
  );
}
