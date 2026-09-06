import { client } from "./client";

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