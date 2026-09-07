export interface ProcessedImage {
  blob: Blob;
  dataUrl: string;
  width: number;
  height: number;
}

const MAX_SIZE = 512;
const QUALITY = 0.85;

export function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("图片加载失败"));
    img.src = src;
  });
}

export function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(new Error("文件读取失败"));
    reader.readAsDataURL(file);
  });
}

export async function compressImage(file: File): Promise<ProcessedImage> {
  const dataUrl = await fileToDataUrl(file);
  const img = await loadImage(dataUrl);

  let { width, height } = img;
  if (width > MAX_SIZE || height > MAX_SIZE) {
    const ratio = Math.min(MAX_SIZE / width, MAX_SIZE / height);
    width = Math.round(width * ratio);
    height = Math.round(height * ratio);
  }

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas 不支持");
  ctx.drawImage(img, 0, 0, width, height);

  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (b) => (b ? resolve(b) : reject(new Error("压缩失败"))),
      "image/jpeg",
      QUALITY
    );
  });

  return {
    blob,
    dataUrl: canvas.toDataURL("image/jpeg", QUALITY),
    width,
    height,
  };
}

export function cropToBlob(
  img: HTMLImageElement,
  cropX: number,
  cropY: number,
  cropSize: number,
  outputSize = 256
): Promise<Blob> {
  return new Promise((resolve, reject) => {
    const canvas = document.createElement("canvas");
    canvas.width = outputSize;
    canvas.height = outputSize;
    const ctx = canvas.getContext("2d");
    if (!ctx) return reject(new Error("Canvas 不支持"));
    ctx.drawImage(
      img,
      cropX,
      cropY,
      cropSize,
      cropSize,
      0,
      0,
      outputSize,
      outputSize
    );
    canvas.toBlob(
      (b) => (b ? resolve(b) : reject(new Error("裁剪失败"))),
      "image/jpeg",
      QUALITY
    );
  });
}
