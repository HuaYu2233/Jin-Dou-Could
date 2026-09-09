"use client";

import type { AdminUserItem } from "@/lib/api/admin";
import { formatSize, formatDate } from "@/lib/utils/format";
import { useTranslation } from "@/lib/i18n";
import styles from "./UserTable.module.css";

interface UserTableProps {
  users: AdminUserItem[];
  loading: boolean;
  onToggle: (user: AdminUserItem, field: "is_active" | "is_admin") => void;
  onEditQuota: (user: AdminUserItem) => void;
  onDelete: (user: AdminUserItem) => void;
}

export default function UserTable({ users, loading, onToggle, onEditQuota, onDelete }: UserTableProps) {
  const { t } = useTranslation();
  return (
    <div className={styles.wrapper}>
      <div className={styles.scroll}>
        <table className={styles.table}>
          <thead className={styles.head}>
            <tr>
              <th className={styles.th}>{t("admin.users.col.user")}</th>
              <th className={styles.th}>{t("admin.users.col.email")}</th>
              <th className={styles.th}>{t("admin.users.col.storage")}</th>
              <th className={`${styles.th} ${styles.thCenter}`}>{t("admin.users.col.status")}</th>
              <th className={`${styles.th} ${styles.thCenter}`}>{t("admin.users.col.admin")}</th>
              <th className={styles.th}>{t("admin.users.col.registeredAt")}</th>
              <th className={`${styles.th} ${styles.thRight}`}>{t("admin.users.col.actions")}</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr className={styles.row}><td colSpan={7} className={styles.loading}>{t("admin.overview.loading")}</td></tr>
            ) : users.length === 0 ? (
              <tr className={styles.row}><td colSpan={7} className={styles.empty}>{t("admin.users.empty")}</td></tr>
            ) : (
              users.map((u) => {
                const percent = u.storage_quota > 0 ? (u.used_storage / u.storage_quota) * 100 : 0;
                const isDanger = percent > 90;
                return (
                  <tr key={u.id} className={styles.row}>
                    <td className={`${styles.td} ${styles.username}`}>{u.username}</td>
                    <td className={styles.td}>{u.email}</td>
                    <td className={styles.td}>
                      <div className={styles.usageText}>
                        {formatSize(u.used_storage)} / {formatSize(u.storage_quota)}
                      </div>
                      <div className={styles.usageBar}>
                        <div
                          className={`${styles.usageFill} ${isDanger ? styles.usageFillDanger : styles.usageFillNormal}`}
                          style={{ width: `${Math.min(percent, 100)}%` }}
                        />
                      </div>
                    </td>
                    <td className={`${styles.td} ${styles.tdCenter}`}>
                      <button
                        className={`${styles.badge} ${u.is_active ? styles.badgeActive : styles.badgeInactive}`}
                        onClick={() => onToggle(u, "is_active")}
                      >
                        {u.is_active ? t("admin.users.status.active") : t("admin.users.status.inactive")}
                      </button>
                    </td>
                    <td className={`${styles.td} ${styles.tdCenter}`}>
                      <button
                        className={`${styles.badge} ${u.is_admin ? styles.badgeAdmin : styles.badgeUser}`}
                        onClick={() => onToggle(u, "is_admin")}
                      >
                        {u.is_admin ? t("admin.users.role.admin") : t("admin.users.role.user")}
                      </button>
                    </td>
                    <td className={`${styles.td} ${styles.date}`}>{formatDate(u.created_at)}</td>
                    <td className={`${styles.td} ${styles.tdRight}`}>
                      <button className={`${styles.actionBtn} ${styles.actionPrimary}`} onClick={() => onEditQuota(u)}>
                        {t("admin.users.action.quota")}
                      </button>
                      <button className={`${styles.actionBtn} ${styles.actionDanger}`} onClick={() => onDelete(u)}>
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