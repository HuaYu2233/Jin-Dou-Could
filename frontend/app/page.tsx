// /Users/zero/project/JinDou-Cloud/frontend/app/page.tsx
"use client";

import Link from "next/link";
import { useAuthStore } from "@/stores/auth";

export default function HomePage() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 p-8">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-gray-900">JinDou Cloud</h1>
        <p className="mt-3 text-gray-500">你的私有云盘，安全可靠</p>
      </div>
      <div className="flex gap-4">
        {isAuthenticated ? (
          <Link
            href="/dashboard"
            className="rounded-lg bg-blue-600 px-6 py-3 text-white font-medium hover:bg-blue-700 transition"
          >
            进入工作台
          </Link>
        ) : (
          <>
            <Link
              href="/login"
              className="rounded-lg bg-blue-600 px-6 py-3 text-white font-medium hover:bg-blue-700 transition"
            >
              登录
            </Link>
            <Link
              href="/register"
              className="rounded-lg border border-gray-300 px-6 py-3 text-gray-700 font-medium hover:bg-gray-50 transition"
            >
              注册
            </Link>
          </>
        )}
      </div>
    </main>
  );
}