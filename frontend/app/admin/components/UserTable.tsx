"use client";

import type { AdminUserItem } from "@/lib/api/admin";
import { formatSize, formatDate } from "@/lib/utils/format";
import styles from "./UserTable.module.css";

interface UserTableProps {
  users: AdminUserItem[];
  loading: boolean;
  onToggle: (user: AdminUserItem, field: "is_active" | "is_admin") => void;
  onEditQuota: (user: AdminUserItem) => void;
  onDelete: (user: AdminUserItem) => void;
}

export default function UserTable({ users, loading, onToggle, onEditQuota, onDelete }: UserTableProps) {
  return (
    <div className={styles.wrapper}>
      <div className={styles.scroll}>
        <table className={styles.table}>
          <thead className={styles.head}>
            <tr>
              <th className={styles.th}>用户</th>
              <th className={styles.th}>邮箱</th>
              <th className={styles.th}>存储用量</th>
              <th className={`${styles.th} ${styles.thCenter}`}>状态</th>
              <th className={`${styles.th} ${styles.thCenter}`}>管理员</th>
              <th className={styles.th}>注册时间</th>
              <th className={`${styles.th} ${styles.thRight}`}>操作</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr className={styles.row}><td colSpan={7} className={styles.loading}>加载中...</td></tr>
            ) : users.length === 0 ? (
              <tr className={styles.row}><td colSpan={7} className={styles.empty}>暂无用户</td></tr>
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
                        {u.is_active ? "启用" : "禁用"}
                      </button>
                    </td>
                    <td className={`${styles.td} ${styles.tdCenter}`}>
                      <button
                        className={`${styles.badge} ${u.is_admin ? styles.badgeAdmin : styles.badgeUser}`}
                        onClick={() => onToggle(u, "is_admin")}
                      >
                        {u.is_admin ? "管理员" : "普通"}
                      </button>
                    </td>
                    <td className={`${styles.td} ${styles.date}`}>{formatDate(u.created_at)}</td>
                    <td className={`${styles.td} ${styles.tdRight}`}>
                      <button className={`${styles.actionBtn} ${styles.actionPrimary}`} onClick={() => onEditQuota(u)}>
                        配额
                      </button>
                      <button className={`${styles.actionBtn} ${styles.actionDanger}`} onClick={() => onDelete(u)}>
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