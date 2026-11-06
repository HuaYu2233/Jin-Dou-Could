import { useAuthStore } from "@/stores/auth";
import { API_BASE_URL } from "@/lib/config";
import { refreshAccessToken } from "./refresh";
import { fetchWithCsrf } from "./csrf";
import { isSessionClosed, trackRequest, untrackRequest } from "./session";

export { getCsrfToken } from "./csrf";

type FetchOptions = RequestInit & { skipAuth?: boolean };

const AUTH_EXPIRED_MSG = "AUTH_EXPIRED";
const AUTH_EXPIRED_PARAM = "auth_expired";
const AUTH_FREE_PREFIX = "/api/v1/auth/";

function _isAuthFree(endpoint: string): boolean {
  return endpoint.startsWith(AUTH_FREE_PREFIX);
}

function _navigateToLogin(reason: string) {
  const wasAuthenticated = useAuthStore.getState().isAuthenticated;
  useAuthStore.getState().logout();
  if (!wasAuthenticated || typeof window === "undefined") return;
  const url = new URL("/login", window.location.origin);
  url.searchParams.set(AUTH_EXPIRED_PARAM, reason);
  window.location.href = url.toString();
}

export async function client<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { skipAuth, body, ...rest } = options;

  if (!skipAuth && !_isAuthFree(endpoint) && isSessionClosed()) {
    throw new Error("Unauthorized");
  }

  const isFormData = body instanceof FormData;
  const headers: Record<string, string> = {
    ...(rest.headers as Record<string, string>),
  };
  if (!isFormData && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const controller = new AbortController();
  trackRequest(controller);
  const init: RequestInit = { ...rest, body, headers, signal: controller.signal };

  try {
    const res = await fetchWithCsrf(`${API_BASE_URL}${endpoint}`, init);

    if (res.status === 403) {
      const errData = await res.json().catch(() => ({}));
      const detail: string = errData.detail || "";

      if (detail === "账号已被禁用") {
        _navigateToLogin(AUTH_EXPIRED_MSG);
        throw new Error("账号已被禁用");
      }

      throw new Error(detail || "Forbidden");
    }

    if (res.status === 401 && !skipAuth) {
      if (!useAuthStore.getState().isAuthenticated) {
        throw new Error("Unauthorized");
      }
      const refreshed = await refreshAccessToken();
      if (refreshed) {
        const retryRes = await fetchWithCsrf(`${API_BASE_URL}${endpoint}`, init);
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
  } finally {
    untrackRequest(controller);
  }
}