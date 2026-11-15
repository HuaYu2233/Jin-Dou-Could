import { client } from "./client";
import { API_BASE_URL } from "@/lib/config";

export interface LanRoom {
  room_id: string;
  code: string;
  join_url: string;
  title: string | null;
  has_password: boolean;
  max_file_size: number;
  max_total_size: number;
  used_size: number;
  file_count: number;
  expires_at: string;
  closed_at: string | null;
}

export interface LanJoinResult {
  room_token: string;
  room_id: string;
  title: string | null;
  max_file_size: number;
  max_total_size: number;
  used_size: number;
  file_count: number;
  expires_at: string;
  same_subnet_hint: boolean;
}

export interface LanFileItem {
  id: string;
  filename: string;
  size: number;
  mime_type: string;
  file_type: string;
  uploader: string;
  created_at: string;
}

export interface LanFileList {
  items: LanFileItem[];
  used_size: number;
  max_total_size: number;
  file_count: number;
}

export interface LanMultipartInit {
  upload_id: string;
  storage_key: string;
  part_size: number;
  total_parts: number;
}

export const LAN_PART_SIZE = 16 * 1024 * 1024;
export const LAN_CHUNK_THRESHOLD = 32 * 1024 * 1024;

async function lanPublicFetch<T>(path: string, init: RequestInit = {}, roomToken?: string | null): Promise<T> {
  const headers = new Headers(init.headers);
  if (roomToken) headers.set("X-Room-Token", roomToken);
  const res = await fetch(`${API_BASE_URL}${path}`, { credentials: "include", ...init, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || `请求失败 (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export async function createLanRoom(body: {
  title?: string | null;
  password?: string | null;
  ttl_hours?: number | null;
}): Promise<LanRoom> {
  return client<LanRoom>("/api/v1/lan-transfer/rooms", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getLanRoom(roomId: string): Promise<LanRoom> {
  return client<LanRoom>(`/api/v1/lan-transfer/rooms/${roomId}`);
}

export async function closeLanRoom(roomId: string): Promise<{ message: string }> {
  return client<{ message: string }>(`/api/v1/lan-transfer/rooms/${roomId}/close`, { method: "POST" });
}

export async function sendDriveFilesToRoom(
  roomId: string,
  fileIds: string[]
): Promise<{ items: LanFileItem[]; used_size: number; file_count: number }> {
  return client<{ items: LanFileItem[]; used_size: number; file_count: number }>(
    `/api/v1/lan-transfer/rooms/${roomId}/send-from-files`,
    { method: "POST", body: JSON.stringify({ file_ids: fileIds }) }
  );
}

export async function joinLanRoom(code: string, password?: string | null): Promise<LanJoinResult> {
  return lanPublicFetch<LanJoinResult>(`/api/v1/lan-transfer/public/rooms/${code}/join`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password: password || null }),
  });
}

export async function listLanRoomFiles(roomId: string, roomToken?: string | null): Promise<LanFileList> {
  return lanPublicFetch<LanFileList>(`/api/v1/lan-transfer/public/rooms/${roomId}/files`, {}, roomToken);
}

export async function deleteLanRoomFile(
  roomId: string,
  roomToken: string | null,
  fileId: string
): Promise<{ message: string }> {
  return lanPublicFetch<{ message: string }>(
    `/api/v1/lan-transfer/public/rooms/${roomId}/files/${fileId}`,
    { method: "DELETE" },
    roomToken
  );
}

export function uploadLanRoomFile(
  roomId: string,
  roomToken: string | null,
  file: File,
  onProgress: (loaded: number, total: number) => void,
  signal?: AbortSignal
): Promise<LanFileItem> {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append("file", file);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}/api/v1/lan-transfer/public/rooms/${roomId}/files`);
    xhr.withCredentials = true;
    if (roomToken) xhr.setRequestHeader("X-Room-Token", roomToken);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(e.loaded, e.total);
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          onProgress(file.size, file.size);
          resolve(JSON.parse(xhr.responseText) as LanFileItem);
        } catch {
          reject(new Error("响应解析失败"));
        }
        return;
      }
      try {
        const err = JSON.parse(xhr.responseText);
        reject(new Error(err.detail || `上传失败 (${xhr.status})`));
      } catch {
        reject(new Error(`上传失败 (${xhr.status})`));
      }
    };

    xhr.onerror = () => reject(new Error("网络错误"));
    xhr.onabort = () => reject(new Error("已取消"));

    if (signal) {
      if (signal.aborted) {
        xhr.abort();
        return;
      }
      signal.addEventListener("abort", () => xhr.abort());
    }

    xhr.send(formData);
  });
}

