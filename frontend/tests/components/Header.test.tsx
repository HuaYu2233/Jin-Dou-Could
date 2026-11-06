import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";

const push = vi.fn();
const replace = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace, refresh }),
}));

const USER = {
  id: "1",
  email: "test@example.com",
  username: "test",
  is_active: true,
  is_admin: false,
  avatar_key: null,
  security_question: null,
  created_at: "2025-01-01",
  storage_quota: 1073741824,
  used_storage: 0,
};

function jsonRes(status: number, body: unknown = {}) {
  return { ok: status < 400, status, json: async () => body, clone: () => ({ json: async () => body }) };
}

function mountHeader(root: Root) {
  return import("@/app/dashboard/components/Header").then(async ({ default: Header }) => {
    await act(async () => {
      root.render(<Header />);
    });
  });
}

describe("Header 用户信息拉取与退出登录", () => {
  let root: Root;

  beforeEach(() => {
    vi.resetModules();
    push.mockClear();
    replace.mockClear();
    refresh.mockClear();
    document.cookie = "csrf_token=token-abc; path=/";
    document.body.innerHTML = '<div id="root"></div>';
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    root = createRoot(document.getElementById("root")!);
  });

  afterEach(() => {
    act(() => root.unmount());
    vi.unstubAllGlobals();
  });

  it("首帧没有用户信息时拉取一次用户信息", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string, init?: RequestInit) => {
        calls.push(`${init?.method ?? "GET"} ${input}`);
        if (input.includes("/users/me")) return jsonRes(200, USER);
        return jsonRes(200, {});
      })
    );

    const { useAuthStore } = await import("@/stores/auth");
    useAuthStore.setState({ user: null, isAuthenticated: false, isLoading: false, error: null });

    await mountHeader(root);
    await act(async () => {
      await new Promise((r) => setTimeout(r, 40));
    });

    expect(calls.filter((c) => c.includes("/users/me"))).toHaveLength(1);
    expect(useAuthStore.getState().user).toEqual(USER);
  });

  it("退出登录后不再重新拉取用户信息", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string, init?: RequestInit) => {
        calls.push(`${init?.method ?? "GET"} ${input}`);
        if (input.includes("/auth/logout")) return jsonRes(200, { detail: "已退出登录" });
        if (input.includes("/auth/refresh")) return jsonRes(401, { detail: "无 refresh token" });
        if (input.includes("/users/me")) return jsonRes(401, { detail: "未认证" });
        return jsonRes(200, {});
      })
    );

    const { useAuthStore } = await import("@/stores/auth");
    useAuthStore.setState({ user: USER, isAuthenticated: true, isLoading: false, error: null });

    await mountHeader(root);

    const btn = [...document.querySelectorAll("button")].find((b) => b.textContent === "退出登录");
    expect(btn).toBeTruthy();
    await act(async () => {
      btn!.click();
      await new Promise((r) => setTimeout(r, 80));
    });

    expect(calls).toEqual(["POST http://localhost:8000/api/v1/auth/logout"]);
    expect(push).toHaveBeenCalledWith("/login");
    expect(refresh).not.toHaveBeenCalled();
    expect(useAuthStore.getState().user).toBeNull();
  });
});