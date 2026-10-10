import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import TrajectoryMap, { bounds } from "./TrajectoryMap";

const geometry = { route: [[0, 0], [50, 0], [100, 5]] as [number, number][], lane_width: 3.6,
  map_route: [[0, 0], [100, 0]] as [number, number][] };
const drive = (dy: number) => ({ t: [0, 1, 2], x: [0, 20, 40], y: [0, dy, dy], yaw: [0, 0, 0] });

describe("TrajectoryMap", () => {
  it("computes bounds over every point set", () => {
    expect(bounds([[[0, 0], [10, -2]], [[5, 3]]])).toEqual({ minX: 0, minY: -2, maxX: 10, maxY: 3 });
  });

  it("draws the lane, the prior map, both tracks and both cars at the cursor", () => {
    const { container } = render(
      <TrajectoryMap geometry={geometry} base={drive(0)} cand={drive(0.8)} cursor={1} onCursor={() => {}} />);
    expect(screen.getByTestId("track-baseline").getAttribute("points")).toBe("0.00,0.00 20.00,0.00 40.00,0.00");
    expect(screen.getByTestId("track-candidate").getAttribute("points")).toContain("20.00,-0.80");
    expect(container.querySelectorAll("polyline")).toHaveLength(5);
    expect(container.querySelectorAll("rect")).toHaveLength(2);
    expect(screen.getByText("1 / 2 s")).toBeInTheDocument();
  });

  it("moves the shared cursor from the slider", () => {
    const onCursor = vi.fn();
    render(<TrajectoryMap geometry={geometry} base={drive(0)} cand={drive(0)} cursor={null} onCursor={onCursor} />);
    fireEvent.change(screen.getByLabelText("time"), { target: { value: "1.5" } });
    expect(onCursor).toHaveBeenCalledWith(1.5);
  });
});

it("follow mode frames a 50 m window around the candidate", () => {
  const { container } = render(
    <TrajectoryMap geometry={geometry} base={drive(0)} cand={drive(0.8)} cursor={1} onCursor={() => {}} />);
  fireEvent.click(screen.getByRole("checkbox"));
  expect(container.querySelector("svg")!.getAttribute("viewBox")).toBe("-5 -13.3 50 25");
});
