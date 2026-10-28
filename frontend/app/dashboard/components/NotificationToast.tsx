"use client";

import { useEffect, useState } from "react";
import { useNotificationStore, type WsNotification } from "@/stores/notifications";
import styles from "./NotificationToast.module.css";

const EVENT_ICONS: Record<string, string> = {
  "upload:complete": "✅",
  "share:created": "🔗",
  "storage:changed": "💾",
};

const EVENT_LABELS: Record<string, string> = {
  "upload:complete": "上传完成",
  "share:created": "分享已创建",
  "storage:changed": "存储空间变更",
};

function ToastItem({ notification, onDismiss }: { notification: WsNotification; onDismiss: () => void }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    requestAnimationFrame(() => setVisible(true));
    const timer = setTimeout(onDismiss, 5000);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  const icon = EVENT_ICONS[notification.event] ?? "🔔";
  const label = EVENT_LABELS[notification.event] ?? notification.event;
  const data = notification.data;

  let detail = "";
  if (notification.event === "upload:complete") {
    detail = data.filename as string;
  } else if (notification.event === "share:created") {
    detail = `提取码: ${data.extract_code}`;
  } else if (notification.event === "storage:changed") {
    const used = (data.used_storage as number) ?? 0;
    const quota = (data.storage_quota as number) ?? 0;
    const pct = quota > 0 ? Math.round((used / quota) * 100) : 0;
    detail = `已用 ${pct}%`;
  }

  return (
    <div className={`${styles.toast} ${visible ? styles.toastVisible : ""}`} onClick={onDismiss}>
      <span className={styles.toastIcon}>{icon}</span>
      <div className={styles.toastContent}>
        <span className={styles.toastLabel}>{label}</span>
        {detail && <span className={styles.toastDetail}>{detail}</span>}
      </div>
      <button className={styles.toastClose} onClick={(e) => { e.stopPropagation(); onDismiss(); }}>×</button>
    </div>
  );
}

export default function NotificationToast() {
  const notifications = useNotificationStore((s) => s.notifications);
  const removeNotification = useNotificationStore((s) => s.removeNotification);
  const [toasts, setToasts] = useState<WsNotification[]>([]);

  useEffect(() => {
    const unread = notifications.filter((n) => !n.read);
    if (unread.length > 0) {
      setToasts((prev) => {
        const existingIds = new Set(prev.map((t) => t.id));
        const fresh = unread.filter((n) => !existingIds.has(n.id));
        return [...prev, ...fresh].slice(-5);
      });
    }
  }, [notifications]);

  return (
    <div className={styles.container}>
      {toasts.map((n) => (
        <ToastItem
          key={n.id}
          notification={n}
          onDismiss={() => {
            removeNotification(n.id);
            setToasts((prev) => prev.filter((t) => t.id !== n.id));
          }}
        />
      ))}
    </div>
  );
}