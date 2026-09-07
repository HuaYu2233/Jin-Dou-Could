import { useAuthStore } from "@/stores/auth";
import { API_BASE_URL } from "@/lib/config";

type FetchOptions = RequestInit & { skipAuth?: boolean };

export async function client<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { skipAuth, body, ...rest } = options;

  const isFormData = body instanceof FormData;
  const headers: Record<string, string> = {
    ...(rest.headers as Record<string, string>),
  };
  if (!isFormData && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...rest,
    body,
    headers,
    credentials: "include",
  });

  if (res.status === 401) {
    useAuthStore.getState().logout();
    try {
      await fetch(`${API_BASE_URL}/api/v1/auth/logout`, { method: "POST", credentials: "include" });
    } catch {}
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Request failed");
  }

  return res.json();
}