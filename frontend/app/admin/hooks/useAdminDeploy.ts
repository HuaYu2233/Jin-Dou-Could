"use client";

import { useCallback, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  confirmDeployAction,
  getDeployContainers,
  getDeployStatus,
  getDeployTask,
  getDeployVersions,
  listDeployHistory,
  submitDeployAction,
  type DeployActionRequest,
  type DeployContainers,
  type DeployHistoryItem,
  type DeployStatus,
  type DeployTaskDetail,
  type DeployVersions,
} from "@/lib/api/deploy";
import { queryKeys } from "@/lib/query/keys";

const DEPLOY_DISABLED_MSG = "部署控制台未启用";
const DANGEROUS_ACTIONS = ["deploy", "rollback"];

function isDisabledError(error: unknown): boolean {
  return error instanceof Error && error.message.includes(DEPLOY_DISABLED_MSG);
}

function isRunning(status: string | undefined): boolean {
  return status === "running" || status === "queued";
}

export function isDangerousAction(action: string): boolean {
  return DANGEROUS_ACTIONS.includes(action);
}

export function useAdminDeploy() {
  const queryClient = useQueryClient();
  const [manualTaskId, setManualTaskId] = useState<string | null | undefined>(undefined);
  const [actionError, setActionError] = useState<string | null>(null);

  const statusQuery = useQuery<DeployStatus>({
    queryKey: queryKeys.admin.deploy.status(),
    queryFn: getDeployStatus,
    retry: false,
    refetchInterval: 5000,
  });

  const enabled = statusQuery.data?.enabled === true;
  const statusTaskId = statusQuery.data?.running_task_id ?? null;
  const taskId = manualTaskId === undefined ? statusTaskId : manualTaskId;

  const versionsQuery = useQuery<DeployVersions>({
    queryKey: queryKeys.admin.deploy.versions(),
    queryFn: getDeployVersions,
    enabled,
  });

  const containersQuery = useQuery<DeployContainers>({
    queryKey: queryKeys.admin.deploy.containers(),
    queryFn: getDeployContainers,
    enabled,
    refetchInterval: 15000,
  });

  const historyQuery = useQuery<DeployHistoryItem[]>({
    queryKey: queryKeys.admin.deploy.history(20),
    queryFn: () => listDeployHistory(20),
    enabled,
  });

  const taskQuery = useQuery<DeployTaskDetail>({
    queryKey: queryKeys.admin.deploy.task(taskId ?? ""),
    queryFn: () => getDeployTask(taskId as string),
    enabled: enabled && !!taskId,
    refetchInterval: (query) => (isRunning(query.state.data?.status) ? 2000 : false),
  });

  const refreshAfterFinish = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: queryKeys.admin.deploy.status() });
    queryClient.invalidateQueries({ queryKey: queryKeys.admin.deploy.history(20) });
    queryClient.invalidateQueries({ queryKey: queryKeys.admin.deploy.containers() });
  }, [queryClient]);

  const taskStatus = taskQuery.data?.status;
  useEffect(() => {
    if (taskStatus && !isRunning(taskStatus)) refreshAfterFinish();
  }, [taskStatus, refreshAfterFinish]);

  const submitMutation = useMutation({
    mutationFn: async (payload: DeployActionRequest) => {
      let confirmToken = payload.confirm_token ?? null;
      if (isDangerousAction(payload.action) && !confirmToken) {
        const issued = await confirmDeployAction({
          action: payload.action,
          target: payload.target ?? null,
        });
        confirmToken = issued.confirm_token;
      }
      return submitDeployAction({ ...payload, confirm_token: confirmToken });
    },
    onSuccess: (data) => {
      setActionError(null);
      setManualTaskId(data.task_id);
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.deploy.status() });
    },
    onError: (error: unknown) => {
      setActionError(error instanceof Error ? error.message : "动作提交失败");
    },
  });

  const submitAction = useCallback(
    (action: string, target?: string | null) => {
      submitMutation.mutate({ action, target: target ?? null, params: {} });
    },
    [submitMutation]
  );

  const clearTask = useCallback(() => setManualTaskId(null), []);
  const watchCurrentTask = useCallback(() => {
    if (statusTaskId) setManualTaskId(statusTaskId);
  }, [statusTaskId]);
  const clearActionError = useCallback(() => setActionError(null), []);

  return {
    status: statusQuery.data ?? null,
    versions: versionsQuery.data ?? null,
    containers: containersQuery.data ?? null,
    history: historyQuery.data ?? [],
    task: taskQuery.data ?? null,
    taskId,
    loading: statusQuery.isLoading,
    error: statusQuery.isError ? statusQuery.error : null,
    disabled: statusQuery.isError && isDisabledError(statusQuery.error),
    actionError,
    submitting: submitMutation.isPending,
    submitAction,
    clearTask,
    watchCurrentTask,
    clearActionError,
  };
}