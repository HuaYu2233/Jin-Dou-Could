import { formatSize } from "@/lib/utils/format";
import styles from "./StorageBar.module.css";

interface StorageBarProps {
  used: number;
  total: number;
  size?: "md" | "sm";
  showText?: boolean;
}

export default function StorageBar({ used, total, size = "md", showText = true }: StorageBarProps) {
  const percent = total > 0 ? (used / total) * 100 : 0;
  const isDanger = percent > 90;
  return (
    <div>
      <div className={`${styles.bar} ${size === "sm" ? styles.barSm : ""}`}>
        <div
          className={`${styles.fill} ${isDanger ? styles.fillDanger : styles.fillNormal}`}
          style={{ width: `${Math.min(percent, 100)}%` }}
        />
      </div>
      {showText && (
        <div className={styles.text}>
          {formatSize(used)} / {formatSize(total)}
          <span className={styles.percent}>（{percent.toFixed(1)}%）</span>
        </div>
      )}
    </div>
  );
}