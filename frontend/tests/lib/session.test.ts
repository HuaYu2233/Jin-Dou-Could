import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

describe("退出登录后的请求治理", () => {
  beforeEach(() => {
    vi.resetModules();
    localStorage.clear();
    document.cookie = "csrf_token=token-abc; path=/";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("会话关闭后不再发出需要认证的请求", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { closeSession } = await import("@/lib/api/session");
    const { client } = await import("@/lib/api/client");

    closeSession();

    await expect(client("/api/v1/files/abc/preview")).rejects.toThrow("Unauthorized");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("会话关闭后登录类接口仍然可用", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ detail: "ok" }),
      clone: () => ({ json: async () => ({ detail: "ok" }) }),
    }));
    vi.stubGlobal("fetch", fetchMock);

    const { closeSession } = await import("@/lib/api/session");
    const { client } = await import("@/lib/api/client");

    closeSession();

    const res = await client<{ detail: string }>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: "a@b.c", password: "x" }),
    });

    expect(res.detail).toBe("ok");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("退出时会中止在途请求", async () => {
    let aborted = false;
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_input: string, init?: RequestInit) =>
          new Promise((_resolve, reject) => {
            init?.signal?.addEventListener("abort", () => {
              aborted = true;
              reject(new DOMException("Aborted", "AbortError"));
            });
          })
      )
    );

    const { client } = await import("@/lib/api/client");
    const { closeSession } = await import("@/lib/api/session");

    const pending = client("/api/v1/files").catch((err: Error) => err.name);
    await new Promise((r) => setTimeout(r, 0));
    closeSession();

    expect(await pending).toBe("AbortError");
    expect(aborted).toBe(true);
  });

  it("本地已退出时 401 不再触发 token 刷新", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string) => {
        calls.push(input);
        return {
          ok: false,
          status: 401,
          json: async () => ({ detail: "Unauthorized" }),
          clone: () => ({ json: async () => ({ detail: "Unauthorized" }) }),
        };
      })
    );

    const { useAuthStore } = await import("@/stores/auth");
    useAuthStore.setState({ user: null, isAuthenticated: false, isLoading: false, error: null });

    const { client } = await import("@/lib/api/client");

    await expect(client("/api/v1/files/abc/preview")).rejects.toThrow("Unauthorized");
    expect(calls.filter((c) => c.includes("/auth/refresh"))).toEqual([]);
  });

  it("退出后重新登录可以正常拉取用户信息", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string) => {
        calls.push(input);
        if (input.includes("/auth/login")) {
          return { ok: true, status: 200, json: async () => ({ detail: "ok" }), clone: () => ({ json: async () => ({}) }) };
        }
        return {
          ok: true,
          status: 200,
          json: async () => ({ id: "1", username: "u" }),
          clone: () => ({ json: async () => ({}) }),
        };
      })
    );

    const { closeSession } = await import("@/lib/api/session");
    const { login, getMe } = await import("@/lib/api/auth");

    closeSession();

    await login({ email: "a@b.c", password: "x" });
    const me = await getMe();

    expect(me.username).toBe("u");
    expect(calls.some((c) => c.includes("/users/me"))).toBe(true);
  });
});