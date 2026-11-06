import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const CSRF_COOKIE = "csrf_token";

function clearCsrfCookie() {
  document.cookie = `${CSRF_COOKIE}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
}

function headersOf(fetchMock: ReturnType<typeof vi.fn>, callIndex: number): Headers {
  const init = fetchMock.mock.calls[callIndex][1] as RequestInit;
  return new Headers(init.headers);
}

describe("fetchWithCsrf", () => {
  beforeEach(() => {
    vi.resetModules();
    clearCsrfCookie();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    clearCsrfCookie();
  });

  it("does not attach CSRF header for safe methods", async () => {
    document.cookie = `${CSRF_COOKIE}=token-abc; path=/`;
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    vi.stubGlobal("fetch", fetchMock);
    const { fetchWithCsrf } = await import("@/lib/api/csrf");

    await fetchWithCsrf("http://localhost:8000/api/v1/users/me");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(headersOf(fetchMock, 0).get("X-CSRF-Token")).toBeNull();
    expect((fetchMock.mock.calls[0][1] as RequestInit).credentials).toBe("include");
  });

  it("attaches CSRF header for unsafe methods when cookie exists", async () => {
    document.cookie = `${CSRF_COOKIE}=token-abc; path=/`;
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    vi.stubGlobal("fetch", fetchMock);
    const { fetchWithCsrf } = await import("@/lib/api/csrf");

    await fetchWithCsrf("http://localhost:8000/api/v1/auth/logout", { method: "POST" });

    expect(headersOf(fetchMock, 0).get("X-CSRF-Token")).toBe("token-abc");
  });

  it("retries once after the csrf cookie is set", async () => {
    const csrfMissing = {
      ok: false,
      status: 403,
      clone: () => ({
        json: async () => ({ detail: "CSRF token missing, retry after cookie is set" }),
      }),
    };
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(async () => {
        document.cookie = `${CSRF_COOKIE}=token-new; path=/`;
        return csrfMissing;
      })
      .mockResolvedValueOnce({ ok: true, status: 200 });
    vi.stubGlobal("fetch", fetchMock);
    const { fetchWithCsrf } = await import("@/lib/api/csrf");

    const res = await fetchWithCsrf("http://localhost:8000/api/v1/auth/refresh", {
      method: "POST",
    });

    expect(res.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(headersOf(fetchMock, 1).get("X-CSRF-Token")).toBe("token-new");
  });

  it("does not retry when the 403 is not about a missing csrf cookie", async () => {
    const forbidden = {
      ok: false,
      status: 403,
      clone: () => ({
        json: async () => ({ detail: "账号已被禁用" }),
      }),
    };
    const fetchMock = vi.fn().mockResolvedValue(forbidden);
    vi.stubGlobal("fetch", fetchMock);
    const { fetchWithCsrf } = await import("@/lib/api/csrf");

    const res = await fetchWithCsrf("http://localhost:8000/api/v1/files", { method: "POST" });

    expect(res.status).toBe(403);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});