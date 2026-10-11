import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import CopySummary from "./CopySummary";

afterEach(() => vi.unstubAllGlobals());

it("copies the markdown summary with links back to the UI", async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, text: async () => "## Fleet Guard #2: **PASS**" });
  vi.stubGlobal("fetch", fetch);
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
  render(<CopySummary campaignId={2} />);
  fireEvent.click(screen.getByText("Copy summary"));
  expect(await screen.findByText("Copied")).toBeInTheDocument();
  expect(writeText).toHaveBeenCalledWith("## Fleet Guard #2: **PASS**");
  expect(fetch.mock.calls[0][0]).toBe(`/api/campaigns/2/summary.md?ui=${encodeURIComponent(window.location.origin)}`);
});
