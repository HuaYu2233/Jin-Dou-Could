import React from "react";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm rounded-lg bg-white p-6 shadow">
        <React.Suspense fallback={<div className="text-center text-gray-500">加载中...</div>}>
          {children}
        </React.Suspense>
      </div>
    </div>
  );
}