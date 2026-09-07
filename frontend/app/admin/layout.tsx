"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/stores/auth";
import Header from "../dashboard/components/Header";
import styles from "./layout.module.css";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isLoading = useAuthStore((s) => s.isLoading);

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      router.replace("/login");
    } else if (user && !user.is_admin) {
      router.replace("/dashboard");
    }
  }, [user, isAuthenticated, isLoading, router]);

  const navItems = [
    { href: "/admin", label: "概览" },
    { href: "/admin/users", label: "用户管理" },
    { href: "/admin/backups", label: "备份管理" },
  ];

  return (
    <div className={styles.container}>
      <Header
        extra={<Link href="/dashboard" className={styles.backLink}>返回网盘</Link>}
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
              {item.label}
            </Link>
          );
        })}
      </nav>
      <main className={styles.main}>{children}</main>
    </div>
  );
}