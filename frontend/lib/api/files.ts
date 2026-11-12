// /Users/zero/project/JinDou-Cloud/frontend/lib/api/files.ts
import { client } from "./client";
import { fetchWithCsrf, getCsrfToken } from "./csrf";

export interface FileItem {
  id: string;
  filename: string;
  size: number;
  mime_type: string;
  file_type: string;
  status: string;
  thumbnail_key: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface FileListResponse {
  items: FileItem[];
  total: number;
  next_cursor?: string;
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
  fileType?: string,
  cursor?: string,
  allFolders = false
): Promise<FileListResponse> {
  const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  if (fileType && fileType !== "all") params.set("file_type", fileType);
  if (cursor) params.set("cursor", cursor);
  if (allFolders) params.set("all_folders", "true");
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

import { API_BASE_URL } from "@/lib/config";

export function uploadFileWithProgress(
  file: File,
  folderId: string | undefined,
  onProgress: (loaded: number, total: number) => void,
  signal?: AbortSignal
): Promise<FileUploadResponse> {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append("file", file);
    const params = new URLSearchParams();
    if (folderId) params.set("folder_id", folderId);
    const query = params.toString();
    const url = `${API_BASE_URL}/api/v1/files${query ? `?${query}` : ""}`;

    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.withCredentials = true;

    const csrfToken = getCsrfToken();
    if (csrfToken) xhr.setRequestHeader("X-CSRF-Token", csrfToken);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        onProgress(e.loaded, e.total);
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const data = JSON.parse(xhr.responseText) as FileUploadResponse;
          onProgress(file.size, file.size);
          resolve(data);
        } catch {
          reject(new Error("响应解析失败"));
        }
      } else if (xhr.status === 401) {
        window.location.href = "/login";
        reject(new Error("Unauthorized"));
      } else {
        try {
          const err = JSON.parse(xhr.responseText);
          reject(new Error(err.detail || "上传失败"));
        } catch {
          reject(new Error(`上传失败 (${xhr.status})`));
        }
      }
    };

    xhr.onerror = () => reject(new Error("网络错误"));
    xhr.ontimeout = () => reject(new Error("请求超时"));

    if (signal) {
      if (signal.aborted) {
        xhr.abort();
        reject(new Error("已取消"));
        return;
      }
      signal.addEventListener("abort", () => {
        xhr.abort();
        reject(new Error("已取消"));
      }, { once: true });
    }

    xhr.send(formData);
  });
}

export async function getFileDownloadUrl(id: string): Promise<string> {
  const { url } = await client<{ url: string }>(`/api/v1/files/${id}/download`);
  return url;
}

export async function getFilePreviewUrl(id: string): Promise<string> {
  const { url } = await client<{ url: string }>(`/api/v1/files/${id}/preview`);
  return url;
}

export async function getFileThumbnailUrl(id: string): Promise<{ url: string; has_thumbnail: boolean }> {
  return client<{ url: string; has_thumbnail: boolean }>(`/api/v1/files/${id}/thumbnail`);
}

export async function downloadFileWithProgress(
  id: string,
  onProgress: (loaded: number, total: number) => void,
  signal?: AbortSignal
): Promise<void> {
  const url = await getFileDownloadUrl(id);
  if (signal?.aborted) throw new Error("已取消");

  const link = document.createElement("a");
  link.href = url;
  link.download = "";
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}



export async function deleteFile(id: string): Promise<void> {
  return client<void>(`/api/v1/files/${id}`, { method: "DELETE" });
}

