import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import { routeFetch } from "../test/fixtures";
import AlertsBanner from "./AlertsBanner";

afterEach(() => vi.unstubAllGlobals());

const alert = {
  fingerprint: "f1",
  alertname: "CandidateRegression",
  status: "firing",
  severity: "warning",
  campaign_id: 2,
  labels: {},
  annotations: { summary: "drive-2.4.0-rc1 regressed against drive-2.3.0" },
  starts_at: new Date().toISOString(),
};

it("lists firing alerts with a link to their campaign", async () => {
  vi.stubGlobal("fetch", vi.fn(routeFetch({ "/api/alerts": [alert] })));
  render(
    <MemoryRouter>
      <AlertsBanner />
    </MemoryRouter>,
  );
  expect(await screen.findByText("1 firing alert")).toBeInTheDocument();
  expect(screen.getByText(/rc1 regressed/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "campaign #2" })).toHaveAttribute("href", "/campaigns/2");
});

it("renders nothing when all is quiet", async () => {
  const fetch = vi.fn(routeFetch({ "/api/alerts": [] }));
  vi.stubGlobal("fetch", fetch);
  const { container } = render(
    <MemoryRouter>
      <AlertsBanner />
    </MemoryRouter>,
  );
  await vi.waitFor(() => expect(fetch).toHaveBeenCalled());
  expect(container).toBeEmptyDOMElement();
});
