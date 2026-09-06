"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getAdminStats, type AdminStats } from "@/lib/api/admin";
import StatCard from "./components/StatCard";
import StorageBar from "./components/StorageBar";
import styles from "./page.module.css";

export default function AdminDashboardPage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await getAdminStats();
        if (active) setStats(data);
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : "加载失败");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, []);

  if (loading) return <div className={styles.loading}>加载中...</div>;
  if (error) return <div className={styles.error}>{error}</div>;
  if (!stats) return null;

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>系统概览</h1>
        <p className={styles.subtitle}>查看网盘整体运行情况</p>
      </div>

      <div className={styles.cardGrid}>
        <StatCard label="用户总数" value={stats.total_users} hint="所有注册用户" color="blue" />
        <StatCard label="活跃用户" value={stats.active_users} hint="已启用账号" color="green" />
        <StatCard label="管理员" value={stats.admin_users} hint="拥有管理权限" color="purple" />
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHead}>
          <h2 className={styles.sectionTitle}>存储用量</h2>
          <Link href="/admin/users" className={styles.link}>管理用户配额 →</Link>
        </div>
        <StorageBar used={stats.total_used} total={stats.total_quota} />
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHead}>
          <h2 className={styles.sectionTitle}>用户管理</h2>
          <Link href="/admin/users" className={styles.link}>进入 →</Link>
        </div>
        <p className={styles.sectionDesc}>
          调整用户存储配额、启用/禁用账号、设置管理员权限或删除用户。
        </p>
      </div>
    </div>
  );
}