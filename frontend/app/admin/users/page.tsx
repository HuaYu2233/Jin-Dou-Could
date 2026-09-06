"use client";

import { useState } from "react";
import Pagination from "@/app/dashboard/components/Pagination";
import UserTable from "../components/UserTable";
import QuotaDialog from "../components/QuotaDialog";
import { useAdminUsers } from "../hooks/useAdminUsers";
import type { AdminUserItem } from "@/lib/api/admin";
import styles from "./page.module.css";

export default function AdminUsersPage() {
  const {
    users, page, total, loading, error, PAGE_SIZE,
    setPage, setError, toggleField, updateQuota, removeUser,
  } = useAdminUsers();

  const [editing, setEditing] = useState<AdminUserItem | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSaveQuota(bytes: number) {
    if (!editing) return;
    setSaving(true);
    try {
      await updateQuota(editing.id, bytes);
      setEditing(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(user: AdminUserItem) {
    if (!confirm(`确定删除用户 ${user.username}（${user.email}）吗？此操作不可恢复。`)) return;
    try {
      await removeUser(user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除失败");
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>用户管理</h1>
        <p className={styles.subtitle}>管理用户账号、配额与权限</p>
      </div>

      {error && (
        <div className={styles.errorBar}>
          {error}
          <button className={styles.errorClose} onClick={() => setError(null)}>关闭</button>
        </div>
      )}

      <UserTable
        users={users}
        loading={loading}
        onToggle={toggleField}
        onEditQuota={setEditing}
        onDelete={handleDelete}
      />

      <div className={styles.pagination}>
        <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />
      </div>

      <QuotaDialog
        user={editing}
        saving={saving}
        onSave={handleSaveQuota}
        onClose={() => setEditing(null)}
      />
    </div>
  );
}