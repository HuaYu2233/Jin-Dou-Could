"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import Header from "./components/Header";
import NotificationToast from "./components/NotificationToast";
import { useWebSocket } from "@/lib/hooks/useWebSocket";
import { useAuthStore } from "@/stores/auth";
import { useNotificationStore } from "@/stores/notifications";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  useWebSocket();
  const router = useRouter();
  const queryClient = useQueryClient();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isLoading = useAuthStore((s) => s.isLoading);
  const unreadCount = useNotificationStore((s) => s.unreadCount);

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      queryClient.clear();
      useNotificationStore.getState().clearAll();
      router.replace("/login");
    }
  }, [isAuthenticated, isLoading, router, queryClient]);

  return (
    <div className="flex h-screen flex-col">
      <Header extra={
        unreadCount > 0 ? (
          <span className="inline-flex items-center justify-center h-5 min-w-[20px] px-1.5 rounded-full bg-danger text-white text-xs font-bold">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        ) : null
      } />
      <main className="flex-1 min-h-0 overflow-hidden">{children}</main>
      <NotificationToast />
    </div>
  );
}