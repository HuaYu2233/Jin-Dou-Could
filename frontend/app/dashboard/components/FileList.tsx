// /Users/zero/project/JinDou-Cloud/frontend/app/dashboard/components/FileList.tsx
"use client";

import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import { VirtuosoGrid, TableVirtuoso } from "react-virtuoso";
import type { FileItem, FolderItem, FolderTrashItem } from "@/lib/api/files";
import { getFileThumbnailUrl, getFilePreviewUrl } from "@/lib/api/files";
import { formatSize, formatDate } from "@/lib/utils/format";
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
  onToggleSelectAll?: (select: boolean) => void;
  onDownload: (file: FileItem) => void;
  onPreview: (file: FileItem) => void;
  onOpenFolder?: (folder: FolderItem) => void;
  onRenameFolder?: (folder: FolderItem) => void;
  onDeleteFolder?: (folder: FolderItem) => void;
  onMoveToFolder?: (fileIds: string[], folderId: string | null) => void;
  onRestoreFolder?: (folder: FolderTrashItem) => void;
  onPurgeFolder?: (folder: FolderTrashItem) => void;
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

const THUMB_URL_TTL = 30 * 60 * 1000;
const thumbUrlCache = new Map<string, { url: string; expires: number }>();
const thumbUrlInFlight = new Map<string, Promise<string>>();

function thumbCacheKey(file: FileItem): string {
  return file.thumbnail_key ? `${file.id}:thumbnail` : `${file.id}:preview`;
}

