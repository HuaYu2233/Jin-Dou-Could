import React from "react";
import Image from "next/image";
import styles from "./auth.module.css";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <div className={styles.brandRow}>
          <span className={styles.brandMark} aria-hidden="true">
            <Image src="/logo-badge-light.png" alt="" width={46} height={46} priority className={styles.brandLogo} />
          </span>
          <span className={styles.brandName}>JinDou Cloud</span>
          <span className={styles.tagline}>安全存储 · 随时随地访问</span>
        </div>
        <React.Suspense fallback={<div className={styles.loading}>加载中...</div>}>
          {children}
        </React.Suspense>
      </div>
    </div>
  );
}