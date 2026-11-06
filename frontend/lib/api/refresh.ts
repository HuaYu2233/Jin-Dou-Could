import { API_BASE_URL } from "@/lib/config";
import { fetchWithCsrf } from "./csrf";

let refreshPromise: Promise<boolean> | null = null;

export async function refreshAccessToken(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = fetchWithCsrf(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
    })
      .then((r) => r.ok)
      .catch(() => false)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}