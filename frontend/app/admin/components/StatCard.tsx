import styles from "./StatCard.module.css";

interface StatCardProps {
  label: string;
  value: number | string;
  hint?: string;
  color?: "blue" | "green" | "purple";
}

const TAG_CLASS: Record<NonNullable<StatCardProps["color"]>, string> = {
  blue: styles.tagBlue,
  green: styles.tagGreen,
  purple: styles.tagPurple,
};

export default function StatCard({ label, value, hint, color = "blue" }: StatCardProps) {
  return (
    <div className={styles.card}>
      <span className={`${styles.tag} ${TAG_CLASS[color]}`}>{label}</span>
      <div className={styles.value}>{value}</div>
      {hint && <div className={styles.hint}>{hint}</div>}
    </div>
  );
}