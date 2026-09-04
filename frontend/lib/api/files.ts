// /Users/zero/project/JinDou-Cloud/frontend/lib/api/files.ts
import { client } from "./client";

export interface FileItem {
  id: string;
  filename: string;
  size: number;
  mime_type: string;
  file_type: string;
  status: string;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface FileListResponse {
  items: FileItem[];
  total: number;
}

export interface FileUploadResponse {
  id: string;
  filename: string;
  size: number;
  mime_type: string;
  file_type: string;
  status: string;
}

export async function listFiles(
  skip = 0,
  limit = 20,
  fileType?: string
): Promise<FileListResponse> {
  const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  if (fileType && fileType !== "all") params.set("file_type", fileType);
  return client<FileListResponse>(`/api/v1/files?${params}`);
}

export async function uploadFile(file: File, folderId?: string): Promise<FileUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const params = new URLSearchParams();
  if (folderId) params.set("folder_id", folderId);
  const query = params.toString();
  return client<FileUploadResponse>(`/api/v1/files${query ? `?${query}` : ""}`, {
    method: "POST",
    body: formData,
  });
}

export async function downloadFile(id: string): Promise<Blob> {
  const token = localStorage.getItem("access_token");
  const res = await fetch(`http://localhost:8000/api/v1/files/${id}/download`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error("下载失败");
  return res.blob();
}

export async function getFileBlob(id: string): Promise<Blob> {
  const token = localStorage.getItem("access_token");
  const res = await fetch(`http://localhost:8000/api/v1/files/${id}/preview`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error("获取文件失败");
  return res.blob();
}

export async function deleteFile(id: string): Promise<void> {
  return client<void>(`/api/v1/files/${id}`, { method: "DELETE" });
}

export async function searchFiles(keyword: string, skip = 0, limit = 20): Promise<FileListResponse> {
  const params = new URLSearchParams({ keyword, skip: String(skip), limit: String(limit) });
  return client<FileListResponse>(`/api/v1/files/search?${params}`);
}

export async function moveFiles(fileIds: string[], targetFolderId?: string): Promise<{ message: string; moved: number }> {
  return client<{ message: string; moved: number }>("/api/v1/files/move", {
    method: "POST",
    body: JSON.stringify({ file_ids: fileIds, target_folder_id: targetFolderId ?? null }),
  });
}

export async function listTrashFiles(skip = 0, limit = 20): Promise<FileListResponse> {
  const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  return client<FileListResponse>(`/api/v1/files/trash?${params}`);
}

export async function restoreFile(id: string): Promise<void> {
  return client<void>(`/api/v1/files/${id}/restore`, { method: "POST" });
}

export async function purgeFile(id: string): Promise<void> {
  return client<void>(`/api/v1/files/${id}/purge`, { method: "DELETE" });
}

export interface FolderItem {
  id: string;
  owner_id: string;
  parent_id: string | null;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface FolderBreadcrumb {
  id: string | null;
  name: string;
  path: string;
}

export interface FolderListResponse {
  folders: FolderItem[];
  files: FileItem[];
  breadcrumbs: FolderBreadcrumb[];
  total_files: number;
}

export async function createFolder(name: string, parentId?: string): Promise<FolderItem> {
  return client<FolderItem>("/api/v1/folders", {
    method: "POST",
    body: JSON.stringify({ name, parent_id: parentId ?? null }),
  });
}

export async function listFolderContents(folderId?: string, skip = 0, limit = 50): Promise<FolderListResponse> {
  const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  if (folderId) params.set("folder_id", folderId);
  return client<FolderListResponse>(`/api/v1/folders?${params}`);
}

export async function listRootFolders(): Promise<FolderItem[]> {
  const res = await listFolderContents(undefined, 0, 200);
  return res.folders;
}

export async function renameFolder(folderId: string, name: string): Promise<FolderItem> {
  return client<FolderItem>(`/api/v1/folders/${folderId}`, {
    method: "PUT",
    body: JSON.stringify({ name }),
  });
}

export async function deleteFolder(folderId: string): Promise<void> {
  return client<void>(`/api/v1/folders/${folderId}`, { method: "DELETE" });
}

export interface ShareCreateResponse {
  id: string;
  share_token: string;
  extract_code: string;
  expires_at: string | null;
  created_at: string;
}

export interface ShareItem {
  id: string;
  file_id: string;
  share_token: string;
  extract_code: string;
  expires_at: string | null;
  views: number;
  created_at: string;
  filename: string;
  file_size: number;
}

export interface ShareListResponse {
  items: ShareItem[];
  total: number;
}

export interface ShareInfo {
  share_token: string;
  filename: string;
  file_size: number;
  file_type: string;
  has_code: boolean;
  expires_at: string | null;
}

export async function createShare(
  fileId: string,
  expiresDays?: number
): Promise<ShareCreateResponse> {
  return client<ShareCreateResponse>(`/api/v1/shares/${fileId}`, {
    method: "POST",
    body: JSON.stringify({ expires_days: expiresDays ?? null }),
  });
}

export async function listShares(
  skip = 0,
  limit = 20
): Promise<ShareListResponse> {
  const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  return client<ShareListResponse>(`/api/v1/shares?${params}`);
}

export async function deleteShare(id: string): Promise<void> {
  return client<void>(`/api/v1/shares/${id}`, { method: "DELETE" });
}

export async function getShareInfo(token: string): Promise<ShareInfo> {
  const res = await fetch(`http://localhost:8000/api/v1/shares/public/${token}`);
  if (!res.ok) throw new Error("分享不存在或已过期");
  return res.json();
}

export async function verifyShare(
  token: string,
  extractCode: string
): Promise<{ share_token: string; filename: string; file_size: number; file_type: string }> {
  const res = await fetch(
    `http://localhost:8000/api/v1/shares/public/${token}/verify`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ extract_code: extractCode }),
    }
  );
  if (!res.ok) throw new Error("提取码错误或分享已过期");
  return res.json();
}

export async function downloadSharedFile(
  token: string,
  extractCode: string
): Promise<Blob> {
  const res = await fetch(
    `http://localhost:8000/api/v1/shares/public/${token}/download?extract_code=${encodeURIComponent(extractCode)}`
  );
  if (!res.ok) throw new Error("下载失败");
  return res.blob();
}