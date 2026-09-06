"use client";

import { useState, useEffect } from "react";
import type { AdminUserItem } from "@/lib/api/admin";
import pageStyles from "../page.module.css";

interface QuotaDialogProps {
  user: AdminUserItem | null;
  saving: boolean;
  onSave: (bytes: number) => void;
  onClose: () => void;
}

export default function QuotaDialog({ user, saving, onSave, onClose }: QuotaDialogProps) {
  const [value, setValue] = useState("");

  useEffect(() => {
    if (!user) return;
    let active = true;
    (async () => {
      const gb = Math.round((user.storage_quota / (1024 * 1024 * 1024)) * 100) / 100;
      if (active) setValue(String(gb));
    })();
    return () => { active = false; };
  }, [user]);

  if (!user) return null;

  function handleSubmit() {
    const gb = parseFloat(value);
    if (isNaN(gb) || gb < 0) return;
    onSave(Math.round(gb * 1024 * 1024 * 1024));
  }

  return (
    <div className={pageStyles.modalOverlay} onClick={() => !saving && onClose()}>
      <div className={pageStyles.modalContent} onClick={(e) => e.stopPropagation()}>
        <h3 className={pageStyles.modalTitle}>修改存储配额</h3>
        <p className={pageStyles.modalDesc}>
          用户：{user.username}（{user.email}）
        </p>
        <label className={pageStyles.modalLabel}>配额大小（GB）</label>
        <input
          type="number"
          step="0.1"
          min="0"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className={pageStyles.modalInput}
          autoFocus
        />
        <div className={pageStyles.modalActions}>
          <button className={pageStyles.modalCancelBtn} onClick={onClose} disabled={saving}>
            取消
          </button>
          <button className={pageStyles.modalConfirmBtn} onClick={handleSubmit} disabled={saving}>
            {saving ? "保存中..." : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}