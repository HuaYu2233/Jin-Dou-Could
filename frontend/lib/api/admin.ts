import { client } from "./client";
import { API_BASE_URL } from "@/lib/config";

export interface AdminStats {
  total_users: number;
  active_users: number;
  admin_users: number;
  total_quota: number;
  total_used: number;
}

export interface AdminUserItem {
  id: string;
  email: string;
  username: string;
  is_active: boolean;
  is_admin: boolean;
  storage_quota: number;
  used_storage: number;
  created_at: string;
}

export interface AdminUserUpdate {
  username?: string;
  storage_quota?: number;
  is_active?: boolean;
  is_admin?: boolean;
}

export async function getAdminStats(): Promise<AdminStats> {
  return client<AdminStats>("/api/v1/admin/stats");
}

export async function listAdminUsers(skip = 0, limit = 20): Promise<AdminUserItem[]> {
  return client<AdminUserItem[]>(`/api/v1/admin/users?skip=${skip}&limit=${limit}`);
}

export async function updateAdminUser(
  userId: string,
  data: AdminUserUpdate
): Promise<AdminUserItem> {
  return client<AdminUserItem>(`/api/v1/admin/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteAdminUser(userId: string): Promise<void> {
  await client<{ detail: string }>(`/api/v1/admin/users/${userId}`, { method: "DELETE" });
}

export interface BackupFile {
  name: string;
  size: number;
  encrypted: boolean;
}

export interface BackupInfo {
  timestamp: string;
  created_at: string;
  status: string;
  encrypted: boolean;
  total_size: number;
  files: BackupFile[];
}

export async function listAdminBackups(): Promise<BackupInfo[]> {
  return client<BackupInfo[]>(`/api/v1/admin/backups`);
}

export async function triggerAdminBackup(): Promise<{ detail: string }> {
  return client<{ detail: string }>(`/api/v1/admin/backups/trigger`, {
    method: "POST",
  });
}

export async function deleteAdminBackup(timestamp: string): Promise<void> {
  await client<{ detail: string }>(`/api/v1/admin/backups/${timestamp}`, {
    method: "DELETE",
  });
}

export async function downloadAdminBackup(timestamp: string, file: string): Promise<void> {
  const url = `${API_BASE_URL}/api/v1/admin/backups/${encodeURIComponent(timestamp)}/download?file=${encodeURIComponent(file)}`;
  const res = await fetch(url, {
    credentials: "include",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `下载失败 (${res.status})`);
  }
  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = file;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(objectUrl);
}