export async function initLanMultipart(
  roomId: string,
  roomToken: string | null,
  body: { filename: string; mime_type: string; total_size: number; total_parts: number }
): Promise<LanMultipartInit> {
  return lanPublicFetch<LanMultipartInit>(
    `/api/v1/lan-transfer/public/rooms/${roomId}/multipart/init`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    roomToken
  );
}

export async function uploadLanPart(
  roomId: string,
  roomToken: string | null,
  uploadId: string,
  partNumber: number,
  data: Blob
): Promise<{ etag: string; part_number: number }> {
  const params = new URLSearchParams({ upload_id: uploadId, part_number: String(partNumber) });
  return lanPublicFetch<{ etag: string; part_number: number }>(
    `/api/v1/lan-transfer/public/rooms/${roomId}/multipart/part?${params}`,
    { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: data },
    roomToken
  );
}

export async function completeLanMultipart(
  roomId: string,
  roomToken: string | null,
  body: {
    upload_id: string;
    storage_key: string;
    filename: string;
    mime_type: string;
    total_size: number;
    parts: { PartNumber: number; ETag: string }[];
  }
): Promise<LanFileItem> {
  return lanPublicFetch<LanFileItem>(
    `/api/v1/lan-transfer/public/rooms/${roomId}/multipart/complete`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    roomToken
  );
}

export async function abortLanMultipart(
  roomId: string,
  roomToken: string | null,
  uploadId: string,
  storageKey?: string
): Promise<{ message: string }> {
  const params = new URLSearchParams({ upload_id: uploadId });
  if (storageKey) params.set("storage_key", storageKey);
  return lanPublicFetch<{ message: string }>(
    `/api/v1/lan-transfer/public/rooms/${roomId}/multipart/abort?${params}`,
    { method: "POST" },
    roomToken
  );
}

export async function uploadLanFileChunked(
  roomId: string,
  roomToken: string | null,
  file: File,
  onProgress: (loaded: number, total: number) => void,
  signal?: AbortSignal
): Promise<LanFileItem> {
  const partSize = LAN_PART_SIZE;
  const totalParts = Math.ceil(file.size / partSize);
  const init = await initLanMultipart(roomId, roomToken, {
    filename: file.name,
    mime_type: file.type || "application/octet-stream",
    total_size: file.size,
    total_parts: totalParts,
  });

  const parts: { PartNumber: number; ETag: string }[] = [];
  let uploaded = 0;
  try {
    for (let i = 1; i <= totalParts; i += 1) {
      if (signal?.aborted) throw new Error("已取消");
      const start = (i - 1) * partSize;
      const blob = file.slice(start, Math.min(start + partSize, file.size));
      const result = await uploadLanPart(roomId, roomToken, init.upload_id, i, blob);
      parts.push({ PartNumber: result.part_number, ETag: result.etag });
      uploaded += blob.size;
      onProgress(uploaded, file.size);
    }
    return await completeLanMultipart(roomId, roomToken, {
      upload_id: init.upload_id,
      storage_key: init.storage_key,
      filename: file.name,
      mime_type: file.type || "application/octet-stream",
      total_size: file.size,
      parts,
    });
  } catch (err) {
    await abortLanMultipart(roomId, roomToken, init.upload_id, init.storage_key).catch(() => {});
    throw err;
  }
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function downloadLanFile(
  roomId: string,
  roomToken: string | null,
  fileId: string,
  filename: string,
  onProgress: (loaded: number, total: number) => void,
  signal?: AbortSignal
): Promise<void> {
  const headers: Record<string, string> = {};
  if (roomToken) headers["X-Room-Token"] = roomToken;
  const res = await fetch(
    `${API_BASE_URL}/api/v1/lan-transfer/public/rooms/${roomId}/files/${fileId}/download`,
    { credentials: "include", headers, signal }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || `下载失败 (${res.status})`);
  }

  const total = Number(res.headers.get("Content-Length") || 0);
  if (!res.body) {
    saveBlob(await res.blob(), filename);
    onProgress(total, total);
    return;
  }

  const reader = res.body.getReader();
  const chunks: BlobPart[] = [];
  let loaded = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    if (value) {
      chunks.push(value);
      loaded += value.byteLength;
      onProgress(loaded, total || loaded);
    }
  }
  saveBlob(new Blob(chunks), filename);
}