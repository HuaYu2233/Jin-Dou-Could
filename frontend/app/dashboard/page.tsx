// /Users/zero/project/JinDou-Cloud/frontend/app/dashboard/page.tsx
"use client";

import { useState, useRef } from "react";
import { type FileItem, type FolderItem, type ShareCreateResponse } from "@/lib/api/files";
import type { CategoryId, ViewMode, StorageInfo } from "./types";
import { useFileList } from "./hooks/useFileList";
import { useAuthStore } from "@/stores/auth";
import Sidebar from "./components/Sidebar";
import Toolbar from "./components/Toolbar";
import Breadcrumb from "./components/Breadcrumb";
import FileList from "./components/FileList";
import Pagination from "./components/Pagination";
import FilePreview from "./components/FilePreview";
import MoveDialog from "./components/MoveDialog";
import SharesView from "./components/SharesView";
import TransfersView from "./components/TransfersView";
import ShareResultDialog from "./components/ShareResultDialog";
import FolderDialog from "./components/FolderDialog";
import { useFileOperations } from "./hooks/useFileOperations";
import pageStyles from "./page.module.css";

export default function DashboardPage() {
  const [category, setCategory] = useState<CategoryId>("all");
  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [dragOver, setDragOver] = useState(false);
  const [previewFile, setPreviewFile] = useState<FileItem | null>(null);
  const [sharesReloadKey, setSharesReloadKey] = useState(0);
  const [folderDialog, setFolderDialog] = useState<{ mode: "create" } | { mode: "rename"; folder: FolderItem } | null>(null);
  const [folderName, setFolderName] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [moveDialogOpen, setMoveDialogOpen] = useState(false);
  const [shareResults, setShareResults] = useState<ShareCreateResponse[]>([]);

  const user = useAuthStore((s) => s.user);
  const fetchMe = useAuthStore((s) => s.fetchMe);
  const storage: StorageInfo = {
    used: user?.used_storage ?? 0,
    total: user?.storage_quota ?? 1024 * 1024 * 1024,
  };

  const {
    files, folders, total, page, loading, error, breadcrumbs,
    keyword, currentFolderId,
    PAGE_SIZE,
    setPage, setKeyword, setError, setCurrentFolderId, setTotal,
    loadFiles,
  } = useFileList(category);

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
          onShare={async () => {
            const results = await handleCreateShare();
            if (results.length > 0) setShareResults(results);
          }}
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
          ) : category === "transfers" ? (
            <div className="p-6">
              <TransfersView />
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
      <FolderDialog
        dialog={folderDialog}
        folderName={folderName}
        onFolderNameChange={setFolderName}
        onSubmit={handleFolderDialogSubmit}
        onClose={() => setFolderDialog(null)}
      />
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
      {shareResults.length > 0 && (
        <ShareResultDialog
          results={shareResults}
          onClose={() => setShareResults([])}
        />
      )}
    </div>
  );
}