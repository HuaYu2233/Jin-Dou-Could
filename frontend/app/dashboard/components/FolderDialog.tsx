"use client";

import type { FolderItem } from "@/lib/api/files";
import pageStyles from "../page.module.css";

interface FolderDialogProps {
  dialog: { mode: "create" } | { mode: "rename"; folder: FolderItem } | null;
  folderName: string;
  onFolderNameChange: (name: string) => void;
  onSubmit: () => void;
  onClose: () => void;
}

export default function FolderDialog({
  dialog,
  folderName,
  onFolderNameChange,
  onSubmit,
  onClose,
}: FolderDialogProps) {
  if (!dialog) return null;

  return (
    <div className={pageStyles.modalOverlay} onClick={onClose}>
      <div className={pageStyles.modalContent} onClick={(e) => e.stopPropagation()}>
        <h3 className={pageStyles.modalTitle}>
          {dialog.mode === "create" ? "新建文件夹" : "重命名文件夹"}
        </h3>
        <input
          className={pageStyles.modalInput}
          value={folderName}
          onChange={(e) => onFolderNameChange(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onSubmit()}
          autoFocus
          placeholder="请输入文件夹名称"
        />
        <div className={pageStyles.modalActions}>
          <button className={pageStyles.modalCancelBtn} onClick={onClose}>
            取消
          </button>
          <button
            className={pageStyles.modalConfirmBtn}
            onClick={onSubmit}
            disabled={!folderName.trim()}
          >
            确定
          </button>
        </div>
      </div>
    </div>
  );
}
