"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import PageHeader from "../components/PageHeader";
import StatCard from "../components/StatCard";
import ContainerTable from "../components/ContainerTable";
import DeployTimeline from "../components/DeployTimeline";
import DeployConfirmDialog from "../components/DeployConfirmDialog";
import ErrorBar from "../components/ErrorBar";
import LogViewer from "../components/LogViewer";
import { useAdminDeploy } from "../hooks/useAdminDeploy";
import { useTranslation } from "@/lib/i18n";
import styles from "./page.module.css";

const RESTART_TARGETS = ["backend", "frontend", "celery-worker"];
const ACTION_STEPS: Record<string, string[]> = {
  check: ["preflight", "doctor"],
  restart: ["restart", "health"],
  deploy: ["preflight", "backup", "tag_rollback", "pull", "build", "up", "health"],
  rollback: ["tag_rollback", "up", "health"],
};

export default function AdminDeployPage() {
  const {
    status,
    versions,
    containers,
    history,
    task,
    taskId,
    loading,
    error,
    disabled,
    actionError,
    submitting,
    submitAction,
    clearTask,
    watchCurrentTask,
    clearActionError,
  } = useAdminDeploy();
  const { t } = useTranslation();
  const [confirmAction, setConfirmAction] = useState<string | null>(null);
  const [restartTarget, setRestartTarget] = useState(RESTART_TARGETS[0]);

  const taskRunning = task?.status === "running" || task?.status === "queued";
  const actionsDisabled = submitting || taskRunning || !status?.runner_online;

  const steps = useMemo(() => {
    const keys = ACTION_STEPS[task?.action ?? ""] ?? [];
    return keys.map((key) => ({
      key,
      label: t(`admin.deploy.step.${key}` as "admin.deploy.step.preflight"),
    }));
  }, [task?.action, t]);

  function handleSubmit(action: string, target?: string | null) {
    submitAction(action, target);
  }

  function handleConfirm() {
    if (!confirmAction) return;
    handleSubmit(confirmAction);
    setConfirmAction(null);
  }

  if (loading) return <div className={styles.loading}>{t("admin.deploy.loading")}</div>;

  if (disabled) {
    return (
      <div className={styles.page}>
        <PageHeader title={t("admin.deploy.title")} subtitle={t("admin.deploy.subtitle")} />
        <div className={styles.notice}>
          <div className={styles.noticeTitle}>{t("admin.deploy.disabled")}</div>
          <div className={styles.noticeDesc}>{t("admin.deploy.disabledHint")}</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.page}>
        <PageHeader title={t("admin.deploy.title")} subtitle={t("admin.deploy.subtitle")} />
        <div className={styles.error}>{t("admin.deploy.loadFailed")}</div>
      </div>
    );
  }

  if (!status) return null;

  const heartbeat = containers?.heartbeat_age_seconds;
  const runnerHint = heartbeat === null || heartbeat === undefined
    ? t("admin.deploy.runnerNever")
    : t("admin.deploy.runnerHint", { seconds: heartbeat });

  return (
    <div className={styles.page}>
      <PageHeader
        title={t("admin.deploy.title")}
        subtitle={t("admin.deploy.subtitle")}
        extra={<Link href="/admin/backups" className={styles.link}>{t("admin.deploy.backupLink")}</Link>}
      />

      <div className={styles.cardGrid}>
        <StatCard
          label={t("admin.deploy.status.enabled")}
          value={status.enabled ? t("admin.users.status.active") : t("admin.users.status.inactive")}
          color={status.enabled ? "green" : "purple"}
        />
        <StatCard
          label={t("admin.deploy.runnerOnline")}
          value={status.runner_online ? t("admin.deploy.runnerOnline") : t("admin.deploy.runnerOffline")}
          hint={runnerHint}
          color={status.runner_online ? "green" : "purple"}
        />
        <StatCard
          label={t("admin.deploy.currentTask")}
          value={status.running_task_id ? t("admin.deploy.running") : t("admin.deploy.idle")}
          hint={status.running_task_id ?? undefined}
          color="blue"
        />
      </div>

      <section className={styles.section}>
        <div className={styles.sectionHead}>
          <h2 className={styles.sectionTitle}>{t("admin.deploy.actions.title")}</h2>
        </div>
        <p className={styles.sectionDesc}>{t("admin.deploy.actions.desc")}</p>
        <div className={styles.actionBar}>
          <button
            className={styles.actionBtn}
            disabled={actionsDisabled}
            onClick={() => handleSubmit("check")}
          >
            {t("admin.deploy.action.check")}
          </button>
          <select
            className={styles.actionSelect}
            value={restartTarget}
            disabled={actionsDisabled}
            onChange={(e) => setRestartTarget(e.target.value)}
            aria-label={t("admin.deploy.action.target")}
          >
            {RESTART_TARGETS.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          <button
            className={styles.actionBtn}
            disabled={actionsDisabled}
            onClick={() => handleSubmit("restart", restartTarget)}
          >
            {t("admin.deploy.action.restart")}
          </button>
          <button
            className={`${styles.actionBtn} ${styles.actionPrimary}`}
            disabled={actionsDisabled}
            onClick={() => setConfirmAction("deploy")}
          >
            {t("admin.deploy.action.deploy")}
          </button>
          <button
            className={styles.actionBtn}
            disabled={actionsDisabled}
            onClick={() => setConfirmAction("rollback")}
          >
            {t("admin.deploy.action.rollback")}
          </button>
          {taskId ? (
            <button className={styles.actionBtn} onClick={clearTask}>
              {t("common.close")}
            </button>
          ) : null}
        </div>
        {!status.runner_online && (
          <div className={styles.actionHint}>{t("admin.deploy.action.runnerOffline")}</div>
        )}
        {taskRunning && (
          <div className={styles.actionHint}>
            {t("admin.deploy.action.busy")}
            {status.running_task_id && (
              <button className={styles.actionLink} onClick={watchCurrentTask}>
                {t("admin.deploy.action.viewCurrent")}
              </button>
            )}
          </div>
        )}
        {task?.status === "stalled" && (
          <div className={styles.actionHint}>{t("admin.deploy.action.stalled")}</div>
        )}
        <ErrorBar message={actionError} onClose={clearActionError} />
      </section>

      {task && (
        <section className={styles.section}>
          <div className={styles.sectionHead}>
            <h2 className={styles.sectionTitle}>{t("admin.deploy.progress.title")}</h2>
            <span
              className={`${styles.badge} ${task.status === "failed" ? styles.badgeWarn : styles.badgeOk}`}
            >
              {task.status}
            </span>
          </div>
          <DeployTimeline
            steps={steps}
            currentStep={task.step}
            stepIndex={task.step_index}
            pct={task.pct}
            status={task.status}
          />
          <div className={styles.taskMeta}>
            <span>
              {t("admin.deploy.progress.step")}: {task.step ?? "-"}
            </span>
            <span>
              {t("admin.deploy.progress.startedAt")}: {task.started_at ?? "-"}
            </span>
            <span>
              {t("admin.deploy.progress.updatedAt")}: {task.updated_at ?? "-"}
            </span>
          </div>
          {task.error && <div className={styles.error}>{task.error}</div>}
        </section>
      )}

      {task && (
        <section className={styles.section}>
          <div className={styles.sectionHead}>
            <h2 className={styles.sectionTitle}>{t("admin.deploy.logs.title")}</h2>
          </div>
          <LogViewer lines={task.logs} emptyText={t("admin.deploy.logs.empty")} />
        </section>
      )}

      <section className={styles.section}>
        <div className={styles.sectionHead}>
          <h2 className={styles.sectionTitle}>{t("admin.deploy.status.title")}</h2>
        </div>
        <div className={styles.kvList}>
          <span className={styles.kvKey}>{t("admin.deploy.status.allowedActions")}</span>
          <span className={styles.kvValue}>
            {status.allowed_actions.length > 0 ? status.allowed_actions.join(" / ") : t("admin.deploy.versions.unknown")}
          </span>
          <span className={styles.kvKey}>{t("admin.deploy.lastResult")}</span>
          <span className={styles.kvValue}>
            {status.last_result
              ? `${status.last_result.action} · ${status.last_result.status} · ${status.last_result.finished_at ?? "-"}`
              : t("admin.deploy.noResult")}
          </span>
          <span className={styles.kvKey}>{t("admin.deploy.currentTask")}</span>
          <span className={styles.kvValue}>{status.running_task_id ?? t("admin.deploy.idle")}</span>
        </div>
      </section>

      <section className={styles.section}>
        <div className={styles.sectionHead}>
          <h2 className={styles.sectionTitle}>{t("admin.deploy.versions.title")}</h2>
        </div>
        {versions ? (
          <>
            <div className={styles.kvList}>
              <span className={styles.kvKey}>{t("admin.deploy.versions.appVersion")}</span>
              <span className={styles.kvValue}>{versions.app_version}</span>
              <span className={styles.kvKey}>{t("admin.deploy.versions.composeHash")}</span>
              <span className={`${styles.kvValue} ${styles.mono}`}>
                {versions.compose_hash ?? t("admin.deploy.versions.unknown")}
              </span>
              <span className={styles.kvKey}>{t("admin.deploy.versions.gitCommit")}</span>
              <span className={`${styles.kvValue} ${styles.mono}`}>
                {versions.git_commit ?? t("admin.deploy.versions.unknown")}
              </span>
              <span className={styles.kvKey}>{t("admin.deploy.versions.collectedAt")}</span>
              <span className={styles.kvValue}>
                {versions.collected_at ?? t("admin.deploy.versions.noSnapshot")}
              </span>
            </div>
            {Object.keys(versions.image_tags).length > 0 && (
              <div className={styles.badgeRow}>
                {Object.entries(versions.image_tags).map(([key, value]) => (
                  <span key={key} className={styles.badge}>
                    {key}: {value}
                  </span>
                ))}
              </div>
            )}
          </>
        ) : (
          <div className={styles.empty}>{t("admin.deploy.versions.noSnapshot")}</div>
        )}
      </section>

      <section className={styles.section}>
        <div className={styles.sectionHead}>
          <h2 className={styles.sectionTitle}>{t("admin.deploy.health.title")}</h2>
          <span className={`${styles.badge} ${status.runner_online ? styles.badgeOk : styles.badgeWarn}`}>
            {status.runner_online ? t("admin.deploy.runnerOnline") : t("admin.deploy.runnerOffline")}
          </span>
        </div>
        <p className={styles.sectionDesc}>{t("admin.deploy.health.desc")}</p>
        <ContainerTable
          services={containers?.available ? containers.services : []}
          emptyText={t("admin.deploy.health.noSnapshot")}
        />
      </section>

      <section className={styles.section}>
        <div className={styles.sectionHead}>
          <h2 className={styles.sectionTitle}>{t("admin.deploy.history.title")}</h2>
        </div>
        {history.length > 0 ? (
          <div className={styles.tableScroll}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th className={styles.th}>{t("admin.deploy.history.col.task")}</th>
                  <th className={styles.th}>{t("admin.deploy.history.col.action")}</th>
                  <th className={styles.th}>{t("admin.deploy.history.col.status")}</th>
                  <th className={styles.th}>{t("admin.deploy.history.col.finishedAt")}</th>
                </tr>
              </thead>
              <tbody>
                {history.map((item) => (
                  <tr key={item.task_id}>
                    <td className={`${styles.td} ${styles.mono}`}>{item.task_id}</td>
                    <td className={styles.td}>{item.action}</td>
                    <td className={styles.td}>
                      {item.rolled_back ? `${item.status} (${t("admin.deploy.history.rolledBack")})` : item.status}
                    </td>
                    <td className={styles.td}>{item.finished_at ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className={styles.empty}>{t("admin.deploy.noResult")}</div>
        )}
      </section>

      <DeployConfirmDialog
        action={confirmAction}
        saving={submitting}
        onConfirm={handleConfirm}
        onClose={() => setConfirmAction(null)}
      />
    </div>
  );
}