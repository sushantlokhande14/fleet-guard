import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { failureDetail } from "../test/failure";
import { routeFetch } from "../test/fixtures";
import FailureDetail from "./FailureDetail";

afterEach(() => vi.unstubAllGlobals());

function renderFailure(extra: Record<string, unknown> = {}) {
  vi.stubGlobal("fetch", vi.fn(routeFetch({ "/api/failures/41": failureDetail, ...extra })));
  return render(
    <MemoryRouter initialEntries={["/failures/41"]}>
      <Routes>
        <Route path="/failures/:id" element={<FailureDetail />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Failure detail", () => {
  it("shows what failed, what changed and the evidence", async () => {
    renderFailure();
    expect(await screen.findByRole("heading", { name: /Control instability: construction_shift-50/ }))
      .toBeInTheDocument();
    expect(screen.getByRole("link", { name: /#2 drive-2.4.0-rc1 vs drive-2.3.0/ })).toHaveAttribute("href",
      "/campaigns/2");
    expect(screen.getByText("control.actuator_delay_ms")).toBeInTheDocument();
    expect(screen.getByText("0.169 -> 0.305")).toBeInTheDocument();
  });

  it("merges both timelines and hides routine latency jitter", async () => {
    renderFailure();
    const timeline = (await screen.findByRole("heading", { name: "Timeline" })).parentElement!;
    const rows = within(timeline).getAllByRole("row").slice(1);
    expect(rows.map((r) => r.textContent)).toEqual([
      expect.stringContaining("baseline"),
      expect.stringContaining("candidate"),
      expect.stringContaining("steer_oscillation"),
    ]);
    expect(within(timeline).queryByText("latency_spike")).toBeNull();
  });
});
