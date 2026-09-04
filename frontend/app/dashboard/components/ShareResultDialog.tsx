"use client";

import { useState } from "react";
import type { ShareCreateResponse } from "@/lib/api/files";
import styles from "./ShareResultDialog.module.css";

interface ShareResultDialogProps {
  results: ShareCreateResponse[];
  onClose: () => void;
}

function buildShareLink(token: string): string {
  if (typeof window !== "undefined") {
    return `${window.location.origin}/share/${token}`;
  }
  return `/share/${token}`;
}

export default function ShareResultDialog({ results, onClose }: ShareResultDialogProps) {
  const [copiedKey, setCopiedKey] = useState<string>("");

  async function copy(text: string, key: string) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(""), 2000);
  }

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.dialog} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h3 className={styles.title}>分享成功</h3>
          <button className={styles.closeBtn} onClick={onClose}>✕</button>
        </div>
        <p className={styles.subtitle}>
          已创建 {results.length} 个分享，复制链接和提取码发送给好友即可
        </p>
        <div className={styles.resultList}>
          {results.map((r, idx) => {
            const link = buildShareLink(r.share_token);
            const copyAllText = `链接：${link}\n提取码：${r.extract_code}`;
            return (
              <div key={r.id} className={styles.resultItem}>
                <div className={styles.field}>
                  <label className={styles.label}>分享链接</label>
                  <div className={styles.fieldRow}>
                    <input className={styles.fieldInput} readOnly value={link} />
                    <button
                      className={styles.copyBtn}
                      onClick={() => copy(link, `link-${idx}`)}
                    >
                      {copiedKey === `link-${idx}` ? "已复制" : "复制"}
                    </button>
                  </div>
                </div>
                <div className={styles.field}>
                  <label className={styles.label}>提取码</label>
                  <div className={styles.fieldRow}>
                    <input
                      className={styles.fieldInput}
                      readOnly
                      value={r.extract_code}
                    />
                    <button
                      className={styles.copyBtn}
                      onClick={() => copy(r.extract_code, `code-${idx}`)}
                    >
                      {copiedKey === `code-${idx}` ? "已复制" : "复制"}
                    </button>
                  </div>
                </div>
                <button
                  className={styles.copyAllBtn}
                  onClick={() => copy(copyAllText, `all-${idx}`)}
                >
                  {copiedKey === `all-${idx}` ? "已复制全部" : "一键复制链接+提取码"}
                </button>
              </div>
            );
          })}
        </div>
        <div className={styles.footer}>
          <button className={styles.doneBtn} onClick={onClose}>完成</button>
        </div>
      </div>
    </div>
  );
}
