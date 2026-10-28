// /Users/zero/project/JinDou-Cloud/frontend/app/dashboard/components/FileList.tsx
"use client";

import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import { VirtuosoGrid, TableVirtuoso } from "react-virtuoso";
import type { FileItem, FolderItem, FolderTrashItem } from "@/lib/api/files";
import { getFileThumbnailUrl, getFilePreviewUrl } from "@/lib/api/files";
import type { ViewMode } from "../types";
import styles from "./FileList.module.css";

type UnifiedItem =
  | { type: "folder"; data: FolderItem }
  | { type: "trashedFolder"; data: FolderTrashItem }
  | { type: "file"; data: FileItem };

interface FileListProps {
  files: FileItem[];
  folders?: FolderItem[];
  trashedFolders?: FolderTrashItem[];
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
  onRestoreFolder?: (folder: FolderTrashItem) => void;
  onPurgeFolder?: (folder: FolderTrashItem) => void;
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
  const [thumbUrl, setThumbUrl] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  const isList = variant === "list";
  const imgRef = useRef<HTMLImageElement>(null);

  useEffect(() => {
    if (file.file_type !== "image" || failed) return;
    let active = true;

    if (file.thumbnail_key) {
      getFileThumbnailUrl(file.id)
        .then(({ url }) => {
          if (active) setThumbUrl(url);
        })
        .catch(() => {
          if (active) setFailed(true);
        });
    } else {
      getFilePreviewUrl(file.id)
        .then((url) => {
          if (active) setThumbUrl(url);
        })
        .catch(() => {
          if (active) setFailed(true);
        });
    }

    return () => { active = false; };
  }, [file.id, file.file_type, file.thumbnail_key, failed]);

  const handleLoad = useCallback(() => setLoaded(true), []);

  if (file.file_type !== "image" || failed) {
    return <span className={isList ? styles.fileIcon : styles.gridIcon}>{getFileIcon(file.file_type, file.mime_type)}</span>;
  }

  if (!thumbUrl) {
    return (
      <div className={isList ? styles.listThumbSkeleton : styles.gridThumbSkeleton}>
        <div className={styles.shimmer} />
      </div>
    );
  }

  return (
    <div className={isList ? styles.listThumbWrap : styles.gridThumbWrap}>
      <img
        ref={imgRef}
        className={`${isList ? styles.listThumbnail : styles.gridThumbnail} ${loaded ? styles.thumbLoaded : styles.thumbBlur}`}
        src={thumbUrl}
        alt={file.filename}
        loading="lazy"
        onLoad={handleLoad}
      />
    </div>
  );
}

export default function FileList({
  files,
  folders,
  trashedFolders,
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
  onRestoreFolder,
  onPurgeFolder,
}: FileListProps) {
  const [dragOverFolderId, setDragOverFolderId] = useState<string | null>(null);

  const unifiedItems = useMemo<UnifiedItem[]>(() => {
    const items: UnifiedItem[] = [];
    if (folders) {
      for (const folder of folders) items.push({ type: "folder", data: folder });
    }
    if (trashedFolders) {
      for (const folder of trashedFolders) items.push({ type: "trashedFolder", data: folder });
    }
    for (const file of files) items.push({ type: "file", data: file });
    return items;
  }, [files, folders, trashedFolders]);

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

  if (unifiedItems.length === 0) {
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
      <VirtuosoGrid
        data={unifiedItems}
        listClassName={styles.gridContainer}
        itemClassName={styles.gridItem}
        itemContent={(index, item) => {
          if (item.type === "folder") {
            const folder = item.data;
            return (
              <>
                <div className={styles.gridIcon}>📁</div>
                <div className={styles.gridName} title={folder.name}>{folder.name}</div>
                <div className={styles.gridSize}>文件夹</div>
              </>
            );
          }
          if (item.type === "trashedFolder") {
            const folder = item.data;
            return (
              <>
                <div className={styles.gridIcon}>📁</div>
                <div className={styles.gridName} title={folder.name}>{folder.name}</div>
                <div className={styles.gridSize}>文件夹</div>
              </>
            );
          }
          const file = item.data;
          return (
            <>
              <Thumbnail file={file} />
              <div className={styles.gridName} title={file.filename}>{file.filename}</div>
              <div className={styles.gridSize}>{formatSize(file.size)}</div>
            </>
          );
        }}
        components={{
          Item: ({ children, ...props }) => {
            const item = unifiedItems[props["data-index"]];
            let className = styles.gridItem;
            if (item) {
              if (item.type === "folder" && dragOverFolderId === item.data.id) {
                className += ` ${styles.gridItemDropTarget}`;
              } else if (item.type === "file" && selectedIds.has(item.data.id)) {
                className += ` ${styles.gridItemSelected}`;
              }
            }
            return (
              <div {...props} className={className}>
                {children}
              </div>
            );
          },
        }}
      />
    );
  }

  return (
    <TableVirtuoso
      data={unifiedItems}
      fixedItemHeight={48}
      className={styles.table}
      components={{
        Table: ({ children, style }: { children?: React.ReactNode; style?: React.CSSProperties }) => (
          <table className={styles.table} style={style}>
            {children}
          </table>
        ),
        TableHead: ({ ...props }) => (
          <thead {...props}>
            <tr className={styles.tableHeader}>
              <th className={styles.checkboxCol}></th>
              <th className={styles.nameCol}>文件名</th>
              <th className={styles.sizeCol}>大小</th>
              <th className={styles.typeCol}>类型</th>
              <th className={styles.dateCol}>修改时间</th>
              <th className={styles.actionCol}>操作</th>
            </tr>
          </thead>
        ),
        TableRow: ({ children, ...props }) => {
          const item = unifiedItems[props["data-index"]];
          let className = styles.tableRow;
          if (item) {
            if (item.type === "folder" && dragOverFolderId === item.data.id) {
              className += ` ${styles.tableRowDropTarget}`;
            } else if (item.type === "file" && selectedIds.has(item.data.id)) {
              className += ` ${styles.tableRowSelected}`;
            }
          }
          return (
            <tr {...props} className={className}>
              {children}
            </tr>
          );
        },
      }}
      itemContent={(index, item) => {
        if (item.type === "folder") {
          const folder = item.data;
          return (
            <>
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
            </>
          );
        }
        if (item.type === "trashedFolder") {
          const folder = item.data;
          return (
            <>
              <td className={styles.checkboxCol}></td>
              <td className={styles.nameCol}>
                <div className={styles.fileNameCell}>
                  <span className={styles.fileIcon}>📁</span>
                  <span className={styles.fileName} title={folder.name}>{folder.name}</span>
                </div>
              </td>
              <td className={styles.sizeCol}>—</td>
              <td className={styles.typeCol}>文件夹</td>
              <td className={styles.dateCol}>{formatDate(folder.deleted_at)}</td>
              <td className={styles.actionCol}>
                <button className={styles.rowActionBtn} onClick={(e) => { e.stopPropagation(); onRestoreFolder?.(folder); }}>
                  恢复
                </button>
                <button className={styles.rowActionBtn} onClick={(e) => { e.stopPropagation(); onPurgeFolder?.(folder); }}>
                  彻底删除
                </button>
              </td>
            </>
          );
        }
        const file = item.data;
        return (
          <>
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
          </>
        );
      }}
    />
  );
}