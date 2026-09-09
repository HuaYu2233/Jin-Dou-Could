// /Users/zero/project/JinDou-Cloud/frontend/app/dashboard/components/Sidebar.tsx
"use client";

import Link from "next/link";
import type { CategoryId, StorageInfo } from "../types";
import { useTransferStore } from "@/stores/transfers";
import { useTranslation, type TranslationKey } from "@/lib/i18n";
import styles from "./Sidebar.module.css";

interface NavItem {
  id: CategoryId;
  labelKey: TranslationKey;
  icon: string;
  groupKey: TranslationKey;
}

const NAV_ITEMS: NavItem[] = [
  { id: "all", labelKey: "sidebar.all", icon: "📁", groupKey: "sidebar.group.myFiles" },
  { id: "image", labelKey: "sidebar.image", icon: "🖼️", groupKey: "sidebar.group.myFiles" },
  { id: "document", labelKey: "sidebar.document", icon: "📄", groupKey: "sidebar.group.myFiles" },
  { id: "video", labelKey: "sidebar.video", icon: "🎬", groupKey: "sidebar.group.myFiles" },
  { id: "audio", labelKey: "sidebar.audio", icon: "🎵", groupKey: "sidebar.group.myFiles" },
  { id: "other", labelKey: "sidebar.other", icon: "📦", groupKey: "sidebar.group.myFiles" },
  { id: "trash", labelKey: "sidebar.trash", icon: "🗑️", groupKey: "sidebar.group.other" },
  { id: "shares", labelKey: "sidebar.shares", icon: "🔗", groupKey: "sidebar.group.other" },
  { id: "transfers", labelKey: "sidebar.transfers", icon: "⚡", groupKey: "sidebar.group.other" },
];

interface SidebarProps {
  activeCategory: CategoryId;
  onCategoryChange: (id: CategoryId) => void;
  storage: StorageInfo;
  isAdmin?: boolean;
}

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

export default function Sidebar({ activeCategory, onCategoryChange, storage, isAdmin }: SidebarProps) {
  const { t } = useTranslation();
  const groupKeys = [...new Set(NAV_ITEMS.map((i) => i.groupKey))];
  const usagePercent = storage.total > 0 ? (storage.used / storage.total) * 100 : 0;
  const hasActive = useTransferStore((s) => s.hasActive());

  return (
    <nav className={styles.sidebar}>
      <div className={styles.navSection}>
        {groupKeys.map((group) => (
          <div key={group} className={styles.navGroup}>
            <div className={styles.navGroupTitle}>{t(group)}</div>
            {NAV_ITEMS.filter((i) => i.groupKey === group).map((item) => (
              <button
                key={item.id}
                className={`${styles.navItem} ${styles.badge} ${activeCategory === item.id ? styles.navItemActive : ""}`}
                onClick={() => onCategoryChange(item.id)}
              >
                <span className={styles.navIcon}>{item.icon}</span>
                <span className={styles.navLabel}>{t(item.labelKey)}</span>
                {item.id === "transfers" && hasActive && <span className={styles.redDot} />}
              </button>
            ))}
          </div>
        ))}
      </div>
      {isAdmin && (
        <Link href="/admin" className={styles.navItem}>
          <span className={styles.navIcon}>⚙️</span>
          <span className={styles.navLabel}>{t("sidebar.admin")}</span>
        </Link>
      )}
      <div className={styles.storageSection}>
        <div className={styles.storageTitle}>{t("sidebar.storage")}</div>
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