"use client";

import { useEffect, useRef, useState } from "react";
import { useI18nStore } from "@/stores/i18n";
import { LOCALES, useTranslation } from "@/lib/i18n";
import styles from "./LanguageSwitcher.module.css";

export default function LanguageSwitcher() {
  const [open, setOpen] = useState(false);
  const currentLocale = useI18nStore((s) => s.locale);
  const setLocale = useI18nStore((s) => s.setLocale);
  const { t } = useTranslation();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  useEffect(() => {
    document.documentElement.lang = currentLocale;
  }, [currentLocale]);

  const current = LOCALES.find((l) => l.value === currentLocale) ?? LOCALES[0];

  return (
    <div className={styles.wrapper} ref={ref}>
      <button
        className={styles.trigger}
        onClick={() => setOpen((v) => !v)}
        aria-label={t("header.language")}
        aria-expanded={open}
      >
        <span className={styles.icon}>🌐</span>
        <span className={styles.short}>{current.shortLabel}</span>
      </button>
      {open && (
        <ul className={styles.menu} role="listbox">
          {LOCALES.map((l) => (
            <li key={l.value}>
              <button
                className={`${styles.item} ${l.value === currentLocale ? styles.active : ""}`}
                onClick={() => {
                  setLocale(l.value);
                  setOpen(false);
                }}
                role="option"
                aria-selected={l.value === currentLocale}
              >
                {l.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
