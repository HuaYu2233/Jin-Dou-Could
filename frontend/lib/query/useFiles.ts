import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import {
  listFiles as apiListFiles,
  searchFiles as apiSearchFiles,
  listTrashFiles as apiListTrashFiles,
  deleteFile as apiDeleteFile,
  moveFiles as apiMoveFiles,
  restoreFile as apiRestoreFile,
  purgeFile as apiPurgeFile,
  FileListResponse,
} from "@/lib/api/files";

const STALE_TIME = 30_000;

export function useFileList(
  category: string,
  page: number,
  folderId: string | null,
  keyword: string
) {
  return useQuery<FileListResponse>({
    queryKey: queryKeys.files.list({ category, page, folderId, keyword }),
    queryFn: () => {
      if (keyword) return apiSearchFiles(keyword, (page - 1) * 20, 20);
      if (category === "trash") return apiListTrashFiles((page - 1) * 20, 20);
      const fileType = category !== "all" ? category : undefined;
      return apiListFiles((page - 1) * 20, 20, fileType);
    },
    staleTime: STALE_TIME,
  });
}

export function useDeleteFile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: apiDeleteFile,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.files.all });
    },
  });
}

export function useMoveFiles() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { fileIds: string[]; targetFolderId?: string }) =>
      apiMoveFiles(params.fileIds, params.targetFolderId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.files.all });
    },
  });
}

export function useRestoreFile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: apiRestoreFile,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.files.all });
    },
  });
}

export function usePurgeFile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: apiPurgeFile,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.files.all });
    },
  });
}