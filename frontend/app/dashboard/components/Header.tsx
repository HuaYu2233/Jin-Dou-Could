"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/stores/auth";
import { API_BASE_URL } from "@/lib/config";
import { useTranslation } from "@/lib/i18n";
import Avatar from "./Avatar";
import LanguageSwitcher from "./LanguageSwitcher";
import styles from "./Header.module.css";

interface HeaderProps {
  extra?: React.ReactNode;
}

export default function Header({ extra }: HeaderProps) {
  const router = useRouter();
  const { t } = useTranslation();
  const user = useAuthStore((s) => s.user);
  const isLoading = useAuthStore((s) => s.isLoading);
  const error = useAuthStore((s) => s.error);
  const fetchMe = useAuthStore((s) => s.fetchMe);

  useEffect(() => {
    if (!user) fetchMe();
  }, [user, fetchMe]);

  async function handleLogout() {
    try {
      await fetch(`${API_BASE_URL}/api/v1/auth/logout`, { method: "POST", credentials: "include" });
    } catch {}
    useAuthStore.getState().logout();
    router.push("/");
  }

  return (
    <header className={styles.header}>
      <div className={styles.brand}>
        <span className={styles.brandText}>{t("app.brand")}</span>
      </div>
      <div className={styles.headerRight}>
        {extra}
        <LanguageSwitcher />
        {user && (
          <Link href="/profile" className={styles.userLink}>
            <Avatar
              userId={user.id}
              username={user.username}
              avatarKey={user.avatar_key}
              size="sm"
            />
            <span className={styles.username}>
              {error ? t("header.getUserFailed") : isLoading && !user ? t("header.loading") : user.username}
            </span>
          </Link>
        )}
        <button onClick={handleLogout} className={styles.logoutBtn}>
          {t("header.logout")}
        </button>
      </div>
    </header>
  );
}