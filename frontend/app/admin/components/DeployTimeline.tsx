"use client";

import styles from "./DeployTimeline.module.css";

export interface DeployTimelineStep {
  key: string;
  label: string;
}

interface DeployTimelineProps {
  steps: DeployTimelineStep[];
  currentStep: string | null;
  stepIndex: number;
  pct: number;
  status: string;
}

function stepState(
  index: number,
  currentIndex: number,
  currentStep: string,
  stepKey: string,
  status: string
): "done" | "active" | "failed" | "pending" {
  if (status === "failed" && stepKey === currentStep) return "failed";
  if (index < currentIndex) return "done";
  if (index === currentIndex) return status === "success" ? "done" : "active";
  return "pending";
}

export default function DeployTimeline({
  steps,
  currentStep,
  stepIndex,
  pct,
  status,
}: DeployTimelineProps) {
  if (steps.length === 0) return null;

  return (
    <div className={styles.wrap}>
      <div className={styles.bar}>
        <div className={styles.fill} style={{ width: `${Math.min(Math.max(pct, 0), 100)}%` }} />
      </div>
      <ol className={styles.list}>
        {steps.map((step, index) => {
          const state = stepState(index, stepIndex, currentStep ?? "", step.key, status);
          return (
            <li key={step.key} className={`${styles.item} ${styles[state] || ""}`}>
              <span className={styles.dot} />
              <span className={styles.label}>{step.label}</span>
            </li>
          );
        })}
      </ol>
      <div className={styles.pct}>{pct}%</div>
    </div>
  );
}