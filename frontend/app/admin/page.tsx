"use client";

import { useQuery } from "@tanstack/react-query";
import { getAdminStats, type AdminStats } from "@/lib/api/admin";
import { useTranslation } from "@/lib/i18n";
import { queryKeys } from "@/lib/query/keys";
import StatCard from "./components/StatCard";
import StorageBar from "./components/StorageBar";
import PageHeader from "./components/PageHeader";
import styles from "./page.module.css";

export default function AdminDashboardPage() {
  const { t } = useTranslation();

  const { data: stats, isLoading: loading, error } = useQuery<AdminStats>({
    queryKey: queryKeys.admin.stats(),
    queryFn: getAdminStats,
  });

  const errorMsg = error ? (error instanceof Error ? error.message : t("admin.overview.loadFailed")) : null;

  if (loading) return <div className={styles.loading}>{t("admin.overview.loading")}</div>;
  if (errorMsg) return <div className={styles.error}>{errorMsg}</div>;
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
          <a href="/admin/users" className={styles.link}>{t("admin.overview.manageQuotaLink")}</a>
        </div>
        <StorageBar used={stats.total_used} total={stats.total_quota} />
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHead}>
          <h2 className={styles.sectionTitle}>{t("admin.overview.userManagement")}</h2>
          <a href="/admin/users" className={styles.link}>{t("admin.overview.enterLink")}</a>
        </div>
        <p className={styles.sectionDesc}>
          {t("admin.overview.userManagementDesc")}
        </p>
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHead}>
          <h2 className={styles.sectionTitle}>{t("admin.overview.backupManagement")}</h2>
          <a href="/admin/backups" className={styles.link}>{t("admin.overview.enterLink")}</a>
        </div>
        <p className={styles.sectionDesc}>
          {t("admin.overview.backupManagementDesc")}
        </p>
      </div>
    </div>
  );
}