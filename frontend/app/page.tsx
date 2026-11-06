"use client";

import Link from "next/link";
import { useAuthStore } from "@/stores/auth";
import { useIsHydrated } from "@/lib/hooks/useIsHydrated";

export default function HomePage() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const hydrated = useIsHydrated();

  return (
    <main className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-page px-6 py-16">
      <div className="pointer-events-none absolute -top-48 left-1/2 h-[560px] w-[560px] -translate-x-1/2 rounded-full bg-brand/10 blur-[120px]" />
      <div className="pointer-events-none absolute -bottom-40 -right-24 h-[420px] w-[420px] rounded-full bg-brand/10 blur-[100px]" />

      <div className="relative z-10 flex w-full max-w-lg flex-col items-center text-center">
        <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand text-2xl font-bold tracking-tight text-white shadow-[0_8px_24px_rgba(30,111,255,0.34)]">
          J
        </span>
        <h1 className="mt-7 text-4xl font-semibold tracking-tight text-ink sm:text-5xl">
          JinDou Cloud
        </h1>
        <p className="mt-4 text-base text-ink-3">你的私有云盘，安全可靠</p>

        <div className="mt-10 flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
          {hydrated && isAuthenticated ? (
            <Link
              href="/dashboard"
              className="inline-flex h-12 items-center justify-center rounded-[10px] bg-brand px-9 text-sm font-medium text-white shadow-[0_4px_14px_rgba(30,111,255,0.28)] transition hover:bg-brand-hover hover:shadow-[0_6px_20px_rgba(30,111,255,0.34)]"
            >
              进入工作台
            </Link>
          ) : (
            <>
              <Link
                href="/login"
                className="inline-flex h-12 items-center justify-center rounded-[10px] bg-brand px-9 text-sm font-medium text-white shadow-[0_4px_14px_rgba(30,111,255,0.28)] transition hover:bg-brand-hover hover:shadow-[0_6px_20px_rgba(30,111,255,0.34)]"
              >
                登录
              </Link>
              <Link
                href="/register"
                className="inline-flex h-12 items-center justify-center rounded-[10px] border border-line bg-surface px-9 text-sm font-medium text-ink-2 transition hover:border-line-strong hover:bg-surface-2 hover:text-ink"
              >
                注册
              </Link>
            </>
          )}
        </div>
      </div>

      <p className="relative z-10 mt-16 text-xs text-ink-4">
        安全存储 · 随时随地访问 · 端到端加密
      </p>
    </main>
  );
}