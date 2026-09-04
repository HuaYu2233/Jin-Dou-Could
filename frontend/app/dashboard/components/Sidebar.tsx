// /Users/zero/project/JinDou-Cloud/frontend/app/dashboard/components/Sidebar.tsx
"use client";

import type { CategoryId, StorageInfo } from "../types";
import { useTransferStore } from "@/stores/transfers";
import styles from "./Sidebar.module.css";

interface NavItem {
  id: CategoryId;
  label: string;
  icon: string;
  group: string;
}

const NAV_ITEMS: NavItem[] = [
  { id: "all", label: "全部", icon: "📁", group: "我的文件" },
  { id: "image", label: "图片", icon: "🖼️", group: "我的文件" },
  { id: "document", label: "文档", icon: "📄", group: "我的文件" },
  { id: "video", label: "视频", icon: "🎬", group: "我的文件" },
  { id: "audio", label: "音乐", icon: "🎵", group: "我的文件" },
  { id: "other", label: "其他", icon: "📦", group: "我的文件" },
  { id: "trash", label: "回收站", icon: "🗑️", group: "其他" },
  { id: "shares", label: "我的分享", icon: "🔗", group: "其他" },
  { id: "transfers", label: "传输", icon: "⚡", group: "其他" },
];

interface SidebarProps {
  activeCategory: CategoryId;
  onCategoryChange: (id: CategoryId) => void;
  storage: StorageInfo;
}

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

export default function Sidebar({ activeCategory, onCategoryChange, storage }: SidebarProps) {
  const groups = [...new Set(NAV_ITEMS.map((i) => i.group))];
  const usagePercent = storage.total > 0 ? (storage.used / storage.total) * 100 : 0;
  const hasActive = useTransferStore((s) => s.hasActive());

  return (
    <nav className={styles.sidebar}>
      <div className={styles.navSection}>
        {groups.map((group) => (
          <div key={group} className={styles.navGroup}>
            <div className={styles.navGroupTitle}>{group}</div>
            {NAV_ITEMS.filter((i) => i.group === group).map((item) => (
              <button
                key={item.id}
                className={`${styles.navItem} ${styles.badge} ${activeCategory === item.id ? styles.navItemActive : ""}`}
                onClick={() => onCategoryChange(item.id)}
              >
                <span className={styles.navIcon}>{item.icon}</span>
                <span className={styles.navLabel}>{item.label}</span>
                {item.id === "transfers" && hasActive && <span className={styles.redDot} />}
              </button>
            ))}
          </div>
        ))}
      </div>
      <div className={styles.storageSection}>
        <div className={styles.storageTitle}>存储空间</div>
        <div className={styles.storageBar}>
          <div className={styles.storageBarFill} style={{ width: `${usagePercent}%` }} />
        </div>
        <div className={styles.storageText}>
          {formatSize(storage.used)} / {formatSize(storage.total)}
        </div>
      </div>
    </nav>
  );
}