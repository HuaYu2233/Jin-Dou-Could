"use client";

import { useState } from "react";
import {
  uploadFileWithProgress,
  downloadFileWithProgress,
  deleteFile,
  restoreFile,
  purgeFile,
  moveFiles,
  createShare,
  createFolder,
  renameFolder,
  deleteFolder,
  restoreFolder,
  purgeFolder,
  type FileItem,
  type FolderItem,
  type FolderTrashItem,
  type ShareCreateResponse,
} from "@/lib/api/files";
import { useTransferStore } from "@/stores/transfers";

interface UseFileOperationsParams {
  selectedIds: Set<string>;
  currentFolderId: string | null;
  folderDialog: { mode: "create"; name: string } | { mode: "rename"; folder: FolderItem; name: string } | null;
  loadFiles: (active?: boolean) => Promise<void>;
  fetchMe: () => Promise<void>;
  setSelectedIds: (ids: Set<string>) => void;
  setError: (msg: string) => void;
  setFolderDialog: (dialog: { mode: "create"; name: string } | { mode: "rename"; folder: FolderItem; name: string } | null) => void;
  setSharesReloadKey: (updater: (k: number) => number) => void;
}

export function useFileOperations({
  selectedIds,
  currentFolderId,
  folderDialog,
  loadFiles,
  fetchMe,
  setSelectedIds,
  setError,
  setFolderDialog,
  setSharesReloadKey,
}: UseFileOperationsParams) {
  const [uploading, setUploading] = useState(false);

  async function handleUpload(file: File) {
    setUploading(true);
    setError("");
    const addTask = useTransferStore.getState().addTask;
    const updateTask = useTransferStore.getState().updateTask;
    const taskId = addTask({ filename: file.name, type: "upload", total: file.size });
    try {
      updateTask(taskId, { status: "transferring" });
      const res = await uploadFileWithProgress(
        file,
        currentFolderId ?? undefined,
        (loaded, total) => updateTask(taskId, { loaded, total })
      );
      updateTask(taskId, { status: "completed", loaded: file.size, progress: 100, fileId: res.id });
      await loadFiles();
      fetchMe();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "上传失败";
      if (msg === "已取消") {
        updateTask(taskId, { status: "canceled" });
      } else {
        updateTask(taskId, { status: "error", error: msg });
        setError(msg);
      }
    } finally {
      setUploading(false);
    }
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
    e.target.value = "";
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file) handleUpload(file);
  }

  async function handleDownload(file: FileItem) {
    const addTask = useTransferStore.getState().addTask;
    const updateTask = useTransferStore.getState().updateTask;
    const taskId = addTask({ filename: file.filename, type: "download", total: file.size, fileId: file.id });
    try {
      updateTask(taskId, { status: "transferring" });
      await downloadFileWithProgress(
        file.id,
        (loaded, total) => updateTask(taskId, { loaded, total })
      );
      updateTask(taskId, { status: "completed", progress: 100 });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "下载失败";
      if (msg === "已取消") {
        updateTask(taskId, { status: "canceled" });
      } else {
        updateTask(taskId, { status: "error", error: msg });
        setError(msg);
      }
    }
  }

  async function handleDelete() {
    if (selectedIds.size === 0) return;
    if (!confirm(`确定将选中的 ${selectedIds.size} 个文件移入回收站吗？`)) return;
    try {
      await Promise.all([...selectedIds].map((id) => deleteFile(id)));
      setSelectedIds(new Set());
      await loadFiles();
      fetchMe();
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除失败");
    }
  }

  async function handleRestore() {
    if (selectedIds.size === 0) return;
    try {
      await Promise.all([...selectedIds].map((id) => restoreFile(id)));
      setSelectedIds(new Set());
      await loadFiles();
      fetchMe();
    } catch (err) {
      setError(err instanceof Error ? err.message : "恢复失败");
    }
  }

  async function handlePurge() {
    if (selectedIds.size === 0) return;
    if (!confirm(`确定彻底删除选中的 ${selectedIds.size} 个文件吗？此操作不可恢复！`)) return;
    try {
      await Promise.all([...selectedIds].map((id) => purgeFile(id)));
      setSelectedIds(new Set());
      await loadFiles();
      fetchMe();
    } catch (err) {
      setError(err instanceof Error ? err.message : "彻底删除失败");
    }
  }

  async function handleCreateShare(): Promise<ShareCreateResponse[]> {
    if (selectedIds.size === 0) return [];
    const results: ShareCreateResponse[] = [];
    try {
      for (const id of selectedIds) {
        const res = await createShare(id);
        results.push(res);
      }
      setSelectedIds(new Set());
      await loadFiles();
      setSharesReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建分享失败");
    }
    return results;
  }

  async function handleMoveToFolder(fileIds: string[], folderId: string | null) {
    if (fileIds.length === 0) return;
    if (folderId === currentFolderId) {
      setError("不能移动到当前所在文件夹");
      return;
    }
    const ids = fileIds.length > 1 || !selectedIds.has(fileIds[0])
      ? fileIds
      : [...selectedIds];
    setError("");
    try {
      await moveFiles(ids, folderId ?? undefined);
      setSelectedIds(new Set());
      await loadFiles();
      fetchMe();
    } catch (err) {
      setError(err instanceof Error ? err.message : "移动失败");
    }
  }

  async function handleFolderDialogSubmit() {
    if (!folderDialog) return;
    const name = folderDialog.name.trim();
    if (!name) return;
    setError("");
    try {
      if (folderDialog.mode === "create") {
        await createFolder(name, currentFolderId ?? undefined);
      } else {
        await renameFolder(folderDialog.folder.id, name);
      }
      setFolderDialog(null);
      await loadFiles();
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    }
  }

  async function handleDeleteFolder(folder: FolderItem) {
    if (!confirm(`确定将文件夹「${folder.name}」移入回收站吗？文件夹内所有内容将一并移入回收站。`)) return;
    setError("");
    try {
      await deleteFolder(folder.id);
      await loadFiles();
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除文件夹失败");
    }
  }

  async function handleRestoreFolder(folder: FolderTrashItem) {
    setError("");
    try {
      await restoreFolder(folder.id);
      await loadFiles();
      fetchMe();
    } catch (err) {
      setError(err instanceof Error ? err.message : "恢复文件夹失败");
    }
  }

  async function handlePurgeFolder(folder: FolderTrashItem) {
    if (!confirm(`确定彻底删除文件夹「${folder.name}」吗？文件夹内所有内容将被永久删除，此操作不可恢复！`)) return;
    setError("");
    try {
      await purgeFolder(folder.id);
      await loadFiles();
      fetchMe();
    } catch (err) {
      setError(err instanceof Error ? err.message : "彻底删除文件夹失败");
    }
  }

  return {
    uploading,
    handleUpload,
    handleFileSelect,
    handleDrop,
    handleDownload,
    handleDelete,
    handleRestore,
    handlePurge,
    handleCreateShare,
    handleMoveToFolder,
    handleFolderDialogSubmit,
    handleDeleteFolder,
    handleRestoreFolder,
    handlePurgeFolder,
  };
}