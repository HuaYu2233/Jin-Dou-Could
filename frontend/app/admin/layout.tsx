"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/stores/auth";
import { useTranslation, type TranslationKey } from "@/lib/i18n";
import Header from "../dashboard/components/Header";
import styles from "./layout.module.css";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isLoading = useAuthStore((s) => s.isLoading);
  const fetchMe = useAuthStore((s) => s.fetchMe);
  const { t } = useTranslation();

  useEffect(() => {
    fetchMe();
  }, [fetchMe]);

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      router.replace("/login");
    } else if (user && !user.is_admin) {
      router.replace("/dashboard");
    }
  }, [user, isAuthenticated, isLoading, router]);

  if (isLoading || (!user && isAuthenticated)) {
    return (
      <div className={styles.container}>
        <Header />
        <main className={styles.main}>
          <div className={styles.loading}>Loading...</div>
        </main>
      </div>
    );
  }

  const navItems = [
    { href: "/admin", labelKey: "admin.nav.overview" as TranslationKey },
    { href: "/admin/users", labelKey: "admin.nav.users" as TranslationKey },
    { href: "/admin/backups", labelKey: "admin.nav.backups" as TranslationKey },
  ];

  return (
    <div className={styles.container}>
      <Header
        extra={<Link href="/dashboard" className={styles.backLink}>{t("admin.backToDrive")}</Link>}
      />
      <nav className={styles.subNav}>
        {navItems.map((item) => {
          const active = item.href === "/admin"
            ? pathname === "/admin"
            : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`${styles.subNavItem} ${active ? styles.subNavItemActive : ""}`}
            >
              {t(item.labelKey)}
            </Link>
          );
        })}
      </nav>
      <main className={styles.main}>{children}</main>
    </div>
  );
}