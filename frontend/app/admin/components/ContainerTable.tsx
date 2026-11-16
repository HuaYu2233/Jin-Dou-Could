"use client";

import type { DeployContainerItem } from "@/lib/api/deploy";
import { useTranslation } from "@/lib/i18n";
import styles from "./ContainerTable.module.css";

interface ContainerTableProps {
  services: DeployContainerItem[];
  emptyText: string;
}

export default function ContainerTable({ services, emptyText }: ContainerTableProps) {
  const { t } = useTranslation();

  if (services.length === 0) {
    return <div className={styles.empty}>{emptyText}</div>;
  }

  return (
    <div className={styles.scroll}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th className={styles.th}>{t("admin.deploy.health.service")}</th>
            <th className={styles.th}>{t("admin.deploy.health.state")}</th>
            <th className={styles.th}>{t("admin.deploy.health.health")}</th>
            <th className={styles.th}>{t("admin.deploy.health.image")}</th>
            <th className={styles.th}>{t("admin.deploy.health.restarts")}</th>
          </tr>
        </thead>
        <tbody>
          {services.map((item) => (
            <tr key={item.service}>
              <td className={styles.td}>{item.service}</td>
              <td className={styles.td}>{item.state}</td>
              <td className={styles.td}>{item.health ?? "-"}</td>
              <td className={`${styles.td} ${styles.mono}`}>{item.image || "-"}</td>
              <td className={styles.td}>{item.restart_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}