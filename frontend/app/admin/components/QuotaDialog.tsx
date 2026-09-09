"use client";

import { useState, useEffect } from "react";
import type { AdminUserItem } from "@/lib/api/admin";
import Modal from "./Modal";
import { useTranslation } from "@/lib/i18n";
import styles from "./QuotaDialog.module.css";

interface QuotaDialogProps {
  user: AdminUserItem | null;
  saving: boolean;
  onSave: (bytes: number) => void;
  onClose: () => void;
}

export default function QuotaDialog({ user, saving, onSave, onClose }: QuotaDialogProps) {
  const { t } = useTranslation();
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

  function handleSubmit() {
    const gb = parseFloat(value);
    if (isNaN(gb) || gb < 0) return;
    onSave(Math.round(gb * 1024 * 1024 * 1024));
  }

  return (
    <Modal
      open={!!user}
      title={t("admin.quota.title")}
      description={user ? t("admin.quota.desc", { username: user.username, email: user.email }) : undefined}
      saving={saving}
      onConfirm={handleSubmit}
      onClose={onClose}
    >
      <label className={styles.label}>{t("admin.quota.label")}</label>
      <input
        type="number"
        step="0.1"
        min="0"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        className={styles.input}
        autoFocus
      />
    </Modal>
  );
}