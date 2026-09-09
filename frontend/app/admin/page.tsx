"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getAdminStats, type AdminStats } from "@/lib/api/admin";
import { useTranslation } from "@/lib/i18n";
import StatCard from "./components/StatCard";
import StorageBar from "./components/StorageBar";
import PageHeader from "./components/PageHeader";
import styles from "./page.module.css";

export default function AdminDashboardPage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { t } = useTranslation();

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await getAdminStats();
        if (active) setStats(data);
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : t("admin.overview.loadFailed"));
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, []);

  if (loading) return <div className={styles.loading}>{t("admin.overview.loading")}</div>;
  if (error) return <div className={styles.error}>{error}</div>;
  if (!stats) return null;

  return (
    <div className={styles.page}>
      <PageHeader title={t("admin.overview.title")} subtitle={t("admin.overview.subtitle")} />

      <div className={styles.cardGrid}>
        <StatCard label={t("admin.overview.totalUsers")} value={stats.total_users} hint={t("admin.overview.totalUsersHint")} color="blue" />
        <StatCard label={t("admin.overview.activeUsers")} value={stats.active_users} hint={t("admin.overview.activeUsersHint")} color="green" />
        <StatCard label={t("admin.overview.adminUsers")} value={stats.admin_users} hint={t("admin.overview.adminUsersHint")} color="purple" />
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHead}>
          <h2 className={styles.sectionTitle}>{t("admin.overview.storageUsage")}</h2>
          <Link href="/admin/users" className={styles.link}>{t("admin.overview.manageQuotaLink")}</Link>
        </div>
        <StorageBar used={stats.total_used} total={stats.total_quota} />
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHead}>
          <h2 className={styles.sectionTitle}>{t("admin.overview.userManagement")}</h2>
          <Link href="/admin/users" className={styles.link}>{t("admin.overview.enterLink")}</Link>
        </div>
        <p className={styles.sectionDesc}>
          {t("admin.overview.userManagementDesc")}
        </p>
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHead}>
          <h2 className={styles.sectionTitle}>{t("admin.overview.backupManagement")}</h2>
          <Link href="/admin/backups" className={styles.link}>{t("admin.overview.enterLink")}</Link>
        </div>
        <p className={styles.sectionDesc}>
          {t("admin.overview.backupManagementDesc")}
        </p>
      </div>
    </div>
  );
}