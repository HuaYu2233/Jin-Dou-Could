"use client";

import PageHeader from "../components/PageHeader";
import ErrorBar from "../components/ErrorBar";
import BackupTable from "../components/BackupTable";
import { useAdminBackups } from "../hooks/useAdminBackups";
import { useTranslation } from "@/lib/i18n";
import styles from "./page.module.css";

export default function AdminBackupsPage() {
  const {
    backups,
    loading,
    error,
    triggering,
    setError,
    trigger,
    remove,
    download,
  } = useAdminBackups();
  const { t } = useTranslation();

  return (
    <div className={styles.page}>
      <PageHeader
        title={t("admin.backups.title")}
        subtitle={t("admin.backups.subtitle")}
      />

      <ErrorBar message={error} onClose={() => setError(null)} />

      <BackupTable
        backups={backups}
        loading={loading}
        triggering={triggering}
        onTrigger={trigger}
        onDownload={download}
        onDelete={remove}
      />
    </div>
  );
}