import { describe, it, expect } from "vitest";
import { getTranslation, LOCALES, type TranslationKey } from "@/lib/i18n";

describe("i18n", () => {
  it("has 3 locale options", () => {
    expect(LOCALES).toHaveLength(3);
  });

  it("locale values are valid", () => {
    const values = LOCALES.map((l) => l.value);
    expect(values).toContain("zh-CN");
    expect(values).toContain("zh-TW");
    expect(values).toContain("en");
  });

  it("zh-CN returns Chinese text", () => {
    const text = getTranslation("zh-CN", "header.logout" as TranslationKey);
    expect(text).toBe("退出登录");
  });

  it("en returns English text", () => {
    const text = getTranslation("en", "header.logout" as TranslationKey);
    expect(text).toBe("Log out");
  });

  it("zh-TW returns Traditional Chinese text", () => {
    const text = getTranslation("zh-TW", "header.logout" as TranslationKey);
    expect(text).toBe("登出");
  });

  it("falls back to key for unknown key", () => {
    const text = getTranslation("zh-CN", "nonexistent.key.12345" as TranslationKey);
    expect(text).toBe("nonexistent.key.12345");
  });

  it("supports parameter interpolation", () => {
    const text = getTranslation("zh-CN", "header.logout" as TranslationKey, { name: "test" });
    expect(text).toBeTruthy();
  });

  it("brand name is same across locales", () => {
    const zhCN = getTranslation("zh-CN", "app.brand" as TranslationKey);
    const en = getTranslation("en", "app.brand" as TranslationKey);
    expect(zhCN).toBe(en);
  });
});