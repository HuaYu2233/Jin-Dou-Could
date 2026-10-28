"use client";

import { useState, useEffect, useCallback } from "react";
import {
  listFiles,
  listTrashFiles,
  listTrashFolders,
  searchFiles,
  listFolderContents,
  type FileItem,
  type FolderItem,
  type FolderTrashItem,
} from "@/lib/api/files";
import type { CategoryId, BreadcrumbItem } from "../types";

const PAGE_SIZE = 20;

export function useFileList(category: CategoryId) {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [folders, setFolders] = useState<FolderItem[]>([]);
  const [trashedFolders, setTrashedFolders] = useState<FolderTrashItem[]>([]);
  const [currentFolderId, setCurrentFolderId] = useState<string | null>(null);
  const [keyword, setKeyword] = useState("");
  const [debouncedKeyword, setDebouncedKeyword] = useState("");
  const [breadcrumbs, setBreadcrumbs] = useState<BreadcrumbItem[]>([
    { id: "root", name: "全部文件", path: "/" },
  ]);

  const loadFiles = useCallback(async (active = true) => {
    if (category === "shares" || category === "transfers") return;
    if (!active) return;
    setLoading(true);
    setError("");
    setFiles([]);
    setFolders([]);
    setTrashedFolders([]);
    setTotal(0);
    try {
      if (debouncedKeyword) {
        const res = await searchFiles(debouncedKeyword, (page - 1) * PAGE_SIZE, PAGE_SIZE);
        if (!active) return;
        setFiles(res.items);
        setTotal(res.total);
        setFolders([]);
      } else if (category === "all") {
        const res = await listFolderContents(currentFolderId ?? undefined, (page - 1) * PAGE_SIZE, PAGE_SIZE);
        if (!active) return;
        setFolders(res.folders);
        setFiles(res.files);
        setBreadcrumbs(res.breadcrumbs.map((b) => ({ ...b, id: b.id ?? "root" })));
        setTotal(res.total_files);
      } else if (category === "trash") {
        const [fileRes, folderRes] = await Promise.all([
          listTrashFiles((page - 1) * PAGE_SIZE, PAGE_SIZE),
          listTrashFolders((page - 1) * PAGE_SIZE, PAGE_SIZE),
        ]);
        if (!active) return;
        setFiles(fileRes.items);
        setTrashedFolders(folderRes.items);
        setTotal(fileRes.total + folderRes.total);
        setFolders([]);
      } else {
        const res = await listFiles((page - 1) * PAGE_SIZE, PAGE_SIZE, category);
        if (!active) return;
        setFiles(res.items);
        setTotal(res.total);
        setFolders([]);
      }
    } catch (err) {
      if (active) setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      if (active) setLoading(false);
    }
  }, [category, page, currentFolderId, debouncedKeyword]);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedKeyword(keyword), 300);
    return () => clearTimeout(timer);
  }, [keyword]);

  useEffect(() => {
    let active = true;
    (async () => {
      await loadFiles(active);
    })();
    return () => { active = false; };
  }, [category, page, currentFolderId, debouncedKeyword, loadFiles]);

  return {
    files, folders, trashedFolders, total, page, loading, error, breadcrumbs,
    keyword, currentFolderId,
    PAGE_SIZE,
    setPage, setKeyword, setError, setCurrentFolderId, setTotal,
    loadFiles,
  };
}