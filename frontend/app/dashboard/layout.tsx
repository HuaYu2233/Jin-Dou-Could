"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const isLoading = useAuthStore((s) => s.isLoading);
  const error = useAuthStore((s) => s.error);
  const fetchMe = useAuthStore((s) => s.fetchMe);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token && !user) fetchMe();
  }, [user, fetchMe]);

  function handleLogout() {
    localStorage.removeItem("access_token");
    document.cookie = "access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    useAuthStore.getState().logout();
    router.push("/");
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="flex h-14 items-center border-b border-gray-200 bg-white">
        <div className="flex h-full items-center px-4" style={{ width: 200, flexShrink: 0 }}>
          <span className="text-lg font-bold text-gray-700">JinDou Cloud</span>
        </div>
        <div className="flex h-full flex-1 items-center justify-end gap-4 px-6">
          <span className="text-sm text-gray-600">
            {error ? "获取用户失败" : isLoading && !user ? "加载中..." : user ? user.username : ""}
          </span>
          <button
            onClick={handleLogout}
            className="text-sm font-medium text-red-600 hover:text-red-700 transition"
          >
            退出
          </button>
        </div>
      </header>
      <main className="flex-1 min-h-0 overflow-hidden">{children}</main>
    </div>
  );
}