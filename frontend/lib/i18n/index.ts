import { useI18nStore, type Locale } from "@/stores/i18n";
import zhCN from "./locales/zh-CN";
import zhTW from "./locales/zh-TW";
import en from "./locales/en";

export type { Locale } from "@/stores/i18n";

export interface LocaleOption {
  value: Locale;
  label: string;
  shortLabel: string;
}

export const LOCALES: LocaleOption[] = [
  { value: "zh-CN", label: "简体中文", shortLabel: "简" },
  { value: "zh-TW", label: "繁體中文", shortLabel: "繁" },
  { value: "en", label: "English", shortLabel: "EN" },
];

const messages: Record<Locale, typeof zhCN> = {
  "zh-CN": zhCN,
  "zh-TW": zhTW,
  en,
};

export type TranslationKey = keyof typeof zhCN;

export type TranslationParams = Record<string, string | number>;

export function getTranslation(
  locale: Locale,
  key: TranslationKey,
  params?: TranslationParams
): string {
  let text = messages[locale][key] ?? zhCN[key] ?? key;
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      text = text.replace(new RegExp(`\{${k}\}`, "g"), String(v));
    }
  }
  return text;
}

export function useTranslation() {
  const locale = useI18nStore((s) => s.locale);
  const t = (key: TranslationKey, params?: TranslationParams): string =>
    getTranslation(locale, key, params);
  return { t, locale };
}