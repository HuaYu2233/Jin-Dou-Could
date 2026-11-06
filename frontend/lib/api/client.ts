import { useAuthStore } from "@/stores/auth";
import { API_BASE_URL } from "@/lib/config";
import { refreshAccessToken } from "./refresh";

type FetchOptions = RequestInit & { skipAuth?: boolean };

const AUTH_EXPIRED_MSG = "AUTH_EXPIRED";
const AUTH_EXPIRED_PARAM = "auth_expired";

function _navigateToLogin(reason: string) {
  useAuthStore.getState().logout();
  const url = new URL("/login", window.location.origin);
  url.searchParams.set(AUTH_EXPIRED_PARAM, reason);
  window.location.href = url.toString();
}

export function getCsrfToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : undefined;
}

export async function client<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { skipAuth, body, ...rest } = options;

  const isFormData = body instanceof FormData;
  const headers: Record<string, string> = {
    ...(rest.headers as Record<string, string>),
  };
  if (!isFormData && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const csrfToken = getCsrfToken();
  if (csrfToken && rest.method && rest.method.toUpperCase() !== "GET") {
    headers["X-CSRF-Token"] = csrfToken;
  }

  const res = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...rest,
    body,
    headers,
    credentials: "include",
  });

  if (res.status === 403) {
    const errData = await res.json().catch(() => ({}));
    const detail: string = errData.detail || "";

    if (detail.includes("CSRF token missing") && detail.includes("retry after cookie is set")) {
      const retryToken = getCsrfToken();
      if (retryToken) {
        const retryHeaders = { ...headers, "X-CSRF-Token": retryToken };
        const retryRes = await fetch(`${API_BASE_URL}${endpoint}`, {
          ...rest,
          body,
          headers: retryHeaders,
          credentials: "include",
        });
        if (retryRes.ok) return retryRes.json();
        const retryErr = await retryRes.json().catch(() => ({}));
        throw new Error(retryErr.detail || "Request failed");
      }
    }

    if (detail === "账号已被禁用") {
      _navigateToLogin(AUTH_EXPIRED_MSG);
      throw new Error("账号已被禁用");
    }

    throw new Error(detail || "Forbidden");
  }

  if (res.status === 401 && !options.skipAuth) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      const retryRes = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...rest,
        body,
        headers,
        credentials: "include",
      });
      if (retryRes.ok) {
        return retryRes.json();
      }
    }
    _navigateToLogin(AUTH_EXPIRED_MSG);
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Request failed");
  }

  return res.json();
}