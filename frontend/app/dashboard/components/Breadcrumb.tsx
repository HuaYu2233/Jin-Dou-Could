// /Users/zero/project/JinDou-Cloud/frontend/app/dashboard/components/Breadcrumb.tsx
"use client";

import { useState } from "react";
import type { BreadcrumbItem } from "../types";
import styles from "./Breadcrumb.module.css";

interface BreadcrumbProps {
  items: BreadcrumbItem[];
  onNavigate: (path: string) => void;
}

export default function Breadcrumb({ items, onNavigate }: BreadcrumbProps) {
  const [editing, setEditing] = useState(false);
  const [inputPath, setInputPath] = useState("");

  function startEdit() {
    setInputPath(items.map((i) => i.path).join("/"));
    setEditing(true);
  }

  function commitEdit() {
    setEditing(false);
    if (inputPath.trim()) {
      onNavigate(inputPath.trim());
    }
  }

  return (
    <div className={styles.breadcrumb}>
      {editing ? (
        <input
          className={styles.pathInput}
          value={inputPath}
          onChange={(e) => setInputPath(e.target.value)}
          onBlur={commitEdit}
          onKeyDown={(e) => e.key === "Enter" && commitEdit()}
          autoFocus
        />
      ) : (
        <div className={styles.crumbs} onClick={(e) => {
          if (e.target === e.currentTarget) startEdit();
        }}>
          {items.map((item, idx) => (
            <span key={item.id ?? "root"} className={styles.crumbWrapper}>
              {idx > 0 && <span className={styles.separator}>/</span>}
              <button
                className={styles.crumb}
                onClick={() => onNavigate(item.path)}
              >
                {item.name}
              </button>
            </span>
          ))}
          <span className={styles.emptyArea} onClick={startEdit} />
        </div>
      )}
    </div>
  );
}