"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/stores/auth";
import { useTranslation } from "@/lib/i18n";
import Header from "../dashboard/components/Header";

export default function ProfileLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isLoading = useAuthStore((s) => s.isLoading);
  const { t } = useTranslation();

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) router.replace("/login");
  }, [isAuthenticated, isLoading, router]);

  return (
    <div className="flex h-screen flex-col">
      <Header
        extra={
          <Link href="/dashboard" className="text-sm text-gray-600 transition-colors hover:text-gray-900">
            {t("profile.backToDrive")}
          </Link>
        }
      />
      <main className="flex-1 min-h-0 overflow-auto bg-gray-50">{children}</main>
    </div>
  );
}