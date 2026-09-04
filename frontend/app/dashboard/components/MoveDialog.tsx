"use client";

import { useState, useEffect } from "react";
import { listRootFolders, moveFiles, type FolderItem } from "@/lib/api/files";
import pageStyles from "../page.module.css";

interface MoveDialogProps {
  open: boolean;
  selectedIds: Set<string>;
  currentFolderId: string | null;
  onMoved: () => void;
  onError: (msg: string) => void;
  onClose: () => void;
}

export default function MoveDialog({
  open,
  selectedIds,
  currentFolderId,
  onMoved,
  onError,
  onClose,
}: MoveDialogProps) {
  const [targetFolders, setTargetFolders] = useState<FolderItem[]>([]);
  const [targetId, setTargetId] = useState<string | null>(null);
  const [moving, setMoving] = useState(false);

  useEffect(() => {
    if (!open) return;
    let active = true;
    listRootFolders()
      .then((folders) => {
        if (!active) return;
        setTargetId(null);
        setTargetFolders(folders.filter((f) => f.id !== currentFolderId));
      })
      .catch((err) => {
        if (!active) return;
        onError(err instanceof Error ? err.message : "加载文件夹失败");
        onClose();
      });
    return () => { active = false; };
  }, [open, currentFolderId, onError, onClose]);

  async function handleMove() {
    if (selectedIds.size === 0) return;
    if (targetId === currentFolderId) {
      onError("不能移动到当前所在文件夹");
      return;
    }
    setMoving(true);
    try {
      await moveFiles([...selectedIds], targetId ?? undefined);
      onClose();
      onMoved();
    } catch (err) {
      onError(err instanceof Error ? err.message : "移动失败");
    } finally {
      setMoving(false);
    }
  }

  if (!open) return null;

  return (
    <div className={pageStyles.modalOverlay} onClick={() => !moving && onClose()}>
      <div className={pageStyles.modalContent} onClick={(e) => e.stopPropagation()}>
        <h3 className={pageStyles.modalTitle}>移动 {selectedIds.size} 个文件到文件夹</h3>
        <div className="max-h-72 overflow-y-auto rounded border border-gray-200">
          <button
            className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-gray-50 ${targetId === null ? "bg-blue-50 text-blue-600 font-medium" : "text-gray-700"}`}
            onClick={() => setTargetId(null)}
          >
            🏠 根目录
          </button>
          {targetFolders.map((folder) => (
            <button
              key={folder.id}
              className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-gray-50 border-t border-gray-100 ${targetId === folder.id ? "bg-blue-50 text-blue-600 font-medium" : "text-gray-700"}`}
              onClick={() => setTargetId(folder.id)}
            >
              📁 {folder.name}
            </button>
          ))}
          {targetFolders.length === 0 && (
            <div className="px-3 py-4 text-center text-sm text-gray-400 border-t border-gray-100">暂无其他文件夹</div>
          )}
        </div>
        <div className={pageStyles.modalActions}>
          <button className={pageStyles.modalCancelBtn} onClick={onClose} disabled={moving}>
            取消
          </button>
          <button className={pageStyles.modalConfirmBtn} onClick={handleMove} disabled={moving}>
            {moving ? "移动中..." : "移动"}
          </button>
        </div>
      </div>
    </div>
  );
}