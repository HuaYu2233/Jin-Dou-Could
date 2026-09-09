import { useTranslation } from "@/lib/i18n";
import styles from "./ErrorBar.module.css";

interface ErrorBarProps {
  message: string | null;
  onClose: () => void;
}

export default function ErrorBar({ message, onClose }: ErrorBarProps) {
  const { t } = useTranslation();
  if (!message) return null;
  return (
    <div className={styles.bar}>
      {message}
      <button className={styles.close} onClick={onClose}>{t("common.close")}</button>
    </div>
  );
}