// /Users/zero/project/JinDou-Cloud/frontend/app/dashboard/components/FileList.tsx
"use client";

import { useState, useEffect } from "react";
import type { FileItem, FolderItem } from "@/lib/api/files";
import { getFileBlob } from "@/lib/api/files";
import type { ViewMode } from "../types";
import styles from "./FileList.module.css";

interface FileListProps {
  files: FileItem[];
  folders?: FolderItem[];
  viewMode: ViewMode;
  loading: boolean;
  selectedIds: Set<string>;
  onToggleSelect: (id: string) => void;
  onDownload: (file: FileItem) => void;
  onPreview: (file: FileItem) => void;
  onOpenFolder?: (folder: FolderItem) => void;
  onRenameFolder?: (folder: FolderItem) => void;
  onDeleteFolder?: (folder: FolderItem) => void;
  onMoveToFolder?: (fileIds: string[], folderId: string | null) => void;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

function getFileIcon(fileType: string, mimeType: string): string {
  if (fileType === "image") return "🖼️";
  if (fileType === "video") return "🎬";
  if (fileType === "audio") return "🎵";
  if (fileType === "document") {
    if (mimeType === "application/pdf") return "📕";
    if (mimeType.startsWith("text/")) return "📄";
    return "📃";
  }
  if (fileType === "archive") return "🗜️";
  return "📦";
}

function Thumbnail({ file, variant = "grid" }: { file: FileItem; variant?: "grid" | "list" }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const isList = variant === "list";

  useEffect(() => {
    if (file.file_type !== "image" || failed) return;
    let objectUrl: string | null = null;
    let active = true;
    getFileBlob(file.id)
      .then((blob) => {
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [file.id, file.file_type, failed]);

  if (file.file_type !== "image" || failed) {
    return <span className={isList ? styles.fileIcon : styles.gridIcon}>{getFileIcon(file.file_type, file.mime_type)}</span>;
  }
  if (!url) {
    return <span className={isList ? styles.fileIcon : styles.gridIcon}>⏳</span>;
  }
  return <img className={isList ? styles.listThumbnail : styles.gridThumbnail} src={url} alt={file.filename} loading="lazy" />;
}

export default function FileList({
  files,
  folders,
  viewMode,
  loading,
  selectedIds,
  onToggleSelect,
  onDownload,
  onPreview,
  onOpenFolder,
  onRenameFolder,
  onDeleteFolder,
  onMoveToFolder,
}: FileListProps) {
  const [dragOverFolderId, setDragOverFolderId] = useState<string | null>(null);

  function handleFileDragStart(e: React.DragEvent, fileId: string) {
    e.dataTransfer.setData("text/plain", fileId);
    e.dataTransfer.effectAllowed = "move";
  }

  function handleFolderDragOver(e: React.DragEvent, folderId: string | null) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDragOverFolderId(folderId ?? "root");
  }

  function handleFolderDrop(e: React.DragEvent, folderId: string | null) {
    e.preventDefault();
    e.stopPropagation();
    setDragOverFolderId(null);
    const fileId = e.dataTransfer.getData("text/plain");
    if (fileId) onMoveToFolder?.([fileId], folderId);
  }

  if (loading) {
    return (
      <div className={styles.loadingContainer}>
        {[...Array(6)].map((_, i) => (
          <div key={i} className={styles.skeletonRow} />
        ))}
      </div>
    );
  }

  if (files.length === 0 && (!folders || folders.length === 0)) {
    return (
      <div className={styles.emptyState}>
        <div className={styles.emptyIcon}>📁</div>
        <p className={styles.emptyTitle}>暂无文件</p>
        <p className={styles.emptyDesc}>点击上方上传按钮添加文件</p>
      </div>
    );
  }

  if (viewMode === "grid") {
    return (
      <div className={styles.gridContainer}>
        {folders?.map((folder) => (
          <div
            key={`folder-${folder.id}`}
            className={`${styles.gridItem} ${dragOverFolderId === folder.id ? styles.gridItemDropTarget : ""}`}
            onClick={() => onOpenFolder?.(folder)}
            onDoubleClick={() => onOpenFolder?.(folder)}
            onDragOver={(e) => handleFolderDragOver(e, folder.id)}
            onDragLeave={() => setDragOverFolderId(null)}
            onDrop={(e) => handleFolderDrop(e, folder.id)}
          >
            <div className={styles.gridIcon}>📁</div>
            <div className={styles.gridName} title={folder.name}>{folder.name}</div>
            <div className={styles.gridSize}>文件夹</div>
          </div>
        ))}
        {files.map((file) => (
          <div
            key={file.id}
            className={`${styles.gridItem} ${selectedIds.has(file.id) ? styles.gridItemSelected : ""}`}
            onClick={() => onToggleSelect(file.id)}
            onDoubleClick={() => onPreview(file)}
            draggable
            onDragStart={(e) => handleFileDragStart(e, file.id)}
          >
            <Thumbnail file={file} />
            <div className={styles.gridName} title={file.filename}>{file.filename}</div>
            <div className={styles.gridSize}>{formatSize(file.size)}</div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <table className={styles.table}>
      <thead>
        <tr className={styles.tableHeader}>
          <th className={styles.checkboxCol}></th>
          <th className={styles.nameCol}>文件名</th>
          <th className={styles.sizeCol}>大小</th>
          <th className={styles.typeCol}>类型</th>
          <th className={styles.dateCol}>修改时间</th>
          <th className={styles.actionCol}>操作</th>
        </tr>
      </thead>
      <tbody>
        {folders?.map((folder) => (
          <tr
            key={`folder-${folder.id}`}
            className={`${styles.tableRow} ${dragOverFolderId === folder.id ? styles.tableRowDropTarget : ""}`}
            onClick={() => onOpenFolder?.(folder)}
            onDragOver={(e) => handleFolderDragOver(e, folder.id)}
            onDragLeave={() => setDragOverFolderId(null)}
            onDrop={(e) => handleFolderDrop(e, folder.id)}
          >
            <td className={styles.checkboxCol}></td>
            <td className={styles.nameCol}>
              <div className={styles.fileNameCell}>
                <span className={styles.fileIcon}>📁</span>
                <span className={styles.fileName} title={folder.name}>{folder.name}</span>
              </div>
            </td>
            <td className={styles.sizeCol}>—</td>
            <td className={styles.typeCol}>文件夹</td>
            <td className={styles.dateCol}>{formatDate(folder.created_at)}</td>
            <td className={styles.actionCol}>
              <button className={styles.rowActionBtn} onClick={(e) => { e.stopPropagation(); onRenameFolder?.(folder); }}>
                重命名
              </button>
              <button className={styles.rowActionBtn} onClick={(e) => { e.stopPropagation(); onDeleteFolder?.(folder); }}>
                删除
              </button>
            </td>
          </tr>
        ))}
        {files.map((file) => (
          <tr
            key={file.id}
            className={`${styles.tableRow} ${selectedIds.has(file.id) ? styles.tableRowSelected : ""}`}
            onClick={() => onToggleSelect(file.id)}
            draggable
            onDragStart={(e) => handleFileDragStart(e, file.id)}
          >
            <td className={styles.checkboxCol}>
              <input
                type="checkbox"
                checked={selectedIds.has(file.id)}
                onChange={(e) => { e.stopPropagation(); onToggleSelect(file.id); }}
                className={styles.checkbox}
              />
            </td>
            <td className={styles.nameCol}>
              <div className={styles.fileNameCell}>
                <Thumbnail file={file} variant="list" />
                <span className={styles.fileName} title={file.filename}>{file.filename}</span>
              </div>
            </td>
            <td className={styles.sizeCol}>{formatSize(file.size)}</td>
            <td className={styles.typeCol}>{file.file_type}</td>
            <td className={styles.dateCol}>{formatDate(file.created_at)}</td>
            <td className={styles.actionCol}>
              <button className={styles.rowActionBtn} onClick={(e) => { e.stopPropagation(); onPreview(file); }}>
                预览
              </button>
              <button className={styles.rowActionBtn} onClick={(e) => { e.stopPropagation(); onDownload(file); }}>
                下载
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}