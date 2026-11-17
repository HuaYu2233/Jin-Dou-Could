"use client";

import { useCallback, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  generateEnvValues,
  getEnvConfig,
  saveEnvConfig,
  type EnvConfigResponse,
} from "@/lib/api/envConfig";
import { queryKeys } from "@/lib/query/keys";

export function useAdminEnvConfig() {
  const queryClient = useQueryClient();
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedBackup, setSavedBackup] = useState<string | null>(null);

  const configQuery = useQuery<EnvConfigResponse>({
    queryKey: queryKeys.admin.envConfig.config(),
    queryFn: getEnvConfig,
    retry: false,
  });

  const saveMutation = useMutation({
    mutationFn: saveEnvConfig,
    onSuccess: (data) => {
      setSaveError(null);
      setSavedBackup(data.backup);
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.envConfig.config() });
    },
    onError: (error: unknown) => {
      setSaveError(error instanceof Error ? error.message : "保存失败");
    },
  });

  const generateMutation = useMutation({
    mutationFn: generateEnvValues,
  });

  const save = useCallback(
    (values: Record<string, string>) => saveMutation.mutateAsync(values),
    [saveMutation]
  );

  const generate = useCallback(
    () => generateMutation.mutateAsync(),
    [generateMutation]
  );

  const clearMessages = useCallback(() => {
    setSaveError(null);
    setSavedBackup(null);
  }, []);

  return {
    config: configQuery.data ?? null,
    loading: configQuery.isLoading,
    error: configQuery.isError ? configQuery.error : null,
    disabled: (configQuery.data && configQuery.data.enabled === false) || configQuery.isError,
    saveError,
    savedBackup,
    saving: saveMutation.isPending,
    generating: generateMutation.isPending,
    save,
    generate,
    clearMessages,
  };
}