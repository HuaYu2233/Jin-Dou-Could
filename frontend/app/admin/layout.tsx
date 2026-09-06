"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/stores/auth";
import styles from "./layout.module.css";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isLoading = useAuthStore((s) => s.isLoading);
  const error = useAuthStore((s) => s.error);
  const fetchMe = useAuthStore((s) => s.fetchMe);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token && !user) fetchMe();
  }, [user, fetchMe]);

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      router.replace("/login");
    } else if (user && !user.is_admin) {
      router.replace("/dashboard");
    }
  }, [user, isAuthenticated, isLoading, router]);

  function handleLogout() {
    localStorage.removeItem("access_token");
    document.cookie = "access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    useAuthStore.getState().logout();
    router.push("/");
  }

  const navItems = [
    { href: "/admin", label: "概览" },
    { href: "/admin/users", label: "用户管理" },
  ];

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <div className={styles.brand}>
          <span className={styles.brandText}>JinDou Cloud</span>
        </div>
        <div className={styles.headerRight}>
          <Link href="/dashboard" className={styles.backLink}>返回网盘</Link>
          <span className={styles.username}>
            {error ? "获取用户失败" : isLoading && !user ? "加载中..." : user ? user.username : ""}
          </span>
          <button onClick={handleLogout} className={styles.logoutBtn}>退出</button>
        </div>
      </header>
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