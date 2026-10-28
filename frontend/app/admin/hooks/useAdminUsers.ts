"use client";

import { useState } from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import {
  listAdminUsers,
  updateAdminUser,
  deleteAdminUser,
  type AdminUserItem,
} from "@/lib/api/admin";
import { queryKeys } from "@/lib/query/keys";

const PAGE_SIZE = 20;

export function useAdminUsers() {
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data: users = [], isLoading: loading } = useQuery({
    queryKey: queryKeys.admin.users(page),
    queryFn: async () => {
      const data = await listAdminUsers((page - 1) * PAGE_SIZE, PAGE_SIZE);
      if (page === 1) setTotal(data.length);
      return data;
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ user, field }: { user: AdminUserItem; field: "is_active" | "is_admin" }) =>
      updateAdminUser(user.id, { [field]: !user[field] }),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.admin.users(page), (old: AdminUserItem[] | undefined) =>
        old?.map((u) => (u.id === updated.id ? updated : u))
      );
    },
    onError: (err) => setError(err instanceof Error ? err.message : "操作失败"),
  });

  const quotaMutation = useMutation({
    mutationFn: ({ userId, bytes }: { userId: string; bytes: number }) =>
      updateAdminUser(userId, { storage_quota: bytes }),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.admin.users(page), (old: AdminUserItem[] | undefined) =>
        old?.map((u) => (u.id === updated.id ? updated : u))
      );
    },
    onError: (err) => setError(err instanceof Error ? err.message : "操作失败"),
  });

  const removeMutation = useMutation({
    mutationFn: (user: AdminUserItem) => deleteAdminUser(user.id),
    onSuccess: (_data, user) => {
      queryClient.setQueryData(queryKeys.admin.users(page), (old: AdminUserItem[] | undefined) =>
        old?.filter((u) => u.id !== user.id)
      );
      setTotal((t) => Math.max(0, t - 1));
    },
    onError: (err) => setError(err instanceof Error ? err.message : "删除失败"),
  });

  return {
    users,
    page,
    total,
    loading,
    error,
    PAGE_SIZE,
    setPage,
    setError,
    toggleField: (user: AdminUserItem, field: "is_active" | "is_admin") => toggleMutation.mutate({ user, field }),
    updateQuota: (userId: string, bytes: number) => quotaMutation.mutateAsync({ userId, bytes }),
    removeUser: (user: AdminUserItem) => removeMutation.mutate(user),
  };
}