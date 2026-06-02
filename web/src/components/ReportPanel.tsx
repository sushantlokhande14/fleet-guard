import { useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { ApiError, api, type Report } from "../api";
import { ago } from "../format";
import { useAsync } from "../hooks";

interface Props {
  failureId: number;
  reproCommand: string;
}

function Repro({ failureId, command }: { failureId: number; command: string }) {
  const [state, setState] = useState<"idle" | "running" | "ok" | "mismatch" | "error">("idle");
  const [detail, setDetail] = useState<string[]>([]);
  async function verify() {
    setState("running");
    try {
      const r = await api.repro(failureId);
      setState(r.reproduced ? "ok" : "mismatch");
      setDetail(r.mismatches);
    } catch (e) {
      setState("error");
      setDetail([e instanceof Error ? e.message : String(e)]);
    }
  }
  return (
    <div className="stack" style={{ gap: 6 }}>
      <div className="row" style={{ alignItems: "center", justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>Reproduce</h2>
        <button onClick={verify} disabled={state === "running"}>
          {state === "running" ? "Replaying..." : "Verify replay"}
        </button>
      </div>
      <pre className="cmd">{command}</pre>
      {state === "ok" && <div className="badge good">replays identically: same outcome, metrics and events</div>}
      {state === "mismatch" && (
        <div className="error">
          Replay differs from the stored run:
          <ul>
            {detail.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        </div>
      )}
      {state === "error" && <div className="error">{detail[0]}</div>}
    </div>
  );
}

export default function ReportPanel({ failureId, reproCommand }: Props) {
  const latest = useAsync<Report | null>(
    () => api.report(failureId).catch((e) => (e instanceof ApiError && e.status === 404 ? null : Promise.reject(e))),
    [failureId],
  );
  const [busy, setBusy] = useState<"llm" | "template" | null>(null);
  const [error, setError] = useState<string>();
  const [fresh, setFresh] = useState<Report>();
  const report = fresh ?? latest.data ?? null;

  async function generate(llm: boolean) {
    setBusy(llm ? "llm" : "template");
    setError(undefined);
    try {
      setFresh(await api.generateReport(failureId, llm));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  const meta = report?.meta ?? {};
  const fellBack = report?.generator === "template" && Boolean(meta.llm_rejected || meta.llm_error);

  return (
    <div className="panel stack">
      <Repro failureId={failureId} command={reproCommand} />
      <div className="row" style={{ alignItems: "center", justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>Report</h2>
        <div className="row" style={{ gap: 8 }}>
          <button onClick={() => generate(false)} disabled={busy !== null}>
            {busy === "template" ? "Writing..." : "Template report"}
          </button>
          <button className="primary" onClick={() => generate(true)} disabled={busy !== null}>
            {busy === "llm" ? "Asking the model..." : "LLM report"}
          </button>
        </div>
      </div>
      {error && <div className="error">{error}</div>}
      {report && (
        <div className="muted">
          {report.generator === "llm" ? `narrative by ${report.model}` : "deterministic template"} ·{" "}
          {ago(report.created_at)}
          {typeof meta.latency_s === "number" && ` · ${meta.latency_s} s`}
          {fellBack && (
            <span className="error">
              {" "}
              · LLM narrative not used ({meta.llm_error ? "endpoint error" : "failed the fact check"})
            </span>
          )}
        </div>
      )}
      {!report && !latest.loading && (
        <p className="muted">
          No report yet. The template report is instant; the LLM report asks the configured model (local Ollama by
          default) for the narrative and checks every number and parameter it states against the data.
        </p>
      )}
      {report && typeof report.markdown === "string" && (
        <article className="report" data-testid="report">
          <Markdown remarkPlugins={[remarkGfm]}>{report.markdown}</Markdown>
        </article>
      )}
    </div>
  );
}
