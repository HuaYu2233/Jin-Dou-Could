// /Users/zero/project/JinDou-Cloud/frontend/app/share/[token]/page.tsx
"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import {
  getShareInfo,
  verifyShare,
  downloadSharedFile,
  type ShareInfo,
} from "@/lib/api/files";

export default function SharePage() {
  const params = useParams();
  const token = params.token as string;

  const [info, setInfo] = useState<ShareInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [verified, setVerified] = useState(false);
  const [code, setCode] = useState("");
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const res = await getShareInfo(token);
        if (active) setInfo(res);
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : "分享不存在");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [token]);

  async function handleVerify() {
    setError("");
    try {
      await verifyShare(token, code);
      setVerified(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "验证失败");
    }
  }

  async function handleDownload() {
    setDownloading(true);
    setError("");
    try {
      await downloadSharedFile(token, code);
    } catch (err) {
      setError(err instanceof Error ? err.message : "下载失败");
    } finally {
      setDownloading(false);
    }
  }

  function formatSize(bytes: number) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + " GB";
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-gray-50">
        <p className="text-gray-500">加载中...</p>
      </main>
    );
  }

  if (error && !info) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-gray-50">
        <div className="text-5xl">😕</div>
        <p className="text-lg font-medium text-gray-700">{error}</p>
        <p className="text-sm text-gray-400">分享可能已过期或被取消</p>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-50 p-4">
      <div className="w-full max-w-md rounded-xl border border-gray-200 bg-white p-8 shadow-sm">
        <div className="mb-6 text-center">
          <h1 className="text-xl font-bold text-gray-900">JinDou Cloud 文件分享</h1>
          <p className="mt-1 text-sm text-gray-500">请输入提取码查看文件</p>
        </div>

        <div className="mb-6 rounded-lg bg-gray-50 p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-xl">
              📄
            </div>
            <div className="flex-1 min-w-0">
              <p className="truncate text-sm font-medium text-gray-900">
                {info?.filename}
              </p>
              <p className="text-xs text-gray-500">
                {info ? formatSize(info.file_size) : ""}
              </p>
            </div>
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
            {error}
          </div>
        )}

        {!verified ? (
          <div className="space-y-4">
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              placeholder="请输入6位提取码"
              maxLength={6}
              className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-center text-lg tracking-widest font-mono focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              onKeyDown={(e) => e.key === "Enter" && handleVerify()}
            />
            <button
              onClick={handleVerify}
              disabled={code.length !== 6}
              className="w-full rounded-lg bg-blue-600 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:bg-gray-300"
            >
              验证提取码
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="rounded-lg bg-green-50 px-4 py-3 text-sm text-green-700">
              ✓ 验证成功，可以下载文件了
            </div>
            <button
              onClick={handleDownload}
              disabled={downloading}
              className="w-full rounded-lg bg-blue-600 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:bg-gray-300"
            >
              {downloading ? "下载中..." : "下载文件"}
            </button>
          </div>
        )}
      </div>
    </main>
  );
}