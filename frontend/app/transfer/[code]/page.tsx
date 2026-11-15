"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Image from "next/image";
import { useParams } from "next/navigation";
import { useTranslation } from "@/lib/i18n";
import { formatSize, formatDate } from "@/lib/utils/format";
import {
  LAN_CHUNK_THRESHOLD,
  deleteLanRoomFile,
  downloadLanFile,
  joinLanRoom,
  listLanRoomFiles,
  uploadLanFileChunked,
  uploadLanRoomFile,
  type LanFileItem,
  type LanJoinResult,
} from "@/lib/api/lanTransfer";
import { useTransferStore } from "@/stores/transfers";

const POLL_INTERVAL = 4000;
const SLOW_POLL_INTERVAL = 15000;
const MAX_FAILURES = 3;

function isLocalhostOrigin(): boolean {
  if (typeof window === "undefined") return false;
  const host = window.location.hostname;
  return host === "localhost" || host === "127.0.0.1" || host === "::1";
}

export default function TransferPage() {
  const params = useParams();
  const code = (params.code as string) || "";
  const { t } = useTranslation();

  const [password, setPassword] = useState("");
  const [joining, setJoining] = useState(false);
  const [joinError, setJoinError] = useState("");
  const [session, setSession] = useState<LanJoinResult | null>(null);

  const [files, setFiles] = useState<LanFileItem[]>([]);
  const [usedSize, setUsedSize] = useState(0);
  const [maxTotalSize, setMaxTotalSize] = useState(0);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [error, setError] = useState("");
  const [networkWarning, setNetworkWarning] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [activeDownloads, setActiveDownloads] = useState<Record<string, number>>({});

  const failures = useRef(0);
  const intervalRef = useRef(POLL_INTERVAL);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const sessionRef = useRef<LanJoinResult | null>(null);

  const addTask = useTransferStore((s) => s.addTask);
  const updateTask = useTransferStore((s) => s.updateTask);

  const refreshFiles = useCallback(async (silent = false) => {
    const current = sessionRef.current;
    if (!current) return;
    if (!silent) setLoadingFiles(true);
    try {
      const data = await listLanRoomFiles(current.room_id, current.room_token);
      setFiles(data.items);
      setUsedSize(data.used_size);
      setMaxTotalSize(data.max_total_size);
      failures.current = 0;
      setNetworkWarning(false);
      intervalRef.current = POLL_INTERVAL;
      setError("");
    } catch (err) {
      failures.current += 1;
      if (failures.current >= MAX_FAILURES) {
        intervalRef.current = SLOW_POLL_INTERVAL;
        setNetworkWarning(true);
      }
      const message = err instanceof Error ? err.message : t("lan.loadFailed");
      if (!silent) setError(message);
      if (message.includes("过期") || message.includes("关闭")) setSession(null);
    } finally {
      setLoadingFiles(false);
    }
  }, [t]);

  const refreshRef = useRef(refreshFiles);

  useEffect(() => {
    refreshRef.current = refreshFiles;
  }, [refreshFiles]);

  useEffect(() => {
    sessionRef.current = session;
    if (!session) {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = null;
      return;
    }
    let cancelled = false;
    function schedule(delay: number) {
      timerRef.current = setTimeout(async () => {
        if (cancelled) return;
        if (document.visibilityState !== "hidden") await refreshRef.current(true);
        if (!cancelled) schedule(intervalRef.current);
      }, delay);
    }
    schedule(0);

    return () => {
      cancelled = true;
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = null;
    };
  }, [session]);

  useEffect(() => {
    function onVisibility() {
      if (document.visibilityState === "visible" && sessionRef.current) refreshFiles(true);
    }
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, [refreshFiles]);

  async function handleJoin() {
    setJoinError("");
    setJoining(true);
    try {
      const result = await joinLanRoom(code.trim().toUpperCase(), password.trim() || null);
      setSession(result);
      setUsedSize(result.used_size);
      setMaxTotalSize(result.max_total_size);
    } catch (err) {
      setJoinError(err instanceof Error ? err.message : t("lan.joinError"));
    } finally {
      setJoining(false);
    }
  }

  async function handleUpload(files: FileList | null) {
    const current = sessionRef.current;
    if (!current || !files || files.length === 0) return;
    setUploading(true);
    setError("");
    for (const file of Array.from(files)) {
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
          await uploadLanFileChunked(current.room_id, current.room_token, file, onProgress);
        } else {
          await uploadLanRoomFile(current.room_id, current.room_token, file, onProgress);
        }
        updateTask(taskId, { status: "completed", loaded: file.size });
      } catch (err) {
        const message = err instanceof Error ? err.message : t("lan.uploadFailed");
        updateTask(taskId, { status: "error", error: message });
        setError(message);
      }
    }
    setUploading(false);
    await refreshFiles(true);
  }

  async function handleDownload(item: LanFileItem) {
    const current = sessionRef.current;
    if (!current) return;
    const taskId = addTask({ filename: item.filename, type: "lan-download", total: item.size });
    updateTask(taskId, { status: "transferring" });
    setActiveDownloads((prev) => ({ ...prev, [item.id]: 0 }));
    try {
      await downloadLanFile(
        current.room_id,
        current.room_token,
        item.id,
        item.filename,
        (loaded, total) => {
          updateTask(taskId, { loaded, total });
          setActiveDownloads((prev) => ({ ...prev, [item.id]: total > 0 ? loaded / total : 0 }));
        }
      );
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
    const current = sessionRef.current;
    if (!current) return;
    if (!confirm(`${t("lan.delete")} ${item.filename}?`)) return;
    try {
      await deleteLanRoomFile(current.room_id, current.room_token, item.id);
      await refreshFiles(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("lan.loadFailed"));
    }
  }

  const localhostHint = isLocalhostOrigin();
  const percent = maxTotalSize > 0 ? Math.min(100, (usedSize / maxTotalSize) * 100) : 0;

  if (!session) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-page p-4">
        <div className="w-full max-w-md rounded-[20px] border border-line bg-surface p-8 shadow-[0_18px_48px_rgba(29,33,41,0.1)]">
          <div className="mb-6 flex flex-col items-center text-center">
            <span className="flex h-11 w-11 items-center justify-center overflow-hidden rounded-full">
              <Image src="/logo-badge-light.png" alt="" width={44} height={44} className="h-full w-full object-contain" />
            </span>
            <h1 className="mt-4 text-lg font-semibold text-ink">{t("lan.joinTitle")}</h1>
            <p className="mt-1 text-sm text-ink-3">{t("lan.joinHint")}</p>
          </div>

          <div className="mb-4 flex items-center gap-3 rounded-[12px] border border-line bg-surface-2 p-4">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[10px] bg-surface text-xl">
              📶
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs text-ink-3">{t("lan.code")}</p>
              <p className="mt-0.5 font-mono text-lg font-semibold tracking-[0.2em] text-ink">{code}</p>
            </div>
          </div>

          {joinError && (
            <div className="mb-4 rounded-[8px] border border-[#ffd4cd] bg-danger-soft px-3 py-2 text-sm text-danger">
              {joinError}
            </div>
          )}

          <label className="mb-4 block text-sm text-ink-2">
            {t("lan.joinPassword")}
            <input
              className="mt-1 w-full rounded-[10px] border border-line bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-brand"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleJoin();
              }}
            />
          </label>

          <button
            className="w-full rounded-[10px] bg-brand px-4 py-2.5 text-sm font-medium text-white hover:bg-[var(--qk-primary-hover)] disabled:opacity-60"
            disabled={joining}
            onClick={handleJoin}
          >
            {joining ? t("lan.creating") : t("lan.join")}
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-page px-4 py-8">
      <div className="mx-auto w-full max-w-3xl">
        <div className="mb-4 rounded-[16px] border border-line bg-surface p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-lg font-semibold text-ink">{session.title || t("lan.title")}</h1>
              <p className="mt-1 font-mono text-sm tracking-[0.2em] text-ink-3">{code}</p>
            </div>
            <div className="text-right text-xs text-ink-3">
              <div>
                {t("lan.fileCount")}: {files.length}
              </div>
              <div className="mt-1">
                {t("lan.createTtl")}: {formatDate(session.expires_at)}
              </div>
            </div>
          </div>
          <div className="mt-5">
            <div className="mb-1 flex items-center justify-between text-xs text-ink-3">
              <span>{t("lan.capacity")}</span>
              <span>
                {formatSize(usedSize)} / {formatSize(maxTotalSize)}
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-surface-3">
              <div className="h-full bg-brand transition-all" style={{ width: `${percent}%` }} />
            </div>
          </div>
        </div>

        {localhostHint && (
          <div className="mb-4 rounded-[8px] border border-[#ffe0b2] bg-[#fff7e6] px-3 py-2 text-sm text-[#b26a00]">
            {t("lan.localhostHint")}
          </div>
        )}

        {session.same_subnet_hint && (
          <div className="mb-4 rounded-[8px] border border-[#ffe0b2] bg-[#fff7e6] px-3 py-2 text-sm text-[#b26a00]">
            {t("lan.sameSubnetHint")}
          </div>
        )}

        {networkWarning && (
          <div className="mb-4 rounded-[8px] border border-[#ffe0b2] bg-[#fff7e6] px-3 py-2 text-sm text-[#b26a00]">
            {t("lan.networkWarning")}
          </div>
        )}

        {error && (
          <div className="mb-4 rounded-[8px] border border-[#ffd4cd] bg-danger-soft px-3 py-2 text-sm text-danger">
            {error}
          </div>
        )}

        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-medium text-ink-2">{t("lan.files")}</h2>
          <div>
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
              className="rounded-[8px] bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-[var(--qk-primary-hover)] disabled:opacity-60"
              disabled={uploading}
              onClick={() => fileInputRef.current?.click()}
            >
              {uploading ? t("lan.uploading") : t("lan.upload")}
            </button>
          </div>
        </div>

        <div className="overflow-hidden rounded-[16px] border border-line bg-surface">
          {loadingFiles && files.length === 0 ? (
            <div className="py-16 text-center text-sm text-ink-4">{t("header.loading")}</div>
          ) : files.length === 0 ? (
            <div className="flex flex-col items-center py-16 text-ink-4">
              <div className="mb-3 text-4xl opacity-50">📶</div>
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
    </main>
  );
}