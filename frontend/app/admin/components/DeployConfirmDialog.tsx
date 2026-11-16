"use client";

import { useState } from "react";
import Modal from "./Modal";
import { useTranslation } from "@/lib/i18n";
import styles from "./DeployConfirmDialog.module.css";

interface DeployConfirmDialogProps {
  action: string | null;
  saving: boolean;
  onConfirm: () => void;
  onClose: () => void;
}

const CONFIRM_DESC: Record<string, "admin.deploy.confirm.deploy" | "admin.deploy.confirm.rollback"> = {
  deploy: "admin.deploy.confirm.deploy",
  rollback: "admin.deploy.confirm.rollback",
};

export default function DeployConfirmDialog({
  action,
  saving,
  onConfirm,
  onClose,
}: DeployConfirmDialogProps) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState<{ action: string | null; text: string }>({
    action: null,
    text: "",
  });

  const typed = draft.action === action ? draft.text : "";
  const matched = action !== null && typed.trim() === action;
  const descKey = action ? CONFIRM_DESC[action] : undefined;

  return (
    <Modal
      open={!!action}
      title={t("admin.deploy.confirm.title")}
      description={descKey ? t(descKey) : undefined}
      saving={saving}
      confirmText={t("admin.deploy.confirm.submit")}
      onConfirm={() => {
        if (matched) onConfirm();
      }}
      onClose={onClose}
    >
      <label className={styles.label}>
        {action ? t("admin.deploy.confirm.inputHint", { action }) : ""}
      </label>
      <input
        type="text"
        value={typed}
        onChange={(e) => setDraft({ action, text: e.target.value })}
        className={styles.input}
        placeholder={action ?? ""}
        autoFocus
      />
      {typed.length > 0 && !matched && (
        <div className={styles.hint}>{t("admin.deploy.confirm.mismatch")}</div>
      )}
    </Modal>
  );
}