"use client";

import { useState } from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import {
  listAdminBackups,
  triggerAdminBackup,
  deleteAdminBackup,
  downloadAdminBackup,
  type BackupInfo,
} from "@/lib/api/admin";
import { queryKeys } from "@/lib/query/keys";

export function useAdminBackups() {
  const [error, setError] = useState<string | null>(null);
  const [triggering, setTriggering] = useState(false);
  const queryClient = useQueryClient();

  const { data: backups = [], isLoading: loading, refetch } = useQuery({
    queryKey: queryKeys.admin.backups(),
    queryFn: listAdminBackups,
  });

  const triggerMutation = useMutation({
    mutationFn: triggerAdminBackup,
    onMutate: () => setTriggering(true),
    onSuccess: () => refetch(),
    onSettled: () => setTriggering(false),
    onError: (err) => setError(err instanceof Error ? err.message : "触发备份失败"),
  });

  const removeMutation = useMutation({
    mutationFn: deleteAdminBackup,
    onSuccess: (_data, timestamp) => {
      queryClient.setQueryData(queryKeys.admin.backups(), (old: BackupInfo[] | undefined) =>
        old?.filter((b) => b.timestamp !== timestamp)
      );
    },
    onError: (err) => setError(err instanceof Error ? err.message : "删除备份失败"),
  });

  const download = async (timestamp: string, file: string) => {
    try {
      await downloadAdminBackup(timestamp, file);
    } catch (err) {
      setError(err instanceof Error ? err.message : "下载失败");
    }
  };

  return {
    backups,
    loading,
    error,
    triggering,
    setError,
    reload: refetch,
    trigger: () => triggerMutation.mutate(),
    remove: (timestamp: string) => removeMutation.mutate(timestamp),
    download,
  };
}