import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export type Locale = "zh-CN" | "zh-TW" | "en";

export const DEFAULT_LOCALE: Locale = "zh-CN";

interface I18nState {
  locale: Locale;
  setLocale: (locale: Locale) => void;
}

export const useI18nStore = create<I18nState>()(
  persist(
    (set) => ({
      locale: DEFAULT_LOCALE,
      setLocale: (locale) => set({ locale }),
    }),
    {
      name: "i18n-storage",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ locale: state.locale }),
    }
  )
);
