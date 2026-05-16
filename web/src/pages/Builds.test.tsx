import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { routeFetch } from "../test/fixtures";
import Builds from "./Builds";

afterEach(() => vi.unstubAllGlobals());

const builds = [
  { name: "drive-2.3.0", parent: null, description: "known good", overrides: { name: "drive-2.3.0" },
    created_at: "2026-05-16T10:00:00Z" },
  { name: "drive-2.4.0-rc1", parent: "drive-2.3.0", description: "rc1",
    overrides: { name: "drive-2.4.0-rc1", control: { steer_gain: 1.25 } }, created_at: "2026-05-16T10:00:00Z" },
];

it("lists builds and diffs the selected pair", async () => {
  const fetch = vi.fn(routeFetch({
    "/api/builds/drive-2.3.0/diff/drive-2.4.0-rc1": [{ key: "control.steer_gain", baseline: 1, candidate: 1.25 }],
    "/api/builds/drive-2.4.0-rc1/diff/drive-2.4.0-rc1": [],
    "/api/builds": builds,
  }));
  vi.stubGlobal("fetch", fetch);
  render(<Builds />);
  expect(await screen.findByText("control.steer_gain=1.25")).toBeInTheDocument();
  expect(screen.getByText("(stack defaults)")).toBeInTheDocument();
  expect(await screen.findByText("control.steer_gain")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("left build"), { target: { value: "drive-2.4.0-rc1" } });
  expect(await screen.findByText("Identical effective parameters.")).toBeInTheDocument();
});
