import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { campaignDone, campaignRunning, routeFetch } from "../test/fixtures";
import Campaigns from "./Campaigns";

afterEach(() => vi.unstubAllGlobals());

function renderPage(routes: Record<string, unknown>) {
  vi.stubGlobal("fetch", vi.fn(routeFetch(routes)));
  return render(
    <MemoryRouter>
      <Campaigns />
    </MemoryRouter>,
  );
}

describe("Campaigns page", () => {
  it("lists campaigns with status, verdict and flagged categories", async () => {
    renderPage({ "/api/campaigns": [campaignRunning, campaignDone], "/api/alerts": [] });
    const done = (await screen.findByText("drive-2.4.0-rc1")).closest("tr")!;
    expect(within(done).getByText("regression")).toBeInTheDocument();
    expect(within(done).getByText("Latency")).toBeInTheDocument();
    expect(within(done).getByText("Control instability")).toBeInTheDocument();
    expect(within(done).getByText("185")).toBeInTheDocument();

    const running = screen.getByText("drive-2.4.0-rc2").closest("tr")!;
    expect(within(running).getByRole("progressbar")).toHaveAttribute("aria-valuenow", "40");
  });

  it("explains the empty state", async () => {
    renderPage({ "/api/campaigns": [], "/api/alerts": [] });
    expect(await screen.findByText(/No campaigns yet/)).toBeInTheDocument();
  });

  it("shows load errors", async () => {
    renderPage({});
    expect(await screen.findByText(/Could not load campaigns/)).toBeInTheDocument();
  });
});