export async function searchFiles(keyword: string, skip = 0, limit = 20, cursor?: string): Promise<FileListResponse> {
  const params = new URLSearchParams({ keyword, skip: String(skip), limit: String(limit) });
  if (cursor) params.set("cursor", cursor);
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

export interface FolderTrashItem {
  id: string;
  owner_id: string;
  parent_id: string | null;
  name: string;
  deleted_at: string;
  created_at: string;
  updated_at: string;
}

export interface FolderTrashListResponse {
  items: FolderTrashItem[];
  total: number;
}

export async function listTrashFolders(skip = 0, limit = 20): Promise<FolderTrashListResponse> {
  const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  return client<FolderTrashListResponse>(`/api/v1/folders/trash?${params}`);
}

export async function restoreFolder(folderId: string): Promise<void> {
  return client<void>(`/api/v1/folders/${folderId}/restore`, { method: "POST" });
}

export async function purgeFolder(folderId: string): Promise<void> {
  return client<void>(`/api/v1/folders/${folderId}/purge`, { method: "DELETE" });
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
  const res = await fetch(`${API_BASE_URL}/api/v1/shares/public/${token}`);
  if (!res.ok) throw new Error("分享不存在或已过期");
  return res.json();
}

export async function verifyShare(
  token: string,
  extractCode: string
): Promise<{ share_token: string; filename: string; file_size: number; file_type: string }> {
  const res = await fetchWithCsrf(
    `${API_BASE_URL}/api/v1/shares/public/${token}/verify`,
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
): Promise<void> {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/shares/public/${token}/download?extract_code=${encodeURIComponent(extractCode)}`
  );
  if (!res.ok) throw new Error("下载失败");
  const { url } = await res.json();
  const a = document.createElement("a");
  a.href = url;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

export interface MultipartInitResult {
  upload_id: string;
  storage_key: string;
  part_size: number;
  total_parts: number;
}

export interface MultipartPartResult {
  part_number: number;
  etag: string;
}

export interface MultipartPartInfo {
  part_number: number;
  etag: string;
}

export async function multipartInit(
  filename: string,
  mimeType: string,
  totalSize: number,
  folderId?: string
): Promise<MultipartInitResult> {
  return client<MultipartInitResult>("/api/v1/files/multipart/init", {
    method: "POST",
    body: JSON.stringify({
      filename,
      mime_type: mimeType,
      total_size: totalSize,
      folder_id: folderId ?? null,
    }),
  });
}

export async function multipartUploadPart(
  storageKey: string,
  uploadId: string,
  partNumber: number,
  data: Blob
): Promise<MultipartPartResult> {
  const formData = new FormData();
  formData.append("part", data);
  const params = new URLSearchParams({
    storage_key: storageKey,
    upload_id: uploadId,
    part_number: String(partNumber),
  });
  return client<MultipartPartResult>(`/api/v1/files/multipart/part?${params}`, {
    method: "POST",
    body: formData,
  });
}

export async function multipartComplete(
  uploadId: string,
  storageKey: string,
  filename: string,
  mimeType: string,
  totalSize: number,
  parts: MultipartPartInfo[],
  folderId?: string
): Promise<FileUploadResponse> {
  return client<FileUploadResponse>("/api/v1/files/multipart/complete", {
    method: "POST",
    body: JSON.stringify({
      upload_id: uploadId,
      storage_key: storageKey,
      filename,
      mime_type: mimeType,
      total_size: totalSize,
      folder_id: folderId ?? null,
      parts: parts.map((p) => ({ part_number: p.part_number, etag: p.etag })),
    }),
  });
}

export async function multipartAbort(
  storageKey: string,
  uploadId: string
): Promise<{ message: string }> {
  const params = new URLSearchParams({
    storage_key: storageKey,
    upload_id: uploadId,
  });
  return client<{ message: string }>(`/api/v1/files/multipart/abort?${params}`, {
    method: "POST",
  });
}

export interface MultipartUploadProgress {
  loaded: number;
  total: number;
}

export async function multipartUploadFile(
  file: File,
  folderId?: string,
  onProgress?: (progress: MultipartUploadProgress) => void,
  signal?: AbortSignal
): Promise<FileUploadResponse> {
  const { upload_id, storage_key, part_size, total_parts } = await multipartInit(
    file.name,
    file.type || "application/octet-stream",
    file.size,
    folderId
  );

  const completedParts: MultipartPartInfo[] = [];
  let loaded = 0;

  for (let i = 0; i < total_parts; i++) {
    if (signal?.aborted) {
      await multipartAbort(storage_key, upload_id).catch(() => {});
      throw new Error("已取消");
    }

    const start = i * part_size;
    const end = Math.min(start + part_size, file.size);
    const blob = file.slice(start, end);

    const { part_number, etag } = await multipartUploadPart(
      storage_key,
      upload_id,
      i + 1,
      blob
    );

    completedParts.push({ part_number, etag });
    loaded += end - start;
    onProgress?.({ loaded, total: file.size });
  }

  return multipartComplete(
    upload_id,
    storage_key,
    file.name,
    file.type || "application/octet-stream",
    file.size,
    completedParts,
    folderId
  );
}