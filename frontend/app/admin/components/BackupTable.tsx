"use client";

import type { BackupInfo } from "@/lib/api/admin";
import { formatSize, formatDate } from "@/lib/utils/format";
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
  return (
    <div className={styles.wrapper}>
      <div className={styles.toolbar}>
        <span className={styles.count}>共 {backups.length} 个备份</span>
        <button
          className={styles.triggerBtn}
          onClick={onTrigger}
          disabled={triggering}
        >
          {triggering ? "备份中..." : "立即备份"}
        </button>
      </div>

      <div className={styles.scroll}>
        <table className={styles.table}>
          <thead className={styles.head}>
            <tr>
              <th className={styles.th}>备份时间</th>
              <th className={styles.th}>状态</th>
              <th className={styles.th}>加密</th>
              <th className={styles.th}>大小</th>
              <th className={styles.th}>包含文件</th>
              <th className={`${styles.th} ${styles.thRight}`}>操作</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} className={styles.loading}>加载中...</td></tr>
            ) : backups.length === 0 ? (
              <tr><td colSpan={6} className={styles.empty}>暂无备份记录</td></tr>
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
                        {b.status === "success" ? "成功" : b.status === "unknown" ? "未知" : b.status}
                      </span>
                    </td>
                    <td className={styles.td}>
                      {b.encrypted ? (
                        <span className={styles.badgeEncrypted}>已加密</span>
                      ) : (
                        <span className={styles.muted}>未加密</span>
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
                          下载
                        </button>
                      )}
                      <button
                        className={`${styles.actionBtn} ${styles.actionDanger}`}
                        onClick={() => {
                          if (confirm(`确定删除备份 ${b.timestamp} 吗？此操作不可恢复。`)) {
                            onDelete(b.timestamp);
                          }
                        }}
                      >
                        删除
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
