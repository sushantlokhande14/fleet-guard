import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ReportPanel from "./ReportPanel";

afterEach(() => vi.unstubAllGlobals());

const md = "# Control instability: s_curve-0\n\n## Summary\n\nSteering reversals rose.\n\n| a | b |\n|---|---|\n| 1 | 2 |\n";

function stub(handler: (url: string, init?: RequestInit) => { status: number; body: unknown }) {
  const fn = vi.fn(async (url: string, init?: RequestInit) => {
    const { status, body } = handler(url, init);
    return { ok: status < 300, status, statusText: String(status), json: async () => body };
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("ReportPanel", () => {
  it("offers to generate when there is no report yet", async () => {
    stub(() => ({ status: 404, body: { detail: "no report yet" } }));
    render(<ReportPanel failureId={7} reproCommand="fgsim compare ..." />);
    expect(await screen.findByText(/No report yet/)).toBeInTheDocument();
    expect(screen.getByText("fgsim compare ...")).toBeInTheDocument();
  });

  it("renders markdown tables and says when the LLM narrative was not used", async () => {
    const fetch = stub((url, init) => {
      if (init?.method === "POST" && url.includes("/report")) {
        return { status: 201, body: { id: 2, failure_id: 7, generator: "template", model: null, markdown: md,
          created_at: new Date().toISOString(), meta: { llm_rejected: true } } };
      }
      return { status: 404, body: { detail: "none" } };
    });
    render(<ReportPanel failureId={7} reproCommand="cmd" />);
    fireEvent.click(await screen.findByText("LLM report"));
    expect(await screen.findByRole("heading", { name: "Control instability: s_curve-0" })).toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText(/failed the fact check/)).toBeInTheDocument();
    expect(fetch.mock.calls.some(([u, i]) => u === "/api/failures/7/report?llm=true" && i?.method === "POST"))
      .toBe(true);
  });

  it("verifies the replay", async () => {
    stub((url) => url.endsWith("/repro")
      ? { status: 200, body: { reproduced: true, mismatches: [], command: "cmd" } }
      : { status: 404, body: { detail: "none" } });
    render(<ReportPanel failureId={7} reproCommand="cmd" />);
    fireEvent.click(screen.getByText("Verify replay"));
    expect(await screen.findByText(/replays identically/)).toBeInTheDocument();
  });

  it("does not render raw HTML from a narrative", async () => {
    stub(() => ({ status: 200, body: { id: 1, failure_id: 7, generator: "llm", model: "m", created_at:
      new Date().toISOString(), meta: {}, markdown: "hello <img src=x onerror=alert(1)> world" } }));
    render(<ReportPanel failureId={7} reproCommand="cmd" />);
    const report = await screen.findByTestId("report");
    expect(report.querySelector("img")).toBeNull();
  });
});
