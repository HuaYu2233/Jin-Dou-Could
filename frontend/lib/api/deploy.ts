import { client } from "./client";

export interface DeployLastResult {
  task_id: string;
  action: string;
  status: string;
  finished_at: string | null;
}

export interface DeployStatus {
  enabled: boolean;
  runner_online: boolean;
  running_task_id: string | null;
  allowed_actions: string[];
  last_result: DeployLastResult | null;
}

export interface DeployContainerItem {
  service: string;
  container: string;
  state: string;
  health: string | null;
  image: string;
  created: string | null;
  restart_count: number;
  ports: string[];
}

export interface DeployContainers {
  available: boolean;
  collected_at: string | null;
  compose_project: string | null;
  heartbeat_age_seconds: number | null;
  runner_online: boolean;
  services: DeployContainerItem[];
}

export interface DeployVersions {
  app_version: string;
  image_tags: Record<string, string>;
  compose_hash: string | null;
  git_commit: string | null;
  collected_at: string | null;
}

export interface DeployHistoryItem {
  task_id: string;
  action: string;
  target: string | null;
  status: string;
  step: string | null;
  started_at: string | null;
  finished_at: string | null;
  rolled_back: boolean;
  requested_by: string | null;
  error: string | null;
}

export interface DeployTaskDetail {
  task_id: string;
  action: string;
  status: string;
  step: string | null;
  step_index: number;
  total_steps: number;
  pct: number;
  started_at: string | null;
  updated_at: string | null;
  finished_at: string | null;
  logs: string[];
  error: string | null;
}

export interface DeployActionRequest {
  action: string;
  target?: string | null;
  params?: Record<string, unknown>;
  confirm_token?: string | null;
}

export interface DeployActionResponse {
  task_id: string;
  status: string;
}

export interface DeployConfirmRequest {
  action: string;
  target?: string | null;
}

export interface DeployConfirmResponse {
  confirm_token: string;
  expires_in: number;
}

export async function getDeployStatus(): Promise<DeployStatus> {
  return client<DeployStatus>("/api/v1/admin/deploy/status");
}

export async function getDeployContainers(): Promise<DeployContainers> {
  return client<DeployContainers>("/api/v1/admin/deploy/containers");
}

export async function getDeployVersions(): Promise<DeployVersions> {
  return client<DeployVersions>("/api/v1/admin/deploy/versions");
}

export async function listDeployHistory(limit = 20): Promise<DeployHistoryItem[]> {
  return client<DeployHistoryItem[]>(`/api/v1/admin/deploy/history?limit=${limit}`);
}

export async function submitDeployAction(
  payload: DeployActionRequest
): Promise<DeployActionResponse> {
  return client<DeployActionResponse>("/api/v1/admin/deploy/actions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function confirmDeployAction(
  payload: DeployConfirmRequest
): Promise<DeployConfirmResponse> {
  return client<DeployConfirmResponse>("/api/v1/admin/deploy/confirm", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getDeployTask(taskId: string): Promise<DeployTaskDetail> {
  return client<DeployTaskDetail>(`/api/v1/admin/deploy/tasks/${taskId}`);
}