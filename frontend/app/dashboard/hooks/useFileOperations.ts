"use client";

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
  multipartUploadFile,
  type FileItem,
  type FolderItem,
  type FolderTrashItem,
  type ShareCreateResponse,
} from "@/lib/api/files";
import { useTransferStore } from "@/stores/transfers";

const MULTIPART_THRESHOLD = 16 * 1024 * 1024;

interface UseFileOperationsParams {
  selectedIds: Set<string>;
  currentFolderId: string | null;
  folderDialog: { mode: "create"; name: string } | { mode: "rename"; folder: FolderItem; name: string } | null;
  invalidateFiles: () => Promise<void>;
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
  invalidateFiles,
  fetchMe,
  setSelectedIds,
  setError,
  setFolderDialog,
  setSharesReloadKey,
}: UseFileOperationsParams) {
  const uploading = useTransferStore((s) =>
    s.tasks.some(
      (t) => t.type === "upload" && (t.status === "pending" || t.status === "transferring")
    )
  );

  function handleUpload(file: File) {
    setError("");
    const isMultipart = file.size >= MULTIPART_THRESHOLD;
    const folderId = currentFolderId ?? undefined;
    useTransferStore.getState().enqueue(
      { filename: file.name, type: "upload", total: file.size, isMultipart },
      async ({ taskId, signal, onProgress }) => {
        try {
          if (isMultipart) {
            const res = await multipartUploadFile(
              file,
              folderId,
              (progress) => onProgress(progress.loaded, progress.total),
              signal
            );
            useTransferStore.getState().updateTask(taskId, { fileId: res.id });
          } else {
            const res = await uploadFileWithProgress(file, folderId, onProgress, signal);
            useTransferStore.getState().updateTask(taskId, { fileId: res.id });
          }
          await invalidateFiles();
          fetchMe();
        } catch (err) {
          if (!signal.aborted) {
            setError(err instanceof Error ? err.message : "上传失败");
          }
          throw err;
        }
      }
    );
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (files) {
      for (let i = 0; i < files.length; i++) {
        handleUpload(files[i]);
      }
    }
    e.target.value = "";
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const files = e.dataTransfer.files;
    if (files) {
      for (let i = 0; i < files.length; i++) {
        handleUpload(files[i]);
      }
    }
  }

  function handleDownload(file: FileItem) {
    useTransferStore.getState().enqueue(
      { filename: file.filename, type: "download", total: file.size, fileId: file.id },
      async ({ signal, onProgress }) => {
        try {
          await downloadFileWithProgress(file.id, onProgress, signal);
        } catch (err) {
          if (!signal.aborted) {
            setError(err instanceof Error ? err.message : "下载失败");
          }
          throw err;
        }
      }
    );
  }

  function handleBatchDownload(files: FileItem[]) {
    if (files.length === 0) return;
    setError("");
    for (const file of files) {
      handleDownload(file);
    }
  }

  async function handleDelete() {
    if (selectedIds.size === 0) return;
    if (!confirm(`确定将选中的 ${selectedIds.size} 个文件移入回收站吗？`)) return;
    try {
      await Promise.all([...selectedIds].map((id) => deleteFile(id)));
      setSelectedIds(new Set());
      await invalidateFiles();
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
      await invalidateFiles();
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
      await invalidateFiles();
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
      await invalidateFiles();
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
      await invalidateFiles();
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
      await invalidateFiles();
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    }
  }

  async function handleDeleteFolder(folder: FolderItem) {
    if (!confirm(`确定将文件夹「${folder.name}」移入回收站吗？文件夹内所有内容将一并移入回收站。`)) return;
    setError("");
    try {
      await deleteFolder(folder.id);
      await invalidateFiles();
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除文件夹失败");
    }
  }

  async function handleRestoreFolder(folder: FolderTrashItem) {
    setError("");
    try {
      await restoreFolder(folder.id);
      await invalidateFiles();
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
      await invalidateFiles();
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
    handleBatchDownload,
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