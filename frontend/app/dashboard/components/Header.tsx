"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/stores/auth";
import Avatar from "./Avatar";
import styles from "./Header.module.css";

interface HeaderProps {
  extra?: React.ReactNode;
}

export default function Header({ extra }: HeaderProps) {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const isLoading = useAuthStore((s) => s.isLoading);
  const error = useAuthStore((s) => s.error);
  const fetchMe = useAuthStore((s) => s.fetchMe);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token && !user) fetchMe();
  }, [user, fetchMe]);

  function handleLogout() {
    localStorage.removeItem("access_token");
    document.cookie = "access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    useAuthStore.getState().logout();
    router.push("/");
  }

  return (
    <header className={styles.header}>
      <div className={styles.brand}>
        <span className={styles.brandText}>JinDou Cloud</span>
      </div>
      <div className={styles.headerRight}>
        {extra}
        {user && (
          <Link href="/profile" className={styles.userLink}>
            <Avatar
              userId={user.id}
              username={user.username}
              avatarKey={user.avatar_key}
              size="sm"
            />
            <span className={styles.username}>
              {error ? "获取用户失败" : isLoading && !user ? "加载中..." : user.username}
            </span>
          </Link>
        )}
        <button onClick={handleLogout} className={styles.logoutBtn}>
          退出
        </button>
      </div>
    </header>
  );
}
