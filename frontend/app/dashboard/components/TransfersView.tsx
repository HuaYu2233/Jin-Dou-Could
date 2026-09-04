"use client";

import { useTransferStore, type TransferTask } from "@/stores/transfers";
import styles from "./TransfersView.module.css";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function statusLabel(task: TransferTask): string {
  switch (task.status) {
    case "pending": return "等待中";
    case "transferring": return "传输中";
    case "completed": return "已完成";
    case "error": return "失败";
    case "canceled": return "已取消";
    default: return "";
  }
}

export default function TransfersView() {
  const tasks = useTransferStore((s) => s.tasks);
  const removeTask = useTransferStore((s) => s.removeTask);
  const clearCompleted = useTransferStore((s) => s.clearCompleted);

  const activeCount = tasks.filter(
    (t) => t.status === "pending" || t.status === "transferring"
  ).length;

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <h3 className={styles.title}>传输列表</h3>
          {activeCount > 0 && (
            <span className={styles.activeBadge}>{activeCount} 个进行中</span>
          )}
        </div>
        {tasks.some((t) => t.status !== "transferring" && t.status !== "pending") && (
          <button className={styles.clearBtn} onClick={clearCompleted}>
            清除已完成
          </button>
        )}
      </div>

      {tasks.length === 0 ? (
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>⚡</div>
          <p className={styles.emptyTitle}>暂无传输任务</p>
          <p className={styles.emptyDesc}>上传或下载文件时将在此处显示进度</p>
        </div>
      ) : (
        <div className={styles.taskList}>
          {tasks.map((task) => (
            <div key={task.id} className={styles.taskItem}>
              <div className={styles.taskIcon}>
                {task.type === "upload" ? "⬆️" : "⬇️"}
              </div>
              <div className={styles.taskBody}>
                <div className={styles.taskTop}>
                  <span className={styles.taskName} title={task.filename}>
                    {task.filename}
                  </span>
                  <span className={`${styles.taskStatus} ${styles[`status_${task.status}`] || ""}`}>
                    {statusLabel(task)}
                  </span>
                </div>
                <div className={styles.progressBar}>
                  <div
                    className={`${styles.progressFill} ${styles[`fill_${task.status}`] || ""}`}
                    style={{ width: `${task.progress}%` }}
                  />
                </div>
                <div className={styles.taskBottom}>
                  <span className={styles.taskSize}>
                    {formatBytes(task.loaded)} / {task.total > 0 ? formatBytes(task.total) : "未知"}
                  </span>
                  <span className={styles.taskPercent}>{task.progress}%</span>
                  {task.error && <span className={styles.taskError}>{task.error}</span>}
                </div>
              </div>
              {(task.status === "completed" || task.status === "error" || task.status === "canceled") && (
                <button
                  className={styles.removeBtn}
                  onClick={() => removeTask(task.id)}
                  title="移除"
                >
                  ✕
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
