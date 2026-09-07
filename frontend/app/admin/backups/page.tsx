"use client";

import PageHeader from "../components/PageHeader";
import ErrorBar from "../components/ErrorBar";
import BackupTable from "../components/BackupTable";
import { useAdminBackups } from "../hooks/useAdminBackups";
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

  return (
    <div className={styles.page}>
      <PageHeader
        title="备份管理"
        subtitle="查看、触发与下载系统备份"
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

