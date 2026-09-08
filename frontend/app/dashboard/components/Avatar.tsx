"use client";

import { useState, useEffect } from "react";
import { getAvatarDownloadUrl } from "@/lib/api/auth";
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
    (async () => {
      if (!avatarKey) {
        if (active) setImgSrc(null);
        return;
      }
      try {
        const url = await getAvatarDownloadUrl();
        if (active) setImgSrc(url);
      } catch {
        if (active) setImgSrc(null);
      }
    })();
    return () => {
      active = false;
    };
  }, [avatarKey]);

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