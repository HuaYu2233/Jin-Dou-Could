import styles from "./ErrorBar.module.css";

interface ErrorBarProps {
  message: string | null;
  onClose: () => void;
}

export default function ErrorBar({ message, onClose }: ErrorBarProps) {
  if (!message) return null;
  return (
    <div className={styles.bar}>
      {message}
      <button className={styles.close} onClick={onClose}>关闭</button>
    </div>
  );
}
