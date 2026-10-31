import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

describe("refreshAccessToken", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns true when refresh endpoint succeeds", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    const { refreshAccessToken } = await import("@/lib/api/refresh");

    await expect(refreshAccessToken()).resolves.toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/auth/refresh"),
      expect.objectContaining({ method: "POST", credentials: "include" })
    );
  });

  it("returns false when refresh endpoint fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false });
    vi.stubGlobal("fetch", fetchMock);
    const { refreshAccessToken } = await import("@/lib/api/refresh");

    await expect(refreshAccessToken()).resolves.toBe(false);
  });

  it("returns false when fetch throws", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error("network down"));
    vi.stubGlobal("fetch", fetchMock);
    const { refreshAccessToken } = await import("@/lib/api/refresh");

    await expect(refreshAccessToken()).resolves.toBe(false);
  });

  it("deduplicates concurrent calls into a single request", async () => {
    let resolveFetch: (value: { ok: boolean }) => void = () => {};
    const fetchMock = vi.fn().mockImplementation(
      () => new Promise((resolve) => { resolveFetch = resolve; })
    );
    vi.stubGlobal("fetch", fetchMock);
    const { refreshAccessToken } = await import("@/lib/api/refresh");

    const first = refreshAccessToken();
    const second = refreshAccessToken();
    const third = refreshAccessToken();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    resolveFetch({ ok: true });
    await expect(Promise.all([first, second, third])).resolves.toEqual([true, true, true]);
  });

  it("allows a new request after the previous one settled", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    const { refreshAccessToken } = await import("@/lib/api/refresh");

    await refreshAccessToken();
    await refreshAccessToken();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});