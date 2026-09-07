"use client";

import { useEffect } from "react";
import styles from "./Modal.module.css";

interface ModalProps {
  open: boolean;
  title: string;
  description?: string;
  saving?: boolean;
  savingText?: string;
  confirmText?: string;
  onConfirm: () => void;
  onClose: () => void;
  children?: React.ReactNode;
}

export default function Modal({
  open,
  title,
  description,
  saving = false,
  savingText = "保存中...",
  confirmText = "保存",
  onConfirm,
  onClose,
  children,
}: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !saving) onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, saving, onClose]);

  if (!open) return null;

  return (
    <div className={styles.overlay} onClick={() => !saving && onClose()}>
      <div className={styles.content} onClick={(e) => e.stopPropagation()}>
        <h3 className={styles.title}>{title}</h3>
        {description && <p className={styles.desc}>{description}</p>}
        {children}
        <div className={styles.actions}>
          <button className={styles.cancelBtn} onClick={onClose} disabled={saving}>
            取消
          </button>
          <button className={styles.confirmBtn} onClick={onConfirm} disabled={saving}>
            {saving ? savingText : confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
