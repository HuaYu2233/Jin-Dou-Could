import { describe, it, expect, beforeEach } from "vitest";
import { useI18nStore, DEFAULT_LOCALE } from "@/stores/i18n";

describe("useI18nStore", () => {
  beforeEach(() => {
    useI18nStore.setState({ locale: DEFAULT_LOCALE });
  });

  it("default locale is zh-CN", () => {
    expect(DEFAULT_LOCALE).toBe("zh-CN");
    expect(useI18nStore.getState().locale).toBe("zh-CN");
  });

  it("setLocale changes locale", () => {
    useI18nStore.getState().setLocale("en");
    expect(useI18nStore.getState().locale).toBe("en");
  });

  it("setLocale to zh-TW", () => {
    useI18nStore.getState().setLocale("zh-TW");
    expect(useI18nStore.getState().locale).toBe("zh-TW");
  });
});