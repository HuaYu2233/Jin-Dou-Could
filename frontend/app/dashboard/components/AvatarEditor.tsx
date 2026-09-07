"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { compressImage, loadImage, cropToBlob } from "@/lib/utils/image";
import styles from "./AvatarEditor.module.css";

interface AvatarEditorProps {
  file: File;
  onConfirm: (blob: Blob) => Promise<void>;
  onClose: () => void;
}

const CROP_SIZE = 240;
const OUTPUT_SIZE = 256;

export default function AvatarEditor({ file, onConfirm, onClose }: AvatarEditorProps) {
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const dragRef = useRef(false);
  const offsetRef = useRef({ x: 0, y: 0 });

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const image = imgRef.current;
    if (!canvas || !image) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const scale = Math.min(360 / image.width, 360 / image.height, 1);
    const dispW = image.width * scale;
    const dispH = image.height * scale;
    canvas.width = dispW;
    canvas.height = dispH;

    ctx.clearRect(0, 0, dispW, dispH);
    ctx.drawImage(image, 0, 0, dispW, dispH);

    const cropDispX = offsetRef.current.x * scale;
    const cropDispY = offsetRef.current.y * scale;
    const cropDispSize = CROP_SIZE * scale;

    ctx.fillStyle = "rgba(0,0,0,0.5)";
    ctx.fillRect(0, 0, dispW, cropDispY);
    ctx.fillRect(0, cropDispY, cropDispX, cropDispSize);
    ctx.fillRect(cropDispX + cropDispSize, cropDispY, dispW, cropDispSize);
    ctx.fillRect(0, cropDispY + cropDispSize, dispW, dispH);

    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 2;
    ctx.strokeRect(cropDispX, cropDispY, cropDispSize, cropDispSize);
  }, []);

  const drawPreview = useCallback(() => {
    const image = imgRef.current;
    if (!image) return;
    const previewCanvas = document.createElement("canvas");
    previewCanvas.width = OUTPUT_SIZE;
    previewCanvas.height = OUTPUT_SIZE;
    const pctx = previewCanvas.getContext("2d");
    if (!pctx) return;
    pctx.drawImage(
      image,
      offsetRef.current.x,
      offsetRef.current.y,
      CROP_SIZE,
      CROP_SIZE,
      0,
      0,
      OUTPUT_SIZE,
      OUTPUT_SIZE
    );
    setPreviewUrl(previewCanvas.toDataURL("image/jpeg", 0.85));
  }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const result = await compressImage(file);
        const loaded = await loadImage(result.dataUrl);
        if (!active) return;
        imgRef.current = loaded;
        setImg(loaded);
        const initX = Math.max(0, (loaded.width - CROP_SIZE) / 2);
        const initY = Math.max(0, (loaded.height - CROP_SIZE) / 2);
        offsetRef.current = { x: initX, y: initY };
        requestAnimationFrame(() => {
          draw();
          drawPreview();
        });
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : "处理失败");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [file, draw, drawPreview]);

  function clampOffset(x: number, y: number) {
    const image = imgRef.current;
    if (!image) return { x: 0, y: 0 };
    const maxX = Math.max(0, image.width - CROP_SIZE);
    const maxY = Math.max(0, image.height - CROP_SIZE);
    return {
      x: Math.min(Math.max(0, x), maxX),
      y: Math.min(Math.max(0, y), maxY),
    };
  }

  function handlePointerDown(e: React.PointerEvent) {
    dragRef.current = true;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    const startX = e.clientX;
    const startY = e.clientY;
    const startOffX = offsetRef.current.x;
    const startOffY = offsetRef.current.y;
    const scale = canvasRef.current
      ? canvasRef.current.width / (imgRef.current?.width || 1)
      : 1;

    function onMove(ev: PointerEvent) {
      if (!dragRef.current) return;
      const dx = (ev.clientX - startX) / scale;
      const dy = (ev.clientY - startY) / scale;
      const next = clampOffset(startOffX + dx, startOffY + dy);
      offsetRef.current = next;
      draw();
      drawPreview();
    }
    function onUp() {
      dragRef.current = false;
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    }
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  }

  async function handleConfirm() {
    const image = imgRef.current;
    if (!image) return;
    setSaving(true);
    setError(null);
    try {
      const blob = await cropToBlob(image, offsetRef.current.x, offsetRef.current.y, CROP_SIZE, OUTPUT_SIZE);
      await onConfirm(blob);
    } catch (err) {
      setError(err instanceof Error ? err.message : "上传失败");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className={styles.overlay} onClick={onClose}>
        <div className={styles.dialog} onClick={(e) => e.stopPropagation()}>
          <div className={styles.loading}>处理图片中...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.overlay} onClick={onClose}>
        <div className={styles.dialog} onClick={(e) => e.stopPropagation()}>
          <div className={styles.loading} style={{ color: "#dc2626" }}>{error}</div>
          <div className={styles.actions}>
            <button className={styles.cancelBtn} onClick={onClose}>关闭</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.overlay} onClick={() => !saving && onClose()}>
      <div className={styles.dialog} onClick={(e) => e.stopPropagation()}>
        <h3 className={styles.title}>调整头像</h3>
        <p className={styles.desc}>拖动图片选择方形区域，已自动压缩</p>

        <div className={styles.canvasWrap}>
          <canvas
            ref={canvasRef}
            className={styles.canvas}
            onPointerDown={handlePointerDown}
          />
        </div>

        <div className={styles.previewRow}>
          <span className={styles.previewLabel}>预览：</span>
          <div className={`${styles.previewBox} ${styles.previewSm}`}>
            {previewUrl && <img src={previewUrl} alt="sm" className={styles.previewImg} />}
          </div>
          <div className={`${styles.previewBox} ${styles.previewMd}`}>
            {previewUrl && <img src={previewUrl} alt="md" className={styles.previewImg} />}
          </div>
          <div className={`${styles.previewBox} ${styles.previewLg}`}>
            {previewUrl && <img src={previewUrl} alt="lg" className={styles.previewImg} />}
          </div>
        </div>

        <div className={styles.actions}>
          <button className={styles.cancelBtn} onClick={onClose} disabled={saving}>
            取消
          </button>
          <button className={styles.confirmBtn} onClick={handleConfirm} disabled={saving}>
            {saving ? "上传中..." : "确认上传"}
          </button>
        </div>
        {error && <div className={styles.hint} style={{ color: "#dc2626" }}>{error}</div>}
      </div>
    </div>
  );
}