"use client";

import { useState, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
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
import { queryKeys } from "@/lib/query/keys";

const PAGE_SIZE = 20;

interface FileListResult {
  files: FileItem[];
  folders: FolderItem[];
  trashedFolders: FolderTrashItem[];
  total: number;
  breadcrumbs: BreadcrumbItem[];
}

export function useFileList(category: CategoryId) {
  const [page, setPage] = useState(1);
  const [currentFolderId, setCurrentFolderId] = useState<string | null>(null);
  const [keyword, setKeyword] = useState("");
  const [debouncedKeyword, setDebouncedKeyword] = useState("");
  const queryClient = useQueryClient();

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedKeyword(keyword), 300);
    return () => clearTimeout(timer);
  }, [keyword]);

  const enabled = category !== "shares" && category !== "transfers";

  const queryKey = queryKeys.files.list({
    category,
    page,
    folderId: currentFolderId,
    keyword: debouncedKeyword,
  });

  const { data, isLoading, error, refetch } = useQuery<FileListResult>({
    queryKey,
    enabled,
    queryFn: async () => {
      if (debouncedKeyword) {
        const res = await searchFiles(debouncedKeyword, (page - 1) * PAGE_SIZE, PAGE_SIZE);
        return { files: res.items, folders: [], trashedFolders: [], total: res.total, breadcrumbs: [] };
      }
      if (category === "all") {
        const res = await listFolderContents(currentFolderId ?? undefined, (page - 1) * PAGE_SIZE, PAGE_SIZE);
        return {
          files: res.files,
          folders: res.folders,
          trashedFolders: [],
          total: res.total_files,
          breadcrumbs: res.breadcrumbs.map((b) => ({ ...b, id: b.id ?? "root" })),
        };
      }
      if (category === "trash") {
        const [fileRes, folderRes] = await Promise.all([
          listTrashFiles((page - 1) * PAGE_SIZE, PAGE_SIZE),
          listTrashFolders((page - 1) * PAGE_SIZE, PAGE_SIZE),
        ]);
        return {
          files: fileRes.items,
          folders: [],
          trashedFolders: folderRes.items,
          total: fileRes.total + folderRes.total,
          breadcrumbs: [],
        };
      }
      const res = await listFiles((page - 1) * PAGE_SIZE, PAGE_SIZE, category);
      return { files: res.items, folders: [], trashedFolders: [], total: res.total, breadcrumbs: [] };
    },
  });

  function invalidateFiles() {
    queryClient.invalidateQueries({ queryKey: queryKeys.files.all });
  }

  return {
    files: data?.files ?? [],
    folders: data?.folders ?? [],
    trashedFolders: data?.trashedFolders ?? [],
    total: data?.total ?? 0,
    page,
    loading: isLoading,
    error: error ? (error instanceof Error ? error.message : "加载失败") : "",
    breadcrumbs: data?.breadcrumbs ?? [{ id: "root", name: "全部文件", path: "/" }],
    keyword,
    currentFolderId,
    PAGE_SIZE,
    setPage,
    setKeyword,
    setError: (_msg?: string) => {},
    setCurrentFolderId,
    setTotal: () => {},
    loadFiles: async (_active?: boolean) => { await refetch(); },
    invalidateFiles,
  };
}