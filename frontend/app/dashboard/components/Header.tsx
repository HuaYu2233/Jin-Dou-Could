"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/stores/auth";
import { useIsHydrated } from "@/lib/hooks/useIsHydrated";
import { logout as logoutApi } from "@/lib/api/auth";
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
  const hydrated = useIsHydrated();

  const didFetchRef = useRef(false);

  useEffect(() => {
    if (didFetchRef.current) return;
    didFetchRef.current = true;
    if (!user) fetchMe();
  }, [user, fetchMe]);

  async function handleLogout() {
    try {
      await logoutApi();
    } catch {}
    useAuthStore.getState().logout();
    router.replace("/login");
  }

  return (
    <header className={styles.header}>
      <div className={styles.brand}>
        <span className={styles.brandMark} aria-hidden="true">
          J
        </span>
        <span className={styles.brandText}>{t("app.brand")}</span>
      </div>
      <div className={styles.headerRight}>
        {extra}
        <LanguageSwitcher />
        {hydrated && user && (
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