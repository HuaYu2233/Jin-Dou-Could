// /Users/zero/project/JinDou-Cloud/frontend/app/dashboard/components/FilePreview.tsx
"use client";

import { useState, useEffect } from "react";
import type { FileItem } from "@/lib/api/files";
import { getFilePreviewUrl } from "@/lib/api/files";
import styles from "./FilePreview.module.css";

interface FilePreviewProps {
  file: FileItem;
  onClose: () => void;
}

export default function FilePreview({ file, onClose }: FilePreviewProps) {
  const [url, setUrl] = useState("");
  const [textContent, setTextContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const previewUrl = await getFilePreviewUrl(file.id);
        if (!active) return;
        if (file.mime_type.startsWith("text/")) {
          const res = await fetch(previewUrl);
          const text = await res.text();
          if (active) setTextContent(text);
        } else {
          if (active) setUrl(previewUrl);
        }
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : "加载失败");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [file]);

  function renderContent() {
    if (loading) return <div className={styles.loading}>加载中...</div>;
    if (error) return <div className={styles.error}>{error}</div>;

    const { file_type, mime_type } = file;

    if (file_type === "image" && url) {
      return <img src={url} alt={file.filename} className={styles.media} />;
    }
    if (file_type === "video" && url) {
      return <video src={url} controls autoPlay className={styles.media} />;
    }
    if (file_type === "audio" && url) {
      return <audio src={url} controls autoPlay className={styles.audioPlayer} />;
    }
    if (mime_type === "application/pdf" && url) {
      return <iframe src={url} title={file.filename} className={styles.pdfFrame} />;
    }
    if (mime_type.startsWith("text/")) {
      return <pre className={styles.textPreview}>{textContent}</pre>;
    }
    return (
      <div className={styles.unsupported}>
        <div className={styles.unsupportedIcon}>📄</div>
        <p className={styles.unsupportedTitle}>不支持预览此文件</p>
        <p className={styles.unsupportedDesc}>请点击下方按钮下载查看</p>
      </div>
    );
  }

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <span className={styles.title} title={file.filename}>{file.filename}</span>
          <button className={styles.closeBtn} onClick={onClose}>✕</button>
        </div>
        <div className={styles.body}>{renderContent()}</div>
      </div>
    </div>
  );
}