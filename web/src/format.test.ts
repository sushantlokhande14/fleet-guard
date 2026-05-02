import { describe, expect, it } from "vitest";

import { ago, direction, duration, isActive, num, pct, signedDelta } from "./format";

describe("format", () => {
  it("formats numbers without trailing zeros", () => {
    expect(num(1.5)).toBe("1.5");
    expect(num(2)).toBe("2");
    expect(num(0.123456, 3)).toBe("0.123");
    expect(num(123456)).toBe("123,456");
    expect(num(null)).toBe("-");
    expect(pct(0.9956)).toBe("99.6%");
  });

  it("formats durations and ages", () => {
    expect(duration("2026-05-02T10:00:00Z", "2026-05-02T10:00:04.5Z")).toBe("4.5 s");
    expect(duration("2026-05-02T10:00:00Z", "2026-05-02T10:02:30Z")).toBe("2 min 30 s");
    expect(duration(null, "2026-05-02T10:00:00Z")).toBe("-");
    const now = Date.parse("2026-05-02T12:00:00Z");
    expect(ago("2026-05-02T11:59:30Z", now)).toBe("just now");
    expect(ago("2026-05-02T11:15:00Z", now)).toBe("45 min ago");
    expect(ago("2026-04-30T12:00:00Z", now)).toBe("2 d ago");
  });

  it("knows which campaign states are still moving", () => {
    expect(isActive("running")).toBe(true);
    expect(isActive("classifying")).toBe(true);
    expect(isActive("done")).toBe(false);
    expect(isActive("failed")).toBe(false);
  });

  it("judges metric changes by their direction", () => {
    expect(direction("recall", 0.995, 0.95)).toBe("worse");
    expect(direction("recall", 0.95, 0.995)).toBe("better");
    expect(direction("planner_p99_p99_ms", 50, 90)).toBe("worse");
    expect(direction("steer_reversal_rate", 0.2, 0.201)).toBe("same");
    expect(direction("recall", null, 0.9)).toBe("same");
    expect(signedDelta(0.2, 0.35)).toBe("+0.15");
    expect(signedDelta(5, 3)).toBe("-2");
  });
});
