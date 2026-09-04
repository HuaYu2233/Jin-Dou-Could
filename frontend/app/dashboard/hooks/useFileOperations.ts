"use client";

import { useState } from "react";
import {
  uploadFile,
  downloadFile,
  deleteFile,
  restoreFile,
  purgeFile,
  moveFiles,
  createShare,
  createFolder,
  renameFolder,
  deleteFolder,
  type FileItem,
  type FolderItem,
} from "@/lib/api/files";

interface UseFileOperationsParams {
  selectedIds: Set<string>;
  currentFolderId: string | null;
  folderName: string;
  folderDialog: { mode: "create" } | { mode: "rename"; folder: FolderItem } | null;
  loadFiles: () => Promise<void>;
  fetchMe: () => Promise<void>;
  setSelectedIds: (ids: Set<string>) => void;
  setError: (msg: string) => void;
  setFolderDialog: (dialog: { mode: "create" } | { mode: "rename"; folder: FolderItem } | null) => void;
  setSharesReloadKey: (updater: (k: number) => number) => void;
}

export function useFileOperations({
  selectedIds,
  currentFolderId,
  folderName,
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
    try {
      await uploadFile(file, currentFolderId ?? undefined);
      await loadFiles();
      fetchMe();
    } catch (err) {
      setError(err instanceof Error ? err.message : "上传失败");
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
    try {
      const blob = await downloadFile(file.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = file.filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "下载失败");
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

  async function handleCreateShare() {
    if (selectedIds.size === 0) return;
    try {
      for (const id of selectedIds) {
        await createShare(id);
      }
      setSelectedIds(new Set());
      await loadFiles();
      setSharesReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建分享失败");
    }
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
    const name = folderName.trim();
    if (!name || !folderDialog) return;
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
    if (!confirm(`确定删除文件夹「${folder.name}」吗？文件夹内所有内容将被永久删除，此操作不可恢复！`)) return;
    setError("");
    try {
      await deleteFolder(folder.id);
      await loadFiles();
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除文件夹失败");
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
  };
}