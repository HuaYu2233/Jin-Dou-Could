import { describe, it, expect } from "vitest";
import { renderToString } from "react-dom/server";
import { useIsHydrated } from "@/lib/hooks/useIsHydrated";
import { useTranslation } from "@/lib/i18n";
import { useI18nStore } from "@/stores/i18n";

function HydratedProbe() {
  const hydrated = useIsHydrated();
  return <span>{hydrated ? "client" : "server"}</span>;
}

function TranslationProbe() {
  const { t } = useTranslation();
  return <span>{t("header.logout")}</span>;
}

describe("服务端渲染一致性", () => {
  it("服务端渲染时 useIsHydrated 返回 false", () => {
    expect(renderToString(<HydratedProbe />)).toContain("server");
  });

  it("服务端渲染固定使用默认语言，不受本地偏好影响", () => {
    useI18nStore.setState({ locale: "en" });
    expect(renderToString(<TranslationProbe />)).toContain("退出登录");
  });
});