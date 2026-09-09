"use client";

import type { BackupInfo } from "@/lib/api/admin";
import { formatSize, formatDate } from "@/lib/utils/format";
import { useTranslation } from "@/lib/i18n";
import styles from "./BackupTable.module.css";

interface BackupTableProps {
  backups: BackupInfo[];
  loading: boolean;
  triggering: boolean;
  onTrigger: () => void;
  onDownload: (timestamp: string, file: string) => void;
  onDelete: (timestamp: string) => void;
}

export default function BackupTable({
  backups,
  loading,
  triggering,
  onTrigger,
  onDownload,
  onDelete,
}: BackupTableProps) {
  const { t } = useTranslation();
  return (
    <div className={styles.wrapper}>
      <div className={styles.toolbar}>
        <span className={styles.count}>{t("admin.backups.count", { count: backups.length })}</span>
        <button
          className={styles.triggerBtn}
          onClick={onTrigger}
          disabled={triggering}
        >
          {triggering ? t("admin.backups.triggering") : t("admin.backups.trigger")}
        </button>
      </div>

      <div className={styles.scroll}>
        <table className={styles.table}>
          <thead className={styles.head}>
            <tr>
              <th className={styles.th}>{t("admin.backups.col.time")}</th>
              <th className={styles.th}>{t("admin.backups.col.status")}</th>
              <th className={styles.th}>{t("admin.backups.col.encrypted")}</th>
              <th className={styles.th}>{t("admin.backups.col.size")}</th>
              <th className={styles.th}>{t("admin.backups.col.files")}</th>
              <th className={`${styles.th} ${styles.thRight}`}>{t("admin.backups.col.actions")}</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} className={styles.loading}>{t("admin.overview.loading")}</td></tr>
            ) : backups.length === 0 ? (
              <tr><td colSpan={6} className={styles.empty}>{t("admin.backups.empty")}</td></tr>
            ) : (
              backups.map((b) => {
                const pgFile = b.files.find((f) => f.name.endsWith(".gz") || f.name.endsWith(".gpg"));
                return (
                  <tr key={b.timestamp} className={styles.row}>
                    <td className={`${styles.td} ${styles.date}`}>
                      {formatDate(b.created_at)}
                    </td>
                    <td className={styles.td}>
                      <span className={`${styles.badge} ${b.status === "success" ? styles.badgeOk : styles.badgeWarn}`}>
                        {b.status === "success" ? t("admin.backups.status.success") : b.status === "unknown" ? t("admin.backups.status.unknown") : b.status}
                      </span>
                    </td>
                    <td className={styles.td}>
                      {b.encrypted ? (
                        <span className={styles.badgeEncrypted}>{t("admin.backups.encrypted.yes")}</span>
                      ) : (
                        <span className={styles.muted}>{t("admin.backups.encrypted.no")}</span>
                      )}
                    </td>
                    <td className={styles.td}>{formatSize(b.total_size)}</td>
                    <td className={`${styles.td} ${styles.files}`}>
                      {b.files.map((f) => f.name).join("，") || "-"}
                    </td>
                    <td className={`${styles.td} ${styles.tdRight}`}>
                      {pgFile && (
                        <button
                          className={`${styles.actionBtn} ${styles.actionPrimary}`}
                          onClick={() => onDownload(b.timestamp, pgFile.name)}
                        >
                          {t("toolbar.download")}
                        </button>
                      )}
                      <button
                        className={`${styles.actionBtn} ${styles.actionDanger}`}
                        onClick={() => {
                          if (confirm(t("admin.backups.deleteConfirm", { timestamp: b.timestamp }))) {
                            onDelete(b.timestamp);
                          }
                        }}
                      >
                        {t("admin.users.action.delete")}
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}