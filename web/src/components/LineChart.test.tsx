import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import LineChart, { pathFor, ticks } from "./LineChart";

describe("ticks", () => {
  it("picks round steps", () => {
    expect(ticks(0, 10, 5)).toEqual([0, 2, 4, 6, 8, 10]);
    expect(ticks(0.03, 0.31, 4)).toEqual([0.1, 0.2, 0.3]);
    expect(ticks(-1.2, 1.2, 4)).toEqual([-1, 0, 1]);
    expect(ticks(-1.2, 1.2, 8)).toEqual([-1, -0.5, 0, 0.5, 1]);
    expect(ticks(5, 5)).toEqual([5]);
    expect(ticks(NaN, 1)).toEqual([]);
  });
});

describe("pathFor", () => {
  const id = (v: number) => v;
  it("breaks the line at missing values", () => {
    expect(pathFor([0, 1, 2, 3, 4], [1, 2, null, 4, 5], id, id)).toBe("M0.0,1.0L1.0,2.0M3.0,4.0L4.0,5.0");
    expect(pathFor([0, 1], [null, null], id, id)).toBe("");
  });
});

describe("LineChart", () => {
  const series = [
    { name: "baseline", color: "blue", x: [0, 0.1, 0.2], y: [10, 11, 12] },
    { name: "candidate", color: "red", x: [0, 0.1, 0.2], y: [10, 12, null] },
  ];

  it("draws one path per series, the cursor and the legend", () => {
    const { container } = render(<LineChart title="Speed" unit="m/s" series={series} cursor={0.1} />);
    expect(container.querySelectorAll("path[data-series]")).toHaveLength(2);
    expect(screen.getByTestId("cursor")).toBeInTheDocument();
    expect(screen.getByText("baseline")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Speed" })).toBeInTheDocument();
  });

  it("says so when there is nothing to plot", () => {
    render(<LineChart title="Gap" series={[{ name: "b", color: "x", x: [0, 1], y: [null, null] }]} />);
    expect(screen.getByText("Gap: no data")).toBeInTheDocument();
  });
});
