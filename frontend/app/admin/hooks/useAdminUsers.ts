"use client";

import { useState, useEffect, useCallback } from "react";
import {
  listAdminUsers,
  updateAdminUser,
  deleteAdminUser,
  type AdminUserItem,
} from "@/lib/api/admin";

const PAGE_SIZE = 20;

export function useAdminUsers() {
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      setLoading(true);
      try {
        const skip = (page - 1) * PAGE_SIZE;
        const data = await listAdminUsers(skip, PAGE_SIZE);
        if (!active) return;
        setUsers(data);
        if (page === 1) setTotal(data.length);
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : "加载用户失败");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [page]);

  const toggleField = useCallback(
    async (user: AdminUserItem, field: "is_active" | "is_admin") => {
      try {
        const updated = await updateAdminUser(user.id, { [field]: !user[field] });
        setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      } catch (err) {
        setError(err instanceof Error ? err.message : "操作失败");
      }
    },
    []
  );

  const updateQuota = useCallback(async (userId: string, bytes: number) => {
    const updated = await updateAdminUser(userId, { storage_quota: bytes });
    setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
    return updated;
  }, []);

  const removeUser = useCallback(async (user: AdminUserItem) => {
    await deleteAdminUser(user.id);
    setUsers((prev) => prev.filter((u) => u.id !== user.id));
    setTotal((t) => Math.max(0, t - 1));
  }, []);

  return {
    users,
    page,
    total,
    loading,
    error,
    PAGE_SIZE,
    setPage,
    setError,
    toggleField,
    updateQuota,
    removeUser,
  };
}