import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { useTranslation } from "@/lib/i18n";

describe("useTranslation 返回的 t 引用稳定性", () => {
  let root: Root;
  const seen: unknown[] = [];

  beforeEach(() => {
    seen.length = 0;
    document.body.innerHTML = '<div id="root"></div>';
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    root = createRoot(document.getElementById("root")!);
  });

  afterEach(() => {
    act(() => root.unmount());
    vi.unstubAllGlobals();
  });

  it("重新渲染时 t 不应产生新引用", async () => {
    const { useI18nStore } = await import("@/stores/i18n");
    useI18nStore.setState({ locale: "zh-CN" });

    function Probe({ tick }: { tick: number }) {
      const { t } = useTranslation();
      seen.push(t);
      return <span>{tick}</span>;
    }

    await act(async () => {
      root.render(<Probe tick={0} />);
    });
    await act(async () => {
      root.render(<Probe tick={1} />);
    });

    expect(seen.length).toBeGreaterThanOrEqual(2);
    expect(seen[0]).toBe(seen[1]);
  });
});