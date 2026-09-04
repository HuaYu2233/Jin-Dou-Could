// /Users/zero/project/JinDou-Cloud/frontend/app/dashboard/page.tsx
"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
  listFiles,
  listTrashFiles,
  searchFiles,
  listFolderContents,
  type FileItem,
  type FolderItem,
} from "@/lib/api/files";
import type { CategoryId, ViewMode, BreadcrumbItem, StorageInfo } from "./types";
import { useAuthStore } from "@/stores/auth";
import Sidebar from "./components/Sidebar";
import Toolbar from "./components/Toolbar";
import Breadcrumb from "./components/Breadcrumb";
import FileList from "./components/FileList";
import Pagination from "./components/Pagination";
import FilePreview from "./components/FilePreview";
import MoveDialog from "./components/MoveDialog";
import SharesView from "./components/SharesView";
import { useFileOperations } from "./hooks/useFileOperations";
import pageStyles from "./page.module.css";

const PAGE_SIZE = 20;

export default function DashboardPage() {
  const [category, setCategory] = useState<CategoryId>("all");
  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [files, setFiles] = useState<FileItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [dragOver, setDragOver] = useState(false);
  const [previewFile, setPreviewFile] = useState<FileItem | null>(null);
  const [sharesReloadKey, setSharesReloadKey] = useState(0);
  const [currentFolderId, setCurrentFolderId] = useState<string | null>(null);
  const [folders, setFolders] = useState<FolderItem[]>([]);
  const [folderDialog, setFolderDialog] = useState<{ mode: "create" } | { mode: "rename"; folder: FolderItem } | null>(null);
  const [folderName, setFolderName] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [moveDialogOpen, setMoveDialogOpen] = useState(false);
  const [keyword, setKeyword] = useState("");
  const [debouncedKeyword, setDebouncedKeyword] = useState("");

  const user = useAuthStore((s) => s.user);
  const fetchMe = useAuthStore((s) => s.fetchMe);
  const storage: StorageInfo = {
    used: user?.used_storage ?? 0,
    total: user?.storage_quota ?? 1024 * 1024 * 1024,
  };

  const [breadcrumbs, setBreadcrumbs] = useState<BreadcrumbItem[]>([
    { id: "root", name: "全部文件", path: "/" },
  ]);

  const loadFiles = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      if (category === "all") {
        const res = await listFolderContents(currentFolderId ?? undefined, (page - 1) * PAGE_SIZE, PAGE_SIZE);
        setFolders(res.folders);
        setFiles(res.files);
        setBreadcrumbs(res.breadcrumbs.map((b) => ({ ...b, id: b.id ?? "root" })));
        setTotal(res.total_files);
      } else if (category === "trash") {
        const res = await listTrashFiles((page - 1) * PAGE_SIZE, PAGE_SIZE);
        setFiles(res.items);
        setTotal(res.total);
        setFolders([]);
      } else {
        const res = await listFiles((page - 1) * PAGE_SIZE, PAGE_SIZE, category);
        setFiles(res.items);
        setTotal(res.total);
        setFolders([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [category, page, currentFolderId]);

  const {
    uploading,
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
  } = useFileOperations({
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
  });

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedKeyword(keyword), 300);
    return () => clearTimeout(timer);
  }, [keyword]);

  useEffect(() => {
    let active = true;
    (async () => {
      if (debouncedKeyword) {
        if (active) { setLoading(true); setError(""); }
        try {
          const res = await searchFiles(debouncedKeyword, (page - 1) * PAGE_SIZE, PAGE_SIZE);
          if (active) { setFiles(res.items); setTotal(res.total); setFolders([]); }
        } catch (err) {
          if (active) setError(err instanceof Error ? err.message : "搜索失败");
        } finally {
          if (active) setLoading(false);
        }
        return;
      }
      if (category === "shares") {
        return;
      }
      if (active) { setLoading(true); setError(""); }
      try {
        if (category === "all") {
          const res = await listFolderContents(currentFolderId ?? undefined, (page - 1) * PAGE_SIZE, PAGE_SIZE);
          if (active) {
            setFolders(res.folders);
            setFiles(res.files);
            setBreadcrumbs(res.breadcrumbs.map((b) => ({ ...b, id: b.id ?? "root" })));
            setTotal(res.total_files);
          }
        } else if (category === "trash") {
          const res = await listTrashFiles((page - 1) * PAGE_SIZE, PAGE_SIZE);
          if (active) { setFiles(res.items); setTotal(res.total); setFolders([]); }
        } else {
          const res = await listFiles((page - 1) * PAGE_SIZE, PAGE_SIZE, category);
          if (active) { setFiles(res.items); setTotal(res.total); setFolders([]); }
        }
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : "加载失败");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [category, page, currentFolderId, debouncedKeyword]);

  function handleCategoryChange(id: CategoryId) {
    setCategory(id);
    setPage(1);
    setSelectedIds(new Set());
    setCurrentFolderId(null);
  }

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function handlePreview(file: FileItem) {
    setPreviewFile(file);
  }

  function handleBreadcrumbNavigate(path: string) {
    if (path === "/") {
      setCurrentFolderId(null);
    } else {
      const match = path.match(/^\/folder\/(.+)$/);
      if (match) setCurrentFolderId(match[1]);
    }
    setPage(1);
    setSelectedIds(new Set());
  }

  function handleOpenFolder(folder: FolderItem) {
    setCurrentFolderId(folder.id);
    setPage(1);
    setSelectedIds(new Set());
  }

  function openCreateFolderDialog() {
    setFolderName("");
    setFolderDialog({ mode: "create" });
  }

  function openRenameFolderDialog(folder: FolderItem) {
    setFolderName(folder.name);
    setFolderDialog({ mode: "rename", folder });
  }

  const selectedCount = selectedIds.size;
  const selectedFile = files.find((f) => selectedIds.has(f.id));

  return (
    <div className={pageStyles.layout}>
      <Sidebar
        activeCategory={category}
        onCategoryChange={handleCategoryChange}
        storage={storage}
      />
      <div className={pageStyles.mainArea}>
        <Toolbar
          viewMode={viewMode}
          onViewModeChange={setViewMode}
          onUpload={() => fileInputRef.current?.click()}
          onDownload={() => selectedFile && handleDownload(selectedFile)}
          onDelete={handleDelete}
          onShare={handleCreateShare}
          onNewFolder={category === "all" ? openCreateFolderDialog : undefined}
          onMove={category === "all" ? () => setMoveDialogOpen(true) : undefined}
          selectedCount={selectedCount}
          uploading={uploading}
          isTrash={category === "trash"}
          onRestore={handleRestore}
          onPurge={handlePurge}
          keyword={keyword}
          onKeywordChange={(v) => {
            setKeyword(v);
            setPage(1);
          }}
        />
        <input
          ref={fileInputRef}
          type="file"
          style={{ display: "none" }}
          onChange={handleFileSelect}
        />
        <Breadcrumb items={breadcrumbs} onNavigate={handleBreadcrumbNavigate} />
        {error && (
          <div className="px-6 py-2 text-sm text-red-600 bg-red-50 border-b border-red-100">
            {error}
          </div>
        )}
        <div
          className={pageStyles.contentArea}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          style={dragOver ? { background: "#eff6ff" } : undefined}
        >
          {category === "trash" ? (
            <FileList
              files={files}
              viewMode={viewMode}
              loading={loading}
              selectedIds={selectedIds}
              onToggleSelect={toggleSelect}
              onDownload={() => {}}
              onPreview={() => {}}
            />
          ) : category === "shares" ? (
            <div className="p-6">
              <SharesView
                page={page}
                pageSize={PAGE_SIZE}
                onError={setError}
                onTotalChange={setTotal}
                reloadKey={sharesReloadKey}
              />
            </div>
          ) : (
            <FileList
              files={files}
              folders={folders}
              viewMode={viewMode}
              loading={loading}
              selectedIds={selectedIds}
              onToggleSelect={toggleSelect}
              onDownload={handleDownload}
              onPreview={handlePreview}
              onOpenFolder={handleOpenFolder}
              onRenameFolder={openRenameFolderDialog}
              onDeleteFolder={handleDeleteFolder}
              onMoveToFolder={handleMoveToFolder}
            />
          )}
        </div>
        <div className={pageStyles.paginationArea}>
          <Pagination
            page={page}
            pageSize={PAGE_SIZE}
            total={total}
            onPageChange={setPage}
          />
        </div>
      </div>
      {previewFile && (
        <FilePreview file={previewFile} onClose={() => setPreviewFile(null)} />
      )}
      {folderDialog && (
        <div className={pageStyles.modalOverlay} onClick={() => setFolderDialog(null)}>
          <div className={pageStyles.modalContent} onClick={(e) => e.stopPropagation()}>
            <h3 className={pageStyles.modalTitle}>
              {folderDialog.mode === "create" ? "新建文件夹" : "重命名文件夹"}
            </h3>
            <input
              className={pageStyles.modalInput}
              value={folderName}
              onChange={(e) => setFolderName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleFolderDialogSubmit()}
              autoFocus
              placeholder="请输入文件夹名称"
            />
            <div className={pageStyles.modalActions}>
              <button className={pageStyles.modalCancelBtn} onClick={() => setFolderDialog(null)}>
                取消
              </button>
              <button className={pageStyles.modalConfirmBtn} onClick={handleFolderDialogSubmit} disabled={!folderName.trim()}>
                确定
              </button>
            </div>
          </div>
        </div>
      )}
      <MoveDialog
        open={moveDialogOpen}
        selectedIds={selectedIds}
        currentFolderId={currentFolderId}
        onMoved={async () => {
          setSelectedIds(new Set());
          await loadFiles();
          fetchMe();
        }}
        onError={(msg) => setError(msg)}
        onClose={() => setMoveDialogOpen(false)}
      />
    </div>
  );
}