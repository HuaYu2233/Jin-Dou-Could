import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import LogViewer from "@/app/admin/components/LogViewer";

describe("LogViewer 日志渲染", () => {
  let root: Root;
  let container: HTMLElement;

  beforeEach(() => {
    document.body.innerHTML = '<div id="root"></div>';
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    container = document.getElementById("root")!;
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    vi.unstubAllGlobals();
  });

  async function render(lines: string[]) {
    await act(async () => {
      root.render(<LogViewer lines={lines} emptyText="暂无日志" />);
    });
  }

  it("逐行渲染日志内容", async () => {
    await render(["[preflight] ok", "[build] 55%"]);
    expect(container.textContent).toContain("[preflight] ok");
    expect(container.textContent).toContain("[build] 55%");
  });

  it("无日志时展示空状态文案", async () => {
    await render([]);
    expect(container.textContent).toBe("暂无日志");
  });

  it("追加日志后滚动到底部", async () => {
    await render(["a"]);
    const node = container.querySelector('[class*="viewer"]') as HTMLElement;
    Object.defineProperty(node, "scrollHeight", { value: 200, configurable: true });
    await render(["a", "b", "c"]);
    expect(node.scrollTop).toBe(200);
  });
});