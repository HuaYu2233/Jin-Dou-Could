// /Users/zero/project/JinDou-Cloud/frontend/app/dashboard/components/Pagination.tsx
"use client";

import styles from "./Pagination.module.css";

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}

export default function Pagination({ page, pageSize, total, onPageChange }: PaginationProps) {
  const totalPages = Math.ceil(total / pageSize) || 1;
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  return (
    <div className={styles.pagination}>
      <span className={styles.info}>
        共 {total} 项，当前显示 {start}-{end} 项
      </span>
      <div className={styles.controls}>
        <button
          className={styles.pageBtn}
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
        >
          上一页
        </button>
        <span className={styles.pageIndicator}>
          {page} / {totalPages}
        </span>
        <button
          className={styles.pageBtn}
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
        >
          下一页
        </button>
      </div>
    </div>
  );
}