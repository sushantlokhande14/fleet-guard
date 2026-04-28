import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api } from "./api";

function mockFetch(status: number, body: unknown) {
  const fn = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    statusText: "status " + status,
    json: () => Promise.resolve(body),
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("builds query strings and skips empty filters", async () => {
    const fetch = mockFetch(200, { total: 0, items: [] });
    await api.failures(7, { category: "route_deviation", family: "", limit: 50 });
    expect(fetch.mock.calls[0][0]).toBe("/api/campaigns/7/failures?category=route_deviation&limit=50");
  });

  it("posts JSON when creating a campaign", async () => {
    const fetch = mockFetch(201, { id: 3 });
    await api.createCampaign({ baseline: "a", candidate: "b", scenario_count: 70 });
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe("/api/campaigns");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ baseline: "a", candidate: "b", scenario_count: 70 });
  });

  it("encodes build names with slashes", async () => {
    const fetch = mockFetch(200, []);
    await api.buildDiff("drive-2.3.0", "seeded/clean.identical");
    expect(fetch.mock.calls[0][0]).toBe("/api/builds/drive-2.3.0/diff/seeded%2Fclean.identical");
  });

  it("surfaces the API's detail message", async () => {
    mockFetch(422, { detail: "unknown build nope" });
    await expect(api.campaign(1)).rejects.toEqual(new ApiError(422, "unknown build nope"));
  });
});
