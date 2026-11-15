"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "@/lib/i18n";
import { formatDate, formatSize } from "@/lib/utils/format";
import {
  LAN_CHUNK_THRESHOLD,
  closeLanRoom,
  createLanRoom,
  deleteLanRoomFile,
  downloadLanFile,
  getLanRoom,
  listLanRoomFiles,
  sendDriveFilesToRoom,
  uploadLanFileChunked,
  uploadLanRoomFile,
  type LanFileItem,
} from "@/lib/api/lanTransfer";
import { listFiles, type FileItem } from "@/lib/api/files";
import { useLanTransferStore } from "@/stores/lanTransfer";
import { useTransferStore } from "@/stores/transfers";
import styles from "./LanTransferView.module.css";

const ROOM_STORAGE_KEY = "lan_transfer_room_id";
const FILES_POLL_INTERVAL = 10000;

const TTL_OPTIONS = [1, 6, 24, 72, 168];

function isLoopbackUrl(url: string): boolean {
  if (typeof window === "undefined") return false;
  try {
    const host = new URL(url, window.location.origin).hostname;
    return host === "localhost" || host === "127.0.0.1" || host === "::1" || host === "[::1]";
  } catch {
    return false;
  }
}

export default function LanTransferView() {
  const { t } = useTranslation();
  const router = useRouter();
  const room = useLanTransferStore((s) => s.room);
  const setRoom = useLanTransferStore((s) => s.setRoom);
  const reset = useLanTransferStore((s) => s.reset);
  const files = useLanTransferStore((s) => s.files);
  const usedSize = useLanTransferStore((s) => s.usedSize);
  const maxTotalSize = useLanTransferStore((s) => s.maxTotalSize);
  const fileCount = useLanTransferStore((s) => s.fileCount);
  const setFiles = useLanTransferStore((s) => s.setFiles);

  const addTask = useTransferStore((s) => s.addTask);
  const updateTask = useTransferStore((s) => s.updateTask);

  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState<"" | "code" | "link">("");
  const [title, setTitle] = useState("");
  const [password, setPassword] = useState("");
  const [ttlHours, setTtlHours] = useState(24);
  const [joinCode, setJoinCode] = useState("");
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerLoading, setPickerLoading] = useState(false);
  const [pickerError, setPickerError] = useState("");
  const [pickerSending, setPickerSending] = useState(false);
  const [driveFiles, setDriveFiles] = useState<FileItem[]>([]);
  const [selectedFileIds, setSelectedFileIds] = useState<string[]>([]);
  const [pickerQuery, setPickerQuery] = useState("");
  const [activeDownloads, setActiveDownloads] = useState<Record<string, number>>({});
  const initialized = useRef(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const localhostHint = useMemo(() => (room ? isLoopbackUrl(room.join_url) : false), [room]);

  const loadRoom = useCallback(
    async (roomId: string) => {
      try {
        const data = await getLanRoom(roomId);
        setRoom(data);
        return data;
      } catch {
        localStorage.removeItem(ROOM_STORAGE_KEY);
        reset();
        return null;
      }
    },
    [reset, setRoom]
  );

  const refreshFiles = useCallback(
    async (roomId: string) => {
      setLoadingFiles(true);
      try {
        const data = await listLanRoomFiles(roomId, null);
        setFiles(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : t("lan.loadFailed"));
      } finally {
        setLoadingFiles(false);
      }
    },
    [setFiles, t]
  );

  useEffect(() => {
    const roomId = room?.room_id;
    if (!roomId) return;
    const kickoff = setTimeout(() => refreshFiles(roomId), 0);
    const timer = setInterval(() => {
      if (document.visibilityState === "hidden") return;
      refreshFiles(roomId);
    }, FILES_POLL_INTERVAL);
    return () => {
      clearTimeout(kickoff);
      clearInterval(timer);
    };
  }, [room?.room_id, refreshFiles]);

  useEffect(() => {
    const savedId = localStorage.getItem(ROOM_STORAGE_KEY);
    const timer = setTimeout(() => {
      if (initialized.current) return;
      initialized.current = true;
      if (!savedId) {
        setLoading(false);
        return;
      }
      loadRoom(savedId).finally(() => setLoading(false));
    }, 0);
    return () => clearTimeout(timer);
  }, [loadRoom]);

  async function handleCreate() {
    setError("");
    setCreating(true);
    try {
      const data = await createLanRoom({
        title: title.trim() || null,
        password: password.trim() || null,
        ttl_hours: ttlHours,
      });
      localStorage.setItem(ROOM_STORAGE_KEY, data.room_id);
      setRoom(data);
      setTitle("");
      setPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("lan.loadFailed"));
    } finally {
      setCreating(false);
    }
  }

  async function handleClose() {
    if (!room) return;
    if (!confirm(t("lan.closeConfirm"))) return;
    setError("");
    try {
      await closeLanRoom(room.room_id);
      localStorage.removeItem(ROOM_STORAGE_KEY);
      reset();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("lan.loadFailed"));
    }
  }

  async function handleRefresh() {
    if (!room) return;
    setError("");
    try {
      const data = await loadRoom(room.room_id);
      if (!data) setError(t("lan.expired"));
      else await refreshFiles(room.room_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("lan.loadFailed"));
    }
  }

  async function handleUpload(list: FileList | null) {
    if (!room || !list || list.length === 0) return;
    setUploading(true);
    setError("");
    for (const file of Array.from(list)) {
      const taskId = addTask({
        filename: file.name,
        type: "lan-upload",
        total: file.size,
        isMultipart: file.size >= LAN_CHUNK_THRESHOLD,
      });
      updateTask(taskId, { status: "transferring" });
      try {
        const onProgress = (loaded: number, total: number) => updateTask(taskId, { loaded, total });
        if (file.size >= LAN_CHUNK_THRESHOLD) {
          await uploadLanFileChunked(room.room_id, null, file, onProgress);
        } else {
          await uploadLanRoomFile(room.room_id, null, file, onProgress);
        }
        updateTask(taskId, { status: "completed", loaded: file.size });
      } catch (err) {
        const message = err instanceof Error ? err.message : t("lan.uploadFailed");
        updateTask(taskId, { status: "error", error: message });
        setError(message);
      }
    }
    setUploading(false);
    await refreshFiles(room.room_id);
  }

  async function handleDownload(item: LanFileItem) {
    if (!room) return;
    const taskId = addTask({ filename: item.filename, type: "lan-download", total: item.size });
    updateTask(taskId, { status: "transferring" });
    setActiveDownloads((prev) => ({ ...prev, [item.id]: 0 }));
    try {
      await downloadLanFile(room.room_id, null, item.id, item.filename, (loaded, total) => {
        updateTask(taskId, { loaded, total });
        setActiveDownloads((prev) => ({ ...prev, [item.id]: total > 0 ? loaded / total : 0 }));
      });
      updateTask(taskId, { status: "completed", loaded: item.size });
    } catch (err) {
      const message = err instanceof Error ? err.message : t("lan.downloadFailed");
      updateTask(taskId, { status: "error", error: message });
      setError(message);
    } finally {
      setActiveDownloads((prev) => {
        const next = { ...prev };
        delete next[item.id];
        return next;
      });
    }
  }

  async function handleDelete(item: LanFileItem) {
    if (!room) return;
    if (!confirm(`${t("lan.delete")} ${item.filename}?`)) return;
    try {
      await deleteLanRoomFile(room.room_id, null, item.id);
      await refreshFiles(room.room_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("lan.loadFailed"));
    }
  }

  async function openDrivePicker() {
    setPickerOpen(true);
    setPickerError("");
    setPickerQuery("");
    setSelectedFileIds([]);
    setPickerLoading(true);
    try {
      const data = await listFiles(0, 100, "all", undefined, true);
      setDriveFiles(data.items);
    } catch (err) {
      setPickerError(err instanceof Error ? err.message : t("lan.drivePickerLoadFailed"));
    } finally {
      setPickerLoading(false);
    }
  }

  function toggleFileSelection(fileId: string) {
    setSelectedFileIds((prev) =>
      prev.includes(fileId) ? prev.filter((id) => id !== fileId) : [...prev, fileId]
    );
  }

  async function handleSendFromDrive() {
    if (!room || selectedFileIds.length === 0) return;
    setPickerSending(true);
    setPickerError("");
    try {
      await sendDriveFilesToRoom(room.room_id, selectedFileIds);
      setPickerOpen(false);
      setSelectedFileIds([]);
      await refreshFiles(room.room_id);
    } catch (err) {
      setPickerError(err instanceof Error ? err.message : t("lan.drivePickerSendFailed"));
    } finally {
      setPickerSending(false);
    }
  }

  const filteredDriveFiles = useMemo(() => {
    const keyword = pickerQuery.trim().toLowerCase();
    if (!keyword) return driveFiles;
    return driveFiles.filter((item) => item.filename.toLowerCase().includes(keyword));
  }, [driveFiles, pickerQuery]);

  function copyText(text: string, kind: "code" | "link") {
    const done = () => {
      setCopied(kind);
      setTimeout(() => setCopied(""), 1800);
    };
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(() => prompt(t("lan.copyLink"), text));
      return;
    }
    prompt(t("lan.copyLink"), text);
  }

  function handleJoinByCode() {
    const normalized = joinCode.trim().toUpperCase();
    if (!normalized) return;
    router.push(`/transfer/${encodeURIComponent(normalized)}`);
  }

  if (loading) {
    return <div className="py-20 text-center text-sm text-ink-4">{t("header.loading")}</div>;
  }

  return (
    <div className="mx-auto w-full max-w-3xl p-6">
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-ink">{t("lan.title")}</h2>
        <p className="mt-1 text-sm text-ink-3">{t("lan.subtitle")}</p>
      </div>

      {error && (
        <div className="mb-4 rounded-[8px] border border-[#ffd4cd] bg-danger-soft px-3 py-2 text-sm text-danger">
          {error}
        </div>
      )}

      {localhostHint && (
        <div className="mb-4 rounded-[8px] border border-[#ffe0b2] bg-[#fff7e6] px-3 py-2 text-sm text-[#b26a00]">
          {t("lan.localhostHint")}
        </div>
      )}

      {room ? (
        <div className={styles.card}>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="text-xs text-ink-3">{t("lan.code")}</div>
              <div className={`${styles.code} mt-1 text-2xl font-semibold text-ink`}>{room.code}</div>
              {room.title && <div className="mt-2 text-sm text-ink-2">{room.title}</div>}
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                className="rounded-[8px] border border-line bg-surface px-3 py-1.5 text-sm text-ink-2 hover:bg-surface-2"
                onClick={() => copyText(room.code, "code")}
              >
                {copied === "code" ? t("lan.copied") : t("lan.copyCode")}
              </button>
              <button
                className="rounded-[8px] border border-line bg-surface px-3 py-1.5 text-sm text-ink-2 hover:bg-surface-2"
                onClick={() => copyText(room.join_url, "link")}
              >
                {copied === "link" ? t("lan.copied") : t("lan.copyLink")}
              </button>
              <button
                className="rounded-[8px] border border-line bg-surface px-3 py-1.5 text-sm text-ink-2 hover:bg-surface-2"
                onClick={handleRefresh}
              >
                {t("lan.refresh")}
              </button>
              <button
                className="rounded-[8px] border border-[#ffd4cd] bg-danger-soft px-3 py-1.5 text-sm text-danger"
                onClick={handleClose}
              >
                {t("lan.close")}
              </button>
            </div>
          </div>

          <div className="mt-6">
            <div className="mb-1 flex items-center justify-between text-xs text-ink-3">
              <span>{t("lan.capacity")}</span>
              <span>
                {formatSize(usedSize)} / {formatSize(maxTotalSize)}
              </span>
            </div>
            <div className={styles.bar}>
              <div
                className={styles.barFill}
                style={{
                  width: `${maxTotalSize > 0 ? Math.min(100, (usedSize / maxTotalSize) * 100) : 0}%`,
                }}
              />
            </div>
            <div className="mt-3 flex flex-wrap gap-6 text-xs text-ink-3">
              <span>
                {t("lan.fileCount")}: {fileCount}
              </span>
              <span>
                {t("lan.createTtl")}: {formatDate(room.expires_at)}
              </span>
              {room.has_password && <span>🔒</span>}
            </div>
          </div>

          <div className="mt-6 border-t border-line pt-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-medium text-ink-2">{t("lan.files")}</h3>
              <div className="flex gap-2">
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  style={{ display: "none" }}
                  onChange={(e) => {
                    handleUpload(e.target.files);
                    e.target.value = "";
                  }}
                />
                <button
                  className="rounded-[8px] border border-line bg-surface px-4 py-2 text-sm text-ink-2 hover:bg-surface-2"
                  onClick={openDrivePicker}
                >
                  {t("lan.sendFromDrive")}
                </button>
                <button
                  className="rounded-[8px] bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-[var(--qk-primary-hover)] disabled:opacity-60"
                  disabled={uploading}
                  onClick={() => fileInputRef.current?.click()}
                >
                  {uploading ? t("lan.uploading") : t("lan.upload")}
                </button>
              </div>
            </div>

            <div className="overflow-hidden rounded-[12px] border border-line">
              {loadingFiles && files.length === 0 ? (
                <div className="py-12 text-center text-sm text-ink-4">{t("header.loading")}</div>
              ) : files.length === 0 ? (
                <div className="flex flex-col items-center py-12 text-ink-4">
                  <div className="mb-3 text-3xl opacity-50">📶</div>
                  <p className="text-sm">{t("lan.empty")}</p>
                </div>
              ) : (
                <ul>
                  {files.map((item) => (
                    <li
                      key={item.id}
                      className="flex items-center gap-3 border-b border-line px-4 py-3 last:border-b-0"
                    >
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] bg-surface-2 text-lg">
                        📄
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-ink">{item.filename}</p>
                        <p className="mt-0.5 text-xs text-ink-3">
                          {formatSize(item.size)} · {item.uploader} · {formatDate(item.created_at)}
                        </p>
                        {activeDownloads[item.id] !== undefined && (
                          <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-surface-3">
                            <div
                              className="h-full bg-brand transition-all"
                              style={{ width: `${Math.round(activeDownloads[item.id] * 100)}%` }}
                            />
                          </div>
                        )}
                      </div>
                      <div className="flex shrink-0 gap-2">
                        <button
                          className="rounded-[8px] border border-line bg-surface px-3 py-1.5 text-xs text-ink-2 hover:bg-surface-2"
                          onClick={() => handleDownload(item)}
                        >
                          {t("lan.download")}
                        </button>
                        <button
                          className="rounded-[8px] border border-[#ffd4cd] bg-danger-soft px-3 py-1.5 text-xs text-danger"
                          onClick={() => handleDelete(item)}
                        >
                          {t("lan.delete")}
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className={styles.card}>
          <div className={styles.form}>
            <label className="text-sm text-ink-2">
              {t("lan.createTitle")}
              <input
                className={`${styles.input} mt-1`}
                value={title}
                maxLength={100}
                onChange={(e) => setTitle(e.target.value)}
              />
            </label>
            <label className="text-sm text-ink-2">
              {t("lan.createPassword")}
              <input
                className={`${styles.input} mt-1`}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            <label className="text-sm text-ink-2">
              {t("lan.createTtl")}
              <select
                className={`${styles.input} mt-1`}
                value={ttlHours}
                onChange={(e) => setTtlHours(Number(e.target.value))}
              >
                {TTL_OPTIONS.map((h) => (
                  <option key={h} value={h}>
                    {h}
                  </option>
                ))}
              </select>
            </label>
            <button
              className="mt-1 rounded-[8px] bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-[var(--qk-primary-hover)] disabled:opacity-60"
              disabled={creating}
              onClick={handleCreate}
            >
              {creating ? t("lan.creating") : t("lan.create")}
            </button>
          </div>
        </div>
      )}

      <div className={`${styles.card} mt-4`}>
        <div className="text-sm font-medium text-ink-2">{t("lan.joinTitle")}</div>
        <p className="mt-1 text-xs text-ink-3">{t("lan.joinHint")}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <input
            className={`${styles.input} min-w-0 flex-1`}
            value={joinCode}
            maxLength={12}
            placeholder={t("lan.code")}
            onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleJoinByCode();
            }}
          />
          <button
            className="rounded-[8px] border border-line bg-surface px-4 py-2 text-sm text-ink-2 hover:bg-surface-2 disabled:opacity-60"
            disabled={!joinCode.trim()}
            onClick={handleJoinByCode}
          >
            {t("lan.join")}
          </button>
        </div>
      </div>

      {pickerOpen && (
        <div className={styles.overlay} onClick={() => !pickerSending && setPickerOpen(false)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-sm font-semibold text-ink">{t("lan.drivePickerTitle")}</h3>
                <p className="mt-1 text-xs text-ink-3">{t("lan.drivePickerHint")}</p>
              </div>
              <button
                className="rounded-[8px] border border-line bg-surface px-3 py-1.5 text-xs text-ink-2 hover:bg-surface-2"
                onClick={() => setPickerOpen(false)}
              >
                ✕
              </button>
            </div>

            <input
              className={`${styles.input} mt-4`}
              value={pickerQuery}
              placeholder={t("lan.drivePickerSearch")}
              onChange={(e) => setPickerQuery(e.target.value)}
            />

            {pickerError && (
              <div className="mt-3 rounded-[8px] border border-[#ffd4cd] bg-danger-soft px-3 py-2 text-sm text-danger">
                {pickerError}
              </div>
            )}

            <div className={`${styles.pickerList} mt-3`}>
              {pickerLoading ? (
                <div className="py-10 text-center text-sm text-ink-4">{t("header.loading")}</div>
              ) : filteredDriveFiles.length === 0 ? (
                <div className="py-10 text-center text-sm text-ink-4">{t("lan.drivePickerEmpty")}</div>
              ) : (
                filteredDriveFiles.map((item) => (
                  <label
                    key={item.id}
                    className="flex cursor-pointer items-center gap-3 border-b border-line px-2 py-2.5 last:border-b-0"
                  >
                    <input
                      type="checkbox"
                      checked={selectedFileIds.includes(item.id)}
                      onChange={() => toggleFileSelection(item.id)}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-ink">{item.filename}</p>
                      <p className="mt-0.5 text-xs text-ink-3">{formatSize(item.size)}</p>
                    </div>
                  </label>
                ))
              )}
            </div>

            <div className="mt-4 flex justify-end gap-2">
              <button
                className="rounded-[8px] border border-line bg-surface px-4 py-2 text-sm text-ink-2 hover:bg-surface-2"
                onClick={() => setPickerOpen(false)}
              >
                {t("common.cancel")}
              </button>
              <button
                className="rounded-[8px] bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-[var(--qk-primary-hover)] disabled:opacity-60"
                disabled={pickerSending || selectedFileIds.length === 0}
                onClick={handleSendFromDrive}
              >
                {pickerSending
                  ? t("lan.drivePickerSending")
                  : t("lan.drivePickerConfirm", { count: selectedFileIds.length })}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}