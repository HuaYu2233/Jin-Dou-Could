import { useAuthStore } from "@/stores/auth";


const API_BASE_URL = "http://localhost:8000";  // ⚠️ 【需修改】Docker 环境前端容器内访问后端用 http://backend:8000，但浏览器里执行代码访问宿主机的后端，保持 localhost:8000 即可

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

  if (!skipAuth) {
    const token = localStorage.getItem("access_token");
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE_URL}${endpoint}`, { ...rest, body, headers });

  if (res.status === 401) {
    localStorage.removeItem("access_token");
    document.cookie = "access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
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