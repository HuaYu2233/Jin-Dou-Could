"use client";

import { useState } from "react";
import PageHeader from "../components/PageHeader";
import { useAdminEnvConfig } from "../hooks/useAdminEnvConfig";
import { useTranslation } from "@/lib/i18n";
import styles from "./page.module.css";

export default function AdminEnvConfigPage() {
  const {
    config,
    loading,
    error,
    disabled,
    saveError,
    savedBackup,
    saving,
    generating,
    save,
    generate,
    clearMessages,
  } = useAdminEnvConfig();
  const { t } = useTranslation();
  const [values, setValues] = useState<Record<string, string> | null>(null);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  if (loading) return <div className={styles.loading}>{t("admin.envConfig.loading")}</div>;

  if (disabled) {
    return (
      <div className={styles.page}>
        <PageHeader title={t("admin.envConfig.title")} subtitle={t("admin.envConfig.subtitle")} />
        <div className={styles.notice}>
          <div className={styles.noticeTitle}>{t("admin.envConfig.disabled")}</div>
          <div className={styles.noticeDesc}>{t("admin.envConfig.disabledHint")}</div>
        </div>
      </div>
    );
  }

  if (error || !config) {
    return (
      <div className={styles.page}>
        <PageHeader title={t("admin.envConfig.title")} subtitle={t("admin.envConfig.subtitle")} />
        <div className={styles.error}>{t("admin.envConfig.loadFailed")}</div>
      </div>
    );
  }

  const baseValues = () =>
    Object.fromEntries(config.groups.flatMap((g) => g.fields.map((f) => [f.key, f.value])));
  const current = values ?? baseValues();
  const dirty = values !== null;

  function setField(key: string, value: string) {
    setValues((prev) => ({ ...(prev ?? baseValues()), [key]: value }));
  }

  async function handleGenerate() {
    clearMessages();
    const generated = await generate();
    setValues((prev) => ({ ...((prev ?? {}) as Record<string, string>), ...generated }));
  }

  async function handleSave() {
    clearMessages();
    await save(current);
  }

  function toggleGroup(name: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  return (
    <div className={styles.page}>
      <PageHeader title={t("admin.envConfig.title")} subtitle={t("admin.envConfig.subtitle")} />

      <div className={styles.meta}>
        <span>{t("admin.envConfig.path")}:</span>
        <span className={styles.metaValue}>{config.path}</span>
      </div>

      {dirty && <div className={styles.error}>{t("admin.envConfig.changed")}</div>}

      <div>
        {config.groups.map((group) => {
          const isCollapsed = collapsed.has(group.name);
          return (
            <div className={styles.group} key={group.name}>
              <div className={styles.groupTitle} onClick={() => toggleGroup(group.name)}>
                <span>{group.name}</span>
                <span className={styles.groupCaret}>{t("admin.envConfig.groupHint")} {isCollapsed ? "+" : "−"}</span>
              </div>
              {!isCollapsed && (
                <div className={styles.groupBody}>
                  {group.fields.map((field) => (
                    <div className={styles.field} key={field.key}>
                      <div className={styles.fieldLabel}>
                        <span className={styles.fieldKey}>{field.key}</span>
                        {field.required && <span className={`${styles.badge} ${styles.badgeReq}`}>{t("admin.envConfig.field.required")}</span>}
                        {field.sensitive && <span className={`${styles.badge} ${styles.badgeSensitive}`}>{t("admin.envConfig.field.sensitive")}</span>}
                      </div>
                      {field.hint && <div className={styles.fieldHint}>{field.hint}</div>}
                      <div className={styles.fieldRow}>
                        <input
                          type={field.sensitive ? "password" : "text"}
                          className={`${styles.input} ${current[field.key] !== field.value ? styles.changed : ""}`}
                          value={current[field.key] ?? ""}
                          onChange={(e) => setField(field.key, e.target.value)}
                          aria-label={field.key}
                        />
                        {field.sensitive && (
                          <button
                            type="button"
                            className={styles.genBtn}
                            disabled={generating}
                            onClick={() => void handleGenerate()}
                          >
                            {t("admin.envConfig.field.generate")}
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className={styles.actions}>
        <button className={styles.saveBtn} disabled={saving} onClick={handleSave}>
          {saving ? t("admin.envConfig.saving") : t("admin.envConfig.save")}
        </button>
        {saveError && <span className={styles.message}>{saveError}</span>}
        {savedBackup && <span className={styles.messageOk}>{t("admin.envConfig.saved", { backup: savedBackup })}</span>}
      </div>
    </div>
  );
}