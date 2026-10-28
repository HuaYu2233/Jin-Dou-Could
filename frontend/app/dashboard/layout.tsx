"use client";

import Header from "./components/Header";
import NotificationToast from "./components/NotificationToast";
import { useWebSocket } from "@/lib/hooks/useWebSocket";
import { useNotificationStore } from "@/stores/notifications";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  useWebSocket();
  const unreadCount = useNotificationStore((s) => s.unreadCount);

  return (
    <div className="flex h-screen flex-col">
      <Header extra={
        unreadCount > 0 ? (
          <span className="inline-flex items-center justify-center h-5 min-w-[20px] px-1.5 rounded-full bg-red-500 text-white text-xs font-bold">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        ) : null
      } />
      <main className="flex-1 min-h-0 overflow-hidden">{children}</main>
      <NotificationToast />
    </div>
  );
}