"use client";

import { useEffect, useRef } from "react";
import styles from "./LogViewer.module.css";

interface LogViewerProps {
  lines: string[];
  emptyText: string;
}

export default function LogViewer({ lines, emptyText }: LogViewerProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = ref.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [lines]);

  if (lines.length === 0) {
    return <div className={styles.empty}>{emptyText}</div>;
  }

  return (
    <div ref={ref} className={styles.viewer}>
      {lines.map((line, index) => (
        <div key={index} className={styles.line}>
          {line}
        </div>
      ))}
    </div>
  );
}