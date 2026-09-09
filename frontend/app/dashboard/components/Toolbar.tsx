// /Users/zero/project/JinDou-Cloud/frontend/app/dashboard/components/Toolbar.tsx
"use client";

import type { ViewMode } from "../types";
import { useTranslation } from "@/lib/i18n";
import styles from "./Toolbar.module.css";

interface ToolbarProps {
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
  onUpload: () => void;
  onDownload: () => void;
  onDelete: () => void;
  onShare?: () => void;
  onNewFolder?: () => void;
  onMove?: () => void;
  selectedCount: number;
  uploading?: boolean;
  isTrash?: boolean;
  keyword?: string;
  onKeywordChange?: (keyword: string) => void;
  onRestore?: () => void;
  onPurge?: () => void;
}

export default function Toolbar({
  viewMode,
  onViewModeChange,
  onUpload,
  onDownload,
  onDelete,
  onShare,
  onNewFolder,
  onMove,
  selectedCount,
  uploading = false,
  isTrash = false,
  keyword = "",
  onKeywordChange,
  onRestore,
  onPurge,
}: ToolbarProps) {
  const { t } = useTranslation();
  return (
    <div className={styles.toolbar}>
      <div className={styles.actionGroup}>
        {isTrash ? (
          <>
            <button
              className={styles.secondaryBtn}
              onClick={onRestore}
              disabled={selectedCount === 0}
            >
              <svg className={styles.btnIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h10a8 8 0 018 8v2M3 10l4 4m-4-4l4-4" />
              </svg>
              <span className={styles.btnLabel}>{t("toolbar.restore")}</span>
            </button>
            <button
              className={styles.dangerBtn}
              onClick={onPurge}
              disabled={selectedCount === 0}
            >
              <svg className={styles.btnIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              <span className={styles.btnLabel}>{t("toolbar.purge")}</span>
            </button>
          </>
        ) : (
          <>
            <button className={styles.primaryBtn} onClick={onUpload} disabled={uploading} aria-label={t("toolbar.upload")}>
              <svg className={styles.btnIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
              </svg>
              <span className={styles.btnLabel}>{uploading ? t("toolbar.uploading") : t("toolbar.upload")}</span>
            </button>
            <button className={styles.secondaryBtn} onClick={onNewFolder} aria-label={t("toolbar.newFolder")}>
              <svg className={styles.btnIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
              </svg>
              <span className={styles.btnLabel}>{t("toolbar.newFolder")}</span>
            </button>
            <button
              className={styles.secondaryBtn}
              onClick={onMove}
              disabled={selectedCount === 0}
            >
              <svg className={styles.btnIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
              </svg>
              <span className={styles.btnLabel}>{t("toolbar.moveTo")}</span>
            </button>
            <button
              className={styles.secondaryBtn}
              onClick={onDownload}
              disabled={selectedCount !== 1}
            >
              <svg className={styles.btnIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              <span className={styles.btnLabel}>{t("toolbar.download")}</span>
            </button>
            <button
              className={styles.secondaryBtn}
              onClick={onShare}
              disabled={selectedCount === 0}
            >
              <svg className={styles.btnIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
              </svg>
              <span className={styles.btnLabel}>{t("toolbar.share")}</span>
            </button>
            <button
              className={styles.dangerBtn}
              onClick={onDelete}
              disabled={selectedCount === 0}
            >
              <svg className={styles.btnIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              <span className={styles.btnLabel}>{t("toolbar.delete")}</span>
            </button>
          </>
        )}
      </div>
      <div className={styles.searchBox}>
        <svg className={styles.searchIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          className={styles.searchInput}
          type="text"
          placeholder={t("toolbar.searchPlaceholder")}
          value={keyword}
          onChange={(e) => onKeywordChange?.(e.target.value)}
        />
        {keyword && (
          <button className={styles.searchClear} onClick={() => onKeywordChange?.("")}>
            ✕
          </button>
        )}
      </div>
      <div className={styles.rightGroup}>
        <div className={styles.viewSwitch}>
          <button
            className={`${styles.viewBtn} ${viewMode === "list" ? styles.viewBtnActive : ""}`}
            onClick={() => onViewModeChange("list")}
            title={t("toolbar.listView")}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className={styles.btnIcon}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <button
            className={`${styles.viewBtn} ${viewMode === "grid" ? styles.viewBtnActive : ""}`}
            onClick={() => onViewModeChange("grid")}
            title={t("toolbar.gridView")}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className={styles.btnIcon}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}