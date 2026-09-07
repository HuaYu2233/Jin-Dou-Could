"use client";

import { useState, useEffect } from "react";
import { getAvatarUrl } from "@/lib/api/auth";
import styles from "./Avatar.module.css";

interface AvatarProps {
  userId: string;
  username: string;
  avatarKey: string | null;
  size?: "sm" | "md" | "lg";
}

const SIZE_CLASS = {
  sm: styles.sizeSm,
  md: styles.sizeMd,
  lg: styles.sizeLg,
};

export default function Avatar({ userId, username, avatarKey, size = "md" }: AvatarProps) {
  const [imgSrc, setImgSrc] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    let objectUrl: string | null = null;
    (async () => {
      if (!avatarKey) {
        await Promise.resolve();
        if (active) setImgSrc(null);
        return;
      }
      try {
        const token = localStorage.getItem("access_token");
        const res = await fetch(getAvatarUrl(userId), {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (!res.ok) throw new Error("fetch failed");
        const blob = await res.blob();
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setImgSrc(objectUrl);
      } catch {
        if (active) setImgSrc(null);
      }
    })();
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [avatarKey, userId]);

  const initial = username ? username.charAt(0).toUpperCase() : "?";
  const sizeClass = SIZE_CLASS[size];

  if (imgSrc) {
    return (
      <div className={`${styles.avatar} ${sizeClass}`}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={imgSrc} alt={username} className={styles.img} />
      </div>
    );
  }

  return (
    <div className={`${styles.avatar} ${sizeClass}`}>
      {initial}
    </div>
  );
}