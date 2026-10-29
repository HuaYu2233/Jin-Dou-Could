import { useAuthStore } from "@/stores/auth";
import { API_BASE_URL } from "@/lib/config";

type FetchOptions = RequestInit & { skipAuth?: boolean };

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
    if (errData.detail === "CSRF token missing, retry after cookie is set") {
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
    throw new Error(errData.detail || "Forbidden");
  }

  if (res.status === 401 && !options.skipAuth) {
    const refreshed = await tryRefreshToken();
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
    useAuthStore.getState().logout();
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Request failed");
  }

  return res.json();
}

let refreshPromise: Promise<boolean> | null = null;

async function tryRefreshToken(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
    })
      .then((r) => r.ok)
      .catch(() => false)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}