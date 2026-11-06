const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export function getCsrfToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : undefined;
}

export async function fetchWithCsrf(input: string, init: RequestInit = {}): Promise<Response> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  const needsCsrf = !SAFE_METHODS.has(method);
  const csrfToken = needsCsrf ? getCsrfToken() : undefined;
  if (csrfToken) headers.set("X-CSRF-Token", csrfToken);

  const res = await fetch(input, { credentials: "include", ...init, headers });
  if (!needsCsrf || csrfToken || res.status !== 403) return res;

  const errData: { detail?: string } = await res.clone().json().catch(() => ({}));
  const detail = errData.detail ?? "";
  if (!detail.includes("CSRF token missing")) return res;

  const retryToken = getCsrfToken();
  if (!retryToken) return res;

  headers.set("X-CSRF-Token", retryToken);
  return fetch(input, { credentials: "include", ...init, headers });
}