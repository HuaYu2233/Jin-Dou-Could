"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  getShareInfo,
  verifyShare,
  downloadSharedFile,
  type ShareInfo,
} from "@/lib/api/files";
import { queryKeys } from "@/lib/query/keys";
import { formatSize } from "@/lib/utils/format";

export default function SharePage() {
  const params = useParams();
  const token = params.token as string;

  const [verified, setVerified] = useState(false);
  const [code, setCode] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [verifyError, setVerifyError] = useState("");

  const { data: info, isLoading: loading, error: queryError } = useQuery<ShareInfo>({
    queryKey: queryKeys.shares.info(token),
    queryFn: () => getShareInfo(token),
  });

  const error = queryError
    ? queryError instanceof Error ? queryError.message : "分享不存在"
    : verifyError;

  async function handleVerify() {
    setVerifyError("");
    try {
      await verifyShare(token, code);
      setVerified(true);
    } catch (err) {
      setVerifyError(err instanceof Error ? err.message : "验证失败");
    }
  }

  async function handleDownload() {
    setDownloading(true);
    setVerifyError("");
    try {
      await downloadSharedFile(token, code);
    } catch (err) {
      setVerifyError(err instanceof Error ? err.message : "下载失败");
    } finally {
      setDownloading(false);
    }
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-page">
        <p className="text-sm text-ink-3">加载中...</p>
      </main>
    );
  }

  if (queryError && !info) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-3 bg-page px-6">
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-surface-2 text-4xl">
          😕
        </div>
        <p className="text-lg font-medium text-ink-2">{error}</p>
        <p className="text-sm text-ink-4">分享可能已过期或被取消</p>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-page p-4">
      <div className="w-full max-w-md rounded-[20px] border border-line bg-surface p-8 shadow-[0_18px_48px_rgba(29,33,41,0.1)]">
        <div className="mb-7 flex flex-col items-center text-center">
          <span className="flex h-11 w-11 items-center justify-center rounded-[12px] bg-brand text-lg font-bold tracking-tight text-white shadow-[0_6px_18px_rgba(30,111,255,0.34)]">
            J
          </span>
          <h1 className="mt-4 text-lg font-semibold text-ink">JinDou Cloud 文件分享</h1>
          <p className="mt-1 text-sm text-ink-3">请输入提取码查看文件</p>
        </div>

        <div className="mb-6 flex items-center gap-3 rounded-[12px] border border-line bg-surface-2 p-4">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[10px] bg-surface text-xl shadow-[0_1px_2px_rgba(29,33,41,0.04)]">
            📄
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-ink">{info?.filename}</p>
            <p className="mt-0.5 text-xs text-ink-3">
              {info ? formatSize(info.file_size) : ""}
            </p>
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-[8px] border border-[#ffd4cd] bg-danger-soft px-3 py-2 text-sm text-danger">
            {error}
          </div>
        )}

        {!verified ? (
          <div className="space-y-3">
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              placeholder="请输入提取码"
              maxLength={8}
              className="w-full rounded-[10px] border border-transparent bg-surface-2 px-4 py-3 text-center text-lg font-mono tracking-[0.2em] text-ink outline-none transition placeholder:tracking-normal placeholder:text-ink-4 focus:border-brand focus:bg-surface focus:ring-[3px] focus:ring-brand/12"
              onKeyDown={(e) => e.key === "Enter" && handleVerify()}
            />
            <button
              onClick={handleVerify}
              disabled={code.length !== 8 && code.length !== 6}
              className="w-full rounded-[10px] bg-brand py-3 text-sm font-medium text-white shadow-[0_4px_14px_rgba(30,111,255,0.28)] transition hover:bg-brand-hover disabled:cursor-not-allowed disabled:bg-surface-3 disabled:text-ink-4 disabled:shadow-none"
            >
              验证提取码
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="rounded-[10px] border border-[#b7f0c1] bg-[#e8ffea] px-4 py-3 text-sm text-[#009a25]">
              ✓ 验证成功，可以下载文件了
            </div>
            <button
              onClick={handleDownload}
              disabled={downloading}
              className="w-full rounded-[10px] bg-brand py-3 text-sm font-medium text-white shadow-[0_4px_14px_rgba(30,111,255,0.28)] transition hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-55 disabled:shadow-none"
            >
              {downloading ? "下载中..." : "下载文件"}
            </button>
          </div>
        )}
      </div>
    </main>
  );
}