function resolveThumbUrl(file: FileItem): Promise<string> {
  const key = thumbCacheKey(file);
  const cached = thumbUrlCache.get(key);
  if (cached && cached.expires > Date.now()) return Promise.resolve(cached.url);

  const pending = thumbUrlInFlight.get(key);
  if (pending) return pending;

  const request = (file.thumbnail_key ? getFileThumbnailUrl(file.id).then((res) => res.url) : getFilePreviewUrl(file.id))
    .then((url) => {
      thumbUrlCache.set(key, { url, expires: Date.now() + THUMB_URL_TTL });
      return url;
    })
    .finally(() => {
      thumbUrlInFlight.delete(key);
    });

  thumbUrlInFlight.set(key, request);
  return request;
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

    resolveThumbUrl(file)
      .then((url) => {
        if (active) setThumbUrl(url);
      })
      .catch(() => {
        if (active) setFailed(true);
      });

    return () => { active = false; };
  }, [file, failed]);

  const handleLoad = useCallback(() => setLoaded(true), []);
  const handleError = useCallback(() => {
    thumbUrlCache.delete(thumbCacheKey(file));
    setFailed(true);
  }, [file]);

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
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        ref={imgRef}
        className={`${isList ? styles.listThumbnail : styles.gridThumbnail} ${loaded ? styles.thumbLoaded : styles.thumbBlur}`}
        src={thumbUrl}
        alt={file.filename}
        loading="lazy"
        onLoad={handleLoad}
        onError={handleError}
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
  onToggleSelectAll,
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

  function handleFileDragEnd() {
    setDragOverFolderId(null);
  }

  function handleRowClick(item: UnifiedItem) {
    if (item.type === "file") {
      onToggleSelect(item.data.id);
      return;
    }
    if (item.type === "folder") {
      onOpenFolder?.(item.data);
    }
  }

  function handleFolderDragOver(e: React.DragEvent, folderId: string | null) {
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = "move";
    setDragOverFolderId(folderId ?? "root");
  }

  function handleFolderDragLeave(e: React.DragEvent) {
    if (e.currentTarget.contains(e.relatedTarget as Node | null)) return;
    setDragOverFolderId(null);
  }

  function handleFolderDrop(e: React.DragEvent, folderId: string | null) {
    e.preventDefault();
    e.stopPropagation();
    setDragOverFolderId(null);
    const fileId = e.dataTransfer.getData("text/plain");
    if (fileId) onMoveToFolder?.([fileId], folderId);
  }

  const selectableIds = useMemo(() => files.map((file) => file.id), [files]);
  const selectedFileCount = useMemo(
    () => selectableIds.reduce((count, id) => (selectedIds.has(id) ? count + 1 : count), 0),
    [selectableIds, selectedIds]
  );
  const allSelected = selectableIds.length > 0 && selectedFileCount === selectableIds.length;
  const partiallySelected = selectedFileCount > 0 && !allSelected;

  const selectAllRef = useCallback(
    (el: HTMLInputElement | null) => {
      if (el) el.indeterminate = partiallySelected;
    },
    [partiallySelected]
  );

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
      <div className={styles.gridLayout}>
        {selectableIds.length > 0 && (
          <div className={styles.gridSelectBar}>
            <label className={styles.selectAllLabel}>
              <input
                type="checkbox"
                className={styles.checkbox}
                checked={allSelected}
                ref={selectAllRef}
                onChange={() => onToggleSelectAll?.(!allSelected)}
                aria-label="全选"
              />
              <span>全选</span>
            </label>
            <span className={styles.selectCount}>
              {selectedFileCount} / {selectableIds.length}
            </span>
          </div>
        )}
        <div className={styles.gridScroll}>
          <VirtuosoGrid
            data={unifiedItems}
            listClassName={styles.gridContainer}
            itemClassName={styles.gridItem}
            itemContent={(_, item) => {
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
                const folderId = item?.type === "folder" ? item.data.id : null;
                const fileId = item?.type === "file" ? item.data.id : null;
                let className = styles.gridItem;
                if (item) {
                  if (item.type === "folder" && dragOverFolderId === item.data.id) {
                    className += ` ${styles.gridItemDropTarget}`;
                  } else if (item.type === "file" && selectedIds.has(item.data.id)) {
                    className += ` ${styles.gridItemSelected}`;
                  }
                }
                return (
                  <div
                    {...props}
                    className={className}
                    onClick={item ? () => handleRowClick(item) : undefined}
                    onKeyDown={
                      item
                        ? (e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              handleRowClick(item);
                            }
                          }
                        : undefined
                    }
                    tabIndex={item ? 0 : undefined}
                    role={item ? "button" : undefined}
                    draggable={fileId ? true : undefined}
                    onDragStart={fileId ? (e) => handleFileDragStart(e, fileId) : undefined}
                    onDragEnd={fileId ? handleFileDragEnd : undefined}
                    onDragOver={folderId ? (e) => handleFolderDragOver(e, folderId) : undefined}
                    onDragLeave={folderId ? handleFolderDragLeave : undefined}
                    onDrop={folderId ? (e) => handleFolderDrop(e, folderId) : undefined}
                  >
                    {children}
                  </div>
                );
              },
            }}
          />
        </div>
      </div>
    );
  }

  return (
    <TableVirtuoso
      data={unifiedItems}
      fixedItemHeight={52}
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
              <th className={styles.checkboxCol}>
                <input
                  type="checkbox"
                  className={styles.checkbox}
                  checked={allSelected}
                  ref={selectAllRef}
                  onChange={() => onToggleSelectAll?.(!allSelected)}
                  disabled={selectableIds.length === 0}
                  aria-label="全选"
                />
              </th>
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
          const folderId = item?.type === "folder" ? item.data.id : null;
          const fileId = item?.type === "file" ? item.data.id : null;
          let className = styles.tableRow;
          if (item) {
            if (item.type === "folder" && dragOverFolderId === item.data.id) {
              className += ` ${styles.tableRowDropTarget}`;
            } else if (item.type === "file" && selectedIds.has(item.data.id)) {
              className += ` ${styles.tableRowSelected}`;
            }
          }
          return (
            <tr
              {...props}
              className={className}
              onClick={item ? () => handleRowClick(item) : undefined}
              aria-selected={fileId ? selectedIds.has(fileId) : undefined}
              draggable={fileId ? true : undefined}
              onDragStart={fileId ? (e) => handleFileDragStart(e, fileId) : undefined}
              onDragEnd={fileId ? handleFileDragEnd : undefined}
              onDragOver={folderId ? (e) => handleFolderDragOver(e, folderId) : undefined}
              onDragLeave={folderId ? handleFolderDragLeave : undefined}
              onDrop={folderId ? (e) => handleFolderDrop(e, folderId) : undefined}
            >
              {children}
            </tr>
          );
        },
      }}
      itemContent={(_, item) => {
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
                onClick={(e) => e.stopPropagation()}
                onChange={() => onToggleSelect(file.id)}
                className={styles.checkbox}
                aria-label={file.filename}
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