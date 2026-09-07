"use client";

import { useState, useEffect, useCallback } from "react";
import {
  listAdminBackups,
  triggerAdminBackup,
  deleteAdminBackup,
  downloadAdminBackup,
  type BackupInfo,
} from "@/lib/api/admin";

export function useAdminBackups() {
  const [backups, setBackups] = useState<BackupInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [triggering, setTriggering] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listAdminBackups();
      setBackups(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载备份失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      setLoading(true);
      try {
        const data = await listAdminBackups();
        if (active) setBackups(data);
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : "加载备份失败");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, []);

  const trigger = useCallback(async () => {
    setTriggering(true);
    try {
      await triggerAdminBackup();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "触发备份失败");
    } finally {
      setTriggering(false);
    }
  }, [load]);

  const remove = useCallback(async (timestamp: string) => {
    try {
      await deleteAdminBackup(timestamp);
      setBackups((prev) => prev.filter((b) => b.timestamp !== timestamp));
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除备份失败");
    }
  }, []);

  const download = useCallback(async (timestamp: string, file: string) => {
    try {
      await downloadAdminBackup(timestamp, file);
    } catch (err) {
      setError(err instanceof Error ? err.message : "下载失败");
    }
  }, []);

  return {
    backups,
    loading,
    error,
    triggering,
    setError,
    reload: load,
    trigger,
    remove,
    download,
  };
}