export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const APP_CONFIG = {
  apiBaseUrl: API_BASE_URL,
  pageSize: 20,
  debounceMs: 300,
} as const;
